import json
import os
from pathlib import Path
from typing import Any

from src.services.env import TOKEN_FILE, SECRETS_FILE

SECRETS_DIRECTORY = "secrets/"
DATA_DIRECTORY = "data/"
LOG_DIRECTORY = "logs/"


def project_root() -> Path:
    current = Path(__file__).resolve().parent

    for parent in [current, *current.parents]:
        if (parent / "src").is_dir():
            return parent

    raise FileNotFoundError(
        f"No project root found above {current} (no 'src/' directory detected)"
    )


def get_tokens_filename() -> str:
    return os.path.abspath(project_root() / SECRETS_DIRECTORY / TOKEN_FILE)


def get_credentials_filename() -> str:
    return os.path.abspath(project_root() / SECRETS_DIRECTORY / SECRETS_FILE)


def get_data_directory() -> Path:
    return project_root() / DATA_DIRECTORY


def get_log_directory() -> Path:
    return project_root() / LOG_DIRECTORY


def get_data_location(location) -> str:
    return os.path.abspath(get_data_directory() / location)


def get_data_location_as_path(location) -> Path:
    return get_data_directory() / location


def load_json_file(path: Path) -> dict[str, Any]:
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    return {}


def save_json_file(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
