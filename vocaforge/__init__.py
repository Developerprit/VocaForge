"""VocaForge - a pure Python framework wrapping DiffSinger for AI singing voice synthesis.

VocaForge is a console-free Python library/SDK. It exposes a pluggable backend
interface so that real DiffSinger inference can be wired in on GPU machines,
while a stub backend keeps the framework runnable (and testable) without models.
"""

__version__ = "0.2.0"

from .core.engine import VocaForgeEngine
from .core.backend import Backend
from .core.model_loader import ModelLoader, ModelArtifact, LocalModelLoader
from .models.registry import ModelRegistry
from .models.manifest import ModelSpec
from .synth.project import SynthProject, Note
from .backends import DiffSingerAdapter, StubBackend

__all__ = [
    "VocaForgeEngine",
    "Backend",
    "ModelLoader",
    "ModelArtifact",
    "LocalModelLoader",
    "ModelRegistry",
    "ModelSpec",
    "SynthProject",
    "Note",
    "DiffSingerAdapter",
    "StubBackend",
    "__version__",
]
