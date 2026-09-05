"""Minimal Standard MIDI File (SMF) reader/writer — stdlib only.

Implements a pragmatic, well-tested subset:
  * reads format 0 and format 1 files (multiple tracks merged into one note list)
  * tempo meta events (``FF 51``), track name (``FF 03``), lyric meta (``FF 05``)
  * note-on / note-off pairing (velocity 0 = note off; running status supported)
  * writes compact **format 0** files with tempo + optional lyric meta events

Note times are exposed in **absolute seconds**; the writer converts them back to
ticks using ``division`` (ticks per quarter note) and ``tempo`` (microseconds per
quarter note). This keeps editing simple and musical (``set_tempo`` rescales time
like a conductor, preserving the notated note count).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

DEFAULT_PPQN = 480            # ticks per quarter note
DEFAULT_TEMPO_US = 500_000    # 120 BPM
CHANNELS = 16


class MidiError(ValueError):
    """Raised for malformed / unsupported MIDI input."""


def _read_vlq(data: bytes, i: int) -> Tuple[int, int]:
    """Read a variable-length quantity; returns (value, new_index)."""
    value = 0
    while True:
        if i >= len(data):
            raise MidiError("truncated variable-length quantity")
        b = data[i]
        i += 1
        value = (value << 7) | (b & 0x7F)
        if not (b & 0x80):
            break
        if value > 0x0FFFFFFF:
            raise MidiError("variable-length quantity too large")
    return value, i


def _encode_vlq(value: int) -> bytes:
    out = bytearray()
    value = int(value)
    out.append(value & 0x7F)
    value >>= 7
    while value:
        out.append(0x80 | (value & 0x7F))
        value >>= 7
    return bytes(reversed(out))


def _read_track(data: bytes, ppqn: int) -> Dict[str, object]:
    """Parse one MTrk payload into an intermediate event description."""
    notes_raw: List[Tuple[int, int, int, int, int, str]] = []  # ch,note,on,off,vel,lyric
    open_notes: Dict[Tuple[int, int], Tuple[int, int, str]] = {}  # (ch,note)->(tick,vel,lyric)
    lyrics: List[Tuple[int, str]] = []
    lyric_i = 0
    tempo_us: Optional[int] = None
    tempo_tick: int = 0
    name: Optional[str] = None
    last_tick = 0

    i = 0
    tick = 0
    running = 0
    while i < len(data):
        d, i = _read_vlq(data, i)
        tick += d
        last_tick = tick
        if i >= len(data):
            break
        status = data[i]
        if status & 0x80 == 0:  # running status: reuse previous channel message
            if not running:
                raise MidiError("running status without a previous status byte")
            status = running
        else:
            i += 1
            if 0x80 <= status <= 0xEF:
                running = status

        high = status & 0xF0
        ch = status & 0x0F

        def _need(n: int) -> bytes:
            nonlocal i
            if i + n > len(data):
                raise MidiError("truncated MIDI event")
            b = data[i:i + n]
            i += n
            return b

        if high in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
            b = _need(2)
            note, val = b[0], b[1]
            if high == 0x90 and val == 0:
                # velocity 0 note-on == note-off
                _close_note(open_notes, notes_raw, ch, note, tick, tempo_tick)
            elif high == 0x90:
                # attach any pending lyric that precedes / coincides with this note-on
                lyric = ""
                j = lyric_i
                while j < len(lyrics) and lyrics[j][0] <= tick:
                    lyric = lyrics[j][1]
                    j += 1
                if j > lyric_i:
                    lyric_i = j
                open_notes[(ch, note)] = (tick, val, lyric)
            elif high == 0x80:
                _close_note(open_notes, notes_raw, ch, note, tick, tempo_tick)
            # 0xA0/0xB0/0xE0 channel messages -> ignored (no sound model here)
        elif high in (0xC0, 0xD0):
            _need(1)  # program / channel pressure -> ignored
        elif status == 0xF0 or status == 0xF7:
            ln, i2 = _read_vlq(data, i)
            i = i2
            _need(ln)  # sysex -> skipped
        elif status == 0xFF:
            meta_type = _need(1)[0]
            ln, i2 = _read_vlq(data, i)
            i = i2
            payload = _need(ln)
            if meta_type == 0x2F:  # end of track
                break
            elif meta_type == 0x51 and len(payload) == 3:  # tempo
                if tempo_us is None or tick < tempo_tick:
                    tempo_us = (payload[0] << 16) | (payload[1] << 8) | payload[2]
                    tempo_tick = tick
            elif meta_type == 0x03:  # track name
                try:
                    name = payload.decode("utf-8", "replace")
                except Exception:  # noqa: BLE001
                    name = None
            elif meta_type == 0x05:  # lyric
                try:
                    lyrics.append((tick, payload.decode("utf-8", "replace")))
                except Exception:  # noqa: BLE001
                    pass
            # other meta events are ignored
        else:
            raise MidiError(f"unsupported status byte 0x{status:02X}")

    # close any dangling notes at the end of the track
    for (ch, note), (on_tick, vel, lyric) in open_notes.items():
        notes_raw.append((ch, note, on_tick, max(last_tick, on_tick + 1), vel, lyric))
    return {
        "notes": notes_raw,
        "tempo_us": tempo_us,
        "name": name,
    }


def _close_note(open_notes: Dict[Tuple[int, int], Tuple[int, int, str]],
                notes_raw: list, ch: int, note: int,
                tick: int, _tempo_tick: int) -> None:
    key = (ch, note)
    ent = open_notes.pop(key, None)
    if ent is None:
        return
    on_tick, vel, lyric = ent
    if tick <= on_tick:
        tick = on_tick + 1
    notes_raw.append((ch, note, on_tick, tick, vel, lyric))


@dataclass
class MidiNote:
    """One played note, in absolute seconds."""

    midi: int = 60              # 0..127; note pitch
    start: float = 0.0          # seconds from the start of the file
    duration: float = 0.4       # seconds
    velocity: int = 100         # 1..127
    channel: int = 0
    lyric: str = ""             # optional text from a lyric meta event

    @property
    def end(self) -> float:
        return self.start + self.duration

    def to_dict(self) -> dict:
        return {"midi": self.midi, "start": round(self.start, 4),
                "duration": round(self.duration, 4), "velocity": self.velocity,
                "channel": self.channel, "lyric": self.lyric}


@dataclass
class MidiFile:
    """An in-memory MIDI piece (notes in seconds)."""

    notes: List[MidiNote] = field(default_factory=list)
    tempo: int = DEFAULT_TEMPO_US          # microseconds per quarter note
    division: int = DEFAULT_PPQN           # ticks per quarter note
    name: str = ""

    # ---- convenience ------------------------------------------------------
    @property
    def bpm(self) -> float:
        return 60_000_000 / float(self.tempo)

    @property
    def duration(self) -> float:
        return max((n.end for n in self.notes), default=0.0)

    @property
    def _us_per_tick(self) -> float:
        return self.tempo / float(self.division) / 1e6

    # ---- editing ----------------------------------------------------------
    def transpose(self, semitones: int) -> "MidiFile":
        """Shift every note by ``semitones`` (clamped to 0..127)."""
        for n in self.notes:
            n.midi = max(0, min(127, n.midi + int(semitones)))
        return self

    def retime(self, rate: float) -> "MidiFile":
        """Multiply all timings by ``rate`` (>1 slows down)."""
        if rate <= 0:
            raise MidiError("rate must be > 0")
        for n in self.notes:
            n.start *= rate
            n.duration *= rate
        return self

    def set_tempo(self, bpm: float) -> "MidiFile":
        """Re-tempo to ``bpm``. Keeps the notated note count, rescales time so
        the music plays faster/slower exactly like a conductor change."""
        if bpm <= 0:
            raise MidiError("bpm must be > 0")
        old = self.tempo
        new = int(60_000_000 / bpm)
        factor = new / float(old)
        self.retime(factor)
        self.tempo = new
        return self

    def trim(self, start: float, end: Optional[float] = None) -> "MidiFile":
        """Keep only notes overlapping ``[start, end)`` (seconds), shifting time."""
        end = self.duration if end is None else end
        kept: List[MidiNote] = []
        for n in self.notes:
            if n.end <= start or n.start >= end:
                continue
            s = max(0.0, n.start - start)
            e = min(n.end, end) - start
            kept.append(MidiNote(midi=n.midi, start=s, duration=max(0.0, e - s),
                                 velocity=n.velocity, channel=n.channel, lyric=n.lyric))
        self.notes = sorted(kept, key=lambda x: (x.start, x.midi))
        return self

    def set_lyrics(self, texts) -> "MidiFile":
        """Assign lyrics to notes in order (``texts``: str -> chars, or any iterable).

        Notes without a lyric when the iterator is exhausted keep their current lyric.
        """
        import itertools

        if isinstance(texts, str):
            texts = [c for c in texts if c.strip()]
        it = itertools.cycle(texts) if texts else []
        for n in self.notes:
            try:
                n.lyric = next(it)
            except StopIteration:
                break
        return self

    # ---- serialization helpers -------------------------------------------
    def _to_ticks(self, seconds: float) -> int:
        return max(0, int(round(seconds / self._us_per_tick)))

    def _sorted_events(self) -> List[Tuple[int, int, bytes]]:
        """Return (tick, rank, raw_event) with rank: tempo/name < lyric < off < on."""
        events: List[Tuple[int, int, bytes]] = []
        if self.name:
            nb = self.name.encode("utf-8", "replace")
            events.append((0, 0, b"\xff\x03" + _encode_vlq(len(nb)) + nb))
        tempo = struct.pack(">I", self.tempo)[1:]
        events.append((0, 0, b"\xff\x51\x03" + tempo))
        us_per_tick = self._us_per_tick
        for n in sorted(self.notes, key=lambda x: (x.start, x.midi)):
            on = self._to_ticks(n.start)
            off = self._to_ticks(n.end)
            if off <= on:
                off = on + 1
            lyric = (n.lyric or "").encode("utf-8", "replace")
            if lyric:
                events.append((on, 1, b"\xff\x05" + _encode_vlq(len(lyric)) + lyric))
            st = 0x90 | (n.channel & 0x0F)
            events.append((on, 3, bytes([st, n.midi & 0x7F, max(1, min(127, n.velocity))])))
            st_off = 0x80 | (n.channel & 0x0F)
            events.append((off, 2, bytes([st_off, n.midi & 0x7F, 0x40])))
        events = [e for e in events if e[2]]
        end_tick = max((e[0] for e in events), default=0) + 1
        events.append((end_tick, 4, b"\xff\x2f\x00"))
        events.sort(key=lambda e: (e[0], e[1]))
        return events

    def to_bytes(self) -> bytes:
        """Encode as a standard format-0 SMF file."""
        events = self._sorted_events()
        track = bytearray()
        prev = 0
        for tick, _rank, raw in events:
            track += _encode_vlq(tick - prev)
            track += raw
            prev = tick
        header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, self.division)
        return header + b"MTrk" + struct.pack(">I", len(track)) + bytes(track)

    def write(self, path: str) -> int:
        """Write the SMF file to ``path``; returns the byte count."""
        data = self.to_bytes()
        with open(path, "wb") as fh:
            fh.write(data)
        return len(data)

    def to_dict(self) -> dict:
        return {"name": self.name, "format": 0, "division": self.division,
                "tempo": self.tempo, "bpm": round(self.bpm, 3),
                "duration": round(self.duration, 4),
                "notes": [n.to_dict() for n in self.notes]}


def read_midi(source) -> MidiFile:
    """Read a MIDI file from a path, bytes, or a file object."""
    if hasattr(source, "read"):
        data = source.read()
    elif isinstance(source, (bytes, bytearray)):
        data = bytes(source)
    else:
        with open(source, "rb") as fh:
            data = fh.read()
    if len(data) < 14 or data[:4] != b"MThd":
        raise MidiError("not a Standard MIDI File (missing MThd header)")
    (hlen, fmt, ntrks, division) = struct.unpack(">IHHH", data[4:14])
    if hlen < 6:
        raise MidiError("invalid MThd header length")
    if fmt > 2:
        raise MidiError(f"unsupported SMF format {fmt}")
    if division & 0x8000:
        raise MidiError("SMPTE time division is not supported")
    ppqn = division

    tracks: List[Dict[str, object]] = []
    pos = 14
    track_index = 0
    while pos + 8 <= len(data) and track_index < ntrks:
        if data[pos:pos + 4] != b"MTrk":
            pos += 1
            continue
        tlen = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        payload = data[pos + 8:pos + 8 + tlen]
        tracks.append(_read_track(payload, ppqn))
        pos += 8 + tlen
        track_index += 1

    # merge tracks into a single logical piece (tempo/name from any track)
    tempo: Optional[int] = None
    name: Optional[str] = None
    for tr in tracks:
        if tr.get("tempo_us") is not None and tempo is None:
            tempo = tr["tempo_us"]
        if tr.get("name") and name is None:
            name = tr["name"]

    mf = MidiFile(tempo=tempo or DEFAULT_TEMPO_US, division=ppqn, name=name or "")
    us_per_tick = mf._us_per_tick
    for tr in tracks:
        for (ch, note, on_tick, off_tick, vel, lyric) in tr["notes"]:
            mf.notes.append(MidiNote(
                midi=note,
                start=on_tick * us_per_tick,
                duration=max(0.0, (off_tick - on_tick) * us_per_tick),
                velocity=vel,
                channel=ch,
                lyric=lyric,
            ))
    mf.notes.sort(key=lambda n: (n.start, n.midi))
    return mf


def write_midi(mf: MidiFile, path: str) -> int:
    """Convenience wrapper around :meth:`MidiFile.write`."""
    return mf.write(path)
