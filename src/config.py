"""
Configuration loader for knowledgeVault-YT.

Loads settings.yaml, verified_channels.yaml, and prompt files
from the config directory.
"""

import os
from pathlib import Path

import yaml


def _find_project_root() -> Path:
    """Walk up from this file to find the project root (contains pyproject.toml)."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    # Fallback: assume src/ is one level below root
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _find_project_root()
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / os.environ.get("DATA_DIR_OVERRIDE", "data")


def load_settings() -> dict:
    """Load the main settings.yaml configuration.

    Environment variables override YAML values for deployment flexibility:
        OLLAMA_HOST        → ollama.host
        NEO4J_URI          → neo4j.uri
        NEO4J_USER         → neo4j.user
        NEO4J_PASSWORD     → neo4j.password
        SQLITE_PATH        → sqlite.path
        CHROMADB_PATH      → chromadb.path
    """
    settings_path = CONFIG_DIR / "settings.yaml"
    if not settings_path.exists():
        raise FileNotFoundError(f"Settings file not found: {settings_path}")
    with open(settings_path, "r") as f:
        settings = yaml.safe_load(f)

    # Env var overrides (take precedence over YAML)
    if os.environ.get("OLLAMA_HOST"):
        settings["ollama"]["host"] = os.environ["OLLAMA_HOST"]
    if os.environ.get("NEO4J_URI"):
        settings["neo4j"]["uri"] = os.environ["NEO4J_URI"]
    if os.environ.get("NEO4J_USER"):
        settings["neo4j"]["user"] = os.environ["NEO4J_USER"]
    if os.environ.get("NEO4J_PASSWORD"):
        settings["neo4j"]["password"] = os.environ["NEO4J_PASSWORD"]
    if os.environ.get("SQLITE_PATH"):
        settings["sqlite"]["path"] = os.environ["SQLITE_PATH"]
    if os.environ.get("CHROMADB_PATH"):
        settings["chromadb"]["path"] = os.environ["CHROMADB_PATH"]

    # Resolve relative paths to absolute (leave absolute paths untouched)
    for key in ("sqlite", "chromadb"):
        p = Path(settings[key]["path"])
        settings[key]["path"] = str(p if p.is_absolute() else PROJECT_ROOT / p)

    # Validate required config keys
    _validate_settings(settings)

    return settings


def _validate_settings(settings: dict) -> None:
    """Validate that all required config keys are present."""
    required_keys = {
        "ollama": ["host", "triage_model"],
        "sqlite": ["path"],
        "chromadb": ["path"],
        "neo4j": ["uri", "user", "password"],
    }
    missing = []
    for section, keys in required_keys.items():
        if section not in settings:
            missing.append(section)
            continue
        for key in keys:
            if key not in settings[section]:
                missing.append(f"{section}.{key}")
    if missing:
        raise ValueError(
            f"Missing required config keys in settings.yaml: {', '.join(missing)}"
        )


def load_verified_channels() -> dict:
    """Load the verified channels whitelist."""
    path = CONFIG_DIR / "verified_channels.yaml"
    if not path.exists():
        return {"verified_channels": [], "shorts_whitelist": []}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {"verified_channels": [], "shorts_whitelist": []}


def load_prompt(prompt_name: str) -> str:
    """Load a prompt template from the config/prompts directory.

    Args:
        prompt_name: Name of the prompt file (without .txt extension).

    Returns:
        The prompt text content.
    """
    prompt_path = CONFIG_DIR / "prompts" / f"{prompt_name}.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    with open(prompt_path, "r") as f:
        return f.read().strip()


def ensure_data_dirs():
    """Create data directories if they don't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "chromadb").mkdir(parents=True, exist_ok=True)


import copy

# Module-level singletons
_settings = None


def get_settings() -> dict:
    """Get cached settings (loaded once).

    Returns a deep copy to prevent callers from mutating the
    shared singleton.
    """
    global _settings
    if _settings is None:
        _settings = load_settings()
    return copy.deepcopy(_settings)
