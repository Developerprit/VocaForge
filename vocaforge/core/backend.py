"""Pluggable backend interface.

A :class:`Backend` turns a :class:`~vocaforge.models.manifest.ModelSpec` into a
loadable handle and renders a :class:`~vocaforge.synth.project.SynthProject` to
raw WAV bytes. ``DiffSingerAdapter`` and ``StubBackend`` both implement this.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models.manifest import ModelSpec
from .model_loader import ModelArtifact


class Backend(ABC):
    """Abstract synthesis backend (Architecture API extension point #1).

    Implement this to plug a custom synthesis engine into VocaForge. Third-party
    projects subclass ``Backend``, then register it via
    :meth:`~vocaforge.core.engine.VocaForgeEngine.register_backend`.
    """

    #: Human-readable backend name, e.g. "diffsinger" or "stub".
    name: str = "base"

    #: Architecture API contract version this backend targets. Bump when the
    #: load_model / synthesize / unload signature changes.
    api_version: str = "1.0"

    @abstractmethod
    def load_model(self, artifact: ModelArtifact) -> Any:
        """Load ``artifact`` (a :class:`ModelArtifact`) and return an opaque handle.

        Read ``artifact.spec`` for metadata and ``artifact.assets`` for the concrete
        model files/URIs. Raise
        :class:`~vocaforge.core.exceptions.VFModelLoadError` on failure.
        """

    @abstractmethod
    def synthesize(self, project: "SynthProject", handle: Any) -> bytes:
        """Render ``project`` to 16-bit PCM WAV bytes using ``handle``."""

    @abstractmethod
    def unload(self, handle: Any) -> None:
        """Release resources held by ``handle``."""
