"""Minimal WAV (16-bit PCM) encoder using only the standard library."""
from __future__ import annotations

import io
import struct
import wave
from typing import Sequence


def float_to_wav_bytes(samples: Sequence[float], sample_rate: int, channels: int = 1) -> bytes:
    """Encode float samples in the range [-1, 1] to 16-bit PCM WAV bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        frames = bytearray()
        for s in samples:
            s = max(-1.0, min(1.0, s))
            frames += struct.pack("<h", int(s * 32767))
        wf.writeframes(bytes(frames))
    return buf.getvalue()


def write_wav_file(path: str, samples: Sequence[float], sample_rate: int, channels: int = 1) -> int:
    """Write WAV to ``path``; returns the number of bytes written."""
    data = float_to_wav_bytes(samples, sample_rate, channels)
    with open(path, "wb") as fh:
        fh.write(data)
    return len(data)
