"""Leitura centralizada de config/settings.toml."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

_SETTINGS_PATH = Path.cwd() / "config" / "settings.toml"


@lru_cache(maxsize=1)
def load_settings() -> dict:
    """Carrega settings.toml; retorna {} se não encontrado."""
    if not _SETTINGS_PATH.exists():
        return {}
    with open(_SETTINGS_PATH, "rb") as f:
        return tomllib.load(f)


def get(section: str, key: str, default=None):
    """Atalho para ler um valor do settings.toml."""
    return load_settings().get(section, {}).get(key, default)
