"""Module for parsing XTCE xml files to specify packet format"""
# Standard
from collections import namedtuple
import datetime as dt
import io
import logging
from pathlib import Path
import socket
import time
from typing import Tuple, Optional, List, TextIO, Dict, Union, BinaryIO, Iterator
# Installed
import lxml.etree as ElementTree
# Local
from space_packet_parser.exceptions import ElementNotFoundError, InvalidParameterTypeError
from space_packet_parser import comparisons, parameters, packets

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


class XtcePacketDefinition:
    """Object representation of the XTCE definition of a CCSDS packet object"""

    _tag_to_type_template = {
        '{{{xtce}}}StringParameterType': parameters.StringParameterType,
        '{{{xtce}}}IntegerParameterType': parameters.IntegerParameterType,
        '{{{xtce}}}FloatParameterType': parameters.FloatParameterType,
        '{{{xtce}}}EnumeratedParameterType': parameters.EnumeratedParameterType,
        '{{{xtce}}}BinaryParameterType': parameters.BinaryParameterType,
        '{{{xtce}}}BooleanParameterType': parameters.BooleanParameterType,
        '{{{xtce}}}AbsoluteTimeParameterType': parameters.AbsoluteTimeParameterType,
        '{{{xtce}}}RelativeTimeParameterType': parameters.RelativeTimeParameterType,
    }

    def __init__(
            self,
            xtce_document: Union[str, Path, TextIO],
            *,
            ns: Optional[dict] = None
    ) -> None:
        """Instantiate an object representation of a CCSDS packet definition, according to a format specified in an XTCE
        XML document. The parser iteratively builds sequences of parameters according to the
        SequenceContainers specified in the XML document's ContainerSet element. The notions of container inheritance
        (via BaseContainer) and nested container (by including a SequenceContainer within a SequenceContainer) are
        supported. Exclusion of containers based on topLevelPacket in AncillaryData is not supported, so all
        containers are examined and returned.

        Parameters
        ----------
        xtce_document : TextIO
            Path to XTCE XML document containing packet definition.
        ns : Optional[dict]
            Optional different namespace than the namespace defined in the XTCE document.
        """
        self._sequence_container_cache = {}  # Lookup for parsed sequence container objects
        self._parameter_cache = {}  # Lookup for parsed parameter objects
        self._parameter_type_cache = {}  # Lookup for parsed parameter type objects
        self.tree = ElementTree.parse(xtce_document)
        self.ns = ns or self.tree.getroot().nsmap
        self.type_tag_to_object = {k.format(**self.ns): v for k, v in
                                   self._tag_to_type_template.items()}

        self._populate_sequence_container_cache()

    def __getitem__(self, item):
        return self._sequence_container_cache[item]

    def _populate_sequence_container_cache(self):
        """Force populating sequence_container_cache by parsing all SequenceContainers"""
        for sequence_container in self.container_set.iterfind('xtce:SequenceContainer', self.ns):
            self._sequence_container_cache[
                sequence_container.attrib['name']
            ] = self.parse_sequence_container_contents(sequence_container)

        # Back-populate the list of inheritors for each container
        for name, sc in self._sequence_container_cache.items():
            if sc.base_container_name:
                self._sequence_container_cache[sc.base_container_name].inheritors.append(name)

    def parse_sequence_container_contents(self,
                                          sequence_container: ElementTree.Element) -> packets.SequenceContainer:
        """Parses the list of parameters in a SequenceContainer element, recursively parsing nested SequenceContainers
        to build an entry list of parameters that flattens the nested structure to derive a sequential ordering of
        expected parameters for each SequenceContainer. Note that this also stores entry lists for containers that are
        not intended to stand alone.

        Parameters
        ----------
        sequence_container : ElementTree.Element
            The SequenceContainer element to parse.

        Returns
        -------
        : SequenceContainer
            SequenceContainer containing an entry_list of SequenceContainers and Parameters
            in the order expected in a packet.
        """
        entry_list = []  # List to house Parameters for the current SequenceContainer
        try:
            base_container, restriction_criteria = self._get_container_base_container(sequence_container)
            base_sequence_container = self.parse_sequence_container_contents(base_container)
            base_container_name = base_sequence_container.name
        except ElementNotFoundError:
            base_container_name = None
            restriction_criteria = None

        container_contents = sequence_container.find('xtce:EntryList', self.ns).findall('*', self.ns)

        for entry in container_contents:
            if entry.tag == '{{{xtce}}}ParameterRefEntry'.format(**self.ns):  # pylint: disable=consider-using-f-string
                parameter_name = entry.attrib['parameterRef']

                # If we've already parsed this parameter in a different container
                if parameter_name in self._parameter_cache:
                    entry_list.append(self._parameter_cache[parameter_name])
                else:
                    parameter_element = self._find_parameter(parameter_name)
                    parameter_type_name = parameter_element.attrib['parameterTypeRef']

                    # If we've already parsed this parameter type for a different parameter
                    if parameter_type_name in self._parameter_type_cache:
                        parameter_type_object = self._parameter_type_cache[parameter_type_name]
                    else:
                        parameter_type_element = self._find_parameter_type(parameter_type_name)
                        try:
                            parameter_type_class = self.type_tag_to_object[parameter_type_element.tag]
                        except KeyError as e:
                            if (
                                    "ArrayParameterType" in parameter_type_element.tag or
                                    "AggregateParameterType" in parameter_type_element.tag
                            ):
                                raise NotImplementedError(f"Unsupported parameter type {parameter_type_element.tag}. "
                                                          "Supporting this parameter type is in the roadmap but has "
                                                          "not yet been implemented.") from e
                            raise InvalidParameterTypeError(f"Invalid parameter type {parameter_type_element.tag}. "
                                                            "If you believe this is a valid XTCE parameter type, "
                                                            "please open a feature request as a Github issue with a "
                                                            "reference to the XTCE element description for the "
                                                            "parameter type element.") from e
                        parameter_type_object = parameter_type_class.from_parameter_type_xml_element(
                            parameter_type_element, self.ns)
                        self._parameter_type_cache[parameter_type_name] = parameter_type_object  # Add to cache

                    parameter_short_description = parameter_element.attrib['shortDescription'] if (
                            'shortDescription' in parameter_element.attrib
                    ) else None
                    parameter_long_description = parameter_element.find('xtce:LongDescription', self.ns).text if (
                            parameter_element.find('xtce:LongDescription', self.ns) is not None
                    ) else None

                    parameter_object = parameters.Parameter(
                        name=parameter_name,
                        parameter_type=parameter_type_object,
                        short_description=parameter_short_description,
                        long_description=parameter_long_description
                    )
                    entry_list.append(parameter_object)
                    self._parameter_cache[parameter_name] = parameter_object  # Add to cache
            elif entry.tag == '{{{xtce}}}ContainerRefEntry'.format(  # pylint: disable=consider-using-f-string
                    **self.ns):
                nested_container = self._find_container(name=entry.attrib['containerRef'])
                entry_list.append(self.parse_sequence_container_contents(nested_container))

        short_description = sequence_container.attrib['shortDescription'] if (
                'shortDescription' in sequence_container.attrib
        ) else None
        long_description = sequence_container.find('xtce:LongDescription', self.ns).text if (
                sequence_container.find('xtce:LongDescription', self.ns) is not None
        ) else None

        return packets.SequenceContainer(name=sequence_container.attrib['name'],
                                         entry_list=entry_list,
                                         base_container_name=base_container_name,
                                         restriction_criteria=restriction_criteria,
                                         abstract=self._is_abstract_container(sequence_container),
                                         short_description=short_description,
                                         long_description=long_description)

    @property
    def named_containers(self) -> Dict[str, packets.SequenceContainer]:
        """Property accessor that returns the dict cache of SequenceContainer objects"""
        return self._sequence_container_cache

    @property
    def named_parameters(self) -> Dict[str, parameters.Parameter]:
        """Property accessor that returns the dict cache of Parameter objects"""
        return self._parameter_cache

    @property
    def named_parameter_types(self) -> Dict[str, parameters.ParameterType]:
        """Property accessor that returns the dict cache of ParameterType objects"""
        return self._parameter_type_cache

    @property
    def container_set(self) -> ElementTree.Element:
        """Property that returns the <xtce:ContainerSet> element, containing all the sequence container elements."""
        return self.tree.getroot().find('xtce:TelemetryMetaData/xtce:ContainerSet', self.ns)

    @property
    def parameter_type_set(self) -> ElementTree.Element:
        """Property that returns the <xtce:ParameterTypeSet> element, containing all parameter type elements."""
        return self.tree.getroot().find('xtce:TelemetryMetaData/xtce:ParameterTypeSet', self.ns)

    @property
    def parameter_set(self) -> ElementTree.Element:
        """Property that returns the <xtce:ParameterSet> element, containing all parameter elements."""
        return self.tree.getroot().find('xtce:TelemetryMetaData/xtce:ParameterSet', self.ns)

    @staticmethod
    def _is_abstract_container(container_element: ElementTree.Element) -> bool:
        """Determine in a SequenceContainer element is abstract

        Parameters
        ----------
        container_element : ElementTree.Element
            SequenceContainer element to examine

        Returns
        -------
        : bool
            True if SequenceContainer element has the attribute abstract=true. False otherwise.
        """
        if 'abstract' in container_element.attrib:
            return container_element.attrib['abstract'].lower() == 'true'
        return False

    def _find_container(self, name: str) -> ElementTree.Element:
        """Finds an XTCE container <xtce:SequenceContainer> by name.

        Parameters
        ----------
        name : str
            Name of the container to find

        Returns
        -------
        : ElementTree.Element
        """
        containers = self.container_set.findall(f"./xtce:SequenceContainer[@name='{name}']", self.ns)
        assert len(containers) == 1, f"Found {len(containers)} matching container_set with name {name}. " \
                                     f"Container names are expected to exist and be unique."
        return containers[0]

    def _find_parameter(self, name: str) -> ElementTree.Element:
        """Finds an XTCE Parameter in the tree.

        Parameters
        ----------
        name : str
            Name of the parameter to find

        Returns
        -------
        : ElementTree.Element
        """
        params = self.parameter_set.findall(f"./xtce:Parameter[@name='{name}']", self.ns)
        assert len(params) == 1, f"Found {len(params)} matching parameters with name {name}. " \
                                 f"Parameter names are expected to exist and be unique."
        return params[0]

    def _find_parameter_type(self, name: str) -> ElementTree.Element:
        """Finds an XTCE ParameterType in the tree.

        Parameters
        ----------
        name : str
            Name of the parameter type to find

        Returns
        -------
        : ElementTree.Element
        """
        param_types = self.parameter_type_set.findall(f"./*[@name='{name}']", self.ns)
        assert len(param_types) == 1, f"Found {len(param_types)} matching parameter types with name {name}. " \
                                      f"Parameter type names are expected to exist and be unique."
        return param_types[0]

    def _get_container_base_container(
            self,
            container_element: ElementTree.Element) -> Tuple[ElementTree.Element, List[comparisons.MatchCriteria]]:
        """Examines the container_element and returns information about its inheritance.

        Parameters
        ----------
        container_element : ElementTree.Element
            The container element for which to find its base container.

        Returns
        -------
        : ElementTree.Element
            The base container element of the input container_element.
        : list
            The restriction criteria for the inheritance.
        """
        base_container_element = container_element.find('xtce:BaseContainer', self.ns)
        if base_container_element is None:
            raise ElementNotFoundError(
                f"Container element {container_element} does not have a BaseContainer child element.")

        restriction_criteria_element = base_container_element.find('xtce:RestrictionCriteria', self.ns)
        if restriction_criteria_element is not None:
            comparison_list_element = restriction_criteria_element.find('xtce:ComparisonList', self.ns)
            single_comparison_element = restriction_criteria_element.find('xtce:Comparison', self.ns)
            boolean_expression_element = restriction_criteria_element.find('xtce:BooleanExpression', self.ns)
            custom_algorithm_element = restriction_criteria_element.find('xtce:CustomAlgorithm', self.ns)
            if custom_algorithm_element is not None:
                raise NotImplementedError("Detected a CustomAlgorithm in a RestrictionCriteria element. "
                                          "This is not implemented.")

            if comparison_list_element is not None:
                comparison_items = comparison_list_element.findall('xtce:Comparison', self.ns)
                restrictions = [
                    comparisons.Comparison.from_match_criteria_xml_element(comp, self.ns) for comp in comparison_items]
            elif single_comparison_element is not None:
                restrictions = [
                    comparisons.Comparison.from_match_criteria_xml_element(single_comparison_element, self.ns)]
            elif boolean_expression_element is not None:
                restrictions = [
                    comparisons.BooleanExpression.from_match_criteria_xml_element(boolean_expression_element, self.ns)]
            else:
                raise ValueError("Detected a RestrictionCriteria element containing no "
                                 "Comparison, ComparisonList, BooleanExpression or CustomAlgorithm.")
            # TODO: Implement NextContainer support inside RestrictionCriteria. This might make the parser much
            #    more complicated.
        else:
            restrictions = []
        return self._find_container(base_container_element.attrib['containerRef']), restrictions

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
            header[item.name] = packets.ParsedDataItem(
                name=item.name,
                # pylint: disable=protected-access
                raw_value=packets._extract_bits(packet_data, current_bit, item.nbits))
            current_bit += item.nbits
        return header

    def parse_ccsds_packet(self,
                           packet: packets.CCSDSPacket,
                           *,
                           root_container_name: str = "CCSDSPacket",
                           **parse_value_kwargs) -> packets.CCSDSPacket:
        """Parse binary packet data according to the self.packet_definition object

        Parameters
        ----------
        packet: packets.CCSDSPacket
            Binary representation of the packet used to get the coming bits and any
            previously parsed data items to infer field lengths.
        root_container_name : str
            Default is CCSDSPacket. Any root container may be specified.

        Returns
        -------
        Packet
            A Packet object containing header and data attributes.
        """
        current_container: packets.SequenceContainer = self._sequence_container_cache[root_container_name]
        while True:
            current_container.parse(packet, **parse_value_kwargs)

            valid_inheritors = []
            for inheritor_name in current_container.inheritors:
                if all(rc.evaluate(packet)
                       for rc in self._sequence_container_cache[inheritor_name].restriction_criteria):
                    valid_inheritors.append(inheritor_name)

            if len(valid_inheritors) == 1:
                # Set the unique valid inheritor as the next current_container
                current_container = self._sequence_container_cache[valid_inheritors[0]]
                continue

            if len(valid_inheritors) == 0:
                if current_container.abstract:
                    raise UnrecognizedPacketTypeError(
                        f"Detected an abstract container with no valid inheritors by restriction criteria. This might "
                        f"mean this packet type is not accounted for in the provided packet definition. "
                        f"APID={packet['PKT_APID'].raw_value}.",
                        partial_data=packet)
                break

            raise UnrecognizedPacketTypeError(
                f"Multiple valid inheritors, {valid_inheritors} are possible for {current_container}.",
                partial_data=packet)
        return packet

    @staticmethod
    def _print_progress(
            *,
            current_bytes: int,
            total_bytes: Optional[int],
            start_time_ns: int,
            current_packets: int,
            end: str = '\r',
            log: bool = False
    ):
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

        # Fast calls initially on Windows can result in a zero elapsed time
        elapsed_ns = max(time.time_ns() - start_time_ns, 1)
        delta = dt.timedelta(microseconds=elapsed_ns / 1E3)
        kbps = int(current_bytes // 8 * 1E6 / elapsed_ns)
        pps = int(current_packets * 1E9 / elapsed_ns)
        info_str = f"[Elapsed: {delta}, " \
                   f"Parsed {current_bytes} bytes ({current_packets} packets) " \
                   f"at {kbps}kb/s ({pps}pkts/s)]"
        loadbar = f"Progress: [{progress * progress_char:{bar_length}}]{percentage}% {info_str}"
        print(loadbar, end=end)
        if log:
            logger.info(loadbar)

    def packet_generator(  # pylint: disable=too-many-branches,too-many-statements
            self,
            binary_data: Union[BinaryIO, socket.socket],
            *,
            parse_bad_pkts: bool = True,
            root_container_name="CCSDSPacket",
            ccsds_headers_only: bool = False,
            yield_unrecognized_packet_errors: bool = False,
            show_progress: bool = False,
            buffer_read_size_bytes: Optional[int] = None,
            skip_header_bytes: int = 0
    ) -> Iterator[Union[packets.CCSDSPacket, UnrecognizedPacketTypeError]]:
        """Create and return a Packet generator that reads from a ConstBitStream or a filelike object or a socket.

        Creating a generator object to return allows the user to create
        many generators from a single Parser and reduces memory usage.

        Parameters
        ----------
        binary_data : Union[BinaryIO, socket.socket]
            Binary data source to parse into Packets.
        parse_bad_pkts : bool
            Default True.
            If True, when the generator encounters a packet with an incorrect length it will still yield the packet
            (the data will likely be invalid). If False, the generator will still write a debug log message but will
            otherwise silently skip the bad packet.
        root_container_name : str
            The name of the root level (lowest level of container inheritance) SequenceContainer. This SequenceContainer
            is assumed to be inherited by every possible packet structure in the XTCE document and is the starting
            point for parsing. Default is 'CCSDSPacket'.
        ccsds_headers_only : bool
            Default False. If True, only parses the packet headers (does not use the provided packet definition).
        yield_unrecognized_packet_errors : bool
            Default False.
            If False, UnrecognizedPacketTypeErrors are caught silently and parsing continues to the next packet.
            If True, the generator will yield an UnrecognizedPacketTypeError in the event of an unrecognized
            packet. Note: These exceptions are not raised by default but are instead returned so that the generator
            can continue. You can raise the exceptions if desired. Leave this as False unless you need to examine the
            partial data from unrecognized packets.
        show_progress : bool
            Default False.
            If True, prints a status bar. Note that for socket sources, the percentage will be zero until the generator
            ends.
        buffer_read_size_bytes : Optional[int]
            Number of bytes to read from e.g. a BufferedReader or socket binary data source on each read attempt.
            If None, defaults to 4096 bytes from a socket, -1 (full read) from a file.
        skip_header_bytes : int
            Default 0. The parser skips this many bytes at the beginning of every packet. This allows dynamic stripping
            of additional header data that may be prepended to packets in "raw record" file formats.

        Yields
        -------
        Union[Packet, UnrecognizedPacketTypeError]
            Generator yields Packet objects containing the parsed packet data for each subsequent packet.
            If yield_unrecognized_packet_errors is True, it will yield an unraised exception object,
            which can be raised or used for debugging purposes.
        """
        # ========
        # Set up the reader based on the type of binary_data
        # ========
        if isinstance(binary_data, io.BufferedIOBase):
            if buffer_read_size_bytes is None:
                # Default to a full read of the file
                buffer_read_size_bytes = -1
            total_length_bytes = binary_data.seek(0, io.SEEK_END)  # This is probably preferable to len
            binary_data.seek(0, 0)
            logger.info(f"Creating packet generator from a filelike object, {binary_data}. "
                        f"Total length is {total_length_bytes} bytes")
            read_bytes_from_source = binary_data.read
        elif isinstance(binary_data, socket.socket):  # It's a socket and we don't know how much data we will get
            logger.info("Creating packet generator to read from a socket. Total length to parse is unknown.")
            total_length_bytes = None  # We don't know how long it is
            if buffer_read_size_bytes is None:
                # Default to 4096 bytes from a socket
                buffer_read_size_bytes = 4096
            read_bytes_from_source = binary_data.recv
        elif isinstance(binary_data, io.TextIOWrapper):
            raise IOError("Packet data file opened in TextIO mode. You must open packet data in binary mode.")
        else:
            raise IOError(f"Unrecognized data source: {binary_data}")

        # ========
        # Packet loop. Each iteration of this loop yields a CCSDSPacket object
        # ========
        start_time = time.time_ns()
        n_bytes_parsed = 0  # Keep track of how many bytes we have parsed
        n_packets_parsed = 0  # Keep track of how many packets we have parsed
        read_buffer = b""  # Empty bytes object to start
        current_pos = 0  # Keep track of where we are in the buffer
        while True:
            if total_length_bytes and n_bytes_parsed == total_length_bytes:
                break  # Exit if we know the length and we've reached it

            if show_progress:
                self._print_progress(current_bytes=n_bytes_parsed, total_bytes=total_length_bytes,
                                     start_time_ns=start_time, current_packets=n_packets_parsed)

            if current_pos > 20_000_000:
                # Only trim the buffer after 20 MB read to prevent modifying
                # the bitstream and trimming after every packet
                read_buffer = read_buffer[current_pos:]
                current_pos = 0

            # Fill buffer enough to parse a header
            while len(read_buffer) - current_pos < skip_header_bytes + CCSDS_HEADER_LENGTH_BYTES:
                result = read_bytes_from_source(buffer_read_size_bytes)
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

            # Based on PKT_LEN fill buffer enough to read a full packet
            while len(read_buffer) - current_pos < n_bytes_packet:
                result = read_bytes_from_source(buffer_read_size_bytes)
                if not result:  # If there is verifiably no more data to add, break
                    break
                read_buffer += result

            # Consider it a counted packet once we've verified that we have read the full packet and parsed the header
            # Update the number of packets and bytes parsed
            n_packets_parsed += 1
            n_bytes_parsed += skip_header_bytes + n_bytes_packet
            if ccsds_headers_only:
                # update the current position to the end of the packet data
                current_pos += n_bytes_packet
                p = packets.CCSDSPacket(raw_data=read_buffer[current_pos - n_bytes_packet:current_pos], **header)
                yield p
                continue

            # current_pos is still before the header, so we are reading the entire packet here
            packet_bytes = read_buffer[current_pos:current_pos + n_bytes_packet]
            current_pos += n_bytes_packet
            # Wrap the bytes in a class that can keep track of position as we read from it
            packet = packets.CCSDSPacket(raw_data=packet_bytes)
            try:
                packet = self.parse_ccsds_packet(packet,
                                                 root_container_name=root_container_name)
            except UnrecognizedPacketTypeError as e:
                logger.debug(f"Unrecognized error on packet with APID {header['PKT_APID'].raw_value}'")
                if yield_unrecognized_packet_errors:
                    # Yield the caught exception without raising it (raising ends generator)
                    yield e
                # Continue to next packet
                continue

            if packet.header['PKT_LEN'].raw_value != header['PKT_LEN'].raw_value:
                raise ValueError(f"Hardcoded header parsing found a different packet length "
                                 f"{header['PKT_LEN'].raw_value} than the definition-based parsing found "
                                 f"{packet.header['PKT_LEN'].raw_value}. This might be because the CCSDS header is "
                                 f"incorrectly represented in your packet definition document.")

            actual_length_parsed = packet.raw_data.pos // 8
            if actual_length_parsed != n_bytes_packet:
                logger.warning(f"Parsed packet length "
                               f"({actual_length_parsed}B) did not match "
                               f"length specified in header ({n_bytes_packet}B). "
                               f"Updating the position to the correct position "
                               "indicated by CCSDS header.")
                if not parse_bad_pkts:
                    logger.warning(f"Skipping (not yielding) bad packet with apid {header['PKT_APID'].raw_value}.")
                    continue

            yield packet

        if show_progress:
            self._print_progress(current_bytes=n_bytes_parsed, total_bytes=total_length_bytes,
                                 start_time_ns=start_time, current_packets=n_packets_parsed,
                                 end="\n", log=True)
