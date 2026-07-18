"""Testes para wallpaperforge.filter."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _write_png(path: Path, width: int, height: int, color: tuple = (100, 149, 237)) -> Path:
    """Cria um PNG sintético de (width × height) pixels."""
    img = Image.new("RGB", (width, height), color=color)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")
    return path


@pytest.fixture
def tmp_images(tmp_path: Path):
    """Conjunto variado de imagens para os testes de filtro."""
    images = {
        "large":    _write_png(tmp_path / "large.png",    2560, 1440),
        "medium":   _write_png(tmp_path / "medium.png",   1920, 1080),
        "small":    _write_png(tmp_path / "small.png",     800,  600),
        "portrait": _write_png(tmp_path / "portrait.png",  600,  900),
        "corrupt":  (tmp_path / "corrupt.jpg"),
    }
    images["corrupt"].write_bytes(b"NOT_AN_IMAGE_BYTES_XXXX")
    return images


# ── filter_corrupt ────────────────────────────────────────────────────────────

class TestFilterCorrupt:
    def test_valid_images_pass(self, tmp_images):
        from wallpaperforge.filter import filter_corrupt

        valid = [tmp_images["large"], tmp_images["medium"]]
        ok, bad = filter_corrupt(valid)
        assert set(ok) == set(valid)
        assert bad == []

    def test_corrupt_image_is_rejected(self, tmp_images):
        from wallpaperforge.filter import filter_corrupt

        ok, bad = filter_corrupt([tmp_images["corrupt"]])
        assert ok == []
        assert tmp_images["corrupt"] in bad

    def test_mixed_list(self, tmp_images):
        from wallpaperforge.filter import filter_corrupt

        paths = [tmp_images["large"], tmp_images["corrupt"]]
        ok, bad = filter_corrupt(paths)
        assert tmp_images["large"] in ok
        assert tmp_images["corrupt"] in bad


# ── filter_by_min_side ────────────────────────────────────────────────────────

class TestFilterByMinSide:
    def test_large_image_passes(self, tmp_images):
        from wallpaperforge.filter import filter_by_min_side

        ok, bad = filter_by_min_side([tmp_images["large"]], min_side=1100)
        assert tmp_images["large"] in ok
        assert bad == []

    def test_small_image_rejected(self, tmp_images):
        from wallpaperforge.filter import filter_by_min_side

        ok, bad = filter_by_min_side([tmp_images["small"]], min_side=1100)
        assert ok == []
        assert tmp_images["small"] in bad

    def test_exactly_at_threshold_passes(self, tmp_path):
        from wallpaperforge.filter import filter_by_min_side

        p = _write_png(tmp_path / "exact.png", 1920, 1100)
        ok, bad = filter_by_min_side([p], min_side=1100)
        assert p in ok

    def test_custom_threshold(self, tmp_images):
        from wallpaperforge.filter import filter_by_min_side

        # com min_side=500 a imagem "small" (800×600) deve passar
        ok, bad = filter_by_min_side([tmp_images["small"]], min_side=500)
        assert tmp_images["small"] in ok


# ── filter_portraits ──────────────────────────────────────────────────────────

class TestFilterPortraits:
    def test_landscape_always_passes(self, tmp_images):
        from wallpaperforge.filter import filter_portraits

        ok, bad = filter_portraits([tmp_images["large"]], portrait_allowed=False)
        assert tmp_images["large"] in ok

    def test_portrait_rejected_by_default(self, tmp_images):
        from wallpaperforge.filter import filter_portraits

        ok, bad = filter_portraits([tmp_images["portrait"]], portrait_allowed=False)
        assert ok == []
        assert tmp_images["portrait"] in bad

    def test_portrait_allowed_when_flag_set(self, tmp_images):
        from wallpaperforge.filter import filter_portraits

        ok, bad = filter_portraits([tmp_images["portrait"]], portrait_allowed=True)
        assert tmp_images["portrait"] in ok


# ── deduplicate ───────────────────────────────────────────────────────────────

class TestDeduplicate:
    def test_no_duplicates_unchanged(self, tmp_path):
        from wallpaperforge.filter import deduplicate
        from PIL import Image, ImageDraw

        def _checkerboard(path, w, h):
            """Xadrez 2×2 quadrantes — phash distante (32 bits) de imagem sólida."""
            img = Image.new("RGB", (w, h), (0, 0, 0))
            d   = ImageDraw.Draw(img)
            d.rectangle([0,    0,    w//2, h//2], fill=(255, 255, 255))
            d.rectangle([w//2, h//2, w,    h   ], fill=(255, 255, 255))
            img.save(path, "PNG")
            return path

        # check_2x2 vs solid_black → Hamming = 32, muito acima do limiar 5
        img_a = _checkerboard(tmp_path / "check.png", 400, 300)
        img_b = _write_png(tmp_path / "solid.png", 400, 300, color=(0, 0, 0))
        kept, removed = deduplicate([img_a, img_b])
        assert len(kept) == 2
        assert removed == []

    def test_exact_duplicate_removed(self, tmp_path):
        from wallpaperforge.filter import deduplicate

        # Dois arquivos idênticos
        p1 = _write_png(tmp_path / "img_a.png", 1920, 1080, color=(200, 100, 50))
        p2 = _write_png(tmp_path / "img_b.png", 1920, 1080, color=(200, 100, 50))
        kept, removed = deduplicate([p1, p2])
        assert len(kept) == 1
        assert len(removed) == 1

    def test_larger_duplicate_is_kept(self, tmp_path):
        from wallpaperforge.filter import deduplicate

        # img_big é maior → deve ser mantida
        small = _write_png(tmp_path / "small_dup.png", 1920, 1080, color=(10, 20, 30))
        big   = _write_png(tmp_path / "big_dup.png",   3840, 2160, color=(10, 20, 30))
        kept, removed = deduplicate([small, big])
        assert big in kept
        assert small in removed
