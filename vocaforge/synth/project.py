"""Synthesis project: lyrics/phonemes, notes, durations."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Note:
    lyric: str = "a"
    midi: int = 60  # MIDI note number; <=0 means rest
    duration: float = 0.4  # seconds

    def to_dict(self) -> Dict[str, Any]:
        return {"lyric": self.lyric, "midi": self.midi, "duration": self.duration}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Note":
        return cls(
            lyric=str(d.get("lyric", "a")),
            midi=int(d.get("midi", 60)),
            duration=float(d.get("duration", 0.4)),
        )


@dataclass
class SynthProject:
    name: str = "untitled"
    sample_rate: int = 44100
    notes: List[Note] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "sample_rate": self.sample_rate,
            "notes": [n.to_dict() for n in self.notes],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SynthProject":
        return cls(
            name=str(d.get("name", "untitled")),
            sample_rate=int(d.get("sample_rate", 44100)),
            notes=[Note.from_dict(n) for n in d.get("notes", [])],
        )

    @classmethod
    def from_lyrics(
        cls, lyrics: str, midi: int = 60, duration: float = 0.35, sample_rate: int = 44100
    ) -> "SynthProject":
        """Build a monotone project from raw lyric text (one note per character)."""
        notes = [Note(lyric=ch, midi=midi, duration=duration) for ch in lyrics if ch.strip()]
        return cls(name="from_lyrics", sample_rate=sample_rate, notes=notes)
