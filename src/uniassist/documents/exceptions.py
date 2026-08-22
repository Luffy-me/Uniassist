"""Document store exceptions."""


class StorageConflictError(Exception):
    """Raised when stored content would overwrite a different file."""
