# bibata-studio

A local-first, pure-Python CLI that builds [Bibata](https://github.com/ful1e5/Bibata_Cursor)
cursor themes. No web stack, no database, no auth, no Figma token — just
SVGs in, cursor `.zip` out.

> **Relationship to upstream.** This is an **independent reimplementation**
> of the Bibata build pipeline, not a fork in the git sense. The cursor SVGs
> and the [`ctgen`](https://github.com/ful1e5/clickgen) build configs are
> **vendored verbatim** from [`ful1e5/Bibata_Cursor`](https://github.com/ful1e5/Bibata_Cursor)
> @ commit `35ccfe2` (2024-06-18). All Python source is new and shares no
> code with the [`ful1e5/bibata`](https://github.com/ful1e5/bibata) web app
> — only the three placeholder hex colors (`#00FF00` / `#0000FF` /
> `#FF0000`) for color substitution are borrowed as a protocol. See
> [`NOTICE`](./NOTICE) for full attribution.

```
$ bibata build --variant modern --color amber --platform windows --windows-size large
[bibata] Rendering 'modern' with palette 'Amber' (#FF8300 / #FFFFFF / #001524)
[bibata]   rendered 164 PNGs in 1.4s
[bibata] Packing Windows theme 'Bibata-Modern-Amber-Large' …
[bibata] Done. Wrote 1 artifact(s):
  → ./out/Bibata-Modern-Amber-Large-Windows.zip
```

## Why this exists

The upstream [`ful1e5/bibata`](https://github.com/ful1e5/bibata) is a Next.js +
Flask + Postgres + Vercel-KV + GitHub-OAuth web app that wraps two simple
ideas:

1. swap three "mask" colors in some SVGs
2. hand the resulting PNGs to [`clickgen`](https://github.com/ful1e5/clickgen)
   so it can pack a Windows or X11 cursor theme

That stack made sense for a Vercel-hosted SaaS with download metering. For
*using* Bibata locally it's all overhead — and as of late 2024 it's also
broken:

- `@vercel/kv` was retired in Dec 2024 (moved to Upstash). Upstream still
  imports it.
- Vercel Postgres became Neon. Upstream's connection strings no longer
  resolve.
- Figma file access requires the original author's `FIGMA_TOKEN`.
- Upstream's last commit is July 2024 and several open issues report the live
  site as broken.

This project drops everything above the dotted line:

```
  ┌───────────────────────────────────────────────┐
  │  Next.js · NextAuth · Prisma · @vercel/kv ·   │   ← dropped
  │  Vercel Postgres · Figma API · Flask · Docker │
  ├ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┤
  │  SVG color replace  +  clickgen packing       │   ← kept
  └───────────────────────────────────────────────┘
```

…and rebuilds the kept part in ~1100 lines of Python.

## Install

Requires **Python ≥ 3.10**. Tested on Windows 11 + Python 3.12.

```powershell
git clone <your-fork-url> bibata-studio
cd bibata-studio
pip install -e .
```

`pip` will pull two runtime dependencies:

- [`resvg-py`](https://pypi.org/project/resvg-py/) — Rust-backed SVG
  rasterizer (ships prebuilt Windows wheels)
- [`clickgen`](https://pypi.org/project/clickgen/) — XCursor/CUR/ANI packer
  by the original Bibata author

## Usage

The one-shot, "I just want it on my desktop" flow:

```powershell
# Build + install + activate the Amber Large theme in one command
python -m bibata_studio install -v modern -c amber

# Or, if `bibata.exe` is on your PATH:
bibata install -v modern -c amber
```

You'll see one UAC prompt (granting `rundll32.exe` permission to write to
`C:\Windows\Cursors\` and `HKCU\Control Panel\Cursors`). Click **Yes**. The
new scheme is activated automatically — no manual trip to Control Panel.

If you only want the zip (e.g. to ship to another machine):

```powershell
python -m bibata_studio build -v modern -c amber -p windows --windows-size large
```

### All commands

```text
bibata build      -v <variant> -c <palette> [-p <platform>] [--windows-size <size>] [-o <dir>]
bibata install    -v <variant> -c <palette> [--windows-size <size>]    # Windows only
bibata uninstall  <path-to-extracted-theme-dir>                         # Windows only
bibata list                                                             # show variants + palettes
```

### Variants

| name             | description                                |
|------------------|--------------------------------------------|
| `modern`         | Rounded edges, left-hand                   |
| `modern-right`   | Rounded edges, right-hand                  |
| `original`       | Sharp edges, left-hand                     |
| `original-right` | Sharp edges, right-hand                    |

### Presets

| name      | base color  | outline | watch background |
|-----------|------------:|--------:|-----------------:|
| `amber`   | `#FF8300`   | white   | `#001524`        |
| `classic` | `#000000`   | white   | black            |
| `ice`     | `#FFFFFF`   | black   | white            |

### Custom palette

```powershell
# Gruvbox dark
bibata build -v original -c custom `
    --base "#282828" --outline "#EBDBB2" --watch-bg "#000000" `
    -p windows --windows-size large

# Dracula
bibata build -v modern -c custom `
    --base "#282A36" --outline "#F8F8F2" --watch-bg "#44475A" `
    -p windows --windows-size large
```

### Platforms

| `-p` value | output                                                              |
|------------|---------------------------------------------------------------------|
| `windows`  | `.zip` with `.cur` / `.ani` files + `install.inf` + `uninstall.bat` |
| `x11`      | Linux XCursor theme directory (see caveat below)                    |
| `both`     | Both at once                                                        |

### Windows sizes

The upstream project ships four pre-tuned hotspot/size profiles per
hand-variant — pick one or build all three:

| `--windows-size` | base size | use for                                |
|------------------|----------:|----------------------------------------|
| `regular`        | 32 px     | typical 1× / 1.25× DPI                 |
| `large` *(default)* | 48 px  | 1.5× / 1.75× DPI                       |
| `xl`             | 64 px     | 2× DPI and above                       |
| `all`            | —         | build all three in one invocation      |

### Install a built zip on Windows manually

If you'd rather not use `bibata install`, you can deploy a `.zip` by hand:

1. Right-click the zip → *Extract All…*
2. In the extracted folder, **Shift+right-click** `install.inf`
   (or right-click → *Show more options* on Win11) → **Install**
3. Approve the UAC prompt
4. The new scheme becomes active immediately. To verify, open
   *Control Panel → Mouse → Pointers* (`control main.cpl ,,1`); the
   *Scheme* dropdown should show `Bibata-…-Windows Cursors` selected.

The scheme is named `Bibata-<Variant>-<Color>-<Size> Cursors` (note the
trailing word "Cursors" — clickgen appends it automatically).

## Architecture

```
bibata-studio/
├── pyproject.toml
└── src/bibata_studio/
    ├── cli.py        # argparse + orchestration
    ├── presets.py    # palettes + variant→group mapping + theme naming
    ├── render.py     # SVG color-replace + resvg-py rasterization
    ├── build.py      # in-process call into clickgen.scripts.ctgen.main
    └── data/
        ├── svg/groups/         # vendored from Bibata_Cursor/svg/groups/
        │   ├── shared/ ...
        │   ├── modern-arrow/ ...
        │   ├── modern/ ...     # variant-specific cursors
        │   ├── modern-right/ ...
        │   ├── original-arrow/ ...
        │   ├── original/ ...
        │   ├── original-right/ ...
        │   ├── hand/ ...
        │   └── hand-right/ ...
        └── configs/            # vendored ctgen TOML configs
            ├── normal/{x,win_rg,win_lg,win_xl}.build.toml
            └── right/{x,win_rg,win_lg,win_xl}.build.toml
```

A build proceeds in three stages:

1. **Walk** the group directories that make up the chosen variant (see
   `presets.VARIANTS`).
2. **Render** each SVG into a flat `bitmaps/` directory at 256×256 PNG, with
   the three mask hex colors substituted for the chosen palette.
3. **Pack** by calling `clickgen.scripts.ctgen.main` in-process with the
   vendored TOML config — clickgen handles `.cur`/`.ani` encoding, multi-size
   resampling, hotspots, Windows symlinks, and `install.inf` generation.

## Caveats

- **X11 themes need symlink permission on Windows.** clickgen creates
  XCursor name aliases via `os.symlink`, which requires either admin rights
  or Developer Mode on Windows. Windows-only output (`-p windows`) is
  unaffected. Linux/macOS have no such restriction.
- **No GUI yet.** A `pyside6`-based picker is on the roadmap (see below).
  In the meantime, `bibata preview -v <variant> -c <color>` emits an HTML
  gallery (all cursors at 96px, animated ones playing) that opens in your
  default browser.

## Roadmap

In rough priority order:

- [ ] `bibata watch` mode: re-render on SVG file change for designer
      workflows.
- [ ] PySide6/Tk GUI with live color preview and "scratch" custom theme.
- [ ] Bundle a portable `.exe` via PyInstaller for users without Python.
- [ ] X11 build path that produces tarballs without needing symlinks (write
      duplicate files instead).
- [ ] Animation re-timing flag (current default copies upstream's 30 ms
      frame delay).

## What's borrowed vs what's new

A precise breakdown — see [`NOTICE`](./NOTICE) for the legal version.

| Asset | Source | How |
|---|---|---|
| 372 SVG cursor files | `ful1e5/Bibata_Cursor` @ `35ccfe2` | Verbatim copy in `src/bibata_studio/data/svg/groups/` |
| 8 `ctgen` build TOMLs | `ful1e5/Bibata_Cursor` @ `35ccfe2` | Verbatim copy in `src/bibata_studio/data/configs/` |
| Variant → group mapping | `ful1e5/Bibata_Cursor/svg/link.py` | Re-expressed as a Python dict in `presets.VARIANTS` |
| Three mask hex colors | `ful1e5/bibata` web app + Bibata_Cursor README | Protocol borrowed (`#00FF00` / `#0000FF` / `#FF0000`) |
| `.cur` / `.ani` packing | `clickgen` pip package | Imported as a runtime library |
| All Python source (~1100 LoC) | — | Written for this project; **no code shared with `ful1e5/bibata`** |

**The `ful1e5/bibata` web application contributed zero lines of code** —
only the color-mask convention. All artwork credit goes to
**Abdulkaiz Khatri** ([@ful1e5](https://github.com/ful1e5)). If you use this
tool and find Bibata useful, [sponsor @ful1e5](https://github.com/sponsors/ful1e5).

## License

MIT. See [`LICENSE`](./LICENSE).
