"""Configuration loader.

Reads YAML configs from project-root config/ directory.
Prompts are loaded from config/prompts/ (one file per prompt).
"""

import logging
import logging.config
from pathlib import Path

import yaml  # type: ignore[import]

from hotsearch import PROJECT_ROOT

_CONFIG_DIR: Path = PROJECT_ROOT / "config"
_PROMPTS_DIR: Path = _CONFIG_DIR / "prompts"


def _load_yaml(name: str) -> dict:
    path = _CONFIG_DIR / name
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


# --- public API ---


def model_config() -> dict:
    """LLM model parameters (temperature, max_tokens, etc.)."""
    return _load_yaml("model_config.yaml").get("llm", {})


def prompt_templates() -> dict[str, str]:
    """Return dict of {name: template_string} from config/prompts/."""
    templates: dict[str, str] = {}
    if not _PROMPTS_DIR.exists():
        return templates
    for path in _PROMPTS_DIR.iterdir():
        if path.is_file() and path.suffix in (".md", ".j2", ".txt"):
            name = path.stem
            templates[name] = path.read_text(encoding="utf-8")
    return templates


def setup_logging() -> None:
    cfg = _load_yaml("logging_config.yaml").get("logging")
    if cfg:
        logging.config.dictConfig(cfg)
