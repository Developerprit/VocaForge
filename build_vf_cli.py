"""Build dist/vf-cli.exe with Nuitka.

Run on a machine with a C compiler (MSVC or MinGW-w64). On the dev box this
reproduces the ctn.exe workflow: a single, Defender-friendly executable.

    python build_vf_cli.py

The windowless ``vf-cli.exe`` is branded with ``VF_icon.png`` at the project
root: we embed that PNG into a standard ``.ico`` container (``VF_icon.ico``)
without any third-party deps, and pass it to Nuitka as the executable icon.
If the icon files change, re-running will regenerate ``VF_icon.ico``.
"""
from __future__ import annotations

import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PNG_PATH = ROOT / "VF_icon.png"
ICO_PATH = ROOT / "VF_icon.ico"


def _resize_png(png: bytes, max_dim: int = 256) -> bytes | None:
    """Resize a PNG to fit within ``max_dim`` using Pillow if available.

    Returns the resized PNG bytes, or ``None`` if Pillow is not installed
    or the image could not be processed.
    """
    try:
        from PIL import Image  # type: ignore
        import io
    except ImportError:
        return None
    img = Image.open(io.BytesIO(png))
    if max(img.size) <= max_dim:
        return png
    img.thumbnail((max_dim, max_dim))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _ensure_ico() -> str | None:
    """Generate ``VF_icon.ico`` from ``VF_icon.png`` (PNG embedded in ICO), if needed.

    Modern Windows ICO supports PNG-encoded image data, so we just wrap the PNG
    bytes inside an ICONDIR + ICONDIRENTRY container -- no Pillow / PIL needed.
    Returns the icon path or ``None`` if no usable PNG is present.
    """
    if not PNG_PATH.exists():
        print("warning: VF_icon.png not found; exe will use the default icon")
        return None
    png = PNG_PATH.read_bytes()
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        print("warning: VF_icon.png is not a PNG; skipped icon generation")
        return None
    if ICO_PATH.exists() and ICO_PATH.stat().st_mtime >= PNG_PATH.stat().st_mtime:
        return str(ICO_PATH)
    # PNG IHDR: width/height are big-endian uint32 at offsets 16 and 20.
    w, h = struct.unpack(">II", png[16:24])
    if w > 256 or h > 256:
        resized = _resize_png(png)
        if resized is None:
            print(
                f"warning: VF_icon.png is {w}x{h} (>256); ICO entries max at 256.\n"
                "         install Pillow (pip install pillow) so the build can auto-shrink it,\n"
                "         or resize VF_icon.png to <=256 pixels yourself."
            )
            return None
        png = resized
        w, h = struct.unpack(">II", png[16:24])
    # ICONDIR: reserved=0, type=1 (icon), count=1.
    icondir = struct.pack("<HHH", 0, 1, 1)
    # ICONDIRENTRY: w/h=0 means 256; colorCount=0 (no palette), planes=1, bpp=32.
    entry = struct.pack(
        "<BBBBHHII",
        0 if w == 256 else w,
        0 if h == 256 else h,
        0, 0, 1, 32,
        len(png),
        6 + 16,  # offset of image data (after ICONDIR + one ICONDIRENTRY)
    )
    ICO_PATH.write_bytes(icondir + entry + png)
    print(f"generated {ICO_PATH.name} from {PNG_PATH.name}  ({w}x{h}, png embedded)")
    return str(ICO_PATH)


def main() -> int:
    cmd = [
        sys.executable, "-m", "nuitka",
        "--onefile",
        "--include-package=vocaforge",
        "--output-filename=vf-cli.exe",
        "--output-dir=dist",
        "--assume-yes-for-downloads",
    ]
    icon = _ensure_ico()
    if icon:
        cmd.append(f"--windows-icon-from-ico={icon}")
    cmd.append(str(ROOT / "vf_cli.py"))
    print("+ " + " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
