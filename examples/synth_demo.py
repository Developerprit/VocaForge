"""Self-check demo: synthesize a short phrase with the stub backend."""
from vocaforge import VocaForgeEngine
from vocaforge.synth.project import Note, SynthProject


def main() -> None:
    engine = VocaForgeEngine()
    project = SynthProject(
        name="demo",
        sample_rate=44100,
        notes=[
            Note("do", 60, 0.4),
            Note("re", 62, 0.4),
            Note("mi", 64, 0.4),
            Note("fa", 65, 0.5),
        ],
    )
    audio = engine.synthesize("stub-zh", project)
    with open("examples/demo.wav", "wb") as fh:
        fh.write(audio)
    print(f"wrote examples/demo.wav ({len(audio)} bytes)")


if __name__ == "__main__":
    main()
