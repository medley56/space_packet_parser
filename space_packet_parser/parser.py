"""Module for parsing CCSDS packets using packet definitions"""
# Standard
from collections import namedtuple
import datetime as dt
import io
import logging
import socket
import time
from typing import BinaryIO, Tuple
import warnings
# Installed
import bitstring
# Local
from space_packet_parser import xtcedef, csvdef

logger = logging.getLogger(__name__)

CcsdsPacketHeaderElement = namedtuple('CcsdsPacketHeaderElement', ['name', 'format_string'])

CCSDS_HEADER_DEFINITION = [
    CcsdsPacketHeaderElement('VERSION', 'uint:3'),
    CcsdsPacketHeaderElement('TYPE', 'uint:1'),
    CcsdsPacketHeaderElement('SEC_HDR_FLG', 'uint:1'),
    CcsdsPacketHeaderElement('PKT_APID', 'uint:11'),
    CcsdsPacketHeaderElement('SEQ_FLGS', 'uint:2'),
    CcsdsPacketHeaderElement('SRC_SEQ_CTR', 'uint:14'),
    CcsdsPacketHeaderElement('PKT_LEN', 'uint:16')
]

CCSDS_HEADER_LENGTH_BITS = 48

Packet = namedtuple('Packet', ['header', 'data'])


