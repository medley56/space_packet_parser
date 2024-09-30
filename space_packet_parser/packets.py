
"""Packet containers and parsing utilities for space packets."""

from dataclasses import dataclass, field
from typing import Union, Optional, Protocol, List


@dataclass
class ParsedDataItem:
    """Representation of a parsed parameter

    Parameters
    ----------
    name : str
        Parameter name
    unit : str
        Parameter units
    raw_value : any
        Raw representation of the parsed value. May be lots of different types but most often an integer
    derived_value : float or str
        May be a calibrated value or an enum lookup
    short_description : str
        Parameter short description
    long_description : str
        Parameter long description
    """
    name: str
    raw_value: Union[bytes, float, int, str]
    unit: Optional[str] = None
    derived_value: Optional[Union[float, str]] = None
    short_description: Optional[str] = None
    long_description: Optional[str] = None


class RawPacketData(bytes):
    """A class to represent raw packet data as bytes but whose length is represented by bit length.

    This class is a subclass of bytes and is used to represent the raw packet data
    in a more readable way. It is used to store the raw packet data in the Packet
    class and used to keep track of the current parsing position.

    Parameters
    ----------
    data : bytes
        Raw packet data. Full CCSDS packets are always an integer number of bytes.
    """
    def __init__(self, data: bytes, *, pos: int = 0):
        self.pos = pos
        self._nbits = len(data) * 8
        super().__init__()

    def __len__(self):
        return self._nbits

    def __repr__(self):
        return f"RawPacketData({self}, {len(self)}b, pos={self.pos})"

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
        if self.pos + nbits > len(self):
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


class CCSDSPacket(dict):
    """CCSDS Packet

    Container that stores the raw packet data (bytes) as an instance attribute and the parsed
    data items in a dict interface. A ``CCSDSPacket`` generally begins as an empty dictionary that gets
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
