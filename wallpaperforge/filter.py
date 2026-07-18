"""Filtragem automática de imagens — STUB (a implementar).

Estágio 3: remove corrompidos, pequenos demais, retratos, duplicatas (phash),
imagens com watermark. Salva resultado em work/filtered/.
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

WORK_DIR     = Path.cwd() / "work"
RAW_DIR      = WORK_DIR / "raw"
FILTERED_DIR = WORK_DIR / "filtered"


def filter_corrupt(paths: list[Path]) -> tuple[list[Path], list[Path]]:
    """Separa arquivos legíveis dos corrompidos (Pillow não abre)."""
    from PIL import Image, UnidentifiedImageError

    ok, bad = [], []
    for p in paths:
        try:
            with Image.open(p) as im:
                im.verify()
            ok.append(p)
        except (UnidentifiedImageError, Exception):
            bad.append(p)
    return ok, bad


def filter_by_min_side(paths: list[Path], min_side: int = 1100) -> tuple[list[Path], list[Path]]:
    """Remove imagens cujo menor lado é menor que min_side px."""
    from PIL import Image

    ok, bad = [], []
    for p in paths:
        try:
            with Image.open(p) as im:
                if min(im.size) >= min_side:
                    ok.append(p)
                else:
                    bad.append(p)
        except Exception:
            bad.append(p)
    return ok, bad


def filter_portraits(
    paths: list[Path],
    portrait_allowed: bool = False,
) -> tuple[list[Path], list[Path]]:
    """Remove imagens em orientação retrato (height > width) se não permitidas."""
    from PIL import Image

    ok, bad = [], []
    for p in paths:
        try:
            with Image.open(p) as im:
                w, h = im.size
            if portrait_allowed or w >= h:
                ok.append(p)
            else:
                bad.append(p)
        except Exception:
            bad.append(p)
    return ok, bad


def deduplicate(paths: list[Path], max_distance: int = 5) -> tuple[list[Path], list[Path]]:
    """Remove duplicatas por phash (Hamming ≤ max_distance); mantém a maior."""
    import imagehash
    from PIL import Image

    seen: dict[str, tuple[Path, int]] = {}  # hash_key → (path, pixel_count)
    removed: list[Path] = []

    for p in paths:
        try:
            with Image.open(p) as im:
                h    = imagehash.phash(im)
                area = im.size[0] * im.size[1]
        except Exception:
            removed.append(p)
            continue

        key = str(h)
        matched = None
        for existing_key in list(seen.keys()):
            try:
                dist = h - imagehash.hex_to_hash(existing_key)
                if dist <= max_distance:
                    matched = existing_key
                    break
            except Exception:
                continue

        if matched is None:
            seen[key] = (p, area)
        else:
            existing_path, existing_area = seen[matched]
            if area > existing_area:
                removed.append(existing_path)
                del seen[matched]
                seen[key] = (p, area)
            else:
                removed.append(p)

    kept = [v[0] for v in seen.values()]
    return kept, removed


def cmd_filter() -> None:
    """CLI handler para `python -m wallpaperforge filter`."""
    from rich.console import Console
    Console().print("[yellow][filter] Módulo ainda não implementado.[/yellow]")
