"""HTML preview generator.

Renders all cursors for a (variant, palette) pair into a `png/` sidecar
directory and emits a single self-contained index.html that lays them out in
a grid. Animated cursors play in-browser via setInterval frame-swapping.
"""

from __future__ import annotations

import json
import tomllib
import webbrowser
from pathlib import Path
from typing import Iterable

from .presets import Palette
from .render import _iter_cursor_entries, _package_data_root, render_variant


def _windows_role_map(hand: str) -> dict[str, str]:
    """Return {svg_cursor_name: WindowsRoleName}, e.g. {'left_ptr': 'Pointer'}."""
    cfg_path = _package_data_root() / "configs" / hand / "win_rg.build.toml"
    with cfg_path.open("rb") as f:
        cfg = tomllib.load(f)
    result: dict[str, str] = {}
    for cursor_key, body in cfg.get("cursors", {}).items():
        if cursor_key == "fallback_settings":
            continue
        if isinstance(body, dict) and "win_name" in body:
            # Strip extension that ctgen adds for win_name (e.g. "Pointer.cur")
            wn = str(body["win_name"])
            result[cursor_key] = wn
    return result


def _index_entries(variant: str) -> list[dict]:
    """Walk groups and produce a JSON-serialisable cursor list."""
    from .render import variant_svg_dirs

    items: list[dict] = []
    for name, src in _iter_cursor_entries(variant_svg_dirs(variant)):
        if isinstance(src, list):
            items.append({"name": name, "animated": True, "frames": len(src)})
        else:
            items.append({"name": name, "animated": False, "frames": 1})
    items.sort(key=lambda d: (not d["animated"], d["name"]))
    return items


