"""Module for parsing XTCE xml files to specify packet format"""
# Standard
import logging
from pathlib import Path
import socket
from typing import Tuple, Optional, List, TextIO, Dict, Union, BinaryIO, Iterator
# Installed
import lxml.etree as ElementTree
# Local
from space_packet_parser.exceptions import ElementNotFoundError, InvalidParameterTypeError, UnrecognizedPacketTypeError
from space_packet_parser import comparisons, parameters, packets

logger = logging.getLogger(__name__)


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

        self._populate_parameter_type_cache()
        self._populate_parameter_cache()
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

    def _populate_parameter_type_cache(self):
        """Force populating parameter_type_cache by parsing all ParameterTypes"""
        for parameter_type_element in self.parameter_type_set.findall('./*', self.ns):
            parameter_type_name = parameter_type_element.attrib['name']
            if parameter_type_name in self._parameter_cache:
                raise ValueError(f"Found duplicate parameter type {parameter_type_name}. "
                                 f"Parameter types are expected to be unique")
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

    def _populate_parameter_cache(self):
        """Force populating parameter_cache by parsing all Parameters"""
        for parameter_element in self.parameter_set.findall("./xtce:Parameter", self.ns):
            parameter_name = parameter_element.attrib['name']
            if parameter_name in self._parameter_cache:
                raise ValueError(f"Found duplicate parameter name {parameter_name}. "
                                 f"Parameters are expected to be unique")
            parameter_type_name = parameter_element.attrib['parameterTypeRef']

            # Lookup from within the parameter type cache
            parameter_type_object = self._parameter_type_cache[parameter_type_name]

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
            self._parameter_cache[parameter_name] = parameter_object  # Add to cache

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
                entry_list.append(self._parameter_cache[parameter_name])

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

    def parse_ccsds_packet(self,
                           packet: packets.CCSDSPacket,
                           *,
                           root_container_name: str = "CCSDSPacket") -> packets.CCSDSPacket:
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
            current_container.parse(packet)

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
                        f"APID={packet['PKT_APID']}.",
                        partial_data=packet)
                break

            raise UnrecognizedPacketTypeError(
                f"Multiple valid inheritors, {valid_inheritors} are possible for {current_container}.",
                partial_data=packet)
        return packet

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
            ``space_packet_parser.packets.ccsds_packet_generator`` can be used directly to parse only the CCSDS headers
            without needing a packet definition.
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

        # Iterate over individual packets in the binary data
        for raw_packet_data in packets.ccsds_generator(binary_data,
                                                       buffer_read_size_bytes=buffer_read_size_bytes,
                                                       show_progress=show_progress,
                                                       skip_header_bytes=skip_header_bytes):
            if ccsds_headers_only:
                yield raw_packet_data
                continue

            packet = packets.CCSDSPacket(raw_data=raw_packet_data)
            # Now do the actual parsing of the packet data
            try:
                packet = self.parse_ccsds_packet(packet, root_container_name=root_container_name)
            except UnrecognizedPacketTypeError as e:
                logger.debug(f"Unrecognized error on packet with APID {packet.raw_data.apid}")
                if yield_unrecognized_packet_errors:
                    # Yield the caught exception without raising it (raising ends generator)
                    yield e
                # Continue to next packet
                continue

            if packet.raw_data.pos != len(packet.raw_data) * 8:
                logger.warning(f"Number of bits parsed ({packet.raw_data.pos}b) did not match "
                               f"the length of data available ({len(packet.raw_data) * 8}b).")
                if not parse_bad_pkts:
                    logger.warning(f"Skipping (not yielding) bad packet with apid {raw_packet_data.apid}.")
                    continue

            yield packet
