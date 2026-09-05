"""Bridge between MIDI and the VocaForge synthesis pipeline.

``SynthProject`` is a *sequential* list of notes (lyric + midi + seconds duration),
so converting a MIDI melody into a project inserts rests for the gaps, and converting
a project back into a MIDI file treats rests (``midi <= 0``) as silence.
"""
from __future__ import annotations

from typing import Iterable, List, Optional

from .smf import MidiFile, MidiNote

#: Gaps shorter than this are absorbed (no rest note inserted).
MIN_REST = 0.005
#: Default lyric used when a note has none.
FALLBACK_LYRIC = "a"


def _iter_lyrics(texts) -> Iterable[str]:
    if isinstance(texts, str):
        return (c for c in texts if c.strip())
    return iter(texts or ())


def midi_to_project(mf: MidiFile, *, lyrics=None, sample_rate: int = 44100,
                    name: str = "from_midi") -> "SynthProject":
    """Flatten a :class:`MidiFile` into a sequential :class:`SynthProject`.

    Overlapping notes are appended in start order (no polyphony in a singing
    project); gaps become rest notes (``midi = 0``) so absolute timing is kept.
    ``lyrics`` (a string -> one char per non-rest note, or an iterable) overrides
    the notes' lyric meta text; notes without a lyric fall back to ``a``.
    """
    from ..synth.project import Note, SynthProject

    lyric_it = _iter_lyrics(lyrics)
    notes: List[Note] = []
    cursor = 0.0
    for n in sorted(mf.notes, key=lambda x: (x.start, x.midi)):
        start = max(cursor, n.start)  # projects are sequential: no overlap
        gap = start - cursor
        if gap > MIN_REST:
            notes.append(Note(lyric="", midi=0, duration=gap))
            cursor += gap
        elif start > cursor:  # tiny gap: absorb into note start
            pass
        lyric = n.lyric or FALLBACK_LYRIC
        try:
            lyric = next(lyric_it)
        except StopIteration:
            pass
        dur = max(0.05, n.duration)
        notes.append(Note(lyric=lyric or FALLBACK_LYRIC, midi=n.midi, duration=dur))
        cursor = max(cursor, n.end)
    return SynthProject(name=name, sample_rate=sample_rate, notes=notes)


def midi_from_project(project, *, tempo_bpm: float = 120.0, division: int = 480,
                      name: Optional[str] = None, channel: int = 0) -> MidiFile:
    """Convert a :class:`SynthProject` into a :class:`MidiFile`.

    Non-rest notes become note events at the running cursor; rests (``midi <= 0``)
    only advance the cursor (silence). Note lyrics are stored as lyric meta events.
    """
    mf = MidiFile(tempo=int(60_000_000 / tempo_bpm), division=division,
                  name=name if name is not None else project.name)
    cursor = 0.0
    for note in project.notes:
        if note.midi <= 0:
            cursor += max(0.0, note.duration)  # rest advances time only
            continue
        mf.notes.append(MidiNote(midi=note.midi, start=cursor,
                                 duration=max(0.05, note.duration),
                                 channel=channel, lyric=note.lyric))
        cursor += max(0.05, note.duration)
    return mf


def render_midi(source, model: str = "stub-zh", *, lyrics=None, sample_rate: int = 44100,
                out: Optional[str] = None, engine=None, name: str = "midi") -> bytes:
    """Render a MIDI file into singing-voice WAV bytes through a VocaForge engine.

    ``source`` may be a path, bytes or a :class:`MidiFile`. Lyrics come from the
    MIDI lyric meta events or ``lyrics`` (characters are assigned to notes in
    order). Writes to ``out`` when given; always returns the WAV bytes.
    """
    from ..core.engine import VocaForgeEngine

    mf = source if isinstance(source, MidiFile) else _read(source)
    project = midi_to_project(mf, lyrics=lyrics, sample_rate=sample_rate, name=name)
    eng = engine or VocaForgeEngine()
    audio = eng.synthesize(model, project)
    if out:
        with open(out, "wb") as fh:
            fh.write(audio)
    return audio


def _read(source):
    from .smf import read_midi
    return read_midi(source)


__all__ = ["midi_to_project", "midi_from_project", "render_midi"]
