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
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import __version__
from .build import (
    _config_path,
    cleanup_intermediates,
    extract_zip,
    install_inf_windows,
    refresh_windows_cursors,
    run_ctgen,
    run_uninstall_bat,
    zip_dir,
)
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


def cmd_install(args: argparse.Namespace) -> int:
    """Build (if needed) + extract + run install.inf with UAC elevation."""
    if sys.platform != "win32":
        raise SystemExit("`bibata install` is Windows-only for now.")

    # Reuse build logic. Force --platform windows + --no-zip so we get the
    # raw theme directory (no need to re-extract our own zip).
    if not getattr(args, "windows_size", None):
        args.windows_size = "large"
    args.platform = "windows"
    args.zip = False
    args.keep_intermediates = False

    # Capture the produced theme dir(s)
    palette_label, palette = _resolve_palette(args)
    out_dir = Path(args.output).resolve()
    _info(
        f"Step 1/3  Building {args.variant} / {palette_label} / "
        f"{args.windows_size} into {out_dir}"
    )
    rc = cmd_build(args)
    if rc != 0:
        return rc

    # Locate the freshly built theme directory under out_dir
    suffix_map = {
        "regular": "Regular", "large": "Large", "xl": "Extra-Large",
    }
    if args.windows_size == "all":
        targets = ["Regular", "Large", "Extra-Large"]
    else:
        targets = [suffix_map[args.windows_size]]

    installed: list[str] = []
    for suffix in targets:
        name = theme_name(args.variant, palette_label, suffix)
        theme_dir = out_dir / f"{name}-Windows"
        if not theme_dir.is_dir():
            _info(f"!! built theme directory not found: {theme_dir}")
            continue
        inf = theme_dir / "install.inf"
        _info(f"Step 2/3  Triggering install.inf for '{name}' (UAC prompt incoming)…")
        try:
            install_inf_windows(inf)
        except subprocess.CalledProcessError as e:
            _info(f"!! installer exited with code {e.returncode} (UAC declined?)")
            return e.returncode
        installed.append(name)

    if not installed:
        _info("Nothing was installed.")
        return 1

    _info("Step 3/3  Refreshing live cursor settings…")
    refresh_windows_cursors()  # best-effort; works when called from user shell

    _info(f"Installed: {len(installed)} theme(s)")
    for n in installed:
        print(f"  - {n} Cursors")
    print(
        "\nIf the on-screen cursor didn't change, open\n"
        "    control main.cpl ,,1\n"
        "select the scheme in the dropdown, click Apply."
    )
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    """Run a previously-installed theme's bundled uninstall.bat with admin."""
    if sys.platform != "win32":
        raise SystemExit("`bibata uninstall` is Windows-only.")
    # Two ways to point at the theme: explicit path, or system install dir
    if args.theme_dir:
        theme_dir = Path(args.theme_dir).resolve()
    else:
        # Default: C:\Windows\Cursors\<scheme-name> doesn't ship uninstall.bat
        # (only the extracted theme dir does). Tell the user to point at it.
        raise SystemExit(
            "Provide the extracted theme directory containing uninstall.bat:\n"
            "    bibata uninstall <path/to/Bibata-..-Windows>"
        )
    if not theme_dir.is_dir():
        raise SystemExit(f"not a directory: {theme_dir}")
    _info(f"Running uninstall.bat in {theme_dir} (UAC prompt incoming)…")
    try:
        run_uninstall_bat(theme_dir)
    except subprocess.CalledProcessError as e:
        _info(f"!! uninstaller exited with code {e.returncode}")
        return e.returncode
    refresh_windows_cursors()
    _info("Uninstalled. Falling back to Windows default cursor scheme.")
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    """Render every cursor + emit an HTML gallery; open it in the browser."""
    from .preview import generate_preview, open_in_browser

    palette_label, palette = _resolve_palette(args)
    out_dir = Path(args.output).resolve() / f"preview-{args.variant}-{palette_label.lower()}"
    _info(
        f"Rendering preview ({args.variant} / {palette_label}) at {args.size}px "
        f"into {out_dir} …"
    )
    t0 = time.perf_counter()
    index = generate_preview(args.variant, palette, palette_label, out_dir, render_size=args.size)
    _info(f"  done in {time.perf_counter() - t0:.1f}s → {index}")
    if not args.no_open:
        open_in_browser(index)
        _info("Opened in default browser. Animated cursors play in-page at 30ms/frame.")
    else:
        _info(f"Open manually: {index.as_uri()}")
    return 0


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

    # ---- install --------------------------------------------------------
    i = sub.add_parser(
        "install",
        help="(Windows) Build + install + activate a Bibata scheme in one go.",
    )
    i.add_argument("-v", "--variant", required=True, choices=sorted(VARIANTS))
    i.add_argument(
        "-c", "--color",
        required=True,
        help=f"Palette preset ({', '.join(PALETTES)}) or 'custom'.",
    )
    i.add_argument("--base", help="Hex color for base (with --color custom).")
    i.add_argument("--outline", help="Hex color for outline (with --color custom).")
    i.add_argument("--watch-bg", dest="watch_bg",
                   help="Hex color for watch background (with --color custom).")
    i.add_argument(
        "--windows-size",
        choices=["regular", "large", "xl", "all"],
        default="large",
        help="Which Windows size profile to install (default: large).",
    )
    i.add_argument(
        "-o", "--output",
        default="./out",
        help="Where to keep the built theme directory (default: ./out).",
    )
    i.set_defaults(func=cmd_install)

    # ---- uninstall ------------------------------------------------------
    u = sub.add_parser(
        "uninstall",
        help="(Windows) Run a theme's bundled uninstall.bat with admin rights.",
    )
    u.add_argument(
        "theme_dir",
        nargs="?",
        help="Path to the extracted Bibata-...-Windows directory.",
    )
    u.set_defaults(func=cmd_uninstall)

    # ---- preview --------------------------------------------------------
    pr = sub.add_parser(
        "preview",
        help="Render all cursors + open an HTML gallery in your browser.",
    )
    pr.add_argument("-v", "--variant", required=True, choices=sorted(VARIANTS))
    pr.add_argument(
        "-c", "--color",
        required=True,
        help=f"Palette preset ({', '.join(PALETTES)}) or 'custom'.",
    )
    pr.add_argument("--base", help="Hex color for base (with --color custom).")
    pr.add_argument("--outline", help="Hex color for outline (with --color custom).")
    pr.add_argument("--watch-bg", dest="watch_bg",
                    help="Hex color for watch background (with --color custom).")
    pr.add_argument("-s", "--size", type=int, default=96,
                    help="Preview render size in px (default: 96).")
    pr.add_argument("-o", "--output", default="./out",
                    help="Parent output directory (default: ./out).")
    pr.add_argument("--no-open", action="store_true",
                    help="Don't auto-open in browser; just print the file URI.")
    pr.set_defaults(func=cmd_preview)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
