"""Musical note helpers: names <-> MIDI numbers, CLI note sequences."""
from __future__ import annotations

import re
from typing import Iterator, List, Tuple

#: Chromatic note names (sharps). Flats are mapped to their sharp equivalents.
SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_TO_SHARP = {
    "db": "c#", "eb": "d#", "gb": "f#", "ab": "g#", "bb": "a#", "cb": "b",
}
_NAME_RE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d+)$")
_SEQ_RE = re.compile(r"\S+")


def name_to_midi(name: str) -> int:
    """Convert a note name to a MIDI number (``C4`` -> 60, ``A4`` -> 69, ``C#4`` -> 61)."""
    m = _NAME_RE.match(name.strip())
    if not m:
        raise ValueError(f"invalid note name: {name!r} (expected e.g. C4, C#4, Bb3)")
    letter, acc, octave = m.group(1).lower(), m.group(2), int(m.group(3))
    if acc == "b":
        letter = FLAT_TO_SHARP.get(letter + "b", letter)
        acc = "#" if letter in ("c#", "d#", "f#", "g#", "a#") else ""
    semitone = SHARP_NAMES.index(letter.upper() + acc if acc else letter.upper())
    return (octave + 1) * 12 + semitone


def midi_to_name(midi: int) -> str:
    """Convert a MIDI number to a note name (``60`` -> ``C4``)."""
    midi = max(0, min(127, int(midi)))
    return f"{SHARP_NAMES[midi % 12]}{midi // 12 - 1}"


def parse_seq(text: str) -> List[Tuple[int, float]]:
    """Parse ``"C4 0.4 E4 0.4 G4 0.4"`` into ``[(midi, dur_seconds), ...]``.

    Pitch tokens accept note names or plain integers; they must alternate with
    duration tokens (seconds). Rests are ``0`` pitches.
    """
    tokens = _SEQ_RE.findall(text or "")
    if len(tokens) % 2 != 0:
        raise ValueError("expected alternating pitch duration tokens, e.g. 'C4 0.4 E4 0.4'")
    out: List[Tuple[int, float]] = []
    for i in range(0, len(tokens), 2):
        pitch, dur = tokens[i], float(tokens[i + 1])
        if dur < 0:
            raise ValueError("durations must be >= 0")
        try:
            midi = int(pitch)
        except ValueError:
            midi = name_to_midi(pitch)
        out.append((midi, dur))
    return out


def seq_names(seq: Iterator[Tuple[int, float]]) -> List[str]:
    """Human-readable description of a note sequence (for CLI output)."""
    return [f"{midi_to_name(m)}({d:g}s)" if m > 0 else f"rest({d:g}s)"
            for m, d in seq]
