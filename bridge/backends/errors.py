
class BaseBackendError(Exception):
    """Base class for all errors raised by the backend."""
    pass


class NotImplementedByBackendError(BaseBackendError):
    """Raised when a backend does not implement a method."""
    pass