"""VocaForge MIDI support: edit / generate / render MIDI into singing voice.

Public surface:
    * :class:`MidiFile` / :class:`MidiNote` — in-memory MIDI (notes in seconds)
    * :func:`read_midi` / :func:`write_midi` — standard SMF files (stdlib only)
    * editing: ``MidiFile.transpose / set_tempo / retime / trim / set_lyrics``
    * :func:`midi_to_project` / :func:`midi_from_project` — SynthProject bridge
    * :func:`render_midi` — MIDI + voice library -> singing WAV bytes
    * note helpers: :func:`name_to_midi` / :func:`midi_to_name` / :func:`parse_seq`
"""
from .notes import midi_to_name, name_to_midi, parse_seq
from .project import midi_from_project, midi_to_project, render_midi
from .smf import (
    DEFAULT_PPQN,
    DEFAULT_TEMPO_US,
    MidiError,
    MidiFile,
    MidiNote,
    read_midi,
    write_midi,
)

__all__ = [
    "MidiFile",
    "MidiNote",
    "MidiError",
    "read_midi",
    "write_midi",
    "midi_to_project",
    "midi_from_project",
    "render_midi",
    "name_to_midi",
    "midi_to_name",
    "parse_seq",
    "DEFAULT_PPQN",
    "DEFAULT_TEMPO_US",
]
