# Vendored SVG artwork

Everything under `groups/` is a verbatim snapshot of
`github.com/ful1e5/Bibata_Cursor` @ commit
[`35ccfe2`](https://github.com/ful1e5/Bibata_Cursor/tree/35ccfe2/svg/groups)
(2024-06-18).

**Do not hand-edit files here as part of bibata-studio work.** If you want
to evolve the artwork, edit it upstream first, then re-vendor — or, if
upstream is unmaintained, hard-fork the SVGs into a separate repo with
clear attribution and re-vendor from that.

## What's here

| Directory | Purpose |
|---|---|
| `groups/shared/` | Cursors shared by every variant (sizing handles, X11-only helpers, the `wait` animation) |
| `groups/modern/` | Modern-style variant-specific cursors (rounded edges) |
| `groups/modern-arrow/` | Modern-style scroll & resize arrows (used by both Modern and Modern-Right) |
| `groups/modern-right/` | Right-hand mirror of `modern/` |
| `groups/original/` | Original-style variant-specific cursors (sharp edges) |
| `groups/original-arrow/` | Original-style scroll & resize arrows |
| `groups/original-right/` | Right-hand mirror of `original/` |
| `groups/hand/` | The grab/grabbing/drag-and-drop hand cursors |
| `groups/hand-right/` | Right-hand mirror of `hand/` |

## Variant composition

The Python mapping in `bibata_studio/presets.py::VARIANTS` reproduces the
logic from upstream's `svg/link.py`:

```python
"modern":         ("shared", "modern-arrow", "modern", "hand"),
"modern-right":   ("shared", "modern-arrow", "modern-right", "hand-right"),
"original":       ("shared", "original-arrow", "original", "hand"),
"original-right": ("shared", "original-arrow", "original-right", "hand-right"),
```

Renderer walks the listed group dirs in order; first occurrence of a given
cursor name wins (no collisions exist in practice).

## Color placeholders

Each SVG uses three hex colors as palette placeholders, swapped at render
time:

| Placeholder | Replaced by |
|---|---|
| `#00FF00` | `Palette.base` |
| `#0000FF` | `Palette.outline` |
| `#FF0000` | `Palette.watch_bg` |

(Case-insensitive substitution; see `render.py::_apply_palette`.)
