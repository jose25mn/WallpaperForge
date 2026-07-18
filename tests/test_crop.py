"""Testes para wallpaperforge.crop."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_image(path: Path, width: int, height: int) -> Path:
    img = Image.new("RGB", (width, height), color=(30, 144, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")
    return path


# ── compute_crop_rect ─────────────────────────────────────────────────────────

class TestComputeCropRect:
    def test_returns_none_when_image_too_small(self):
        from wallpaperforge.crop import compute_crop_rect

        # Imagem 1000×600 não cabe num monitor 1920×1080
        result = compute_crop_rect(1000, 600, 1920, 1080)
        assert result is None

    def test_exact_fit_returns_origin(self):
        from wallpaperforge.crop import compute_crop_rect

        rect = compute_crop_rect(1920, 1080, 1920, 1080)
        assert rect is not None
        assert rect.x == 0
        assert rect.y == 0
        assert rect.width == 1920
        assert rect.height == 1080

    def test_center_crop_is_centered(self):
        from wallpaperforge.crop import compute_crop_rect

        # Imagem 4K, alvo FHD, foco no centro exato
        rect = compute_crop_rect(3840, 2160, 1920, 1080, focus_x=0.5, focus_y=0.5)
        assert rect is not None
        assert rect.x == (3840 - 1920) // 2
        assert rect.y == (2160 - 1080) // 2
        assert rect.width  == 1920
        assert rect.height == 1080

    def test_crop_rect_stays_within_bounds(self):
        from wallpaperforge.crop import compute_crop_rect

        # Foco extremo (canto superior esquerdo)
        rect = compute_crop_rect(3840, 2160, 1920, 1080, focus_x=0.0, focus_y=0.0)
        assert rect is not None
        assert rect.x >= 0
        assert rect.y >= 0

        # Foco extremo (canto inferior direito)
        rect = compute_crop_rect(3840, 2160, 1920, 1080, focus_x=1.0, focus_y=1.0)
        assert rect is not None
        assert rect.x + rect.width  <= 3840
        assert rect.y + rect.height <= 2160

    def test_non_center_focus_shifts_crop(self):
        from wallpaperforge.crop import compute_crop_rect

        center = compute_crop_rect(3840, 2160, 1920, 1080, focus_x=0.5, focus_y=0.5)
        right  = compute_crop_rect(3840, 2160, 1920, 1080, focus_x=0.9, focus_y=0.5)
        assert center is not None and right is not None
        # com foco à direita o x do crop deve ser maior
        assert right.x > center.x

    def test_correct_dimensions_always_preserved(self):
        from wallpaperforge.crop import compute_crop_rect

        for fx, fy in [(0.1, 0.1), (0.5, 0.5), (0.9, 0.9)]:
            rect = compute_crop_rect(5000, 3000, 2560, 1440, fx, fy)
            assert rect is not None
            assert rect.width  == 2560
            assert rect.height == 1440


# ── crop_image_for_monitor ────────────────────────────────────────────────────

class TestCropImageForMonitor:
    def test_successful_crop_produces_file(self, tmp_path):
        from wallpaperforge.crop import crop_image_for_monitor

        src = _make_image(tmp_path / "src.png", 3840, 2160)
        dst = tmp_path / "out" / "result.png"

        result = crop_image_for_monitor(src, 1920, 1080, dst)

        assert result.success
        assert dst.exists()
        with Image.open(dst) as im:
            assert im.size == (1920, 1080)

    def test_image_too_small_returns_failure(self, tmp_path):
        from wallpaperforge.crop import crop_image_for_monitor

        src = _make_image(tmp_path / "tiny.png", 800, 600)
        dst = tmp_path / "out" / "result.png"

        result = crop_image_for_monitor(src, 1920, 1080, dst)

        assert not result.success
        assert not dst.exists()
        assert "menor" in result.reason.lower()

    def test_jpeg_output(self, tmp_path):
        from wallpaperforge.crop import crop_image_for_monitor

        src = _make_image(tmp_path / "src.png", 3840, 2160)
        dst = tmp_path / "out" / "result.png"  # extensão trocada para .jpg internamente

        result = crop_image_for_monitor(src, 1920, 1080, dst, jpeg=True, jpeg_quality=90)

        assert result.success
        out_jpg = dst.with_suffix(".jpg")
        assert out_jpg.exists()
        with Image.open(out_jpg) as im:
            assert im.size == (1920, 1080)

    def test_corrupt_source_returns_failure(self, tmp_path):
        from wallpaperforge.crop import crop_image_for_monitor

        corrupt = tmp_path / "bad.jpg"
        corrupt.write_bytes(b"JUNK")
        dst = tmp_path / "out" / "result.png"

        result = crop_image_for_monitor(corrupt, 1920, 1080, dst)

        assert not result.success

    def test_exact_fit_no_distortion(self, tmp_path):
        from wallpaperforge.crop import crop_image_for_monitor

        # Imagem exatamente do tamanho alvo → crop de dimensão zero, ok
        src = _make_image(tmp_path / "exact.png", 1920, 1080)
        dst = tmp_path / "out" / "exact_out.png"

        result = crop_image_for_monitor(src, 1920, 1080, dst)

        assert result.success
        with Image.open(dst) as im:
            assert im.size == (1920, 1080)
