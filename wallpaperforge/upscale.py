"""Upscale via Real-ESRGAN — STUB (a implementar).

Estágio 5: binário realesrgan-ncnn-vulkan (Vulkan), tiling (-t 256) para
respeitar 4 GB VRAM GTX 1650, cache por hash+modelo+escala.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def cmd_upscale(model: str | None = None) -> None:
    """CLI handler para `python -m wallpaperforge upscale`."""
    from rich.console import Console
    Console().print("[yellow][upscale] Módulo ainda não implementado.[/yellow]")
