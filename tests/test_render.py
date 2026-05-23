"""Smoke tests for the render pipeline.

Doesn't exercise clickgen (heavier, separate concern) — just verifies that
the SVG → PNG step works for every variant + palette combination and that
color substitution actually lands in the pixels.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from PIL import Image

from bibata_studio.presets import PALETTES, VARIANTS, Palette
from bibata_studio.render import _apply_palette, render_variant


# ---------------------------------------------------------------------------
# Unit: color substitution


def test_apply_palette_replaces_mask_colors():
    svg = '<svg fill="#00FF00" stroke="#0000FF" data-watch="#FF0000"/>'
    out = _apply_palette(svg, PALETTES["amber"])
    assert "#FF8300" in out  # base
    assert "#FFFFFF" in out  # outline
    assert "#001524" in out  # watch_bg
    assert "#00FF00" not in out
    assert "#0000FF" not in out


def test_apply_palette_is_case_insensitive():
    svg = '<svg fill="#00ff00" stroke="#0000ff"/>'
    out = _apply_palette(svg, PALETTES["classic"])
    assert "#000000" in out
    assert "#FFFFFF" in out


# ---------------------------------------------------------------------------
# Integration: full variant render


@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_render_variant_produces_expected_pngs(variant, tmp_path):
    out_dir = tmp_path / "bitmaps"
    n = render_variant(variant, PALETTES["amber"], out_dir)
    # Every variant has at minimum: ~50 static cursors + 108 frames of two
    # animated cursors (left_ptr_watch + wait, 54 each).
    assert n > 150, f"only rendered {n} PNGs for {variant}"

    # Sanity: must include left_ptr (the most important cursor), animated wait,
    # and the variant-specific arrow.
    must_exist = ["left_ptr.png", "wait-01.png", "left_ptr_watch-01.png", "move.png"]
    for f in must_exist:
        assert (out_dir / f).is_file(), f"missing {f} in {variant} output"


def test_amber_palette_lands_in_pixels(tmp_path):
    out_dir = tmp_path / "bitmaps"
    render_variant("modern", PALETTES["amber"], out_dir)

    img = Image.open(out_dir / "left_ptr.png").convert("RGBA")
    amber_pixels = sum(
        1 for p in img.get_flattened_data() if False  # placeholder
    )
    # Fall back to getdata for Pillow <14
    if not hasattr(img, "get_flattened_data"):
        data = list(img.getdata())
    else:
        try:
            data = list(img.get_flattened_data())
        except Exception:
            data = list(img.getdata())

    amber = sum(
        1
        for p in data
        if p[3] > 200 and abs(p[0] - 0xFF) < 5 and abs(p[1] - 0x83) < 8 and abs(p[2]) < 5
    )
    assert amber > 1000, f"amber pixel count too low: {amber}"


def test_custom_palette_round_trip(tmp_path):
    """A bright magenta palette should produce no green/blue/red mask pixels."""
    out_dir = tmp_path / "bitmaps"
    custom = Palette(base="#FF00FF", outline="#00FFFF", watch_bg="#FFFF00")
    render_variant("modern", custom, out_dir)
    img = Image.open(out_dir / "left_ptr.png").convert("RGBA")
    data = list(img.getdata())
    mask_leaks = sum(
        1
        for p in data
        if p[3] > 200
        and (
            (p[0] == 0 and p[1] > 240 and p[2] == 0)  # #00FF00
            or (p[0] == 0 and p[1] == 0 and p[2] > 240)  # #0000FF
            or (p[0] > 240 and p[1] == 0 and p[2] == 0)  # #FF0000
        )
    )
    assert mask_leaks == 0, f"mask colors leaked into output: {mask_leaks} px"
