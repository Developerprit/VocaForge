"""Top-level orchestrator: registry + backend + project -> audio."""
from __future__ import annotations

from typing import Any, List, Optional

from ..backends.stub import StubBackend
from ..core.backend import Backend
from ..core.exceptions import VFModelNotFound, VFSynthesisError
from ..models.manifest import ModelSpec
from ..models.registry import ModelRegistry
from ..synth.project import SynthProject


class VocaForgeEngine:
    def __init__(
        self,
        registry: Optional[ModelRegistry] = None,
        backend: Optional[Backend] = None,
    ):
        self.registry = registry or ModelRegistry()
        self.backend = backend or StubBackend()

    # Agent-facing lookup. Returns ModelSpec or raises VFModelNotFound (-> 404).
    def resolve(self, key: str) -> ModelSpec:
        return self.registry.get(key)

    def exists(self, key: str) -> bool:
        return self.registry.has(key)

    def synthesize(self, model_key: str, project: SynthProject) -> bytes:
        spec = self.resolve(model_key)  # raises VFModelNotFound if absent
        backend = self._backend_for(spec)
        handle = backend.load_model(spec)
        try:
            return backend.synthesize(project, handle)
        except Exception as exc:  # noqa: BLE001
            raise VFSynthesisError(f"synthesis failed for {model_key!r}: {exc}") from exc
        finally:
            backend.unload(handle)

    def _backend_for(self, spec: ModelSpec) -> Backend:
        want = (spec.backend or "auto").lower()
        if want in ("auto", ""):
            return self.backend
        if want == "stub":
            return StubBackend()
        if want == "diffsinger":
            from ..backends.diffsinger import DiffSingerAdapter
            return DiffSingerAdapter()
        return self.backend

    def list_models(self) -> List[ModelSpec]:
        return self.registry.list()