class ParsedDataItem(xtcedef.AttrComparable):
    """Representation of a parsed parameter"""

    def __init__(self, name: str, raw_value: any, unit: str = None, derived_value: float or str = None,
                 short_description: str = None, long_description: str = None):
        """Constructor

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
        if name is None or raw_value is None:
            raise ValueError("Invalid ParsedDataItem. Must define name and raw_value.")
        self.name = name
        self.raw_value = raw_value
        self.unit = unit
        self.derived_value = derived_value
        self.short_description = short_description
        self.long_description = long_description

    def __repr__(self):
        return (f"{self.__class__.__name__}("
                f"{self.name}, raw={self.raw_value}, derived={self.derived_value}, unit={self.unit}"
                f")")


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
    def _parse_header(packet_data: bitstring.ConstBitStream,
                      start_position: int = None,
                      reset_cursor: bool = False) -> dict:
        """Parses the CCSDS standard header.

        Parameters
        ----------
        packet_data : bitstring.ConstBitStream
            Binary data stream of packet data.
        start_position : int
            Position from which to start parsing. If not provided, will start whenever the cursor currently is.
        reset_cursor : bool
            If True, upon parsing the header data, reset the cursor to the original position in the stream.
            This still applies even if start_position is specified. start_position will be used only for parsing the
            header and then the cursor will be returned to the location it was at before this function was called.

        Returns
        -------
        header : dict
            Dictionary of header items.
        """
        original_cursor_position = packet_data.pos

        if start_position:
            packet_data.pos = start_position

        header = {
            item.name: ParsedDataItem(name=item.name, unit=None, raw_value=packet_data.read(item.format_string))
            for item in CCSDS_HEADER_DEFINITION
        }

        if reset_cursor:
            packet_data.pos = original_cursor_position

        return header

    @staticmethod
    def _total_packet_bits_from_pkt_len(pkt_len: int):
        """Calculate the total length of a CCSDS packet in bits based on the PKT_LEN field in its header.

        Parameters
        ----------
        pkt_len : int
            PKT_LEN value from CCSDS header

        Returns
        -------
        : int
            Length, in bits of the packet

        """
        # 4.1.3.5.3 The length count C shall be expressed as:
        #   C = (Total Number of Octets in the Packet Data Field) – 1
        # We also just reparsed the CCSDS header though as well, so that's an additional 6 octets
        return 8 * (pkt_len + 1 + 6)

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
    def parse_packet(packet_data: bitstring.ConstBitStream,
                     containers: dict,
                     root_container_name: str = "CCSDSPacket",
                     **parse_value_kwargs) -> Packet:
        """Parse binary packet data according to the self.packet_definition object

        Parameters
        ----------
        packet_data : bitstring.BitString
            Binary packet data to parse into Packets
        containers : dict
            Dictionary of named containers, including their inheritance information.
        root_container_name : str, Optional
            Default is CCSDSPacket. Any root container may be specified.

        Returns
        -------
        Packet
            A Packet object container header and data attributes.
        """

        def _parse_parameter(p: xtcedef.Parameter):
            parsed_value, derived_value = p.parameter_type.parse_value(
                packet_data, parsed_data=parsed_items, **parse_value_kwargs)

            parsed_items[p.name] = ParsedDataItem(
                name=p.name,
                unit=p.parameter_type.unit,
                raw_value=parsed_value,
                derived_value=derived_value,
                short_description=p.short_description,
                long_description=p.long_description
            )

        def _parse_sequence_container(sc: xtcedef.SequenceContainer):
            for e in sc.entry_list:
                if isinstance(e, xtcedef.SequenceContainer):
                    _parse_sequence_container(e)
                else:
                    _parse_parameter(e)

        parsed_items = {}
        current_container: xtcedef.SequenceContainer = containers[root_container_name]
        while True:
            for entry in current_container.entry_list:
                if isinstance(entry, xtcedef.Parameter):
                    _parse_parameter(entry)
                elif isinstance(entry, xtcedef.SequenceContainer):
                    _parse_sequence_container(entry)

            valid_inheritors = []
            for inheritor_name in current_container.inheritors:
                if all(rc.evaluate(parsed_items) for rc in containers[inheritor_name].restriction_criteria):
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
                        f"APID={parsed_items['PKT_APID'].raw_value}.",
                        partial_data=parsed_items)
                break

            raise UnrecognizedPacketTypeError(
                f"Multiple valid inheritors, {valid_inheritors} are possible for {current_container}.",
                partial_data=parsed_items)
        header = dict(list(parsed_items.items())[:7])
        user_data = dict(list(parsed_items.items())[7:])
        return Packet(header, user_data)

    @staticmethod
    def legacy_parse_packet(packet_data: bitstring.ConstBitStream, entry_list: list, **parse_value_kwargs) -> Packet:
        """Parse binary packet data according to the self.flattened_containers property

        Parameters
        ----------
        packet_data : bitstring.BitString
            Binary packet data to parse into Packets
        entry_list : list
            List of Parameter objects

        Returns
        -------
        Packet
            A Packet object container header and data attributes.
        """
        warnings.warn("The 'legacy_parse_packet' method is deprecated.", DeprecationWarning)
        header = {}
        for parameter in entry_list[0:7]:
            parsed_value, _ = parameter.parameter_type.parse_value(packet_data, header)

            header[parameter.name] = ParsedDataItem(
                name=parameter.name,
                unit=parameter.parameter_type.unit,
                raw_value=parsed_value
            )

        user_data = {}
        for parameter in entry_list[7:]:
            combined_parsed_data = {**header}
            combined_parsed_data.update(user_data)
            parsed_value, derived_value = parameter.parameter_type.parse_value(
                packet_data, parsed_data=combined_parsed_data, **parse_value_kwargs)

            user_data[parameter.name] = ParsedDataItem(
                name=parameter.name,
                unit=parameter.parameter_type.unit,
                raw_value=parsed_value,
                derived_value=derived_value,
                short_description=parameter.short_description,
                long_description=parameter.long_description
            )

        return Packet(header=header, data=user_data)

    @staticmethod
    def print_progress(current_bits: int, total_bits: int or None,
                       start_time_ns: int, current_packets: int,
                       end: str = '\r', log: bool = False):
        """Prints a progress bar, including statistics on parsing rate.

        Parameters
        ----------
        current_bits : int
            Number of bits parsed so far.
        total_bits : int
            Number of total bits to parse (if known)
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

        if total_bits is not None:  # If we actually have an endpoint (i.e. not using a socket)
            percentage = int((current_bits / total_bits) * 100)  # Percent Completed Calculation
            progress = int((bar_length * current_bits) / total_bits)  # Progress Done Calculation
        else:
            percentage = "???"
            progress = 0

        elapsed_ns = time.time_ns() - start_time_ns
        delta = dt.timedelta(microseconds=elapsed_ns / 1E3)
        kbps = int(current_bits * 1E6 / elapsed_ns)
        pps = int(current_packets * 1E9 / elapsed_ns)
        info_str = f"[Elapsed: {delta}, " \
                   f"Parsed {current_bits} bits ({current_packets} packets) " \
                   f"at {kbps}kb/s ({pps}pkts/s)]"
        loadbar = f"Progress: [{progress*progress_char:{bar_length}}]{percentage}% {info_str}"
        print(loadbar, end=end)
        if log is True:
            logger.info(loadbar)

    def generator(self,  # pylint: disable=too-many-branches,too-many-statements
                  binary_data: bitstring.ConstBitStream or BinaryIO or socket.socket,
                  parse_bad_pkts: bool = True,
                  skip_header_bits: int = 0,
                  root_container_name="CCSDSPacket",
                  ccsds_headers_only: bool = False,
                  yield_unrecognized_packet_errors: bool = False,
                  show_progress: bool = False,
                  buffer_read_size_bytes: int = 4096):
        """Create and return a Packet generator that reads from a ConstBitStream or a filelike object or a socket.

        Creating a generator object to return allows the user to create
        many generators from a single Parser and reduces memory usage.

        Parameters
        ----------
        binary_data : bitstring.ConstBitStream or BinaryIO or socket.socket
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
            Default is 4096 bytes.

        Yields
        -------
        : Packet or UnrecognizedPacketTypeError
            Generator yields Packet objects containing the parsed packet data for each subsequent packet.
            If yield_unrecognized_packet_errors is True, it will yield an unraised exception object,
            which can be raised or used for debugging purposes.
        """

        def fill_read_buffer(source: bitstring.ConstBitStream or BinaryIO or socket.socket,
                             buffer: bitstring.BitStream,
                             read_size_bytes: int) -> int:
            """Read data from a source and add it to an existing buffer (BitStream).

            Parameters
            ----------
            source : bitstring.ConstBitStream or BinaryIO or socket.socket
                Source of data.
            buffer : bitstring.BitStream
                A reference to a rotating buffer to which the new data is appended. Mutating this changes the data
                available to the caller by reference so we don't return it.
            read_size_bytes : int
                Max number of bytes to read from the source per read attempt. For sockets, this should be a small
                power of 2 (e.g. 4096) due to networking and hardware conventions. For a file or ConstBitStream object
                this could be set to the full size of the data but a large value will increase memory utilization
                when parsing large data sources all at once.

            Returns
            -------
            result : int
                Number of bits added to the buffer. Note that the buffer may still have nonzero length from previous
                data even when this returns zero.
            """
            curser_pos = buffer.pos  # Keep track of the original buffer cursor location
            if isinstance(source, io.BufferedIOBase):
                new_bytes = source.read(read_size_bytes)
                buffer += new_bytes
                n_new_bits = len(new_bytes)*8
            elif isinstance(source, socket.socket):
                new_bytes = source.recv(read_size_bytes)
                buffer += new_bytes  # Append BitStream with newly read bytes
                n_new_bits = len(new_bytes)*8
            elif isinstance(source, bitstring.ConstBitStream):
                # This either reads read_size_bytes bytes or it just reads to the end of the data
                new_bits = source[source.pos:source.pos + read_size_bytes * 8]
                source.pos += len(new_bits)  # Set the source.pos to exactly where we read to
                buffer += new_bits
                n_new_bits = len(new_bits)
            elif isinstance(source, io.TextIOWrapper):
                raise IOError("Packet data file opened in TextIO mode. You must open packet data in binary mode.")
            else:
                raise IOError(f"Unrecognized data source: {source}")

            # Reset buffer.pos to the original position before we extended it
            buffer.pos = curser_pos
            return n_new_bits

        # ========
        # Start of generator
        # ========
        if isinstance(binary_data, bitstring.ConstBitStream):
            total_length_bits = len(binary_data)
            logger.info(
                f"Creating packet generator from pre-loaded ConstBitStream. Total length is {total_length_bits}")
        elif isinstance(binary_data, io.BufferedIOBase):
            total_length_bits = 8 * binary_data.seek(0, io.SEEK_END)  # This is probably preferable to len
            binary_data.seek(0, 0)
            logger.info(f"Creating packet generator from a filelike object, {binary_data}. "
                        f"Total length is {total_length_bits}bits")
        else:  # It's a socket and we don't know how much data we will get
            logger.info("Creating packet generator to read from a socket. Total length to parse is unknown.")
            total_length_bits = None  # We don't know how long it is

        # ========
        # Packet loop. Each iteration of this loop yields a ParsedPacket object
        # ========
        start_time = time.time_ns()
        n_bits_parsed = 0  # Keep track of how many bits we have parsed
        n_packets_parsed = 0  # Keep track of how many packets we have parsed
        read_buffer = bitstring.BitStream()  # Not const because it's a rotating buffer
        while True:
            if total_length_bits and n_bits_parsed == total_length_bits:
                break  # Exit if we know the length and we've reached it

            if show_progress is True:
                self.print_progress(current_bits=n_bits_parsed, total_bits=total_length_bits,
                                    start_time_ns=start_time, current_packets=n_packets_parsed)

            start_pos = read_buffer.pos
            if start_pos > 160_000_000:
                # Only trim the buffer after 20 MB read to prevent modifying
                # the bitstream and trimming after every packet
                read_buffer = read_buffer[start_pos:]
                start_pos = 0

            # Fill buffer enough to parse a header
            while len(read_buffer) - start_pos < skip_header_bits + CCSDS_HEADER_LENGTH_BITS:
                result = fill_read_buffer(binary_data, read_buffer,
                                          read_size_bytes=buffer_read_size_bytes)
                if not result:  # If there is verifiably no more data to add, break
                    break

            read_buffer.pos += skip_header_bits
            header = self._parse_header(read_buffer, reset_cursor=True)
            specified_total_packet_length_bits = self._total_packet_bits_from_pkt_len(header['PKT_LEN'].raw_value)
            # Consider it a counted packet once we've parsed the header
            # and update the number of bits parsed
            n_packets_parsed += 1
            n_bits_in_packet = skip_header_bits + specified_total_packet_length_bits
            n_bits_parsed += n_bits_in_packet
            if ccsds_headers_only is True:
                # Update the read_buffer to the end of the packet
                read_buffer.pos = start_pos + n_bits_in_packet
                yield Packet(header=header, data=None)
                continue

            # Based on PKT_LEN fill buffer enough to read a full packet
            while (len(read_buffer) - read_buffer.pos) < skip_header_bits + specified_total_packet_length_bits:
                result = fill_read_buffer(binary_data, read_buffer,
                                          read_size_bytes=buffer_read_size_bytes)
                if not result:  # If there is verifiably no more data to add, break
                    break

            try:
                if isinstance(self.packet_definition, xtcedef.XtcePacketDefinition):
                    packet = self.parse_packet(read_buffer,
                                               self.packet_definition.named_containers,
                                               root_container_name=root_container_name,
                                               word_size=self.word_size)
                else:
                    _, parameter_list = self._determine_packet_by_restrictions(header)
                    packet = self.legacy_parse_packet(read_buffer, parameter_list, word_size=self.word_size)
            except UnrecognizedPacketTypeError as e:
                # Regardless of whether we handle the error, we still want to update the read_buffer
                # in preparation for parsing the next packet
                read_buffer.pos = start_pos + n_bits_in_packet
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

            actual_length_parsed = read_buffer.pos - start_pos - skip_header_bits

            if actual_length_parsed != specified_total_packet_length_bits:
                read_buffer.pos = start_pos + n_bits_in_packet
                logger.warning(f"Parsed packet length "
                               f"({actual_length_parsed}b) did not match "
                               f"length specified in header ({specified_total_packet_length_bits}b). "
                               f"Updating bit string position to correct position "
                               "indicated by CCSDS header.")
                if not parse_bad_pkts:
                    logger.warning("Skipping (not yielding) bad packet because parse_bad_pkts is falsy.")
                    continue

            yield packet

        if show_progress is True:
            self.print_progress(current_bits=n_bits_parsed, total_bits=total_length_bits,
                                start_time_ns=start_time, current_packets=n_packets_parsed,
                                end="\n", log=True)
