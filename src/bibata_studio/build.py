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
import subprocess
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


# ---------------------------------------------------------------------------
# Windows-only: drive Setup API to install/uninstall a theme via its .inf
# ---------------------------------------------------------------------------


def _run_elevated_and_wait(exe: str, argline: str) -> int:
    """Spawn an elevated process via PowerShell `Start-Process -Verb RunAs -Wait`.

    Returns the child's exit code. Raises CalledProcessError if the PowerShell
    wrapper itself failed (e.g. user clicked No on UAC).
    """
    ps_script = (
        f"$p = Start-Process -FilePath '{exe}' "
        f"-ArgumentList {argline} "
        f"-Verb RunAs -Wait -PassThru; "
        f"if ($p) {{ exit $p.ExitCode }} else {{ exit 1 }}"
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script],
        check=True,
    )
    return completed.returncode


def install_inf_windows(inf_path: Path) -> None:
    """Trigger `[DefaultInstall]` of a Windows cursor INF, with UAC elevation.

    Equivalent to right-click → Show more options → Install in Explorer.
    Synchronous: returns only after the child rundll32 exits.
    """
    if sys.platform != "win32":
        raise OSError("install_inf_windows is only available on Windows")
    inf_path = inf_path.resolve()
    if not inf_path.is_file():
        raise FileNotFoundError(inf_path)
    # 132 = 128 (no UI on success) + 4 (allow reboot prompt if needed)
    args = ",".join(
        f'"{a}"' for a in ("setupapi.dll,InstallHinfSection", "DefaultInstall", "132", str(inf_path))
    )
    _run_elevated_and_wait("rundll32.exe", args)


def run_uninstall_bat(theme_dir: Path) -> None:
    """Invoke a theme's bundled `uninstall.bat` with admin privileges."""
    if sys.platform != "win32":
        raise OSError("run_uninstall_bat is only available on Windows")
    bat = (theme_dir / "uninstall.bat").resolve()
    if not bat.is_file():
        raise FileNotFoundError(bat)
    _run_elevated_and_wait("cmd.exe", f"'/c','{bat}'")


def refresh_windows_cursors() -> bool:
    """Ask Windows to re-read cursor settings from the registry.

    Sends SPI_SETCURSORS via SystemParametersInfoW. Only effective when called
    from the user's own interactive session — i.e. when the user runs
    `bibata install` themselves, not when the harness shells out from a
    different desktop session.
    """
    if sys.platform != "win32":
        return False
    import ctypes

    SPI_SETCURSORS = 0x0057
    SPIF_UPDATEINIFILE = 0x01
    SPIF_SENDCHANGE = 0x02
    user32 = ctypes.windll.user32
    user32.SystemParametersInfoW.argtypes = [
        ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint
    ]
    user32.SystemParametersInfoW.restype = ctypes.c_bool
    return bool(
        user32.SystemParametersInfoW(
            SPI_SETCURSORS, 0, None, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
        )
    )


def extract_zip(zip_path: Path, dst_dir: Path) -> Path:
    """Extract a theme zip; return the path to the inner theme folder."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dst_dir)
        roots = {Path(n).parts[0] for n in zf.namelist() if n}
    if len(roots) != 1:
        raise RuntimeError(f"unexpected zip layout (multiple roots): {roots}")
    return dst_dir / next(iter(roots))
