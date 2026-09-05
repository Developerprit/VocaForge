"""Example: a third-party project integrating into VocaForge.

This is NOT a plugin. The host project imports VocaForge, implements its own
:class:`Backend` (synthesis engine) and :class:`ModelLoader` (model storage
resolver), registers them on an engine, and synthesizes. No auto-discovery, no
entry-points -- the project wires VocaForge in explicitly.

Run:  python examples/integrate_custom_backend.py
"""
from __future__ import annotations

import math
import tempfile
from typing import Any

from vocaforge import (
    Backend,
    ModelArtifact,
    ModelLoader,
    ModelSpec,
    SynthProject,
    VocaForgeEngine,
)
from vocaforge.models.registry import ModelRegistry
from vocaforge.util.audio import float_to_wav_bytes


class DatabaseModelLoader(ModelLoader):
    """Example custom loader: resolves a model id to weights stored elsewhere.

    Replace the body with your own storage (DB, object store, encrypted pack).
    """

    name = "db"

    def load(self, spec: ModelSpec) -> ModelArtifact:
        # Pretend we fetched weights for `spec.id` from a database and now expose
        # the resolved location / config via `assets`.
        return ModelArtifact(
            spec=spec,
            assets={"root": spec.path or "<in-memory>", "fetched_from": "database"},
            meta={"loader": self.name},
        )

    def release(self, artifact: ModelArtifact) -> None:
        return None


class SineBackend(Backend):
    """A tiny custom synthesis engine: renders each note as a sine tone."""

    name = "sine"
    api_version = "1.0"

    def load_model(self, artifact: ModelArtifact) -> Any:
        return {"spec": artifact.spec, "assets": artifact.assets}

    def synthesize(self, project: SynthProject, handle: Any) -> bytes:
        spec = handle["spec"]
        sr = project.sample_rate or spec.sample_rate
        samples: list[float] = []
        for note in project.notes:
            n = int(sr * max(0.05, note.duration))
            if note.midi <= 0:
                samples.extend([0.0] * n)
                continue
            freq = 440.0 * (2.0 ** ((note.midi - 69) / 12.0))
            samples.extend(0.7 * math.sin(2 * math.pi * freq * (i / sr)) for i in range(n))
        return float_to_wav_bytes(samples, sr)

    def unload(self, handle: Any) -> None:
        return None


def main() -> None:
    # Use an isolated manifest so this example never pollutes the shipped
    # models/manifest.json.
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
        manifest_path = tf.name
    registry = ModelRegistry(manifest_path=manifest_path)

    engine = VocaForgeEngine(registry=registry)
    engine.register_model_loader(DatabaseModelLoader())  # plug custom storage
    engine.register_backend(SineBackend())               # plug custom engine

    engine.add_model(
        ModelSpec(id="demo-voice", name="Demo Voice", type="synthesizer", path="", backend="sine")
    )

    wav = engine.synthesize("demo-voice", SynthProject.from_lyrics("VocaForge", midi=67))
    out = "examples/custom_backend_demo.wav"
    with open(out, "wb") as fh:
        fh.write(wav)
    print(f"[OK] third-party backend synthesized {len(wav)} bytes -> {out}")


if __name__ == "__main__":
    main()
