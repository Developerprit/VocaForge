"""Demonstrate VocaForge MIDI support end to end.

Generates a MIDI melody (from note names), round-trips it back through the SMF
reader, edits it (transpose + re-tempo), exports it to a SynthProject JSON, and
finally renders it into a singing WAV through the stub voice backend.

Run:  python examples/midi_demo.py
"""
from __future__ import annotations

import json
import os
import tempfile

from vocaforge import midi_from_project, midi_to_project, read_midi, render_midi
from vocaforge.midi import MidiFile, MidiNote, parse_seq
from vocaforge.synth.project import Note, SynthProject


def main() -> None:
    work = tempfile.mkdtemp(prefix="midi_demo_")
    try:
        # 1) build a SynthProject (lyrics + pitches + durations)
        project = SynthProject(name="twinkle", notes=[
            Note(lyric="小", midi=60, duration=0.5),
            Note(lyric="星", midi=60, duration=0.5),
            Note(lyric="星", midi=67, duration=0.5),
            Note(lyric="亮", midi=67, duration=0.5),
            Note(lyric="晶", midi=69, duration=0.5),
            Note(lyric="晶", midi=69, duration=0.5),
            Note(lyric="", midi=0, duration=0.4),      # rest
            Note(lyric="挂", midi=67, duration=1.0),
        ])

        # 2) project -> MIDI (lyrics embedded as lyric meta events)
        mf = midi_from_project(project, tempo_bpm=100)
        mid_path = os.path.join(work, "twinkle.mid")
        mf.write(mid_path)
        print(f"[1] wrote {mid_path}  notes={len(mf.notes)}  dur={mf.duration:.2f}s  bpm={mf.bpm:.0f}")

        # 3) round-trip: read it back and confirm it matches
        back = read_midi(mid_path)
        same = len(back.notes) == len(mf.notes) and all(
            abs(a.start - b.start) < 0.02 and abs(a.duration - b.duration) < 0.02 and a.midi == b.midi
            for a, b in zip(back.notes, mf.notes)
        )
        print(f"[2] round-trip read OK (format 0, notes match: {same})  bpm={back.bpm:.0f}")
        print(f"    lyrics from meta: {[n.lyric for n in back.notes if n.lyric]}")

        # 4) edit: transpose +2 semitones and speed up to 140 BPM
        edited = read_midi(mid_path).transpose(2).set_tempo(140)
        edited_path = os.path.join(work, "twinkle_up.mid")
        edited.write(edited_path)
        print(f"[3] edited -> {edited_path}  first note {edited.notes[0].midi}  bpm={edited.bpm:.0f}")

        # 5) export MIDI -> project JSON (rests preserved as silence)
        proj2 = midi_to_project(back, name="twinkle_imported")
        js = os.path.join(work, "twinkle.project.json")
        with open(js, "w", encoding="utf-8") as fh:
            json.dump(proj2.to_dict(), fh, ensure_ascii=False, indent=2)
        print(f"[4] exported {len(proj2.notes)} notes to {js}  (rests included: "
              f"{sum(1 for n in proj2.notes if n.midi <= 0)})")

        # 6) render MIDI -> singing WAV through the stub voice backend
        wav = os.path.join(work, "twinkle.wav")
        audio = render_midi(mid_path, model="stub-zh", out=wav)
        print(f"[5] rendered MIDI -> voice WAV {wav} ({len(audio)} bytes)")

        # 7) library-only quick path: note-name sequence -> MIDI -> WAV
        seq = parse_seq("C4 0.4 E4 0.4 G4 0.4 C5 0.6")
        mm = MidiFile(notes=[MidiNote(midi=m, start=c * 0.4, duration=d) for c, (m, d) in enumerate(seq)])
        wav2 = render_midi(mm, model="stub-zh")
        print(f"[6] sequence render OK ({len(wav2)} bytes, {len(mm.notes)} notes)")

        print("\nOK: MIDI generate -> edit -> round-trip -> render pipeline works.")
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
