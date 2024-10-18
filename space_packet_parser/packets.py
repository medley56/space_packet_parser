
"""Packet containers and parsing utilities for space packets."""

from collections import defaultdict, Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Protocol, Union

# Check if extra libraries are available
try:
    import numpy as np
    _NP_AVAILABLE = True
except ImportError:
    _NP_AVAILABLE = False

try:
    import xarray as xr
    _XR_AVAILABLE = True
except ImportError:
    _XR_AVAILABLE = False

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


class PacketCollection(list):
    """Stores a list of packets."""
    def __init__(
        self,
        packets: Iterable[CCSDSPacket],
        *,
        # TODO: Figure out typing with imports from definitions causing circular imports
        # definitions.XtcePacketDefinition | None
        packet_definition=None,
    ):
        """
        Create a PacketCollection.

        Parameters
        ----------
        apid_dict : dict
            Mapping of APID to a list of packets with that apid.
        packet_definition : XtcePacketDefinition
            The packet definition to use for this collection.
        """
        super().__init__(packets)
        self.packet_definition = packet_definition

    def __str__(self):
        apids = Counter(packet["PKT_APID"] for packet in self)
        return (f"<PacketCollection>: {len(self)} packets\n"
                + "Packets per apid (apid: npackets)\n"
                + "\n".join(f"  {apid}: {count}" for apid, count in apids.items()))

    @classmethod
    def from_packet_file(
        cls,
        packet_file: str | Path,
        # TODO: Figure out typing with imports from definitions causing circular imports
        # str | Path | definitions.XtcePacketDefinition | None
        packet_definition=None,
    ) -> "PacketCollection":
        """
        Create a PacketCollection from a packet file.

        Parameters
        ----------
        packet_file : str
            Path to a file containing CCSDS packets.
        packet_definition : str or Path or XtcePacketDefinition, optional
            XTCE packet definition, or the path to the XTCE packet definition file.

        Returns
        -------
        packet_collection : PacketCollection
            A list of packets grouped together.
        """
        # TODO: Bring this import to the top of the file once circular dependencies are resolved
        from space_packet_parser import definitions
        if packet_definition is not None and not isinstance(packet_definition, definitions.XtcePacketDefinition):
            # We got the path to a packet definition, so read it in
            packet_definition = definitions.XtcePacketDefinition(packet_definition)

        with open(packet_file, "rb") as binary_data:
            # packet_generator = packets.packet_generator(binary_data, definition=packet_definition)
            packet_generator = packet_definition.packet_generator(binary_data)
            return cls(packet_generator, packet_definition=packet_definition)

    def to_numpy(self, variable, raw_value=False):
        """Turn the requested variable into a numpy array.

        Parameters
        ----------
        raw_value : bool, default False
            Whether or not to use the raw value from the packet.

        Returns
        -------
        data : numpy.ndarray
            A numpy array of values for the requested variable.
        """
        if not _NP_AVAILABLE:
            raise ImportError("Numpy is required to use this function, you can install it with `pip install numpy`.")
        data = [packet[variable].raw_value if raw_value else packet[variable]
                for packet in self
                if variable in packet]
        if self.packet_definition is not None:
            min_dtype = self.packet_definition._get_minimum_numpy_datatype(variable, raw_value=raw_value)
        else:
            min_dtype = None
        return np.array(data, dtype=min_dtype)

    def to_xarray(self, *, apid=None, raw_value=False, ignore_header=False):
        """Turn this collection into an xarray dataset.

        The collection must have a single apid to be turned into a dataset, or
        the desired apid must be specified. The collection must have a consistent
        structure across all packets with that apid (i.e. it cannot be a nested
        packet structure).

        Parameters
        ----------
        apid : int, optional
            Turn this specific apid into a dataset, by default None
        raw_value : bool, optional
            _description_, by default False
        ignore_header : bool, optional
            _description_, by default False
        """
        if not _XR_AVAILABLE:
            raise ImportError("Xarray is required to use this function, you can install it with `pip install xarray`.")
        if len(self) == 0:
            return xr.Dataset()

        # Create a mapping of {variables: [values]}}
        variable_dict = defaultdict(list)
        # Keep track of the packet number for the coordinate
        # useful if we have interspersed packets with different APIDs
        packet_number = []

        if apid is None:
            apid = self[0]["PKT_APID"]
            if any(packet["PKT_APID"] != apid for packet in self):
                raise ValueError("All packets must have the same APID to convert to an xarray dataset.")

        for i, packet in enumerate(self):
            if packet["PKT_APID"] != apid:
                continue
            packet_number.append(i)

            if ignore_header:
                packet_content = packet.user_data
            else:
                packet_content = packet

            if len(variable_dict):
                # TODO: Can we relax this requirement and combine the variables together somehow?
                if variable_dict.keys() != packet_content.keys():
                    raise ValueError("All packets must have the same variables to convert to an xarray dataset. "
                                     "This likely means that the packet definition has a nested packet structure "
                                     "with variables spread across multiple packets.")

            for key, value in packet_content.items():
                if raw_value:
                    value = value.raw_value
                variable_dict[key].append(value)

        ds = xr.Dataset(
            {
                variable: (
                    "packet",
                    np.asarray(list_of_values, dtype=self.packet_definition._get_minimum_numpy_datatype(
                        variable, raw_value=raw_value)),
                )
                for variable, list_of_values in variable_dict.items()
            },
            # Default to packet number as the coordinate
            # TODO: Allow a user to specify this as a keyword argument?
            #       Or give an example of how to change this after the fact
            coords={"packet": packet_number},
        )
        return ds


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
