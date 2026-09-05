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
import shutil
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

    def supports(self, spec: ModelSpec) -> bool:
        """Whether this loader can handle ``spec``.

        The engine routes a spec to the first loader whose ``supports`` returns True.
        Default loaders return ``True``; override to narrow (e.g. only ``.vfvp`` paths).
        """
        return True


class LocalModelLoader(ModelLoader):
    """Default loader: verifies ``spec.path`` exists on disk and exposes it."""

    name = "local"

    def supports(self, spec: ModelSpec) -> bool:
        # Defer .vfvp packages to VfvpModelLoader.
        return not (spec.path and spec.path.lower().endswith(".vfvp"))

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


class VfvpModelLoader(ModelLoader):
    """Loader for ``.vfvp`` voice-library packages (standard 7z archives).

    When a :class:`~vocaforge.models.manifest.ModelSpec` points at a ``.vfvp`` file,
    this loader extracts it to a temp dir and exposes the canonical assets
    (``model/acoustic.pth``, ``model/vocoder.pth``, ``model/config.json``,
    ``info.json``, ``phoneme_map.json``) on the :class:`ModelArtifact`.
    """

    name = "vfvp"

    def supports(self, spec: ModelSpec) -> bool:
        return bool(spec.path) and spec.path.lower().endswith(".vfvp")

    def load(self, spec: ModelSpec) -> ModelArtifact:
        from ..core.exceptions import VFModelLoadError
        from ..vfvp import VfvpError, INFO_FILE, MODEL_DIR, PHONEME_MAP_FILE, extract_temp, read_info

        if not self.supports(spec):
            raise VFModelLoadError(
                f"VfvpModelLoader only handles .vfvp paths, got {spec.path!r}"
            )
        if not os.path.exists(spec.path):
            raise VFModelLoadError(f"vfvp not found: {spec.path}")
        try:
            root = extract_temp(spec.path)
        except VfvpError as exc:  # surface 7z / py7zr issues as a load error
            raise VFModelLoadError(str(exc)) from exc

        assets = {
            "root": root,
            "acoustic": os.path.join(root, MODEL_DIR, "acoustic.pth"),
            "vocoder": os.path.join(root, MODEL_DIR, "vocoder.pth"),
            "config": os.path.join(root, MODEL_DIR, "config.json"),
            "phoneme_map": os.path.join(root, PHONEME_MAP_FILE),
            "info": os.path.join(root, INFO_FILE),
        }
        meta: Dict[str, Any] = {}
        try:
            meta = read_info(spec.path)
        except VfvpError:
            pass
        return ModelArtifact(spec=spec, assets=assets, meta=meta)

    def release(self, artifact: ModelArtifact) -> None:
        root = artifact.assets.get("root")
        if root and os.path.isdir(root):
            shutil.rmtree(root, ignore_errors=True)
