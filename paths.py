"""Shared paths — anchored to this file so tools work from any CWD."""
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = APP_DIR / "uploads"
DOCKER_DIR = APP_DIR / "docker_containers"
CONFIGS_DIR = APP_DIR / "configs"   # Batfish reads .cfg files from here
