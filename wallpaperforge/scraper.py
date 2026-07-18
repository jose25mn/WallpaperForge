"""Coleta de imagens — STUB (a implementar).

Estágio 2: gallery-dl (subprocess) + ddgs (DuckDuckGo Images).
Salva em work/raw/ com manifest.json.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def cmd_scrape(query: str | None, url: str | None, limit: int = 300) -> None:
    """CLI handler para `python -m wallpaperforge scrape`."""
    from rich.console import Console
    Console().print("[yellow][scraper] Módulo ainda não implementado.[/yellow]")
