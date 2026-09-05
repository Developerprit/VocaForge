"""VocaForge - a pure Python framework wrapping DiffSinger for AI singing voice synthesis.

VocaForge is a console-free Python library/SDK. It exposes a pluggable backend
interface so that real DiffSinger inference can be wired in on GPU machines,
while a stub backend keeps the framework runnable (and testable) without models.
"""

__version__ = "0.4.0"

from .core.engine import VocaForgeEngine
from .core.backend import Backend
from .core.model_loader import ModelLoader, ModelArtifact, LocalModelLoader, VfvpModelLoader
from .models.registry import ModelRegistry
from .models.manifest import ModelSpec
from .synth.project import SynthProject, Note
from .backends import DiffSingerAdapter, StubBackend
from .vfvp import VfvpPackage
from .midi import (
    MidiFile,
    MidiNote,
    read_midi,
    write_midi,
    midi_to_project,
    midi_from_project,
    render_midi,
    name_to_midi,
    midi_to_name,
    parse_seq,
)

__all__ = [
    "VocaForgeEngine",
    "Backend",
    "ModelLoader",
    "ModelArtifact",
    "LocalModelLoader",
    "VfvpModelLoader",
    "ModelRegistry",
    "ModelSpec",
    "SynthProject",
    "Note",
    "DiffSingerAdapter",
    "StubBackend",
    "VfvpPackage",
    "MidiFile",
    "MidiNote",
    "read_midi",
    "write_midi",
    "midi_to_project",
    "midi_from_project",
    "render_midi",
    "name_to_midi",
    "midi_to_name",
    "parse_seq",
    "__version__",
]
