"""bibata-studio CLI.

    bibata build --variant modern --color amber --platform windows \\
                 --windows-size large --output ./out

Pipelines:
    1. Render: vendored SVGs → recolored PNGs (resvg-py)
    2. Pack:   PNGs → cursor theme (clickgen ctgen) → optional zip

Examples
--------
Single Windows zip:
    bibata build -v modern -c amber -p windows -o ./out

All three sizes (Regular + Large + Extra-Large):
    bibata build -v modern -c amber -p windows --windows-size all -o ./out

X11 (Linux) theme:
    bibata build -v modern -c amber -p x11 -o ./out

Custom palette via hex:
    bibata build -v original -c custom --base '#282828' \\
        --outline '#EBDBB2' --watch-bg '#000000' -p windows -o ./out
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

from . import __version__
from .build import _config_path, cleanup_intermediates, run_ctgen, zip_dir
from .presets import (
    PALETTES,
    Palette,
    VARIANTS,
    WIN_SIZE_TOMLS,
    X11_TOML,
    theme_name,
)
from .render import render_variant


def _resolve_palette(args: argparse.Namespace) -> tuple[str, Palette]:
    """Return (palette_label, Palette) from CLI args."""
    if args.color == "custom":
        for f in ("base", "outline", "watch_bg"):
            v = getattr(args, f)
            if not v:
                raise SystemExit(
                    f"--color custom requires --{f.replace('_', '-')} <hex>"
                )
        return "Custom", Palette(
            base=args.base, outline=args.outline, watch_bg=args.watch_bg
        )
    try:
        return args.color.capitalize(), PALETTES[args.color]
    except KeyError as e:
        raise SystemExit(
            f"Unknown --color {args.color!r}. Choose from: "
            f"{sorted(PALETTES)} or 'custom'."
        ) from e


def _is_right_variant(variant: str) -> bool:
    return variant.endswith("-right")


def _windows_size_targets(flag: str) -> list[tuple[str, str]]:
    """Return [(suffix, toml_basename), ...] for the requested size profile."""
    if flag == "all":
        return [
            ("Regular", WIN_SIZE_TOMLS["regular"]),
            ("Large",   WIN_SIZE_TOMLS["large"]),
            ("Extra-Large", WIN_SIZE_TOMLS["xl"]),
        ]
    label = {"regular": "Regular", "large": "Large", "xl": "Extra-Large"}[flag]
    return [(label, WIN_SIZE_TOMLS[flag])]


def _info(msg: str) -> None:
    print(f"[bibata] {msg}", flush=True)


def cmd_build(args: argparse.Namespace) -> int:
    if args.variant not in VARIANTS:
        raise SystemExit(
            f"Unknown --variant {args.variant!r}. Choose from: {sorted(VARIANTS)}"
        )

    palette_label, palette = _resolve_palette(args)
    hand = "right" if _is_right_variant(args.variant) else "normal"
    out_dir = Path(args.output).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- 1) Render once into a temp bitmaps dir ----------------------------
    tmp = Path(tempfile.mkdtemp(prefix="bibata-studio-"))
    bitmaps_dir = tmp / "bitmaps"
    themes_dir = tmp / "themes"

    t0 = time.perf_counter()
    _info(
        f"Rendering '{args.variant}' with palette '{palette_label}' "
        f"({palette.base} / {palette.outline} / {palette.watch_bg}) "
        f"→ {bitmaps_dir}"
    )
    n_pngs = render_variant(args.variant, palette, bitmaps_dir)
    _info(f"  rendered {n_pngs} PNGs in {time.perf_counter() - t0:.1f}s")

    # --- 2) Pack via clickgen ----------------------------------------------
    produced: list[Path] = []

    if args.platform in ("windows", "both"):
        for suffix, toml_name in _windows_size_targets(args.windows_size):
            name = theme_name(args.variant, palette_label, suffix)
            _info(f"Packing Windows theme '{name}' …")
            run_ctgen(
                config=_config_path(hand, toml_name),
                bitmaps_dir=bitmaps_dir,
                out_dir=themes_dir,
                name=name,
                comment=f"Bibata {args.variant} ({palette_label}) - {suffix}",
                platforms="windows",
            )
            produced.append(themes_dir / f"{name}-Windows")

    if args.platform in ("x11", "both"):
        name = theme_name(args.variant, palette_label)
        _info(f"Packing X11 theme '{name}' …")
        run_ctgen(
            config=_config_path(hand, X11_TOML),
            bitmaps_dir=bitmaps_dir,
            out_dir=themes_dir,
            name=name,
            comment=f"Bibata {args.variant} ({palette_label}) - XCursors",
            platforms="x11",
        )
        produced.append(themes_dir / name)

    # --- 3) Copy results into --output and (optionally) zip ----------------
    final_outputs: list[Path] = []
    for theme_dir in produced:
        if not theme_dir.exists():
            _info(f"!! expected output not found: {theme_dir}")
            continue
        if args.zip:
            zip_path = out_dir / f"{theme_dir.name}.zip"
            zip_dir(theme_dir, zip_path)
            final_outputs.append(zip_path)
        else:
            # Move the whole theme dir into out_dir
            dst = out_dir / theme_dir.name
            if dst.exists():
                import shutil
                shutil.rmtree(dst)
            theme_dir.rename(dst)
            final_outputs.append(dst)

    if not args.keep_intermediates:
        cleanup_intermediates(tmp)

    _info(f"Done. Wrote {len(final_outputs)} artifact(s):")
    for p in final_outputs:
        print(f"  → {p}")

    return 0 if final_outputs else 1


def cmd_list(_args: argparse.Namespace) -> int:
    print("Variants:")
    for v in VARIANTS:
        print(f"  - {v}")
    print("\nPalettes (presets):")
    for name, p in PALETTES.items():
        print(f"  - {name:<8} base={p.base}  outline={p.outline}  watch_bg={p.watch_bg}")
    print(
        "\nUse '--color custom --base #RRGGBB --outline #RRGGBB --watch-bg #RRGGBB' "
        "for arbitrary colors."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bibata",
        description="Local-first Bibata cursor builder.",
    )
    p.add_argument("--version", action="version", version=f"bibata-studio {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="Render + pack a cursor theme.")
    b.add_argument(
        "-v", "--variant",
        required=True,
        choices=sorted(VARIANTS),
        help="Cursor shape family.",
    )
    b.add_argument(
        "-c", "--color",
        required=True,
        help=f"Palette preset ({', '.join(PALETTES)}) or 'custom'.",
    )
    b.add_argument("--base", help="Hex color for base (with --color custom).")
    b.add_argument("--outline", help="Hex color for outline (with --color custom).")
    b.add_argument("--watch-bg", dest="watch_bg",
                   help="Hex color for watch background (with --color custom).")

    b.add_argument(
        "-p", "--platform",
        choices=["windows", "x11", "both"],
        default="windows",
        help="Output platform (default: windows).",
    )
    b.add_argument(
        "--windows-size",
        choices=["regular", "large", "xl", "all"],
        default="large",
        help="Which Windows size profile to build (default: large).",
    )
    b.add_argument(
        "-o", "--output",
        default="./out",
        help="Output directory (default: ./out).",
    )
    b.add_argument(
        "--no-zip",
        dest="zip",
        action="store_false",
        default=True,
        help="Don't zip the result; copy the theme directory instead.",
    )
    b.add_argument(
        "--keep-intermediates",
        action="store_true",
        help="Keep the temp bitmaps and theme directories (for debugging).",
    )
    b.set_defaults(func=cmd_build)

    l = sub.add_parser("list", help="List available variants and palettes.")
    l.set_defaults(func=cmd_list)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
