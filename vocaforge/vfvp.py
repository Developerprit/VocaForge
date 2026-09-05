"""VFVP voice-library package format.

A ``.vfvp`` file is a **standard 7z archive** (an ordinary ``.7z`` produced by 7-Zip /
py7zr) with a fixed internal layout:

    model/
        acoustic.pth      # DiffSinger acoustic model
        vocoder.pth       # vocoder
        config.json       # model structure config
    info.json             # voice-library meta info
    phoneme_map.json      # phoneme -> token mapping table

This module reads and writes that layout. ``py7zr`` is imported lazily so the
VocaForge **core stays dependency-free**; 7z support is only required when a real
``.vfvp`` is packed or loaded. If it is missing, a clear install hint is raised.

Public surface:
    * :class:`VfvpPackage`  -- high-level pack / extract / validate / info
    * :func:`pack_source` / :func:`extract_temp` / :func:`read_info` / :func:`validate`
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .core.exceptions import VocaForgeError

# Canonical member names inside a .vfvp archive.
INFO_FILE = "info.json"
PHONEME_MAP_FILE = "phoneme_map.json"
MODEL_DIR = "model"
REQUIRED_MODEL_FILES = ("acoustic.pth", "vocoder.pth", "config.json")

# Minimum set of members every valid .vfvp must contain.
EXPECTED_MEMBERS = {
    INFO_FILE,
    PHONEME_MAP_FILE,
    f"{MODEL_DIR}/acoustic.pth",
    f"{MODEL_DIR}/vocoder.pth",
    f"{MODEL_DIR}/config.json",
}


class VfvpError(VocaForgeError):
    """Raised for .vfvp pack / load / validation failures."""


def _require_py7zr():
    """Import ``py7zr`` on demand; raise a helpful hint if it is not installed."""
    try:
        import py7zr  # type: ignore
        return py7zr
    except ImportError as exc:  # pragma: no cover - depends on env
        raise VfvpError(
            "py7zr is required to read/write .vfvp packages.\n"
            "Install it with:\n"
            "    pip install py7zr\n"
            "(VocaForge core stays dependency-free; 7z support is loaded on demand.)"
        ) from exc


def _validate_source_layout(source_dir: str) -> List[str]:
    """Return a list of missing canonical members inside ``source_dir``."""
    missing: List[str] = []
    if not os.path.isfile(os.path.join(source_dir, INFO_FILE)):
        missing.append(INFO_FILE)
    if not os.path.isfile(os.path.join(source_dir, PHONEME_MAP_FILE)):
        missing.append(PHONEME_MAP_FILE)
    model_dir = os.path.join(source_dir, MODEL_DIR)
    if not os.path.isdir(model_dir):
        missing.append(f"{MODEL_DIR}/")
    else:
        for fn in REQUIRED_MODEL_FILES:
            if not os.path.isfile(os.path.join(model_dir, fn)):
                missing.append(f"{MODEL_DIR}/{fn}")
    return missing


def pack_source(source_dir: str, out_path: str, *, overwrite: bool = False) -> str:
    """Pack ``source_dir`` (with the canonical layout) into a ``.vfvp`` 7z archive.

    Returns ``out_path``. Raises :class:`VfvpError` if the layout is invalid or the
    output already exists (unless ``overwrite``).
    """
    py7zr = _require_py7zr()
    source_dir = os.path.abspath(source_dir)
    missing = _validate_source_layout(source_dir)
    if missing:
        raise VfvpError("cannot pack .vfvp: missing required members: " + ", ".join(missing))
    if os.path.exists(out_path) and not overwrite:
        raise VfvpError(f"output already exists: {out_path} (pass overwrite=True)")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    # Preserve the canonical flat layout: each top-level entry is written with its
    # own name as the archive prefix (model/ -> model/..., info.json -> info.json).
    with py7zr.SevenZipFile(out_path, "w") as z:
        for name in sorted(os.listdir(source_dir)):
            full = os.path.join(source_dir, name)
            z.writeall(full, arcname=name)
    return out_path


def extract_temp(archive_path: str) -> str:
    """Extract a ``.vfvp`` into a fresh temp dir; returns the dir path.

    Caller is responsible for cleanup (or use :meth:`VfvpPackage.open`)."""
    py7zr = _require_py7zr()
    tmp = tempfile.mkdtemp(prefix="vfvp_")
    with py7zr.SevenZipFile(archive_path, "r") as z:
        z.extractall(path=tmp)
    return tmp


def read_member(archive_path: str, name: str) -> Optional[bytes]:
    """Read a single member (by name) from the archive, without full extraction.

    py7zr has no in-memory ``read``; we extract just that member to a temp dir and
    read the file back. For a single small JSON file this is cheap and portable.
    """
    py7zr = _require_py7zr()
    tmp = tempfile.mkdtemp(prefix="vfvp_rd_")
    try:
        with py7zr.SevenZipFile(archive_path, "r") as z:
            z.extract(targets=[name], path=tmp)
        fp = os.path.join(tmp, name)
        if not os.path.exists(fp):
            return None
        with open(fp, "rb") as fh:
            return fh.read()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def read_info(archive_path: str) -> Dict[str, Any]:
    """Read and parse ``info.json`` from a ``.vfvp``."""
    raw = read_member(archive_path, INFO_FILE)
    if raw is None:
        raise VfvpError(f"{INFO_FILE} not found inside {archive_path}")
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise VfvpError(f"invalid {INFO_FILE} in {archive_path}: {exc}") from exc


def validate(archive_path: str) -> Dict[str, Any]:
    """Validate a ``.vfvp``'s structure. Returns a report dict."""
    py7zr = _require_py7zr()
    if not os.path.exists(archive_path):
        return {"valid": False, "missing": ["<file>"], "members": [], "exists": False}
    with py7zr.SevenZipFile(archive_path, "r") as z:
        names = set(z.getnames())
    missing = sorted(EXPECTED_MEMBERS - names)
    return {
        "valid": not missing,
        "exists": True,
        "missing": missing,
        "members": sorted(names),
    }


@dataclass
class VfvpPackage:
    """High-level handle for a ``.vfvp`` file on disk."""

    path: str
    info: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, source_dir: str, out_path: str, *, overwrite: bool = False) -> "VfvpPackage":
        pack_source(source_dir, out_path, overwrite=overwrite)
        return cls(path=out_path, info=read_info(out_path))

    @classmethod
    def open_info(cls, archive_path: str) -> Dict[str, Any]:
        return read_info(archive_path)

    def extract(self) -> str:
        """Extract to a temp dir and return its path (clean up yourself)."""
        return extract_temp(self.path)

    def report(self) -> Dict[str, Any]:
        return validate(self.path)

    def asset_paths(self, root: str) -> Dict[str, str]:
        """Given an extracted ``root``, return the canonical asset file paths."""
        return {
            "root": root,
            "acoustic": os.path.join(root, MODEL_DIR, "acoustic.pth"),
            "vocoder": os.path.join(root, MODEL_DIR, "vocoder.pth"),
            "config": os.path.join(root, MODEL_DIR, "config.json"),
            "phoneme_map": os.path.join(root, PHONEME_MAP_FILE),
            "info": os.path.join(root, INFO_FILE),
        }
