"""VocaForge exception hierarchy."""


class VocaForgeError(Exception):
    """Base error for all VocaForge operations."""


class VFMissingBackendError(VocaForgeError):
    """Raised when a required backend (e.g. diffsinger) is not importable."""


class VFModelNotFound(VocaForgeError):
    """Raised when a requested model id/name is not in the registry (-> HTTP 404)."""


class VFModelLoadError(VocaForgeError):
    """Raised when a model spec exists but cannot be loaded."""


class VFSynthesisError(VocaForgeError):
    """Raised when synthesis fails after a model was loaded."""
