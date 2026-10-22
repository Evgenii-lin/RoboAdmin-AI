"""Docker tools for the system_engineer agent.

Full test loop:
    check_service  ->  create_service_stack  ->  docker_compose_up
    ->  test_endpoint  ->  docker_logs (if anything looks wrong)  ->  docker_compose_down

create_service_stack writes BOTH files into ONE timestamped folder:

    docker_containers/<name>_<YYYY-MM-DD_HH-MM-SS>/
        Dockerfile
        docker-compose.yml

docker_compose_up / docker_logs / docker_compose_down all operate on that
folder (compose runs with cwd = the folder, so it always finds its file).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

import requests
from smolagents import tool

from paths import DOCKER_DIR

# Folder of the most recently created stack; set by create_service_stack.
_current_stack: Path | None = None


def _safe_name(name: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-") or "service"


def _new_stack_dir(name: str) -> Path:
    """Create docker_containers/<name>_<timestamp>/ (unique even within a second)."""
    base = f"{_safe_name(name)}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    folder = DOCKER_DIR / base
    i = 1
    while folder.exists():
        folder = DOCKER_DIR / f"{base}-{i}"
        i += 1
    folder.mkdir(parents=True)
    return folder


def _require_stack() -> Path:
    """Return the current stack folder, or raise with guidance for the model."""
    if _current_stack is not None and _current_stack.is_dir():
        return _current_stack
    raise RuntimeError(
        "No stack folder exists yet. Call create_service_stack first — it creates "
        "docker_containers/<name>_<time>/ with Dockerfile and docker-compose.yml."
    )


def _compose_cmd() -> list[str]:
    """Return the compose invocation: 'docker compose' (v2) or 'docker-compose' (v1)."""
    if subprocess.run(["docker", "compose", "version"], capture_output=True).returncode == 0:
        return ["docker", "compose"]
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    raise RuntimeError("docker compose plugin and docker-compose CLI are both missing.")


def _run(args: list[str], cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, cwd=str(cwd), capture_output=True, text=True, timeout=timeout
    )


@tool
def check_service() -> str:
    """Check if the Docker daemon is running and reachable.

    Call this before generating or launching containers.
    """
    r = subprocess.run(
        ["docker", "info", "--format",
         "Server: {{.ServerVersion}}\n"
         "Containers: {{.Containers}} ({{.ContainersRunning}} running)\n"
         "OS: {{.OperatingSystem}}"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return "Docker daemon is NOT reachable. Is Docker Desktop / dockerd running?"
    return r.stdout.strip()


@tool
def create_service_stack(
    container_name: str,
    image: str,
    host_port: int,
    container_port: int = 80,
    healthcheck_path: str = "/",
) -> str:
    """Create docker_containers/<container_name>_<time>/ containing BOTH a Dockerfile
    and a docker-compose.yml for one service, and return their content.

    Call this once per service; docker_compose_up / docker_logs / docker_compose_down
    then operate on this folder.

    Args:
        container_name: Short name of the service, e.g. "nginx" or "my-redis".
            The folder becomes docker_containers/nginx_2026-10-21_10-35-00 (name + creation time).
        image: Docker image to run, e.g. "nginx:1.25"
        host_port: Port to publish on the host, e.g. 8080
        container_port: Port the service listens on inside the container, e.g. 80
        healthcheck_path: Path used by the healthcheck, e.g. "/" or "/health"
    """
    global _current_stack
    safe = _safe_name(container_name)
    folder = _new_stack_dir(container_name)

    hc = (
        f"wget --spider -q http://localhost:{container_port}{healthcheck_path} "
        f"|| curl -f http://localhost:{container_port}{healthcheck_path}"
    )

    dockerfile = (
        f"FROM {image}\n"
        f"EXPOSE {container_port}\n"
        f"HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD {hc}\n"
    )
    (folder / "Dockerfile").write_text(dockerfile, encoding="utf-8")

    compose = (
        "services:\n"
        f"  {safe}:\n"
        f"    image: {image}\n"
        f"    container_name: {folder.name}\n"
        "    ports:\n"
        f'      - "{host_port}:{container_port}"\n'
        "    restart: unless-stopped\n"
        "    healthcheck:\n"
        f'      test: ["CMD-SHELL", "{hc}"]\n'
        "      interval: 30s\n"
        "      timeout: 5s\n"
        "      retries: 3\n"
    )
    (folder / "docker-compose.yml").write_text(compose, encoding="utf-8")

    _current_stack = folder
    return (
        f"Created {folder} with Dockerfile and docker-compose.yml.\n\n"
        f"── Dockerfile ──\n{dockerfile}\n"
        f"── docker-compose.yml ──\n{compose}\n"
        "Next steps: docker_compose_up → test_endpoint(host_port="
        f"{host_port}, path={healthcheck_path!r}) → docker_compose_down."
    )


@tool
def docker_compose_up(wait_seconds: int = 45) -> str:
    """Start the stack (docker compose up -d) from the folder created by
    create_service_stack, and wait until the service reports running/healthy.
    On failure it includes the container logs.

    Args:
        wait_seconds: How long to wait for the container(s) to come up.
    """
    try:
        stack = _require_stack()
        cmd = _compose_cmd()
    except RuntimeError as e:
        return f"ERROR: {e}"

    if not (stack / "docker-compose.yml").is_file():
        return f"ERROR: {stack}/docker-compose.yml does not exist. Call create_service_stack first."

    try:
        r = _run(cmd + ["up", "-d"], cwd=stack, timeout=180)
    except (subprocess.TimeoutExpired, OSError) as e:
        return f"ERROR: docker compose up failed: {e}"
    if r.returncode != 0:
        return f"ERROR: docker compose up failed:\n{(r.stderr or r.stdout).strip()[:1000]}"

    # poll until running/healthy
    status_out = ""
    deadline = time.time() + max(wait_seconds, 5)
    while time.time() < deadline:
        ps = _run(cmd + ["ps"], cwd=stack)
        status_out = ps.stdout.strip()
        out = status_out.lower()
        if "healthy" in out or "running" in out:
            return f"Services are up and running.\n\n{status_out}"
        time.sleep(2)

    logs = _run(cmd + ["logs", "--tail", "40"], cwd=stack)
    return (
        f"WARNING: services did not report running/healthy within {wait_seconds}s.\n"
        f"\nStatus:\n{status_out}\n\nLast logs:\n{(logs.stdout or logs.stderr)[-1500:]}"
    )


@tool
def docker_logs(tail: int = 40) -> str:
    """Show recent logs of the stack (for debugging).

    Args:
        tail: Number of log lines to show.
    """
    try:
        stack = _require_stack()
        cmd = _compose_cmd()
    except RuntimeError as e:
        return f"ERROR: {e}"
    if not (stack / "docker-compose.yml").is_file():
        return "ERROR: no docker-compose.yml in the stack folder — call create_service_stack first."
    r = _run(cmd + ["logs", "--tail", str(max(1, min(tail, 200)))], cwd=stack)
    return (r.stdout or r.stderr or "(no output)").strip()[-2000:]


@tool
def test_endpoint(host_port: int, path: str = "/") -> str:
    """HTTP GET http://localhost:{host_port}{path} and report status code + body.

    Use this after docker_compose_up to verify the container actually serves
    traffic on the published port.

    Args:
        host_port: Port published on the host (the same host_port used in create_service_stack)
        path: URL path to request, e.g. "/health" or "/"
    """
    url = f"http://localhost:{host_port}{path}"
    try:
        r = requests.get(url, timeout=5)
    except requests.RequestException as e:
        return f"ERROR: request to {url} failed: {e}"
    return f"HTTP {r.status_code} {r.reason}\n\n{r.text[:500]}"


@tool
def docker_compose_down() -> str:
    """Stop and remove the stack's services (docker compose down).

    Call this after testing to free the published ports.
    """
    try:
        stack = _require_stack()
        cmd = _compose_cmd()
    except RuntimeError as e:
        return f"ERROR: {e}"
    if not (stack / "docker-compose.yml").is_file():
        return "Nothing to stop: no docker-compose.yml in the stack folder."
    r = _run(cmd + ["down"], cwd=stack)
    return f"Stopped and removed services.\n{(r.stdout or r.stderr).strip()[:500]}"
