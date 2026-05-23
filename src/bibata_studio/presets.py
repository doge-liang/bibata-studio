"""Color presets and variant→group mappings.

Sourced from upstream `Bibata_Cursor/render.json` and `svg/link.py` (commit
35ccfe2, 2024-06-18).
"""

from __future__ import annotations

from dataclasses import dataclass

# SVG placeholder ("mask") colors. The vendored SVG sources use these three
# hex values as stand-ins for the user's chosen palette. See the upstream
# `Bibata_Cursor` README §"Customize Colors" for the convention.
MASK_BASE = "#00FF00"
MASK_OUTLINE = "#0000FF"
MASK_WATCH_BG = "#FF0000"


@dataclass(frozen=True)
class Palette:
    base: str
    outline: str
    watch_bg: str

    def as_replacements(self) -> dict[str, str]:
        """Mapping from mask color → replacement, suitable for str.replace."""
        return {
            MASK_BASE: self.base,
            MASK_OUTLINE: self.outline,
            MASK_WATCH_BG: self.watch_bg,
        }


# Three official Bibata palettes from upstream `render.json`.
PALETTES: dict[str, Palette] = {
    "amber":   Palette(base="#FF8300", outline="#FFFFFF", watch_bg="#001524"),
    "classic": Palette(base="#000000", outline="#FFFFFF", watch_bg="#000000"),
    "ice":     Palette(base="#FFFFFF", outline="#000000", watch_bg="#FFFFFF"),
}


# Variant → ordered list of group directory names. Mirrors `svg/link.py` from
# upstream — file-name conflicts between groups are resolved by *later* groups
# overriding earlier ones, but in practice each cursor lives in exactly one
# group so order is cosmetic.
VARIANTS: dict[str, tuple[str, ...]] = {
    "modern":         ("shared", "modern-arrow", "modern", "hand"),
    "modern-right":   ("shared", "modern-arrow", "modern-right", "hand-right"),
    "original":       ("shared", "original-arrow", "original", "hand"),
    "original-right": ("shared", "original-arrow", "original-right", "hand-right"),
}


# Mapping from CLI --windows-size flag → upstream TOML basename. Upstream ships
# four pre-tuned size profiles (Regular/Large/Extra-Large) per hand-variant.
WIN_SIZE_TOMLS: dict[str, str] = {
    "regular": "win_rg.build.toml",
    "large":   "win_lg.build.toml",
    "xl":      "win_xl.build.toml",
}

X11_TOML = "x.build.toml"


def theme_name(variant: str, palette: str, suffix: str | None = None) -> str:
    """Build a canonical theme name, e.g. `Bibata-Modern-Amber-Regular`."""
    # variant strings look like "modern-right"; turn into "Modern-Right"
    parts = ["Bibata"] + [seg.capitalize() for seg in variant.split("-")]
    parts.append(palette.capitalize())
    if suffix:
        parts.append(suffix)
    return "-".join(parts)
