"""DiffSinger backend adapter (integration point for real inference).

This adapter lazily imports the ``diffsinger`` package. On machines without it
installed it raises :class:`VFMissingBackendError` with install guidance, instead
of crashing at import time. Wire real acoustic/vocoder inference here.
"""
from __future__ import annotations

import os
from typing import Any

from ..core.backend import Backend
from ..core.exceptions import VFMissingBackendError, VFSynthesisError
from ..core.model_loader import ModelArtifact
from ..models.manifest import ModelSpec


class DiffSingerAdapter(Backend):
    name = "diffsinger"

    def _require_diffsinger(self):
        try:
            import diffsinger  # noqa: F401
        except ImportError as exc:  # pragma: no cover - depends on env
            raise VFMissingBackendError(
                "diffsinger is not installed. Install it with: pip install diffsinger\n"
                "Then register a model in models/manifest.json (or a .vfvp package) "
                "pointing at your acoustic + vocoder checkpoints."
            ) from exc
        return __import__("diffsinger")

    def load_model(self, artifact: ModelArtifact) -> Any:
        ds = self._require_diffsinger()
        if not ds:  # pragma: no cover
            raise VFMissingBackendError("diffsinger import returned empty")
        spec = artifact.spec if isinstance(artifact, ModelArtifact) else artifact

        # --- integration point -------------------------------------------------
        # Consume the resolved assets produced by the active ModelLoader. For a .vfvp
        # package these are the extracted canonical files; for a raw path layout they are
        # whatever LocalModelLoader exposed. We surface them on the handle so real
        # inference has everything it needs (paths to acoustic/vocoder/config/phoneme_map).
        assets = getattr(artifact, "assets", {}) or {}
        handle = {
            "spec": spec,
            "backend": self.name,
            "acoustic": assets.get("acoustic"),
            "vocoder": assets.get("vocoder"),
            "config": assets.get("config"),
            "phoneme_map": assets.get("phoneme_map"),
            "info": assets.get("info"),
        }

        # When this is a real .vfvp / DiffSinger spec, validate the model files exist so
        # failures are reported at load time rather than deep inside inference.
        if str(getattr(spec, "backend", "auto")).lower() == "diffsinger":
            missing = [
                k for k in ("acoustic", "vocoder", "config")
                if not (handle[k] and os.path.exists(handle[k]))
            ]
            if missing:
                raise VFMissingBackendError(
                    f"vfvp is missing required model files: {missing}. "
                    f"Check that model/acoustic.pth, model/vocoder.pth and model/config.json "
                    f"are present in the package."
                )
        return handle

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
