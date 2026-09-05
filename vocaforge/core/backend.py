"""Pluggable backend interface.

A :class:`Backend` turns a :class:`~vocaforge.models.manifest.ModelSpec` into a
loadable handle and renders a :class:`~vocaforge.synth.project.SynthProject` to
raw WAV bytes. ``DiffSingerAdapter`` and ``StubBackend`` both implement this.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models.manifest import ModelSpec


class Backend(ABC):
    """Abstract synthesis backend."""

    #: Human-readable backend name, e.g. "diffsinger" or "stub".
    name: str = "base"

    @abstractmethod
    def load_model(self, spec: ModelSpec) -> Any:
        """Load ``spec`` and return an opaque handle (or raise VFModelLoadError)."""

    @abstractmethod
    def synthesize(self, project: "SynthProject", handle: Any) -> bytes:
        """Render ``project`` to 16-bit PCM WAV bytes using ``handle``."""

    @abstractmethod
    def unload(self, handle: Any) -> None:
        """Release resources held by ``handle``."""
