"""Batfish: REST client, lifecycle helpers, and the agent tools that use it."""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

import requests
from smolagents import tool

from paths import CONFIGS_DIR, UPLOADS_DIR

BATFISH_IMAGE   = "batfish/batfish"
CONTAINER_NAME  = "bf-audit"
API_PORT        = 8080                      # host port
API_BASE        = f"http://localhost:{API_PORT}"
CONFIG_CTR_DIR  = "/configs"                # path inside the container
INIT_TIMEOUT_S  = 120


def _batfish_healthy() -> bool:
    """True if the Batfish API already answers (no need to (re)start it)."""
    try:
        return requests.get(f"{API_BASE}/v2/health", timeout=3).status_code == 200
    except requests.RequestException:
        return False


def _sync_configs() -> None:
    """Copy uploaded .cfg/.conf files into the configs dir Batfish reads.

    So the user can just Upload a config and ask network_engineer to audit it.
    """
    if not UPLOADS_DIR.is_dir():
        return
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    for f in sorted(UPLOADS_DIR.iterdir()):
        if f.is_file() and f.suffix.lower() in (".cfg", ".conf"):
            shutil.copy2(f, CONFIGS_DIR / f.name)


def _ensure_batfish_running() -> None:
    """Idempotent: use the running container, start one only if it's not up."""
    if _batfish_healthy():
        return

    # remove stale container if it exists
    subprocess.run(
        ["docker", "rm", "-f", CONTAINER_NAME],
        capture_output=True,
    )

    # start (config files must be in CONFIGS_DIR)
    subprocess.run(
        [
            "docker", "run", "-d",
            "--name", CONTAINER_NAME,
            "-v", f"{CONFIGS_DIR}:{CONFIG_CTR_DIR}",
            "-p", f"{API_PORT}:80",
            BATFISH_IMAGE,
        ],
        check=True,
        capture_output=True,
    )

    # wait until the API answers
    deadline = time.time() + INIT_TIMEOUT_S
    while time.time() < deadline:
        try:
            r = requests.get(f"{API_BASE}/v2/health", timeout=3)
            if r.status_code == 200:
                return
        except requests.ConnectionError:
            pass
        time.sleep(2)
    raise RuntimeError("Batfish did not become ready in time.")


def _ask(question_type: str, **params) -> str:
    """
    Ask one Batfish question, return the rows as a JSON string.
    question_type must be a valid token: showroutes, bgpneighbors, …
    """
    # uploaded configs -> ./configs, then make sure the server is up
    _sync_configs()
    _ensure_batfish_running()

    # create analysis (idempotent – re-creates if needed)
    requests.post(
        f"{API_BASE}/v2/analysis/audit",
        json={"configDirectoryPath": CONFIG_CTR_DIR},
        timeout=30,
    )

    # wait for initialisation
    r = requests.get(
        f"{API_BASE}/v2/analysis/audit/initialization",
        params={"waitTimeoutInMilliseconds": INIT_TIMEOUT_S * 1000},
        timeout=INIT_TIMEOUT_S + 10,
    )
    r.raise_for_status()

    # ask the question
    r = requests.post(
        f"{API_BASE}/v2/analysis/audit/question/{question_type}",
        json=params,
        timeout=60,
    )
    r.raise_for_status()
    rows = r.json().get("table", {}).get("rows", [])
    return json.dumps(rows, indent=2)


# ── VALID question types (exposed to the LLM) ─
VALID_QUESTIONS = {
    "showroutes",
    "showinterfaces",
    "interfaceproperties",
    "configuration",
    "bgpneighbors",
    "ospfneighbors",
    "prefixes",
    "traceroute",
    "testroutes",
}


