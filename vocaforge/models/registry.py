"""Local model registry backed by a JSON manifest."""
from __future__ import annotations

import json
import os
from typing import Dict, List

from ..core.exceptions import VFModelNotFound
from ..config import default_manifest_path
from .manifest import ModelSpec


class ModelRegistry:
    """Maps model id/name -> ModelSpec, persisted as JSON."""

    def __init__(self, manifest_path: str | None = None):
        self.manifest_path = manifest_path or default_manifest_path()
        self._specs: Dict[str, ModelSpec] = {}
        self._load()

    # ---- loading / persistence ----
    def _load(self) -> None:
        self._specs.clear()
        if not os.path.exists(self.manifest_path):
            return
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as fh:
                data = json.load(fh) or {}
        except (ValueError, OSError):
            # Empty or corrupt manifest -> start with no models.
            return
        for entry in data.get("models", []):
            spec = ModelSpec.from_dict(entry)
            self._specs[spec.id] = spec

    def save(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.manifest_path)), exist_ok=True)
        payload = {"models": [s.to_dict() for s in self._specs.values()]}
        with open(self.manifest_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

    # ---- query ----
    def has(self, key: str) -> bool:
        if key in self._specs:
            return True
        return any(s.name == key for s in self._specs.values())

    def get(self, key: str) -> ModelSpec:
        if key in self._specs:
            return self._specs[key]
        for spec in self._specs.values():
            if spec.name == key:
                return spec
        raise VFModelNotFound(f"model not found: {key!r}")

    def list(self) -> List[ModelSpec]:
        return list(self._specs.values())

    # ---- mutation ----
    def add(self, spec: ModelSpec) -> None:
        self._specs[spec.id] = spec
        self.save()

    def remove(self, key: str) -> None:
        if key in self._specs:
            del self._specs[key]
        else:
            for sid, spec in list(self._specs.items()):
                if spec.name == key:
                    del self._specs[sid]
                    break
        self.save()
