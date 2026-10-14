"""Domain exceptions."""


class R48Error(Exception):
    """Base application error."""


class ProtocolError(R48Error):
    """Invalid protocol operation."""


class ValidationError(R48Error):
    """Invalid user input or out-of-range value."""


class TransportError(R48Error):
    """Serial / CAN transport failure."""