@dataclass
class BatfishClient:
    """Thin wrapper around the Batfish v2 REST API."""

    base_url: str = "http://localhost:8080"
    analysis_name: str = "my-analysis"
    config_dir: str = "/configs"          # path *inside* the container
    timeout: int = 120                    # seconds to wait for init

    session: requests.Session = field(default_factory=requests.Session, repr=False)

    # ── lifecycle ──────────────────────────────
    def start(self) -> None:
        """Create (or reset) the analysis and wait until it's ready."""

        # 1. Create analysis (idempotent – overwrites same name)
        r = self.session.post(
            f"{self.base_url}/v2/analysis/{self.analysis_name}",
            json={
                "configDirectoryPath": self.config_dir,
                "vendorConfiguration": True,   # parse vendor-specific too
            },
            timeout=30,
        )
        r.raise_for_status()
        print(f"✓ Analysis '{self.analysis_name}' created.")

        # 2. Poll until initialisation finishes
        r = self.session.get(
            f"{self.base_url}/v2/analysis/{self.analysis_name}/initialization",
            params={"waitTimeoutInMilliseconds": self.timeout * 1000},
            timeout=self.timeout + 10,
        )
        r.raise_for_status()
        body = r.json()
        status = body.get("status", "UNKNOWN")
        print(f"✓ Initialisation status: {status}")
        if status != "SUCCESS":
            raise RuntimeError(f"Batfish init failed: {body}")

    def stop(self) -> None:
        """Delete the analysis (optional cleanup)."""
        self.session.delete(
            f"{self.base_url}/v2/analysis/{self.analysis_name}",
            timeout=15,
        )
        print("✓ Analysis deleted.")

    # ── questions ──────────────────────────────
    def ask(self, question_name: str, **params: Any) -> list[dict]:
        """
        Ask a Batfish question and return the table rows as a list of dicts.

        Examples of question_name:
            "showroutes", "showinterfaces", "interfaceproperties",
            "configuration", "traceroute", "testroutes", "prefixes",
            "bgpneighbors", "ospfneighbors"
        """
        url = f"{self.base_url}/v2/analysis/{self.analysis_name}/question/{question_name}"
        payload = {k: v for k, v in params.items() if v is not None}
        r = self.session.post(url, json=payload, timeout=60)
        r.raise_for_status()

        body = r.json()
        # Batfish wraps the table: {"table": {"rows": [...], "columns": [...]}}
        rows = body.get("table", {}).get("rows", [])
        return rows

    # ── convenience helpers ────────────────────
    def show_routes(self, node: str | None = None) -> list[dict]:
        params = {}
        if node:
            params["nodes"] = [node]
        return self.ask("showroutes", **params)

    def show_interfaces(self, node: str | None = None) -> list[dict]:
        params = {}
        if node:
            params["nodes"] = [node]
        return self.ask("showinterfaces", **params)

    def traceroute(
        self,
        source_node: str,
        destination_ip: str,
        ip_protocol: int = 6,          # 6=TCP, 17=UDP, 1=ICMP
        destination_port: int = 80,
    ) -> list[dict]:
        return self.ask(
            "traceroute",
            locations=[{
                "node": source_node,
                "interface": None,
                "vrf": None,
            }],
            headers={
                "ipProtocol": ip_protocol,
                "ip": destination_ip,
            },
            extensions={"displayPath": True},
        )

    def list_nodes(self) -> list[str]:
        """Return every node (device) name Batfish discovered."""
        rows = self.ask("configuration")
        return sorted({r.get("Node", "") for r in rows if r.get("Node")})


# ── tools ─────────────────────────────────────

@tool
def audit_network(
    question_type: str,
    node: str = "",
) -> str:
    """Audit a network configuration using Batfish.

    Reads all .cfg files from the ./configs directory and answers
    a structured question about the network.

    Args:
        question_type: One of: showroutes, showinterfaces,
            interfaceproperties, configuration, bgpneighbors,
            ospfneighbors, prefixes, traceroute, testroutes.
        node: Optional device name to filter (e.g. "rtr-core-01").
            Leave empty for all nodes.
    """
    if question_type not in VALID_QUESTIONS:
        return (
            f"Invalid question_type '{question_type}'. "
            f"Valid options: {', '.join(sorted(VALID_QUESTIONS))}"
        )

    params: dict = {}
    if node:
        params["nodes"] = [node]

    try:
        return _ask(question_type, **params)
    except requests.exceptions.ConnectionError:
        return "ERROR: Batfish server is not reachable. Is Docker running?"
    except requests.exceptions.HTTPError as e:
        return f"ERROR: Batfish API returned {e.response.status_code}: {e.response.text[:300]}"
    except subprocess.CalledProcessError as e:
        return f"ERROR: Docker failed: {e.stderr.decode(errors='replace')[:300]}"
    except FileNotFoundError:
        return "ERROR: Docker is not installed or not in PATH."
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"


@tool
def list_devices() -> str:
    """List all network devices (nodes) Batfish discovered from the configs.

    Returns a comma-separated list of node names.
    """
    try:
        rows_raw = _ask("configuration")
        rows = json.loads(rows_raw)
        nodes = sorted({r.get("Node", "") for r in rows if r.get("Node")})
        return ", ".join(nodes) if nodes else "No devices found. Check ./configs."
    except Exception as e:
        return f"ERROR: {e}"
