"""Top-level orchestrator: registry + model loader + backend + project -> audio.

This is the public entry point of the VocaForge Architecture API. Third-party
projects build an engine, register their own :class:`Backend` / :class:`ModelLoader`,
and call :meth:`synthesize`.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from ..backends.stub import StubBackend
from ..core.backend import Backend
from ..core.exceptions import VFModelNotFound, VFSynthesisError
from ..core.model_loader import (
    LocalModelLoader,
    ModelArtifact,
    ModelLoader,
    VfvpModelLoader,
)
from ..models.manifest import ModelSpec
from ..models.registry import ModelRegistry
from ..synth.project import SynthProject


class VocaForgeEngine:
    def __init__(
        self,
        registry: Optional[ModelRegistry] = None,
        backend: Optional[Backend] = None,
        model_loader: Optional[ModelLoader] = None,
        discover_dir: Optional[str] = None,
    ):
        self.registry = registry or ModelRegistry()
        self.backend = backend or StubBackend()
        # Ordered chain of model loaders. The engine routes a spec to the first
        # loader whose ``supports(spec)`` returns True. `.vfvp` packages are handled
        # by VfvpModelLoader out of the box; other paths fall through to LocalModelLoader.
        self._loaders: List[ModelLoader] = [model_loader or LocalModelLoader(), VfvpModelLoader()]
        # Registry of pluggable, named backends (active integration, no auto-discovery).
        self._backends: Dict[str, Backend] = {}
        if discover_dir is not None:
            self.discover(discover_dir)

    # ---- Architecture API: active registration -----------------------------
    def register_backend(self, backend: Backend) -> None:
        """Register a third-party :class:`Backend` under ``backend.name``."""
        self._backends[backend.name] = backend

    def register_model_loader(self, loader: ModelLoader) -> None:
        """Append a custom :class:`ModelLoader` (e.g. remote / encrypted storage).

        Custom loaders are tried after the built-in chain, so override routing by
        implementing ``supports()``.
        """
        self._loaders.append(loader)

    def list_loaders(self) -> List[str]:
        return [l.name for l in self._loaders]

    def list_backends(self) -> List[str]:
        names = [self.backend.name] + list(self._backends.keys())
        return sorted(set(names))

    # ---- query --------------------------------------------------------------
    def resolve(self, key: str) -> ModelSpec:
        return self.registry.get(key)

    def exists(self, key: str) -> bool:
        return self.registry.has(key)

    def add_model(self, spec: ModelSpec) -> None:
        """Register a voice library (active integration from a host project)."""
        self.registry.add(spec)

    def list_models(self) -> List[ModelSpec]:
        return self.registry.list()

    def discover(self, search_dir: Optional[str] = None) -> List[ModelSpec]:
        """Scan a directory for ``*.vfvp`` packages and register any not yet known.

        Defaults to the directory holding the manifest. Returns the newly discovered specs.
        """
        d = search_dir or os.path.dirname(os.path.abspath(self.registry.manifest_path))
        return self.registry.discover_vfvp(d)

    # ---- model loader routing ----------------------------------------------
    def _loader_for(self, spec: ModelSpec) -> ModelLoader:
        for loader in self._loaders:
            try:
                if loader.supports(spec):
                    return loader
            except Exception:  # noqa: BLE001 - a broken supports() must not break synth
                continue
        return self._loaders[0]

    # ---- synthesis pipeline -------------------------------------------------
    def synthesize(self, model_key: str, project: SynthProject) -> bytes:
        spec = self.resolve(model_key)  # raises VFModelNotFound if absent
        loader = self._loader_for(spec)
        artifact = loader.load(spec)
        try:
            backend = self._backend_for(spec)
            handle = backend.load_model(artifact)
            try:
                return backend.synthesize(project, handle)
            except Exception as exc:  # noqa: BLE001
                raise VFSynthesisError(
                    f"synthesis failed for {model_key!r}: {exc}"
                ) from exc
            finally:
                backend.unload(handle)
        finally:
            loader.release(artifact)

    def _backend_for(self, spec: ModelSpec) -> Backend:
        want = (spec.backend or "auto").lower()
        if want in ("auto", ""):
            return self.backend
        if want == "stub":
            return StubBackend()
        if want == "diffsinger":
            from ..backends.diffsinger import DiffSingerAdapter
            return DiffSingerAdapter()
        # Allow registered custom backends to be selected by name.
        if want in self._backends:
            return self._backends[want]
        return self.backend
