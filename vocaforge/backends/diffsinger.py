"""DiffSinger backend adapter (integration point for real inference).

This adapter lazily imports the ``diffsinger`` package. On machines without it
installed it raises :class:`VFMissingBackendError` with install guidance, instead
of crashing at import time. Wire real acoustic/vocoder inference here.
"""
from __future__ import annotations

from typing import Any

from ..core.backend import Backend
from ..core.exceptions import VFMissingBackendError, VFSynthesisError
from ..models.manifest import ModelSpec


class DiffSingerAdapter(Backend):
    name = "diffsinger"

    def _require_diffsinger(self):
        try:
            import diffsinger  # noqa: F401
        except ImportError as exc:  # pragma: no cover - depends on env
            raise VFMissingBackendError(
                "diffsinger is not installed. Install it with: pip install diffsinger\n"
                "Then register a model in models/manifest.json pointing at your "
                "acoustic + vocoder checkpoints."
            ) from exc
        return __import__("diffsinger")

    def load_model(self, spec: ModelSpec) -> Any:
        ds = self._require_diffsinger()
        if not ds:  # pragma: no cover
            raise VFMissingBackendError("diffsinger import returned empty")
        # --- integration point -------------------------------------------------
        # Real loading would build a diffsinger fs2/acoustic + vocoder pipeline from
        # spec.path / spec.extra. We validate the spec and return a lightweight
        # handle; heavy GPU work happens lazily inside synthesize().
        return {"spec": spec, "backend": self.name}

    def synthesize(self, project: Any, handle: Any) -> bytes:
        # Real inference: diffsinger(fs2/ds) -> vocoder -> waveform.
        # Not executed in this delivery (requires models + GPU). The stub backend
        # provides an end-to-end runnable path for testing/CI.
        raise VFSynthesisError(
            "DiffSingerAdapter.synthesize requires acoustic/vocoder models and a GPU. "
            "Install diffsinger + models, then implement inference here. For a runnable "
            "test path without models, use StubBackend (backend='stub')."
        )

    def unload(self, handle: Any) -> None:
        # Release GPU tensors / pipelines here.
        if isinstance(handle, dict):
            handle.clear()
