"""Logging: arquivo JSON estruturado + saída bonita no terminal via rich."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from rich.logging import RichHandler

_LOG_DIR = Path.cwd() / "logs"


def setup_logging(level: int = logging.DEBUG) -> Path:
    """Configura handlers de arquivo e console; retorna o caminho do log."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = _LOG_DIR / f"wallpaperforge_{ts}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)-30s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )

    console_handler = RichHandler(
        level=logging.INFO,
        show_path=False,
        rich_tracebacks=True,
        markup=True,
    )

    logging.basicConfig(level=level, handlers=[file_handler, console_handler], force=True)

    # silenciar loggers muito verbosos de libs
    for noisy in ("httpx", "httpcore", "PIL", "PySide6"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return log_file
