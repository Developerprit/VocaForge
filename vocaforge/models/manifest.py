"""Model specification data class + (de)serialization."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict


@dataclass
class ModelSpec:
    """A single registered voice library (声库).

    ``type`` is one of: ``diffusion``, ``synthesizer``, ``vocoder``.
    """

    id: str
    name: str
    type: str
    path: str
    sample_rate: int = 44100
    lang: str = "zh"
    backend: str = "auto"  # auto | diffsinger | stub
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ModelSpec":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})
