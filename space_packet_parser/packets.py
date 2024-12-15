
"""Packet containers and parsing utilities for space packets."""

from dataclasses import dataclass, field
from enum import IntEnum
from functools import cached_property
from typing import List, Optional, Protocol, Union

BuiltinDataTypes = Union[bytes, float, int, str]


class _Parameter:
    """Mixin class for storing access to the raw value of a parsed data item.

    The raw value is the closest representation of the data item as it appears in the packet.
    e.g. bytes for binary data, int for integer data, etc. It has not been calibrated or
    adjusted in any way and is an easy way for user's to debug the transformations that
    happened after the fact.

    Notes
    -----
    We need to override the __new__ method to store the raw value of the data item
    on immutable built-in types. So this is just a way of allowing us to inject our
    own attribute into the built-in types.
    """
    def __new__(cls, value: BuiltinDataTypes, raw_value: BuiltinDataTypes = None) -> BuiltinDataTypes:
        obj = super().__new__(cls, value)
        # Default to the same value as the parsed value if it isn't provided
        obj.raw_value = raw_value if raw_value is not None else value
        return obj


class BinaryParameter(_Parameter, bytes):
    """A class to represent a binary data item."""


class BoolParameter(_Parameter, int):
    """A class to represent a parsed boolean data item."""
    # A bool is a subclass of int, so all we are really doing here
    # is making a nice representation using the bool type because
    # bool can't be subclassed directly.
    def __repr__(self) -> str:
        return bool.__repr__(bool(self))


class FloatParameter(_Parameter, float):
    """A class to represent a float data item."""


class IntParameter(_Parameter, int):
    """A class to represent a integer data item."""


class StrParameter(_Parameter, str):
    """A class to represent a string data item."""


ParameterDataTypes = Union[BinaryParameter, BoolParameter, FloatParameter, IntParameter, StrParameter]


class SequenceFlags(IntEnum):
    """Enumeration of the possible sequence flags in a CCSDS packet."""
    CONTINUATION = 0
    FIRST = 1
    LAST = 2
    UNSEGMENTED = 3


