"""Demonstrate the VocaForge .vfvp voice-library format end to end.

This example is fully self-contained: it builds a (placeholder) voice-library source
folder in a temp dir, packs it into a ``.vfvp`` 7z archive, validates the package,
reads its ``info.json``, and loads it through the real engine pipeline (the
``VfvpModelLoader`` extracts the archive to a temp dir, the synth runs, then the
temp dir is released). Nothing is written into the project tree.

Run:  python examples/vfvp_demo.py
"""
from __future__ import annotations

import json
import os
import tempfile

from vocaforge import VocaForgeEngine
from vocaforge.core.model_loader import VfvpModelLoader
from vocaforge.synth.project import SynthProject
from vocaforge.vfvp import MODEL_DIR, VfvpPackage


def _build_sample_source(root: str) -> None:
    model_dir = os.path.join(root, MODEL_DIR)
    os.makedirs(model_dir, exist_ok=True)

    info = {
        "id": "demo-singer",
        "name": "Demo Singer",
        "type": "synthesizer",
        "lang": "zh",
        "sample_rate": 44100,
        "backend": "diffsinger",
        "author": "VocaForge",
        "version": "1.0.0",
        "description": "A demo .vfvp voice library (placeholder weights).",
    }
    phoneme_map = {
        "phonemes": {"a": "a", "i": "i", "u": "u", "e": "e", "o": "o"},
        "pad": "PAD",
    }
    config = {"model_type": "diffsinger", "n_spk": 1, "hop_size": 320, "sampling_rate": 44100}

    with open(os.path.join(root, "info.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(root, "phoneme_map.json"), "w", encoding="utf-8") as fh:
        json.dump(phoneme_map, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(model_dir, "config.json"), "w", encoding="utf-8") as fh:
        json.dump(config, fh, ensure_ascii=False, indent=2)
    # Placeholder weights (real .pth files are produced by DiffSinger training).
    with open(os.path.join(model_dir, "acoustic.pth"), "wb") as fh:
        fh.write(b"DUMMY_ACOUSTIC_WEIGHTS_VOCAFORGE")
    with open(os.path.join(model_dir, "vocoder.pth"), "wb") as fh:
        fh.write(b"DUMMY_VOCODER_WEIGHTS_VOCAFORGE")


def main() -> None:
    work = tempfile.mkdtemp(prefix="vfvp_demo_")
    try:
        # Isolate the registry so this example NEVER writes into the shipped
        # models/manifest.json (the engine's default registry would persist add_model()).
        os.environ["VF_MODEL_MANIFEST"] = os.path.join(work, "registry", "manifest.json")

        source = os.path.join(work, "sample_voice")
        _build_sample_source(source)

        vfvp_path = os.path.join(work, "demo-singer.vfvp")

        # 1) Pack
        pkg = VfvpPackage.create(source, vfvp_path)
        print("[1] packed ->", vfvp_path)

        # 2) Validate + read meta
        rep = pkg.report()
        print(f"[2] valid={rep['valid']} members={rep['members']}")
        print("[2] info.json id =", pkg.open_info(vfvp_path).get("id"))

        # 3) Load via the engine's VfvpModelLoader (extracts to a temp dir).
        spec = VocaForgeEngine().registry.spec_from_vfvp(vfvp_path)
        print(f"[3] spec: id={spec.id} name={spec.name} backend={spec.backend}")
        artifact = VfvpModelLoader().load(spec)
        print("[3] extracted assets:")
        for k, v in artifact.assets.items():
            print(f"      {k}: {v}  (exists={os.path.exists(v)})")
        VfvpModelLoader().release(artifact)

        # 4) End-to-end through the engine. Use backend='stub' so we can run without
        #    real DiffSinger/GPU; this proves the .vfvp path is loaded & released.
        spec.backend = "stub"
        engine = VocaForgeEngine()
        engine.add_model(spec)
        wav = engine.synthesize(spec.id, SynthProject.from_lyrics("vfvp demo"))
        out_wav = os.path.join(work, "demo_out.wav")
        with open(out_wav, "wb") as fh:
            fh.write(wav)
        print(f"[4] synthesized through engine pipeline -> {out_wav} ({len(wav)} bytes)")

        print("\nOK: .vfvp format works (pack -> validate -> load -> synthesize).")
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
