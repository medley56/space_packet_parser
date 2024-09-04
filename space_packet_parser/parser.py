"""Module for parsing CCSDS packets using packet definitions"""
# Standard
from collections import namedtuple
import datetime as dt
import io
import logging
import socket
import time
from typing import BinaryIO, Optional, Tuple, Union
import warnings
# Local
from space_packet_parser import xtcedef, csvdef

logger = logging.getLogger(__name__)

CcsdsPacketHeaderElement = namedtuple('CcsdsPacketHeaderElement', ['name', 'nbits'])

CCSDS_HEADER_DEFINITION = [
    CcsdsPacketHeaderElement('VERSION', 3),
    CcsdsPacketHeaderElement('TYPE', 1),
    CcsdsPacketHeaderElement('SEC_HDR_FLG', 1),
    CcsdsPacketHeaderElement('PKT_APID', 11),
    CcsdsPacketHeaderElement('SEQ_FLGS', 2),
    CcsdsPacketHeaderElement('SRC_SEQ_CTR', 14),
    CcsdsPacketHeaderElement('PKT_LEN', 16)
]

CCSDS_HEADER_LENGTH_BYTES = 6

# Bring this into the namespace for backwards compatibility
ParsedDataItem = xtcedef.ParsedDataItem
Packet = xtcedef.Packet


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


