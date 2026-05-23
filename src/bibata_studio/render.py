"""SVG → PNG bitmap rendering with color substitution.

Walks a variant's group directories, applies the chosen palette to each SVG
(case-insensitive, mirroring upstream's `card.tsx` behavior), and rasterizes
to PNG via `resvg-py` (Rust-backed, fast, ships Windows wheels).

The output layout matches what `ctgen` expects:

    <bitmaps_dir>/
        bd_double_arrow.png        # static cursor
        circle.png
        ...
        left_ptr_watch-01.png      # animated cursor (flat-named frames)
        left_ptr_watch-02.png
        ...
"""

from __future__ import annotations

import re
from importlib import resources
from pathlib import Path
from typing import Iterable

import resvg_py

from .presets import Palette, VARIANTS

# Source SVGs canvas size (all upstream bibata SVGs are 256×256). Rendering at
# this resolution gives clickgen enough headroom to rescale for any target
# size with bilinear/lanczos downscale.
RENDER_SIZE = 256


def _package_data_root() -> Path:
    """Path to the on-disk `data/` directory, even when installed as a wheel."""
    # `importlib.resources.files` returns a Traversable; for plain filesystem
    # packages it can be cast to a real Path. Wheel installs work identically.
    return Path(str(resources.files("bibata_studio").joinpath("data")))


def variant_svg_dirs(variant: str) -> list[Path]:
    """Return the group directories that compose a variant, in order."""
    try:
        groups = VARIANTS[variant]
    except KeyError as e:
        raise ValueError(
            f"Unknown variant {variant!r}. Choose from: {sorted(VARIANTS)}"
        ) from e
    root = _package_data_root() / "svg" / "groups"
    return [root / g for g in groups]


def _apply_palette(svg_text: str, palette: Palette) -> str:
    """Replace the three mask colors (case-insensitive)."""
    for mask, replacement in palette.as_replacements().items():
        svg_text = re.sub(re.escape(mask), replacement, svg_text, flags=re.IGNORECASE)
    return svg_text


def _rasterize(svg_text: str, size: int) -> bytes:
    """SVG string → PNG bytes at size×size, transparent background."""
    out = resvg_py.svg_to_bytes(svg_string=svg_text, width=size, height=size)
    return bytes(out)


def _iter_cursor_entries(svg_dirs: Iterable[Path]) -> Iterable[tuple[str, Path | list[Path]]]:
    """Yield (cursor_name, source) tuples.

    `source` is either a single `Path` to a static SVG, or a list of `Path`s
    for an animated cursor (sorted lexicographically — frame names are
    zero-padded so this gives the right order).
    """
    seen: set[str] = set()
    for group_dir in svg_dirs:
        if not group_dir.is_dir():
            raise FileNotFoundError(f"missing group directory: {group_dir}")
        for entry in sorted(group_dir.iterdir()):
            if entry.name in seen:
                continue
            if entry.is_file() and entry.suffix.lower() == ".svg":
                seen.add(entry.name)
                yield entry.stem, entry
            elif entry.is_dir():
                seen.add(entry.name)
                frames = sorted(p for p in entry.iterdir() if p.suffix.lower() == ".svg")
                if frames:
                    yield entry.name, frames


def render_variant(
    variant: str,
    palette: Palette,
    out_dir: Path,
    *,
    render_size: int = RENDER_SIZE,
    on_progress=None,
) -> int:
    """Render every cursor in `variant` recolored with `palette` to `out_dir`.

    Returns the total number of PNG files written.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    svg_dirs = variant_svg_dirs(variant)

    total = 0
    for name, source in _iter_cursor_entries(svg_dirs):
        if isinstance(source, list):
            # Animated cursor: render each frame to <name>-NN.png
            for frame in source:
                svg_text = frame.read_text(encoding="utf-8")
                png = _rasterize(_apply_palette(svg_text, palette), render_size)
                (out_dir / f"{frame.stem}.png").write_bytes(png)
                total += 1
            if on_progress:
                on_progress(name, len(source))
        else:
            svg_text = source.read_text(encoding="utf-8")
            png = _rasterize(_apply_palette(svg_text, palette), render_size)
            (out_dir / f"{name}.png").write_bytes(png)
            total += 1
            if on_progress:
                on_progress(name, 1)
    return total
