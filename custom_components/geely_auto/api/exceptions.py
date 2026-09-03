"""Exception hierarchy for the Geely Auto protocol layer."""


class GeelyError(Exception):
    """Base error for all Geely Auto failures."""


class GeelyAuthError(GeelyError):
    """Authentication is invalid, expired, or revoked."""


class GeelyRateLimitError(GeelyError):
    """The service refused a request because of rate limiting."""


class GeelyProtocolError(GeelyError):
    """A response did not match the verified protocol contract."""


class GeelyCommandError(GeelyError):
    """A remote command was rejected or could not be confirmed."""


class GeelyConnectionError(GeelyError):
    """A connection or timeout failure occurred."""


class GeelyProtocolUnavailable(GeelyProtocolError):
    """The protocol gate is closed because no verified capture exists."""
