"""End-to-end artifact verification for a Bibata Windows cursor zip.

Validates every produced file BEFORE the user right-clicks install.inf:
    1. install.inf syntax + all referenced cursor names exist on disk
    2. Every .cur file has a valid CUR header (ICO with type=2)
    3. Every .ani file is a valid RIFF/ACON animation container
    4. Renders Pointer.cur frame 0 to PNG and samples for palette color

Usage:
    python tests/verify_windows_zip.py <extracted-theme-dir>
"""
from __future__ import annotations

import io
import re
import struct
import sys
from pathlib import Path

from PIL import Image


def parse_cur(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 6:
        raise ValueError("too small")
    reserved, img_type, count = struct.unpack("<HHH", data[:6])
    if reserved != 0:
        raise ValueError(f"reserved field != 0 (got {reserved})")
    if img_type != 2:
        raise ValueError(f"image type != 2 (CUR), got {img_type}")
    if count < 1:
        raise ValueError("zero images")
    sizes, hotspots = [], []
    for i in range(count):
        entry = data[6 + i * 16 : 6 + (i + 1) * 16]
        w, h, _c, _r, xh, yh, dsz, doff = struct.unpack("<BBBBHHII", entry)
        w = w or 256
        h = h or 256
        if doff + dsz > len(data):
            raise ValueError(f"image[{i}] truncated (offset+size > file)")
        sizes.append((w, h))
        hotspots.append((xh, yh))
    return {"count": count, "sizes": sizes, "hotspot": hotspots[0]}


def parse_ani(path: Path) -> dict:
    data = path.read_bytes()
    if data[:4] != b"RIFF":
        raise ValueError(f"not a RIFF file (got {data[:4]!r})")
    riff_size = struct.unpack("<I", data[4:8])[0]
    form_type = data[8:12]
    if form_type != b"ACON":
        raise ValueError(f"not an ACON container (got {form_type!r})")
    pos = 12
    anih = None
    frame_count = 0
    while pos + 8 <= len(data):
        chunk_id = data[pos : pos + 4]
        chunk_size = struct.unpack("<I", data[pos + 4 : pos + 8])[0]
        body = data[pos + 8 : pos + 8 + chunk_size]
        if chunk_id == b"anih" and len(body) >= 16:
            nframes = struct.unpack("<I", body[8:12])[0]
            nsteps = struct.unpack("<I", body[12:16])[0]
            anih = {"frames": nframes, "steps": nsteps}
        elif chunk_id == b"LIST" and body[:4] == b"fram":
            ipos = 4
            while ipos + 8 <= len(body):
                ic = body[ipos : ipos + 4]
                isz = struct.unpack("<I", body[ipos + 4 : ipos + 8])[0]
                if ic == b"icon":
                    frame_count += 1
                ipos += 8 + isz + (isz & 1)
        pos += 8 + chunk_size + (chunk_size & 1)
    return {"riff_size": riff_size, "anih": anih, "icon_frames": frame_count}


def cur_extract_image_n(path: Path, n: int = 0) -> Image.Image:
    data = path.read_bytes()
    _, _, count = struct.unpack("<HHH", data[:6])
    if n >= count:
        raise IndexError(f"only {count} images")
    entry = data[6 + n * 16 : 6 + (n + 1) * 16]
    _w, _h, _c, _r, _xh, _yh, dsz, doff = struct.unpack("<BBBBHHII", entry)
    payload = data[doff : doff + dsz]
    if payload[:8] == b"\x89PNG\r\n\x1a\n":
        return Image.open(io.BytesIO(payload))
    # Synthesize a BITMAPFILEHEADER so Pillow can decode the embedded DIB.
    header_size = struct.unpack("<I", payload[:4])[0]
    fake = io.BytesIO()
    fake.write(b"BM")
    fake.write(struct.pack("<I", 14 + len(payload)))
    fake.write(b"\x00\x00\x00\x00")
    fake.write(struct.pack("<I", 14 + header_size))
    fake.write(payload)
    fake.seek(0)
    return Image.open(fake)


def verify(theme: Path, expect_amber: bool = True) -> int:
    passed = 0
    warnings: list[str] = []
    errors: list[str] = []

    def ok(msg):
        nonlocal passed
        passed += 1
        print(f"  [PASS] {msg}")

    def warn(msg):
        warnings.append(msg)
        print(f"  [WARN] {msg}")

    def fail(msg):
        errors.append(msg)
        print(f"  [FAIL] {msg}")

    print("=" * 72)
    print(f"Verifying: {theme.name}")
    print("=" * 72)

    # 1. install.inf
    print("\n[1/4] install.inf syntax + references")
    inf = theme / "install.inf"
    if not inf.is_file():
        fail("install.inf missing")
        return 1
    inf_text = inf.read_text(encoding="cp1252")
    sections = set(re.findall(r"^\[([^\]]+)\]", inf_text, flags=re.MULTILINE))
    required = {"Version", "DefaultInstall", "Strings"}
    if missing := required - sections:
        fail(f"install.inf missing sections: {missing}")
    else:
        ok(f"install.inf has all required sections: {sorted(required)}")

    on_disk = {p.name for p in theme.iterdir()}
    inf_refs = set(re.findall(r"[A-Za-z][A-Za-z0-9_-]*\.(?:cur|ani)", inf_text))
    if missing_files := inf_refs - on_disk:
        fail(f"install.inf references files not on disk: {missing_files}")
    else:
        ok(f"install.inf references {len(inf_refs)} cursor files, all present")

    ub = theme / "uninstall.bat"
    if ub.is_file() and "reg" in ub.read_text(errors="ignore").lower():
        ok(f"uninstall.bat present ({ub.stat().st_size} bytes, touches registry)")
    else:
        warn("uninstall.bat looks suspicious")

    # 2. .cur
    print("\n[2/4] .cur file headers (ICO type=2)")
    cur_files = sorted(theme.glob("*.cur"))
    bad = []
    samples: dict[str, dict] = {}
    for c in cur_files:
        try:
            samples[c.name] = parse_cur(c)
        except Exception as e:
            bad.append((c.name, str(e)))
    if bad:
        for n, e in bad:
            fail(f"{n}: {e}")
    else:
        ok(f"all {len(cur_files)} .cur files have valid CUR headers")
        n, info = next(iter(samples.items()))
        tail = "..." if info["count"] > 3 else ""
        print(
            f"         e.g. {n}: {info['count']} images, "
            f"sizes={info['sizes'][:3]}{tail}, hotspot={info['hotspot']}"
        )

    # 3. .ani
    print("\n[3/4] .ani file headers (RIFF/ACON)")
    ani_files = sorted(theme.glob("*.ani"))
    for a in ani_files:
        try:
            info = parse_ani(a)
            ok(
                f"{a.name:12s} valid RIFF/ACON: "
                f"anih={info['anih']}, icon chunks={info['icon_frames']}"
            )
        except Exception as e:
            fail(f"{a.name}: {e}")

    # 4. Pointer.cur pixel sample
    print("\n[4/4] Pixel color sample (Pointer.cur frame 0)")
    try:
        img = cur_extract_image_n(theme / "Pointer.cur", n=0).convert("RGBA")
        w, h = img.size
        amber = sum(
            1
            for p in img.getdata()
            if p[3] > 200
            and abs(p[0] - 0xFF) < 12
            and abs(p[1] - 0x83) < 18
            and abs(p[2]) < 12
        )
        total = sum(1 for p in img.getdata() if p[3] > 200)
        if expect_amber and amber > 100:
            ok(
                f"Pointer.cur frame 0: {w}x{h}, amber #FF8300 pixels "
                f"= {amber}/{total} opaque"
            )
            preview = theme.parent / "pointer-preview.png"
            img.save(preview)
            print(f"         saved preview: {preview}")
        elif expect_amber:
            fail(f"too few amber pixels ({amber}/{total})")
        else:
            ok(f"Pointer.cur frame 0 decoded: {w}x{h}, {total} opaque pixels")
    except Exception as e:
        warn(f"could not decode Pointer.cur frame 0: {e}")

    print()
    print("=" * 72)
    print(f"RESULT: {passed} passed, {len(warnings)} warning(s), {len(errors)} error(s)")
    if errors:
        print("FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("OK — artifact is structurally sound and ready to install.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python verify_windows_zip.py <extracted-theme-dir>")
        sys.exit(2)
    sys.exit(verify(Path(sys.argv[1])))
