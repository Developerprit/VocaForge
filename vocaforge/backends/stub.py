"""Stub backend: renders a project to audible WAV without any ML models.

Used for framework self-checks, CI, and as a safe default when DiffSinger is not
installed. Produces 16-bit PCM WAV whose pitch follows the project's notes.
"""
from __future__ import annotations

import math
from typing import Any, List

from ..core.backend import Backend
from ..core.exceptions import VFSynthesisError
from ..core.model_loader import ModelArtifact
from ..models.manifest import ModelSpec
from ..synth.project import SynthProject
from ..util.audio import float_to_wav_bytes


class StubBackend(Backend):
    name = "stub"

    def load_model(self, artifact: ModelArtifact) -> Any:
        spec = artifact.spec if isinstance(artifact, ModelArtifact) else artifact
        return {"spec": spec, "backend": self.name, "assets": getattr(artifact, "assets", {})}

    def synthesize(self, project: SynthProject, handle: Any) -> bytes:
        if not isinstance(project, SynthProject):
            raise VFSynthesisError("StubBackend.synthesize expects a SynthProject")
        spec = handle.get("spec") if isinstance(handle, dict) else None
        sr = project.sample_rate or (spec.sample_rate if spec else 44100)
        samples: List[float] = []
        for note in project.notes:
            midi = note.midi
            dur = max(0.05, note.duration)
            n = int(sr * dur)
            if midi <= 0:
                samples.extend([0.0] * n)  # rest
                continue
            freq = 440.0 * (2.0 ** ((midi - 69) / 12.0))
            for i in range(n):
                t = i / sr
                env = min(1.0, t / 0.01) * min(1.0, (dur - t) / 0.02)
                env = max(0.0, env)
                s = 0.6 * math.sin(2 * math.pi * freq * t) + 0.2 * math.sin(2 * math.pi * 2 * freq * t)
                samples.append(s * env * 0.8)
        return float_to_wav_bytes(samples, sr)

    def unload(self, handle: Any) -> None:
        pass
