"""bibata-studio: local Bibata cursor builder.

Pure-Python CLI. Reads vendored SVG sources from upstream `Bibata_Cursor`,
applies color substitution via `resvg-py`, then hands the PNG bitmaps to
`clickgen` to produce X11 or Windows cursor themes.
"""

__version__ = "0.1.0"
