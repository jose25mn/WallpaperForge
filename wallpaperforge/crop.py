"""Corte por monitor — parcialmente implementado.

Estágio 6: para cada imagem × monitor gera um crop no tamanho exato.
Usa saliency detector (OpenCV) para centralizar o corte.
Resample Lanczos; salva PNG ou JPEG.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

log = logging.getLogger(__name__)


class Rect(NamedTuple):
    x: int
    y: int
    width: int
    height: int


@dataclass
class CropResult:
    path: Path
    monitor_name: str
    success: bool
    reason: str = ""


def compute_crop_rect(
    img_w: int,
    img_h: int,
    target_w: int,
    target_h: int,
    focus_x: float = 0.5,   # 0.0–1.0, ponto de interesse horizontal
    focus_y: float = 0.5,   # 0.0–1.0, ponto de interesse vertical
) -> Rect | None:
    """Calcula o rect de crop centrado no ponto de interesse.

    Retorna None se a imagem for menor que o alvo em alguma dimensão
    (indicando que o upscale não foi suficiente).
    """
    if img_w < target_w or img_h < target_h:
        return None

    # clamp para não sair da imagem
    cx = int(focus_x * img_w)
    cy = int(focus_y * img_h)

    x  = max(0, min(cx - target_w // 2, img_w - target_w))
    y  = max(0, min(cy - target_h // 2, img_h - target_h))

    return Rect(x=x, y=y, width=target_w, height=target_h)


def detect_saliency_center(image_path: Path) -> tuple[float, float]:
    """Retorna (focus_x, focus_y) via saliency spectral residual do OpenCV.

    Fallback para (0.5, 0.5) caso o detector falhe.
    """
    try:
        import cv2
        import numpy as np

        img = cv2.imread(str(image_path))
        if img is None:
            return 0.5, 0.5

        saliency = cv2.saliency.StaticSaliencySpectralResidual.create()
        ok, saliency_map = saliency.computeSaliency(img)
        if not ok:
            return 0.5, 0.5

        # coordenada do pixel com maior saliência
        flat_idx = int(np.argmax(saliency_map))
        h, w     = saliency_map.shape[:2]
        py, px   = divmod(flat_idx, w)
        return px / w, py / h

    except Exception as exc:
        log.debug("detect_saliency_center falhou (%s); usando centro.", exc)
        return 0.5, 0.5


def crop_image_for_monitor(
    image_path: Path,
    target_w: int,
    target_h: int,
    output_path: Path,
    *,
    jpeg: bool = False,
    jpeg_quality: int = 95,
) -> CropResult:
    """Recorta a imagem para (target_w × target_h) e salva em output_path."""
    from PIL import Image

    monitor_label = f"{target_w}×{target_h}"

    try:
        with Image.open(image_path) as im:
            img_w, img_h = im.size

        focus_x, focus_y = detect_saliency_center(image_path)
        rect = compute_crop_rect(img_w, img_h, target_w, target_h, focus_x, focus_y)

        if rect is None:
            reason = (
                f"imagem {img_w}×{img_h} menor que o monitor {monitor_label} "
                "mesmo após upscale"
            )
            log.warning("Rejeitada %s: %s", image_path.name, reason)
            return CropResult(path=image_path, monitor_name=monitor_label,
                              success=False, reason=reason)

        with Image.open(image_path) as im:
            cropped = im.crop((rect.x, rect.y, rect.x + rect.width, rect.y + rect.height))
            # Lanczos para downsample residual (caso haja)
            if cropped.size != (target_w, target_h):
                cropped = cropped.resize((target_w, target_h), Image.LANCZOS)

            output_path.parent.mkdir(parents=True, exist_ok=True)
            if jpeg:
                output_path = output_path.with_suffix(".jpg")
                cropped.save(output_path, "JPEG", quality=jpeg_quality, optimize=True)
            else:
                cropped.save(output_path, "PNG", optimize=True)

        log.debug("Crop salvo: %s", output_path)
        return CropResult(path=output_path, monitor_name=monitor_label, success=True)

    except Exception as exc:
        log.error("Erro ao processar %s: %s", image_path.name, exc)
        return CropResult(path=image_path, monitor_name=monitor_label,
                          success=False, reason=str(exc))


def cmd_crop() -> None:
    """CLI handler para `python -m wallpaperforge crop`."""
    from rich.console import Console
    Console().print("[yellow][crop] Integração com pipeline ainda não implementada.[/yellow]")
