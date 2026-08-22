"""NVIDIA provider exception types."""


class NVIDIAConfigError(RuntimeError):
    """Raised when NVIDIA configuration is missing or invalid."""


class NVIDIAAuthenticationError(RuntimeError):
    """Raised when NVIDIA authentication fails."""


class NVIDIARateLimitError(RuntimeError):
    """Raised when NVIDIA rate limits the request."""


class NVIDIATimeoutError(RuntimeError):
    """Raised when the NVIDIA request times out."""


class NVIDIAAPIError(RuntimeError):
    """Raised for other NVIDIA API failures."""
