"""Space Packet Parser Exceptions"""


class ElementNotFoundError(Exception):
    """Exception for missing XML element"""
    pass


class ComparisonError(Exception):
    """Exception for problems performing comparisons"""
    pass


class FormatStringError(Exception):
    """Error indicating a problem determining how to parse a variable length string."""
    pass


class DynamicLengthBinaryParameterError(Exception):
    """Exception to raise when we try to parse a dynamic length binary field as fixed length"""
    pass


class CalibrationError(Exception):
    """For errors encountered during value calibration"""
    pass


class InvalidParameterTypeError(Exception):
    """Error raised when someone is using an invalid ParameterType element"""
    pass


class UnrecognizedPacketTypeError(Exception):
    """Error raised when we can't figure out which kind of packet we are dealing with based on the header"""

    def __init__(self, *args, partial_data: dict = None):
        """
        Parameters
        ----------
        partial_data : dict, Optional
            Data parsed so far (for debugging at higher levels)
        """
        super().__init__(*args)
        self.partial_data = partial_data
