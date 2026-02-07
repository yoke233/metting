"""Dynaconf settings loader for the meeting system."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict

from dynaconf import Dynaconf


@lru_cache(maxsize=1)
def _settings() -> Dynaconf:
    base_dir = Path(__file__).resolve().parent.parent
    return Dynaconf(
        envvar_prefix="MEETING",
        settings_files=[
            str(base_dir / "config" / "settings.toml"),
            str(base_dir / "config" / ".secrets.toml"),
        ],
        environments=True,
        default_env="default",
        load_dotenv=True,
    )


def get_role_prompts() -> Dict[str, str]:
    settings = _settings()
    role_prompts = settings.get("role_prompts") or {}
    if hasattr(role_prompts, "items"):
        return {str(k): str(v) for k, v in role_prompts.items()}
    return {}


def get_system_prompt() -> str:
    settings = _settings()
    prompt = settings.get("system_prompt") or ""
    return str(prompt).strip()


def get_recorder_output_prompt() -> str:
    settings = _settings()
    prompt = settings.get("recorder_output_prompt") or ""
    return str(prompt).strip()


def get_role_output_prompt() -> str:
    settings = _settings()
    prompt = settings.get("role_output_prompt") or ""
    return str(prompt).strip()


def get_role_repair_prompt() -> str:
    settings = _settings()
    prompt = settings.get("role_repair_prompt") or ""
    return str(prompt).strip()


def get_round_summary_prompt() -> str:
    settings = _settings()
    prompt = settings.get("round_summary_prompt") or ""
    return str(prompt).strip()
