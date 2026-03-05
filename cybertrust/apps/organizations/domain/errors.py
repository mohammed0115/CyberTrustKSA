class DomainError(Exception):
    """Base error for organization domain operations."""


class ValidationError(DomainError):
    """Raised when a domain rule or input validation fails."""


class PermissionDenied(DomainError):
    """Raised when the actor is not allowed to perform an operation."""
