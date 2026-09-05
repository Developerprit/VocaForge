"""Model loader extension point (Architecture API, v1).

A :class:`ModelLoader` resolves a :class:`~vocaforge.models.manifest.ModelSpec`
into a ready-to-load :class:`ModelArtifact` -- verifying local paths, fetching
remote weights, decrypting packs, etc. Third-party projects implement their own
loader and register it on the engine to plug custom model storage into VocaForge
*without* touching inference code.

This is the second public extension point of the VocaForge Architecture API
(the first being :class:`~vocaforge.core.backend.Backend`).
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict

from ..models.manifest import ModelSpec


@dataclass
class ModelArtifact:
    """A spec plus the resolved, loadable assets produced by a ModelLoader.

    ``Backend.load_model`` receives this object, reads ``spec`` for metadata and
    ``assets`` for the concrete model files/URIs to load.
    """

    spec: ModelSpec
    assets: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.spec.id


class ModelLoader(ABC):
    """Abstract model loader. ``name`` is a stable identifier for the API."""

    #: Stable loader id, e.g. ``"local"`` or ``"hf"``.
    name: str = "base"

    @abstractmethod
    def load(self, spec: ModelSpec) -> ModelArtifact:
        """Resolve ``spec`` into a :class:`ModelArtifact`.

        Raise :class:`~vocaforge.core.exceptions.VFModelLoadError` if the model
        cannot be located / prepared.
        """

    @abstractmethod
    def release(self, artifact: ModelArtifact) -> None:
        """Release resources (temp files, network handles) held by ``artifact``."""


class LocalModelLoader(ModelLoader):
    """Default loader: verifies ``spec.path`` exists on disk and exposes it."""

    name = "local"

    def load(self, spec: ModelSpec) -> ModelArtifact:
        from ..core.exceptions import VFModelLoadError

        # An empty path is allowed (e.g. the stub backend needs no weights); only
        # a non-empty path that does not exist on disk is an error.
        if spec.path and not os.path.exists(spec.path):
            raise VFModelLoadError(f"model path not found: {spec.path}")
        assets = {"root": spec.path} if spec.path else {}
        return ModelArtifact(spec=spec, assets=assets)

    def release(self, artifact: ModelArtifact) -> None:  # local files need no release
        return None
