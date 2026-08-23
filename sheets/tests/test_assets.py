"""Structural checks on the extracted sheet background images.

These confirm ``tools/extract_sheet_assets.py`` produced usable, correctly
oriented images -- not that the artwork is pixel-perfect (that can only be
checked by a human/vision reviewer looking at the actual scan).
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

IMAGES_DIR = Path(__file__).resolve().parent.parent / "static" / "sheets" / "images"

PORTRAIT_IMAGES = ("character-page-1.webp", "character-page-2.webp")
LANDSCAPE_IMAGES = ("ship-page.webp",)
ALL_IMAGES = PORTRAIT_IMAGES + LANDSCAPE_IMAGES


@pytest.mark.parametrize("filename", ALL_IMAGES)
def test_image_exists(filename):
    assert (IMAGES_DIR / filename).exists(), f"missing extracted asset: {filename}"


@pytest.mark.parametrize("filename", ALL_IMAGES)
def test_image_has_nonzero_dimensions(filename):
    with Image.open(IMAGES_DIR / filename) as image:
        width, height = image.size
    assert width > 0
    assert height > 0


@pytest.mark.parametrize("filename", PORTRAIT_IMAGES)
def test_character_pages_are_portrait(filename):
    with Image.open(IMAGES_DIR / filename) as image:
        width, height = image.size
    assert height > width, f"{filename} expected portrait, got {width}x{height}"


@pytest.mark.parametrize("filename", LANDSCAPE_IMAGES)
def test_ship_page_is_landscape(filename):
    with Image.open(IMAGES_DIR / filename) as image:
        width, height = image.size
    assert width > height, f"{filename} expected landscape, got {width}x{height}"


@pytest.mark.parametrize("filename", ALL_IMAGES)
def test_image_is_lossless_webp(filename):
    with Image.open(IMAGES_DIR / filename) as image:
        assert image.format == "WEBP"


@pytest.mark.parametrize("filename", ALL_IMAGES)
def test_image_dimensions_match_placeholder_schema(filename):
    """The placeholder schema JSON records the real extracted dimensions.

    This guards against the schema's ``image.width``/``image.height``
    silently drifting from the actual asset if either is regenerated.
    """
    from sheets.schema import load_schema

    page_id = filename.removesuffix(".webp")
    schema = load_schema(page_id)
    with Image.open(IMAGES_DIR / filename) as image:
        width, height = image.size
    assert schema.image_width == width
    assert schema.image_height == height
