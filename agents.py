"""Agent definitions: one shared Ollama model, three specialists, one manager."""
from smolagents import CodeAgent, LiteLLMModel, ToolCallingAgent

from batfish import audit_network, list_devices
from tools_db import read_schema, run_query
from tools_docker import (
    check_service,
    create_service_stack,
    docker_compose_down,
    docker_compose_up,
    docker_logs,
    test_endpoint,
)
from tools_files import file_reader, list_uploads, save_config_file
import requests

# One model instance is enough; all agents share it.
DEFAULT_MODEL_ID = "ollama/qwen2.5:14b"
model = LiteLLMModel(model_id=DEFAULT_MODEL_ID)


def list_ollama_models() -> list[str]:
    """Return LiteLLM ids (ollama/<name>) of every model in local Ollama.

    Returns an empty list if Ollama is not running or has no models.
    """
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        names = [m["model"] for m in r.json().get("models", [])]
        return [f"ollama/{name}" for name in names]
    except requests.RequestException:
        return []


def set_model_for_all_agents(model_id: str) -> None:
    """Point every agent at a new model (id like 'ollama/qwen2.5:14b')."""
    new_model = LiteLLMModel(model_id=model_id)
    for agent in (
        manager_agent,
        system_engineer_agent,
        network_engineer_agent,
        dba_engineer_agent,
    ):
        agent.model = new_model



system_engineer_agent = ToolCallingAgent(
    tools=[
        check_service,
        create_service_stack,
        docker_compose_up,
        test_endpoint,
        docker_logs,
        docker_compose_down,
        save_config_file,
        list_uploads,
        file_reader,
    ],
    model=model,
    name="system_engineer_agent",
    description=(
        "Manages Linux/Docker tasks: checks the Docker daemon, creates "
        "docker_containers/<name>_<time>/ with Dockerfile and docker-compose.yml "
        "(create_service_stack), starts it (docker_compose_up), tests the published "
        "port (test_endpoint), reads logs (docker_logs), and stops it (docker_compose_down). "
        "Saves generated configs with save_config_file; reads uploads via list_uploads/file_reader."
    ),
    max_steps=12,
)

network_engineer_agent = ToolCallingAgent(
    tools=[audit_network, list_devices, save_config_file, list_uploads, file_reader],
    model=model,
    name="network_engineer_agent",
    description=(
        "Audits network configs via Batfish and lists discovered devices. "
        "Read uploaded configs with list_uploads/file_reader; create or adjust a "
        "network config with save_config_file (saved .cfg files are what Batfish audits)."
    ),
    max_steps=8,
)

dba_engineer_agent = ToolCallingAgent(
    tools=[read_schema, run_query, list_uploads, file_reader],
    model=model,
    name="dba_engineer_agent",
    description=(
        "Reads DB schema (read_schema, optionally from an uploaded .sql file) and runs "
        "read-only SELECT queries. Use list_uploads/file_reader to read uploaded .sql files."
    ),
    max_steps=5,
)

manager_agent = CodeAgent(
    tools=[list_uploads, file_reader],
    model=model,
    managed_agents=[
        system_engineer_agent,
        network_engineer_agent,
        dba_engineer_agent,
    ],
)
