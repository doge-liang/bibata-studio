"""PNG bitmaps → packaged cursor theme via clickgen's ctgen API.

We don't shell out to `ctgen.exe` (which isn't on PATH after `pip install --user`
on Windows). Instead we invoke `clickgen.scripts.ctgen.main` in-process by
patching `sys.argv` — same code path, no PATH dance.

The vendored TOML configs from `Bibata_Cursor/configs/{normal,right}/` carry
all the hotspot and symlink metadata; we just point `-d` at our freshly
rendered bitmaps directory and let clickgen do the packing.
"""

from __future__ import annotations

import shutil
import sys
import zipfile
from contextlib import contextmanager
from pathlib import Path

from clickgen.scripts.ctgen import main as _ctgen_main

from .render import _package_data_root


def _config_path(hand: str, toml_basename: str) -> Path:
    p = _package_data_root() / "configs" / hand / toml_basename
    if not p.is_file():
        raise FileNotFoundError(f"missing vendored ctgen config: {p}")
    return p


@contextmanager
def _argv(argv: list[str]):
    """Run a block with sys.argv temporarily replaced."""
    saved = sys.argv
    sys.argv = argv
    try:
        yield
    finally:
        sys.argv = saved


def run_ctgen(
    *,
    config: Path,
    bitmaps_dir: Path,
    out_dir: Path,
    name: str,
    comment: str,
    website: str = "https://github.com/ful1e5/bibata",
    platforms: str | None = None,
) -> None:
    """Drive clickgen.ctgen.main() in-process with the given parameters."""
    argv = [
        "ctgen",
        str(config),
        "-d", str(bitmaps_dir),
        "-o", str(out_dir),
        "-n", name,
        "-c", comment,
        "-w", website,
    ]
    if platforms:
        argv += ["-p", platforms]
    with _argv(argv):
        _ctgen_main()


def zip_dir(src: Path, dst_zip: Path) -> Path:
    """Zip the contents of `src` (recursively) into `dst_zip`. Returns dst_zip."""
    dst_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dst_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in src.rglob("*"):
            zf.write(p, p.relative_to(src.parent))
    return dst_zip


def cleanup_intermediates(*paths: Path) -> None:
    for p in paths:
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
