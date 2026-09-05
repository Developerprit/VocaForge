"""Framework-wide constants for VocaForge."""
from __future__ import annotations

import os

VERSION = "0.1.0"

# Default RPC bind for `vf-cli serve`
DEFAULT_RPC_HOST = "127.0.0.1"
DEFAULT_RPC_PORT = 8765

# Manifest file name looked up (in priority order):
#   1. $VF_MODEL_MANIFEST  (env override)
#   2. <cwd>/models/manifest.json
#   3. <package>/../models/manifest.json
DEFAULT_MANIFEST_FILENAME = "manifest.json"


def default_manifest_path() -> str:
    env = os.environ.get("VF_MODEL_MANIFEST")
    if env:
        return env
    cwd_manifest = os.path.join(os.getcwd(), "models", DEFAULT_MANIFEST_FILENAME)
    if os.path.exists(cwd_manifest):
        return cwd_manifest
    pkg_models = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "models",
        DEFAULT_MANIFEST_FILENAME,
    )
    return pkg_models
