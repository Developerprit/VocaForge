"""Build dist/vf-cli.exe with Nuitka.

Run on a machine with a C compiler (MSVC or MinGW-w64). On the dev box this
reproduces the ctn.exe workflow: a single, Defender-friendly executable.

    python build_vf_cli.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    cmd = [
        sys.executable, "-m", "nuitka",
        "--onefile",
        "--include-package=vocaforge",
        "--output-filename=vf-cli.exe",
        "--output-dir=dist",
        "--assume-yes-for-downloads",
        str(ROOT / "vf_cli.py"),
    ]
    print("+ " + " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