class PacketParser:
    """Class for parsing CCSDS packets"""

    def __init__(self,
                 packet_definition: xtcedef.XtcePacketDefinition or csvdef.CsvPacketDefinition,
                 word_size: int = None):
        """Constructor

        Parameters
        ----------
        packet_definition: xtcedef.XtcePacketDefinition or csvdef.CsvPacketDefinition
            The packet definition object to use for parsing incoming data.
        word_size: int, Optional
            Number of bits per word. If set, binary parameters are assumed to end on a word boundary and any unused bits
            at the end of each binary parameter are skipped. Default is no word boundary enforcement. Typical usecase
            is 32bit words.
        """
        self.packet_definition = packet_definition
        self.word_size = word_size

    @staticmethod
    def _parse_header(packet_data: bytes) -> dict:
        """Parses the CCSDS standard header.

        Parameters
        ----------
        packet_data : bytes
            6 bytes of binary data.

        Returns
        -------
        header : dict
            Dictionary of header items.
        """
        header = {}
        current_bit = 0
        for item in CCSDS_HEADER_DEFINITION:
            header[item.name] = xtcedef.ParsedDataItem(
                name=item.name,
                unit=None,
                # pylint: disable=protected-access
                raw_value=xtcedef._extract_bits(packet_data, current_bit, item.nbits))
            current_bit += item.nbits
        return header

    # DEPRECATED! Remove in next major release along with CSV parser
    # pylint: disable=inconsistent-return-statements
    def _determine_packet_by_restrictions(self, parsed_header: dict) -> Tuple[str, list]:
        """Examines a dictionary representation of a CCSDS header and determines which packet type applies.
        This packet type must be unique. If the header data satisfies the restrictions for more than one packet
        type definition, an exception is raised.

        Parameters
        ----------
        parsed_header : dict
            Pre-parsed header data in dictionary form for evaluating restriction criteria.
            NOTE: Restriction criteria can ONLY be evaluated against header items. There is no reasonable way to
            start parsing all the BaseContainer inheritance restrictions without assuming that all restrictions will
            be based on header items, which can be parsed ahead of time due to the consistent nature of a CCSDS header.

        Returns
        -------
        : str
            Name of packet definition.
        : list
            A list of Parameter objects
        """
        warnings.warn("The '_determine_packet_by_restrictions' method is deprecated.", DeprecationWarning)
        flattened_containers = self.packet_definition.flattened_containers
        meets_requirements = []
        for container_name, flattened_container in flattened_containers.items():
            try:
                checks = [
                    criterion.evaluate(parsed_header)
                    for criterion in flattened_container.restrictions
                ]
            except AttributeError as err:
                raise ValueError("Hitherto unparsed parameter name found in restriction criteria for container "
                                 f"{container_name}. Because we can't parse packet data until we know the type, "
                                 "only higher up parameters (e.g. APID) are permitted as container "
                                 "restriction criteria.") from err

            if all(checks):
                meets_requirements.append(container_name)

        if len(meets_requirements) == 1:
            name = meets_requirements.pop()
            return name, flattened_containers[name].entry_list

        if len(meets_requirements) > 1:
            raise UnrecognizedPacketTypeError(
                "Found more than one possible packet definition based on restriction criteria. "
                f"{meets_requirements}", partial_data=parsed_header)

        if len(meets_requirements) < 1:
            raise UnrecognizedPacketTypeError(
                "Header does not allow any packet definitions based on restriction criteria. "
                "Unable to choose a packet type to parse. "
                "Note: Restricting container inheritance based on non-header data items is not possible in a "
                "general way and is not supported by this package.", partial_data=parsed_header)
        # pylint: enable=inconsistent-return-statements

    @staticmethod
    def parse_packet(packet: xtcedef.Packet,
                     containers: dict,
                     root_container_name: str = "CCSDSPacket",
                     **parse_value_kwargs) -> Packet:
        """Parse binary packet data according to the self.packet_definition object

        Parameters
        ----------
        packet: xtcedef.Packet
            Binary representation of the packet used to get the coming bits and any
            previously parsed data items to infer field lengths.
        containers : dict
            Dictionary of named containers, including their inheritance information.
        root_container_name : str, Optional
            Default is CCSDSPacket. Any root container may be specified.

        Returns
        -------
        Packet
            A Packet object container header and data attributes.
        """
        current_container: xtcedef.SequenceContainer = containers[root_container_name]
        while True:
            packet.parsed_data = current_container.parse(packet, **parse_value_kwargs)

            valid_inheritors = []
            for inheritor_name in current_container.inheritors:
                if all(rc.evaluate(packet.parsed_data) for rc in containers[inheritor_name].restriction_criteria):
                    valid_inheritors.append(inheritor_name)

            if len(valid_inheritors) == 1:
                # Set the unique valid inheritor as the next current_container
                current_container = containers[valid_inheritors[0]]
                continue

            if len(valid_inheritors) == 0:
                if current_container.abstract is True:
                    raise UnrecognizedPacketTypeError(
                        f"Detected an abstract container with no valid inheritors by restriction criteria. This might "
                        f"mean this packet type is not accounted for in the provided packet definition. "
                        f"APID={packet.parsed_data['PKT_APID'].raw_value}.",
                        partial_data=packet.parsed_data)
                break

            raise UnrecognizedPacketTypeError(
                f"Multiple valid inheritors, {valid_inheritors} are possible for {current_container}.",
                partial_data=packet.parsed_data)
        return packet

    @staticmethod
    def legacy_parse_packet(packet: xtcedef.Packet, entry_list: list, **parse_value_kwargs) -> Packet:
        """Parse binary packet data according to the self.flattened_containers property

        Parameters
        ----------
        packet : xtcedef.Packet
            Binary packet data to parse into Packets
        entry_list : list
            List of Parameter objects

        Returns
        -------
        Packet
            A Packet object container header and data attributes.
        """
        warnings.warn("The 'legacy_parse_packet' method is deprecated.", DeprecationWarning)
        for parameter in entry_list[0:7]:
            parsed_value, _ = parameter.parameter_type.parse_value(packet)

            packet.parsed_data[parameter.name] = xtcedef.ParsedDataItem(
                name=parameter.name,
                unit=parameter.parameter_type.unit,
                raw_value=parsed_value
            )

        for parameter in entry_list[7:]:
            parsed_value, derived_value = parameter.parameter_type.parse_value(
                packet, **parse_value_kwargs)

            packet.parsed_data[parameter.name] = xtcedef.ParsedDataItem(
                name=parameter.name,
                unit=parameter.parameter_type.unit,
                raw_value=parsed_value,
                derived_value=derived_value,
                short_description=parameter.short_description,
                long_description=parameter.long_description
            )

        return packet

    @staticmethod
    def print_progress(current_bytes: int, total_bytes: Optional[int],
                       start_time_ns: int, current_packets: int,
                       end: str = '\r', log: bool = False):
        """Prints a progress bar, including statistics on parsing rate.

        Parameters
        ----------
        current_bytes : int
            Number of bytes parsed so far.
        total_bytes : Optional[int]
            Number of total bytes to parse, if known. None otherwise.
        current_packets : int
            Number of packets parsed so far.
        start_time_ns : int
            Start time on system clock, in nanoseconds.
        end : str
            Print function end string. Default is `\\r` to create a dynamically updating loading bar.
        log : bool
            If True, log the progress bar at INFO level.
        """
        progress_char = "="
        bar_length = 20

        if total_bytes is not None:  # If we actually have an endpoint (i.e. not using a socket)
            percentage = int((current_bytes / total_bytes) * 100)  # Percent Completed Calculation
            progress = int((bar_length * current_bytes) / total_bytes)  # Progress Done Calculation
        else:
            percentage = "???"
            progress = 0

        elapsed_ns = time.time_ns() - start_time_ns
        delta = dt.timedelta(microseconds=elapsed_ns / 1E3)
        kbps = int(current_bytes // 8 * 1E6 / elapsed_ns)
        pps = int(current_packets * 1E9 / elapsed_ns)
        info_str = f"[Elapsed: {delta}, " \
                   f"Parsed {current_bytes} bytes ({current_packets} packets) " \
                   f"at {kbps}kb/s ({pps}pkts/s)]"
        loadbar = f"Progress: [{progress*progress_char:{bar_length}}]{percentage}% {info_str}"
        print(loadbar, end=end)
        if log is True:
            logger.info(loadbar)

    def generator(self,  # pylint: disable=too-many-branches,too-many-statements
                  binary_data: Union[BinaryIO, socket.socket],
                  parse_bad_pkts: bool = True,
                  skip_header_bits: int = 0,
                  root_container_name="CCSDSPacket",
                  ccsds_headers_only: bool = False,
                  yield_unrecognized_packet_errors: bool = False,
                  show_progress: bool = False,
                  buffer_read_size_bytes: Optional[int] = None):
        """Create and return a Packet generator that reads from a ConstBitStream or a filelike object or a socket.

        Creating a generator object to return allows the user to create
        many generators from a single Parser and reduces memory usage.

        Parameters
        ----------
        binary_data : BinaryIO or socket.socket
            Binary data source to parse into Packets.
        parse_bad_pkts : bool, Optional
            Default True.
            If True, when the generator encounters a packet with an incorrect length it will still yield the packet
            (the data will likely be invalid). If False, the generator will still write a debug log message but will
            otherwise silently skip the bad packet.
        skip_header_bits : int, Optional
            If provided, the parser skips this many bits at the beginning of every packet. This allows dynamic stripping
            of additional header data that may be prepended to packets.
        root_container_name : str, Optional
            The name of the root level (lowest level of container inheritance) SequenceContainer. This SequenceContainer
            is assumed to be inherited by every possible packet structure in the XTCE document and is the starting
            point for parsing. Default is 'CCSDSPacket'.
        ccsds_headers_only : bool, Optional
            If True, only parses the packet headers (does not use the provided packet definition).
        yield_unrecognized_packet_errors : bool, Optional
            Default False.
            If False, UnrecognizedPacketTypeErrors are caught silently and parsing continues to the next packet.
            If True, the generator will yield an UnrecognizedPacketTypeError in the event of an unrecognized
            packet. Note: These exceptions are not raised by default but are instead returned so that the generator
            can continue. You can raise the exceptions if desired. Leave this as False unless you need to examine the
            partial data from unrecognized packets.
        show_progress : bool, Optional
            If True, prints a status bar. Note that for socket sources, the percentage will be zero until the generator
            ends.
        buffer_read_size_bytes : int, Optional
            Number of bytes to read from e.g. a BufferedReader or socket binary data source on each read attempt.
            Default is 4096 bytes from a socket, -1 (full read) from a file.

        Yields
        -------
        Packet or UnrecognizedPacketTypeError
            Generator yields Packet objects containing the parsed packet data for each subsequent packet.
            If yield_unrecognized_packet_errors is True, it will yield an unraised exception object,
            which can be raised or used for debugging purposes.
        """

        def read_bytes_from_source(source: Union[BinaryIO, socket.socket],
                                   read_size_bytes: int) -> bytes:
            """Read data from a source and return the bytes read.

            Parameters
            ----------
            source : BinaryIO or socket.socket
                Source of data.
            read_size_bytes : int
                Max number of bytes to read from the source per read attempt. For sockets, this should be a small
                power of 2 (e.g. 4096) due to networking and hardware conventions. For a file or ConstBitStream object
                this could be set to the full size of the data but a large value will increase memory utilization
                when parsing large data sources all at once.

            Returns
            -------
            : bytes
                The bytes that were read from the source.
            """
            if isinstance(source, io.BufferedIOBase):
                return source.read(read_size_bytes)
            if isinstance(source, socket.socket):
                return source.recv(read_size_bytes)
            if isinstance(source, io.TextIOWrapper):
                raise IOError("Packet data file opened in TextIO mode. You must open packet data in binary mode.")
            raise IOError(f"Unrecognized data source: {source}")

        # ========
        # Start of generator
        # ========
        if isinstance(binary_data, io.BufferedIOBase):
            if buffer_read_size_bytes is None:
                # Default to a full read of the file
                buffer_read_size_bytes = -1
            total_length_bytes = binary_data.seek(0, io.SEEK_END)  # This is probably preferable to len
            binary_data.seek(0, 0)
            logger.info(f"Creating packet generator from a filelike object, {binary_data}. "
                        f"Total length is {total_length_bytes} bytes")
        else:  # It's a socket and we don't know how much data we will get
            logger.info("Creating packet generator to read from a socket. Total length to parse is unknown.")
            total_length_bytes = None  # We don't know how long it is
            if buffer_read_size_bytes is None:
                # Default to 4096 bytes from a socket
                buffer_read_size_bytes = 4096

        # ========
        # Packet loop. Each iteration of this loop yields a ParsedPacket object
        # ========
        start_time = time.time_ns()
        n_bytes_parsed = 0  # Keep track of how many bytes we have parsed
        n_packets_parsed = 0  # Keep track of how many packets we have parsed
        read_buffer = b""  # Empty bytes object to start
        skip_header_bytes = skip_header_bits // 8  # Internally keep track of bytes
        current_pos = 0  # Keep track of where we are in the buffer
        while True:
            if total_length_bytes and n_bytes_parsed == total_length_bytes:
                break  # Exit if we know the length and we've reached it

            if show_progress is True:
                self.print_progress(current_bytes=n_bytes_parsed, total_bytes=total_length_bytes,
                                    start_time_ns=start_time, current_packets=n_packets_parsed)

            if current_pos > 20_000_000:
                # Only trim the buffer after 20 MB read to prevent modifying
                # the bitstream and trimming after every packet
                read_buffer = read_buffer[current_pos:]
                current_pos = 0

            # Fill buffer enough to parse a header
            while len(read_buffer) - current_pos < skip_header_bytes + CCSDS_HEADER_LENGTH_BYTES:
                result = read_bytes_from_source(binary_data, read_size_bytes=buffer_read_size_bytes)
                if not result:  # If there is verifiably no more data to add, break
                    break
                read_buffer += result
            # Skip the header bytes
            current_pos += skip_header_bytes
            header_bytes = read_buffer[current_pos:current_pos + CCSDS_HEADER_LENGTH_BYTES]
            header = self._parse_header(header_bytes)

            # per the CCSDS spec
            # 4.1.3.5.3 The length count C shall be expressed as:
            #   C = (Total Number of Octets in the Packet Data Field) – 1
            n_bytes_data = header['PKT_LEN'].raw_value + 1
            n_bytes_packet = CCSDS_HEADER_LENGTH_BYTES + n_bytes_data

            # Consider it a counted packet once we've parsed the header
            # and update the number of bits parsed
            n_packets_parsed += 1
            n_bytes_parsed += skip_header_bytes + n_bytes_packet
            if ccsds_headers_only is True:
                # update the current position to the end of the packet data
                current_pos += n_bytes_packet
                yield Packet(read_buffer[current_pos-n_bytes_packet:current_pos], parsed_data=header)
                continue

            # Based on PKT_LEN fill buffer enough to read a full packet
            while len(read_buffer) - current_pos < n_bytes_packet:
                result = read_bytes_from_source(binary_data, read_size_bytes=buffer_read_size_bytes)
                if not result:  # If there is verifiably no more data to add, break
                    break
                read_buffer += result

            # current_pos is still before the header, so we are reading the entire packet here
            packet_bytes = read_buffer[current_pos:current_pos + n_bytes_packet]
            current_pos += n_bytes_packet
            # Wrap the bytes in a class that can keep track of position as we read from it
            packet = xtcedef.Packet(packet_bytes)
            try:
                if isinstance(self.packet_definition, xtcedef.XtcePacketDefinition):
                    packet = self.parse_packet(packet,
                                               self.packet_definition.named_containers,
                                               root_container_name=root_container_name,
                                               word_size=self.word_size)
                else:
                    _, parameter_list = self._determine_packet_by_restrictions(header)
                    packet = self.legacy_parse_packet(packet, parameter_list, word_size=self.word_size)
            except UnrecognizedPacketTypeError as e:
                logger.debug(f"Unrecognized error on packet with APID {header['PKT_APID'].raw_value}'")
                if yield_unrecognized_packet_errors is True:
                    # Yield the caught exception without raising it (raising ends generator)
                    yield e
                # Continue to next packet
                continue

            if packet.header['PKT_LEN'].raw_value != header['PKT_LEN'].raw_value:
                raise ValueError(f"Hardcoded header parsing found a different packet length "
                                 f"{header['PKT_LEN'].raw_value} than the definition-based parsing found "
                                 f"{packet.header['PKT_LEN'].raw_value}. This might be because the CCSDS header is "
                                 f"incorrectly represented in your packet definition document.")

            actual_length_parsed = packet.pos // 8
            if actual_length_parsed != n_bytes_packet:
                logger.warning(f"Parsed packet length "
                               f"({actual_length_parsed}B) did not match "
                               f"length specified in header ({n_bytes_packet}B). "
                               f"Updating the position to the correct position "
                               "indicated by CCSDS header.")
                if not parse_bad_pkts:
                    logger.warning("Skipping (not yielding) bad packet because parse_bad_pkts is falsy.")
                    continue

            yield packet

        if show_progress is True:
            self.print_progress(current_bytes=n_bytes_parsed, total_bytes=total_length_bytes,
                                start_time_ns=start_time, current_packets=n_packets_parsed,
                                end="\n", log=True)