_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Bibata Preview · {variant} / {palette_label}</title>
<style>
  :root {{
    --bg: #0f0f10;
    --panel: #1c1c1f;
    --panel-hi: #28282d;
    --text: #e6e6e6;
    --dim: #8a8a92;
    --accent: {accent};
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 32px;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  }}
  header {{ display: flex; align-items: baseline; gap: 16px; margin-bottom: 8px; flex-wrap: wrap; }}
  header h1 {{ margin: 0; font-weight: 600; font-size: 22px; }}
  header .meta {{ color: var(--dim); font-size: 13px; font-family: ui-monospace, "JetBrains Mono", monospace; }}
  .swatches {{ display: flex; gap: 8px; margin-bottom: 24px; }}
  .swatches span {{
    width: 22px; height: 22px; border-radius: 4px;
    border: 1px solid rgba(255,255,255,0.08);
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 12px;
  }}
  .card {{
    background: var(--panel);
    border-radius: 10px;
    padding: 14px 10px 10px;
    text-align: center;
    border: 1px solid transparent;
    transition: background 0.15s, transform 0.15s, border-color 0.15s;
  }}
  .card:hover {{ background: var(--panel-hi); transform: translateY(-2px); }}
  .card.win-mapped {{ border-color: rgba(255, 131, 0, 0.35); }}
  .card .img-wrap {{
    height: 88px;
    display: flex; align-items: center; justify-content: center;
    background:
      linear-gradient(45deg, #2a2a2e 25%, transparent 25%),
      linear-gradient(-45deg, #2a2a2e 25%, transparent 25%),
      linear-gradient(45deg, transparent 75%, #2a2a2e 75%),
      linear-gradient(-45deg, transparent 75%, #2a2a2e 75%);
    background-size: 14px 14px;
    background-position: 0 0, 0 7px, 7px -7px, -7px 0;
    border-radius: 6px;
  }}
  .card img {{ max-width: 72px; max-height: 72px; image-rendering: pixelated; }}
  .card .name {{
    margin-top: 8px;
    font-family: ui-monospace, "JetBrains Mono", monospace;
    font-size: 11px;
    color: var(--text);
    word-break: break-all;
  }}
  .card .badge {{
    margin-top: 3px;
    font-size: 10px;
    color: var(--accent);
    font-weight: 600;
  }}
  .card .anim-tag {{
    display: inline-block;
    margin-top: 3px;
    padding: 1px 6px;
    border-radius: 999px;
    background: rgba(255, 131, 0, 0.18);
    color: var(--accent);
    font-size: 9px;
    letter-spacing: 0.04em;
  }}
  footer {{
    margin-top: 32px;
    color: var(--dim);
    font-size: 12px;
    line-height: 1.6;
  }}
  footer code {{ color: var(--text); background: var(--panel); padding: 1px 6px; border-radius: 3px; }}
</style>
</head>
<body>
<header>
  <h1>Bibata · {variant} · {palette_label}</h1>
  <div class="meta">{n_total} cursors · {n_anim} animated · rendered at {render_size}px</div>
</header>
<div class="swatches" title="palette">
  <span style="background: {base};" title="base {base}"></span>
  <span style="background: {outline};" title="outline {outline}"></span>
  <span style="background: {watch_bg};" title="watch_bg {watch_bg}"></span>
</div>
<div id="grid" class="grid"></div>
<footer>
  Orange border = mapped to a standard Windows cursor type
  (e.g. <code>left_ptr</code> ↔ <code>Pointer.cur</code>).
  Plain cards exist only in X11/Linux themes. Hover to enlarge,
  click to copy the cursor name.
</footer>
<script>
const ENTRIES = {entries_json};
const WIN_MAP = {win_map_json};
const FRAME_DELAY_MS = 30;
const grid = document.getElementById("grid");

for (const e of ENTRIES) {{
  const div = document.createElement("div");
  div.className = "card" + (WIN_MAP[e.name] ? " win-mapped" : "");
  const winRole = WIN_MAP[e.name] ? `<div class="badge">→ ${{WIN_MAP[e.name]}}</div>` : "";
  const animTag = e.animated ? `<div class="anim-tag">${{e.frames}}f animated</div>` : "";
  const src = e.animated
    ? `png/${{e.name}}-01.png`
    : `png/${{e.name}}.png`;
  div.innerHTML = `
    <div class="img-wrap"><img data-name="${{e.name}}" ${{e.animated ? `data-frames="${{e.frames}}"` : ""}} src="${{src}}" alt="${{e.name}}"></div>
    <div class="name">${{e.name}}</div>
    ${{winRole}}
    ${{animTag}}
  `;
  div.title = e.name;
  div.onclick = () => {{
    navigator.clipboard?.writeText(e.name);
    div.style.borderColor = "var(--accent)";
    setTimeout(() => div.style.borderColor = "", 400);
  }};
  grid.appendChild(div);
}}

// Play animated cursors
document.querySelectorAll("img[data-frames]").forEach(img => {{
  const total = parseInt(img.dataset.frames);
  const name = img.dataset.name;
  let i = 1;
  setInterval(() => {{
    i = (i % total) + 1;
    img.src = `png/${{name}}-${{String(i).padStart(2, "0")}}.png`;
  }}, FRAME_DELAY_MS);
}});
</script>
</body>
</html>
"""


def generate_preview(
    variant: str,
    palette: Palette,
    palette_label: str,
    out_dir: Path,
    render_size: int = 96,
) -> Path:
    """Render cursors + HTML page. Returns path to index.html."""
    out_dir.mkdir(parents=True, exist_ok=True)
    png_dir = out_dir / "png"
    render_variant(variant, palette, png_dir, render_size=render_size)

    entries = _index_entries(variant)
    hand = "right" if variant.endswith("-right") else "normal"
    win_map = _windows_role_map(hand)

    html = _HTML.format(
        variant=variant,
        palette_label=palette_label,
        n_total=len(entries),
        n_anim=sum(1 for e in entries if e["animated"]),
        render_size=render_size,
        base=palette.base,
        outline=palette.outline,
        watch_bg=palette.watch_bg,
        accent=palette.base if palette.base.lower() not in ("#ffffff", "#000000") else "#ff8300",
        entries_json=json.dumps(entries),
        win_map_json=json.dumps(win_map),
    )
    index = out_dir / "index.html"
    index.write_text(html, encoding="utf-8")
    return index


def open_in_browser(path: Path) -> None:
    webbrowser.open(path.resolve().as_uri())