class RawPacketData(bytes):
    """A class to represent raw packet data as bytes but whose length is represented by bit length.

    This class is a subclass of bytes and is used to represent the raw packet data
    in a more readable way. It is used to store the raw packet data in the Packet
    class and used to keep track of the current parsing position (accessible through the `pos` attribute).

    There are also a few convenience methods to extract the CCSDS header fields from the packet data.
    """
    HEADER_LENGTH_BYTES = 6
    pos = 0  # in bits

    def __str__(self) -> str:
        return (f"RawPacketData Header: ({self.version_number=}, {self.type=}, "
                f"{self.secondary_header_flag=}, {self.apid=}, {self.sequence_flags=}, "
                f"{self.sequence_count=}, {self.data_length=})").replace("self.", "")

    @cached_property
    def version_number(self) -> int:
        """CCSDS Packet Version Number"""
        return _extract_bits(self, 0, 3)

    @cached_property
    def type(self) -> int:
        """CCSDS Packet Type

        0 = Telemetry Packet
        1 = Telecommand Packet
        """
        return _extract_bits(self, 3, 1)

    @cached_property
    def secondary_header_flag(self) -> int:
        """CCSDS Secondary Header Flag

        0 = No secondary header
        1 = Secondary header present
        """

        return _extract_bits(self, 4, 1)

    @cached_property
    def apid(self) -> int:
        """CCSDS Application Process Identifier (APID)"""
        return _extract_bits(self, 5, 11)

    @cached_property
    def sequence_flags(self) -> int:
        """CCSDS Packet Sequence Flags

        00 = Continuation packet
        01 = First packet
        10 = Last packet
        11 = Unsegmented packet (standalone)
        """
        return _extract_bits(self, 16, 2)

    @cached_property
    def sequence_count(self) -> int:
        """CCSDS Packet Sequence Count"""
        return _extract_bits(self, 18, 14)

    @cached_property
    def data_length(self) -> int:
        """CCSDS Packet Data Length

        Section 4.1.3.5.3 The length count C shall be expressed as:
        C = (Total Number of Octets in the Packet Data Field) – 1
        """
        # This has already been parsed previously to give us the length of the packet
        # so avoid the extract_bits call again and calculate it based on the length of the data
        # Subtract 6 bytes for the header and 1 for the length count
        return len(self) - RawPacketData.HEADER_LENGTH_BYTES - 1

    def read_as_bytes(self, nbits: int) -> bytes:
        """Read a number of bits from the packet data as bytes. Reads minimum number of complete bytes required to
        capture `nbits`. Moves `pos` cursor `nbits` forward, even if `nbits` is not an integer number of bytes.

        Parameters
        ----------
        nbits : int
            Number of bits to read

        Returns
        -------
        : bytes
            Raw bytes from the packet data
        """
        if self.pos + nbits > len(self) * 8:
            raise ValueError("End of packet reached")
        if self.pos % 8 == 0 and nbits % 8 == 0:
            # If the read is byte-aligned, we can just return the bytes directly
            data = self[self.pos//8:self.pos//8 + (nbits+7) // 8]
            self.pos += nbits
            return data
        # We are non-byte aligned, so we need to extract the bits and convert to bytes
        bytes_as_int = _extract_bits(self, self.pos, nbits)
        self.pos += nbits
        return int.to_bytes(bytes_as_int, (nbits + 7) // 8, "big")

    def read_as_int(self, nbits: int) -> int:
        """Read a number of bits from the packet data as an integer.

        Parameters
        ----------
        nbits : int
            Number of bits to read

        Returns
        -------
        : int
            Integer representation of the bits read from the packet
        """
        int_data = _extract_bits(self, self.pos, nbits)
        self.pos += nbits
        return int_data


def create_ccsds_packet(data=b"\x00",
                        *,
                        version_number=0,
                        type=0,  # pylint: disable=redefined-builtin
                        secondary_header_flag=0,
                        apid=2047,  # 2047 is defined as a fill packet in the CCSDS spec
                        sequence_flags=SequenceFlags.UNSEGMENTED,
                        sequence_count=0):
    """Create a binary CCSDS packet.

    Pack the header fields into the proper bit locations and append the data bytes.

    Parameters
    ----------
    data : bytes
        User data bytes (up to 65536 bytes)
    version_number : int
        CCSDS Packet Version Number (3 bits)
    type : int
        CCSDS Packet Type (1 bit)
    secondary_header_flag : int
        CCSDS Secondary Header Flag (1 bit)
    apid : int
        CCSDS Application Process Identifier (APID) (11 bits)
    sequence_flags : int
        CCSDS Packet Sequence Flags (2 bits)
    sequence_count : int
        CCSDS Packet Sequence Count (14 bits)
    """
    if version_number < 0 or version_number > 7:  # 3 bits
        raise ValueError("version_number must be between 0 and 7")
    if type < 0 or type > 1:  # 1 bit
        raise ValueError("type_ must be 0 or 1")
    if secondary_header_flag < 0 or secondary_header_flag > 1:  # 1 bit
        raise ValueError("secondary_header_flag must be 0 or 1")
    if apid < 0 or apid > 2047:  # 11 bits
        raise ValueError("apid must be between 0 and 2047")
    if sequence_flags < 0 or sequence_flags > 3:  # 2 bits
        raise ValueError("sequence_flags must be between 0 and 3")
    if sequence_count < 0 or sequence_count > 16383:  # 14 bits
        raise ValueError("sequence_count must be between 0 and 16383")
    if len(data) < 1 or len(data) > 65536:  # 16 bits
        raise ValueError("length of data (in bytes) must be between 1 and 65536")

    # CCSDS primary header
    # bitshift left to the correct position for that field (48 - start_bit - nbits)
    try:
        header = (version_number << 48 - 3
                  | type << 48 - 4
                  | secondary_header_flag << 48 - 5
                  | apid << 48 - 16
                  | sequence_flags << 48 - 18
                  | sequence_count << 48 - 32
                  | len(data) - 1)
        packet = header.to_bytes(RawPacketData.HEADER_LENGTH_BYTES, "big") + data
    except TypeError as e:
        raise TypeError("CCSDS Header items must be integers and the input data bytes.") from e
    return RawPacketData(packet)


class CCSDSPacket(dict):
    """Packet representing parsed data items from CCSDS packet(s).

    Container that stores the raw packet data (bytes) as an instance attribute and the parsed
    data items in a dictionary interface. A ``CCSDSPacket`` generally begins as an empty dictionary that gets
    filled as the packet is parsed. The first 7 items in the dictionary make up the
    packet header (accessed with ``CCSDSPacket.header``), and the rest of the items
    make up the user data (accessed with ``CCSDSPacket.user_data``). To access the
    raw bytes of the packet, use the ``CCSDSPacket.raw_data`` attribute.

    Parameters
    ----------
    *args : Mapping or Iterable
        Initial items to store in the packet, passed to the dict() constructor.
    raw_data : bytes, optional
        The binary data for a single packet.
    **kwargs : dict
        Additional packet items to store, passed to the dict() constructor.
    """
    def __init__(self, *args, raw_data: bytes = b"", **kwargs):
        self.raw_data = RawPacketData(raw_data)
        super().__init__(*args, **kwargs)

    @property
    def header(self) -> dict:
        """The header content of the packet."""
        return dict(list(self.items())[:7])

    @property
    def user_data(self) -> dict:
        """The user data content of the packet."""
        return dict(list(self.items())[7:])


class Parseable(Protocol):
    """Defines an object that can be parsed from packet data."""
    def parse(self, packet: CCSDSPacket, **parse_value_kwargs) -> None:
        """Parse this entry from the packet data and add the necessary items to the packet."""


@dataclass
class SequenceContainer(Parseable):
    """<xtce:SequenceContainer>

    Parameters
    ----------
    name : str
        Container name
    entry_list : list
        List of Parameter objects
    long_description : str
        Long description of the container
    base_container_name : str
        Name of the base container from which this may inherit if restriction criteria are met.
    restriction_criteria : list
        A list of MatchCriteria elements that evaluate to determine whether the SequenceContainer should
        be included.
    abstract : bool
        True if container has abstract=true attribute. False otherwise.
    inheritors : list, Optional
        List of SequenceContainer objects that may inherit this one's entry list if their restriction criteria
        are met. Any SequenceContainers with this container as base_container_name should be listed here.
    """
    name: str
    entry_list: list  # List of Parameter objects, found by reference
    short_description: Optional[str] = None
    long_description: Optional[str] = None
    base_container_name: Optional[str] = None
    restriction_criteria: Optional[list] = field(default_factory=lambda: [])
    abstract: bool = False
    inheritors: Optional[List['SequenceContainer']] = field(default_factory=lambda: [])

    def __post_init__(self):
        # Handle the explicit None passing for default values
        self.restriction_criteria = self.restriction_criteria or []
        self.inheritors = self.inheritors or []

    def parse(self, packet: CCSDSPacket, **parse_value_kwargs) -> None:
        """Parse the entry list of parameters/containers in the order they are expected in the packet.

        This could be recursive if the entry list contains SequenceContainers.
        """
        for entry in self.entry_list:
            entry.parse(packet=packet, **parse_value_kwargs)


def _extract_bits(data: bytes, start_bit: int, nbits: int):
    """Extract nbits from the data starting from the least significant end.

    If data = 00110101 11001010, start_bit = 2, nbits = 9, then the bits extracted are "110101110".
    Those bits are turned into a Python integer and returned.

    Parameters
    ----------
    data : bytes
        Data to extract bits from
    start_bit : int
        Starting bit location within the data
    nbits : int
        Number of bits to extract

    Returns
    -------
    int
        Extracted bits as an integer
    """
    # Get the bits from the packet data
    # Select the bytes that contain the bits we want.
    start_byte = start_bit // 8  # Byte index containing the start_bit
    start_bit_within_byte = start_bit % 8  # Bit index within the start_byte
    end_byte = start_byte + (start_bit_within_byte + nbits + 7) // 8
    data = data[start_byte:end_byte]  # Chunk of bytes containing the data item we want to parse
    # Convert the bytes to an integer for bitwise operations
    value = int.from_bytes(data, byteorder="big")
    if start_bit_within_byte == 0 and nbits % 8 == 0:
        # If we're extracting whole bytes starting at a byte boundary, we don't need any bitshifting
        # This is faster, especially for large binary chunks
        return value

    # Shift the value to the right to move the LSB of the data item we want to parse
    # to the least significant position, then mask out the number of bits we want to keep
    return (value >> (len(data) * 8 - start_bit_within_byte - nbits)) & (2 ** nbits - 1)
