"""Module for parsing XTCE xml files to specify packet format"""
import logging
import socket
import warnings
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Optional, TextIO, Union

import lxml.etree as ElementTree

from space_packet_parser import comparisons, packets, parameters
from space_packet_parser.exceptions import ElementNotFoundError, InvalidParameterTypeError, UnrecognizedPacketTypeError
from space_packet_parser.xtce import XTCE_NSMAP

logger = logging.getLogger(__name__)

DEFAULT_ROOT_CONTAINER = "CCSDSPacket"

TAG_TO_TYPE_TEMPLATE = {
        '{{{xtce}}}StringParameterType': parameters.StringParameterType,
        '{{{xtce}}}IntegerParameterType': parameters.IntegerParameterType,
        '{{{xtce}}}FloatParameterType': parameters.FloatParameterType,
        '{{{xtce}}}EnumeratedParameterType': parameters.EnumeratedParameterType,
        '{{{xtce}}}BinaryParameterType': parameters.BinaryParameterType,
        '{{{xtce}}}BooleanParameterType': parameters.BooleanParameterType,
        '{{{xtce}}}AbsoluteTimeParameterType': parameters.AbsoluteTimeParameterType,
        '{{{xtce}}}RelativeTimeParameterType': parameters.RelativeTimeParameterType,
    }


class XtcePacketDefinition:
    """Object representation of the XTCE definition of a CCSDS packet object"""

    def __init__(
            self,
            sequence_container_list: Optional[list[packets.SequenceContainer]] = None,
            *,
            ns: dict = XTCE_NSMAP,
            root_container_name: Optional[str] = DEFAULT_ROOT_CONTAINER,
            space_system_name: Optional[str] = None,
            xtce_version: str = "1.0",
            date: str = None,
            author: Optional[str] = None
    ):
        f"""

        Parameters
        ----------
        sequence_container_list : Optional[list[packets.SequenceContainer]]
            List of SequenceContainer objects, containing entry lists of Parameter objects, which contain their
            ParameterTypes. This is effectively the entire XTCE document in one list of objects.
        ns : dict
            XML namespace, expected as a single entry dictionary with the key being the namespace label and the
            value being the namespace URI. Default {XTCE_NSMAP}
        root_container_name : Optional[str]
            Name of root sequence container (where to start parsing)
        space_system_name : Optional[str]
            Name of space system to encode in XML when serializing.
        xtce_version : str
            Default "1.0"
        date: Optional[str]
            Optional header date string.
        author : Optional[str]
            Optional author name to include in XML when serializing.
        """
        self._parameter_type_cache = {}
        self._parameter_cache = {}
        self._sequence_container_cache = {}

        # Populate the three caches for easy lookup later.
        # TODO: The parameter_type_cache and parameter_cache should be refactored into cached properties that simply
        #  iterate through the sequence container cache and pull out the parameters and parameter types
        if sequence_container_list:
            for sc in sequence_container_list:
                self._parameter_type_cache.update({p.parameter_type.name: p.parameter_type for p in sc.entry_list})
                self._parameter_cache.update({p.name: p for p in sc.entry_list})
            self._sequence_container_cache.update({sc.name: sc for sc in sequence_container_list})

        self.ns = ns
        self.root_container_name = root_container_name
        self.space_system_name = space_system_name
        self.xtce_version = xtce_version
        self.date = date
        self.author = author

    def to_xml_tree(self) -> ElementTree.ElementTree:
        """Initializes and returns an ElementTree object based on parameter type, parameter, and container information

        Returns
        -------
        : ElementTree.ElementTree
        """
        xtce_label, xtce_uri = next(iter(self.ns.items()))
        xtce = f"{{{xtce_uri}}}"
        tree = ElementTree.ElementTree(ElementTree.XML(
f"""<?xml version='1.0' encoding='UTF-8'?>
<xtce:SpaceSystem xmlns:{xtce_label}="{xtce_uri}"/>""".encode()
        ))

        if self._sequence_container_cache and self._parameter_type_cache and self._parameter_cache:
            space_system_root = tree.getroot()
            if self.space_system_name:
                space_system_root.attrib["name"] = self.space_system_name

            header = ElementTree.SubElement(space_system_root, xtce + "Header",
                                            attrib={
                                                "date": self.date or datetime.now().isoformat(),
                                                "version": self.xtce_version
                                            },
                                            nsmap=self.ns)
            if self.author:
                header.attrib["author"] = self.author

            telemetry_metadata_element = ElementTree.SubElement(space_system_root,
                                                                xtce + "TelemetryMetaData",
                                                                nsmap=self.ns)

            parameter_type_set = ElementTree.SubElement(telemetry_metadata_element,
                                                        xtce + "ParameterTypeSet",
                                                        nsmap=self.ns)
            for _, ptype in self._parameter_type_cache.items():
                parameter_type_set.append(ptype.to_parameter_type_xml_element(self.ns))

            parameter_set = ElementTree.SubElement(telemetry_metadata_element,
                                                   xtce + "ParameterSet",
                                                   nsmap=self.ns)
            for _, param in self._parameter_cache.items():
                parameter_set.append(param.to_parameter_xml_element(self.ns))

            sequence_container_set = ElementTree.SubElement(telemetry_metadata_element,
                                                            xtce + "ContainerSet",
                                                            nsmap=self.ns)
            for _, sc in self._sequence_container_cache.items():
                sequence_container_set.append(sc.to_sequence_container_xml_element(self.ns))

        return tree

    @classmethod
    def from_document(
            cls,
            xtce_document: Union[str, Path, TextIO],
            *,
            ns: Optional[dict] = None,
            root_container_name: Optional[str] = DEFAULT_ROOT_CONTAINER
    ) -> 'XtcePacketDefinition':
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
        root_container_name : Optional[str]
            Optional override to the root container name. Default is 'CCSDSPacket'.
        """
        tree = ElementTree.parse(xtce_document)  # noqa: S320
        space_system = tree.getroot()
        ns = ns or tree.getroot().nsmap
        header = space_system.find("xtce:Header", ns)
        xtce_definition = cls(
            ns=ns,
            root_container_name=root_container_name,
            author=header.attrib.get("author", None),
            date=header.attrib.get("date", None),
            space_system_name=space_system.attrib.get("name", None)
        )

        xtce_definition._parameter_type_cache = cls._get_parameter_types(tree, ns)
        xtce_definition._parameter_cache = cls._get_parameters(
            tree, xtce_definition._parameter_type_cache, ns
        )
        xtce_definition._sequence_container_cache = cls._get_sequence_containers(
            tree, xtce_definition._parameter_cache, ns
        )

        return xtce_definition

    def __getitem__(self, item):
        return self._sequence_container_cache[item]

    @staticmethod
    def _get_sequence_containers(
            tree: ElementTree.Element,
            parameters_lookup: dict[str, parameters.Parameter],
            ns: dict
    ) -> dict[str, packets.SequenceContainer]:
        """Parse the <xtce:ContainerSet> element into a a dictionary of SequenceContainer objects

        Parameters
        ----------
        tree : ElementTree.Element
            Full XTCE tree
        parameters_lookup : dict[str, parameters.Parameter]
            Parameters that are contained in container entry lists
        ns : dict
            XTCE namespace dict

        Returns
        -------

        """
        sequence_container_dict = {}
        for sequence_container in tree.getroot().iterfind(
                'xtce:TelemetryMetaData/xtce:ContainerSet/xtce:SequenceContainer',
                ns
        ):
            sequence_container_dict[
                sequence_container.attrib['name']
            ] = XtcePacketDefinition.parse_sequence_container_contents(
                tree, sequence_container, parameters_lookup, ns
            )

        # Back-populate the list of inheritors for each container
        for name, sc in sequence_container_dict.items():
            if sc.base_container_name:
                sequence_container_dict[sc.base_container_name].inheritors.append(name)

        return sequence_container_dict

    @staticmethod
    def _get_parameter_types(
            tree: ElementTree.ElementTree,
            ns: dict
    ) -> dict[str, parameters.ParameterType]:
        """Parse the <xtce:ParameterTypeSet> into a dictionary of ParameterType objects

        Parameters
        ----------
        tree : ElementTree.ElementTree
            Full XTCE tree
        ns : dict
            XML namespace dict

        Returns
        -------
        : dict[str, parameters.ParameterType]
        """
        type_tag_to_object = {k.format(**ns): v for k, v in TAG_TO_TYPE_TEMPLATE.items()}

        parameter_type_dict = {}
        for parameter_type_element in tree.getroot().iterfind('xtce:TelemetryMetaData/xtce:ParameterTypeSet/*', ns):
            parameter_type_name = parameter_type_element.attrib['name']
            if parameter_type_name in parameter_type_dict:
                raise ValueError(f"Found duplicate parameter type {parameter_type_name}. "
                                 f"Parameter types names are expected to be unique")
            try:
                parameter_type_class = type_tag_to_object[parameter_type_element.tag]
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
                parameter_type_element, ns)
            parameter_type_dict[parameter_type_name] = parameter_type_object  # Add to cache

        return parameter_type_dict

    @staticmethod
    def _get_parameters(
            tree: ElementTree.ElementTree,
            parameter_type_lookup: dict[str, parameters.ParameterType],
            ns: dict
    ) -> dict[str, parameters.Parameter]:
        """Parse an <xtce:ParameterSet> object into a dictionary of Parameter objects

        Parameters
        ----------
        tree : ElementTree.ElementTree
            Full XTCE tree
        parameter_type_lookup : dict[str, parameters.ParameterType]
            Parameter types referenced by parameters.
        ns : dict
            XML namespace dict

        Returns
        -------
        : dict[str, parameters.Parameter]
        """
        parameter_dict = {}

        for parameter_element in tree.getroot().iterfind('xtce:TelemetryMetaData/xtce:ParameterSet/xtce:Parameter', ns):
            parameter_name = parameter_element.attrib['name']
            if parameter_name in parameter_dict:
                raise ValueError(f"Found duplicate parameter name {parameter_name}. "
                                 f"Parameters are expected to be unique")
            parameter_type_name = parameter_element.attrib['parameterTypeRef']

            # Lookup from within the parameter type cache
            parameter_type_object = parameter_type_lookup[parameter_type_name]

            parameter_short_description = parameter_element.attrib['shortDescription'] if (
                    'shortDescription' in parameter_element.attrib
            ) else None
            parameter_long_description = parameter_element.find('xtce:LongDescription', ns).text if (
                    parameter_element.find('xtce:LongDescription', ns) is not None
            ) else None

            parameter_object = parameters.Parameter(
                name=parameter_name,
                parameter_type=parameter_type_object,
                short_description=parameter_short_description,
                long_description=parameter_long_description
            )
            parameter_dict[parameter_name] = parameter_object  # Add to cache

        return parameter_dict

    @staticmethod
    def parse_sequence_container_contents(
            tree: ElementTree.ElementTree,
            sequence_container_element: ElementTree.Element,
            parameter_lookup: dict[str, parameters.Parameter],
            ns: dict
    ) -> packets.SequenceContainer:
        """Parses the list of parameters in a SequenceContainer element, recursively parsing nested SequenceContainers
        to build an entry list of parameters that flattens the nested structure to derive a sequential ordering of
        expected parameters for each SequenceContainer. Note that this also stores entry lists for containers that are
        not intended to stand alone.

        Parameters
        ----------
        tree : ElementTree.ElementTree
            Full XTCE tree
        sequence_container_element : ElementTree.Element
            The SequenceContainer element to parse.
        parameter_lookup : dict[str, parameters.Parameter]
            Parameters contained in the entrylists of sequence containers
        ns : dict
            XML namespace dict

        Returns
        -------
        : SequenceContainer
            SequenceContainer containing an entry_list of SequenceContainers and Parameters with ParameterTypes
            in the order expected in a packet.
        """
        entry_list = []  # List to house Parameters for the current SequenceContainer
        try:
            base_container, restriction_criteria = XtcePacketDefinition._get_container_base_container(
                tree, sequence_container_element, ns
            )
            base_sequence_container = XtcePacketDefinition.parse_sequence_container_contents(
                tree, base_container, parameter_lookup, ns
            )
            base_container_name = base_sequence_container.name
        except ElementNotFoundError:
            base_container_name = None
            restriction_criteria = None

        container_contents = sequence_container_element.find('xtce:EntryList', ns).findall('*', ns)

        for entry in container_contents:
            if entry.tag == '{{{xtce}}}ParameterRefEntry'.format(**ns):
                parameter_name = entry.attrib['parameterRef']
                entry_list.append(parameter_lookup[parameter_name])

            elif entry.tag == '{{{xtce}}}ContainerRefEntry'.format(
                    **ns):
                nested_container = XtcePacketDefinition._find_container_by_name(
                    tree,
                    name=entry.attrib['containerRef'],
                    ns=ns
                )
                entry_list.append(
                    XtcePacketDefinition.parse_sequence_container_contents(
                        tree, nested_container, parameter_lookup, ns
                    )
                )

        short_description = sequence_container_element.attrib['shortDescription'] if (
                'shortDescription' in sequence_container_element.attrib
        ) else None
        long_description = sequence_container_element.find('xtce:LongDescription', ns).text if (
                sequence_container_element.find('xtce:LongDescription', ns) is not None
        ) else None

        return packets.SequenceContainer(name=sequence_container_element.attrib['name'],
                                         entry_list=entry_list,
                                         base_container_name=base_container_name,
                                         restriction_criteria=restriction_criteria,
                                         abstract=XtcePacketDefinition._is_abstract_container(
                                             sequence_container_element
                                         ),
                                         short_description=short_description,
                                         long_description=long_description)

    @property
    def named_containers(self) -> dict[str, packets.SequenceContainer]:
        """Property accessor that returns the dict cache of SequenceContainer objects"""
        return self._sequence_container_cache

    @property
    def named_parameters(self) -> dict[str, parameters.Parameter]:
        """Property accessor that returns the dict cache of Parameter objects"""
        return self._parameter_cache

    @property
    def named_parameter_types(self) -> dict[str, parameters.ParameterType]:
        """Property accessor that returns the dict cache of ParameterType objects"""
        return self._parameter_type_cache

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

    @staticmethod
    def _find_container_by_name(tree: ElementTree.ElementTree, name: str, ns: dict) -> ElementTree.Element:
        """Finds an XTCE container <xtce:SequenceContainer> by name.

        Parameters
        ----------
        name : str
            Name of the container to find

        Returns
        -------
        : ElementTree.Element
        """
        containers = tree.getroot().findall(
            f"xtce:TelemetryMetaData/xtce:ContainerSet/xtce:SequenceContainer[@name='{name}']",
            ns
        )
        if len(containers) != 1:
            raise ValueError(f"Found {len(containers)} matching container_set with name {name}. "
                             f"Container names are expected to exist and be unique.")
        return containers[0]

    @staticmethod
    def _get_container_base_container(
            tree: ElementTree.Element,
            container_element: ElementTree.Element,
            ns: dict
    ) -> tuple[ElementTree.Element, list[comparisons.MatchCriteria]]:
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
        base_container_element = container_element.find('xtce:BaseContainer', ns)
        if base_container_element is None:
            raise ElementNotFoundError(
                f"Container element {container_element} does not have a BaseContainer child element.")

        restriction_criteria_element = base_container_element.find('xtce:RestrictionCriteria', ns)
        if restriction_criteria_element is not None:
            comparison_list_element = restriction_criteria_element.find('xtce:ComparisonList', ns)
            single_comparison_element = restriction_criteria_element.find('xtce:Comparison', ns)
            boolean_expression_element = restriction_criteria_element.find('xtce:BooleanExpression', ns)
            custom_algorithm_element = restriction_criteria_element.find('xtce:CustomAlgorithm', ns)
            if custom_algorithm_element is not None:
                raise NotImplementedError("Detected a CustomAlgorithm in a RestrictionCriteria element. "
                                          "This is not implemented.")

            if comparison_list_element is not None:
                comparison_items = comparison_list_element.findall('xtce:Comparison', ns)
                restrictions = [
                    comparisons.Comparison.from_match_criteria_xml_element(comp, ns) for comp in comparison_items]
            elif single_comparison_element is not None:
                restrictions = [
                    comparisons.Comparison.from_match_criteria_xml_element(single_comparison_element, ns)]
            elif boolean_expression_element is not None:
                restrictions = [
                    comparisons.BooleanExpression.from_match_criteria_xml_element(boolean_expression_element, ns)]
            else:
                raise ValueError("Detected a RestrictionCriteria element containing no "
                                 "Comparison, ComparisonList, BooleanExpression or CustomAlgorithm.")
            # TODO: Implement NextContainer support inside RestrictionCriteria. This might make the parser much
            #    more complicated.
        else:
            restrictions = []
        return (
            XtcePacketDefinition._find_container_by_name(tree, base_container_element.attrib['containerRef'], ns),
            restrictions
        )

    def parse_ccsds_packet(self,
                           packet: packets.CCSDSPacket,
                           *,
                           root_container_name: Optional[str] = None) -> packets.CCSDSPacket:
        """Parse binary packet data according to the self.packet_definition object

        Parameters
        ----------
        packet: packets.CCSDSPacket
            Binary representation of the packet used to get the coming bits and any
            previously parsed data items to infer field lengths.
        root_container_name : Optional[str]
            Default is taken from the XtcePacketDefinition object. Any root container may be specified, but it must
            begin with the definition of a CCSDS header in order to parse correctly.

        Returns
        -------
        Packet
            A Packet object containing header and data attributes.
        """
        root_container_name = root_container_name or self.root_container_name
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

    def packet_generator(
            self,
            binary_data: Union[BinaryIO, socket.socket],
            *,
            parse_bad_pkts: bool = True,
            root_container_name: Optional[str] = None,
            ccsds_headers_only: bool = False,
            combine_segmented_packets: bool = False,
            secondary_header_bytes: int = 0,
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
            point for parsing. Default is taken from the parent XtcePacketDefinition object.
        ccsds_headers_only : bool
            Default False. If True, only parses the packet headers (does not use the provided packet definition).
            ``space_packet_parser.packets.ccsds_packet_generator`` can be used directly to parse only the CCSDS headers
            without needing a packet definition.
        combine_segmented_packets : bool
            Default False. If True, combines segmented packets into a single packet for parsing. This is useful for
            parsing packets that are split into multiple packets due to size constraints. The packet data is combined
            by concatenating the data from each packet together. The combined packet is then parsed as a single packet.
        secondary_header_bytes : int
            Default 0. The length of the secondary header in bytes.
            This is used to skip the secondary header of segmented packets.
            The byte layout within the returned packet has all data concatenated together as follows:
            [packet0header, packet0secondaryheader, packet0data, packet1data, packet2data, ...].
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
        root_container_name = root_container_name or self.root_container_name

        # Used to keep track of any continuation packets that we encounter
        # gathering them all up before combining them into a single packet
        # for the XTCE to parse, lookup is by APID.
        # _segmented_packets[APID] = [RawPacketData, ...]
        _segmented_packets = {}

        # Iterate over individual packets in the binary data
        for raw_packet_data in packets.ccsds_generator(binary_data,
                                                       buffer_read_size_bytes=buffer_read_size_bytes,
                                                       show_progress=show_progress,
                                                       skip_header_bytes=skip_header_bytes):
            if ccsds_headers_only:
                yield raw_packet_data
                continue

            if not combine_segmented_packets or raw_packet_data.sequence_flags == packets.SequenceFlags.UNSEGMENTED:
                packet = packets.CCSDSPacket(raw_data=raw_packet_data)
            elif raw_packet_data.sequence_flags == packets.SequenceFlags.FIRST:
                _segmented_packets[raw_packet_data.apid] = [raw_packet_data]
                continue
            elif not _segmented_packets.get(raw_packet_data.apid, []):
                warnings.warn("Continuation packet found without declaring the start, skipping this packet.")
                continue
            elif raw_packet_data.sequence_flags == packets.SequenceFlags.CONTINUATION:
                _segmented_packets[raw_packet_data.apid].append(raw_packet_data)
                continue
            else:  # raw_packet_data.sequence_flags == packets.SequenceFlags.LAST:
                _segmented_packets[raw_packet_data.apid].append(raw_packet_data)
                # We have received the final packet, close it up and combine all of
                # the segmented packets into a single "packet" for XTCE parsing
                sequence_counts = [p.sequence_count for p in _segmented_packets[raw_packet_data.apid]]
                if not all((sequence_counts[i + 1] - sequence_counts[i]) % 16384 == 1
                           for i in range(len(sequence_counts) - 1)):
                    warnings.warn(f"Continuation packets for apid {raw_packet_data.apid} "
                                  f"are not in sequence {sequence_counts}, skipping these packets.")
                    continue
                # Add all content (including header) from the first packet
                raw_data = _segmented_packets[raw_packet_data.apid][0]
                # Add the continuation packets to the first packet, skipping the headers
                for p in _segmented_packets[raw_packet_data.apid][1:]:
                    raw_data += p[raw_packet_data.HEADER_LENGTH_BYTES + secondary_header_bytes:]
                packet = packets.CCSDSPacket(raw_data=raw_data)

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
                warnings.warn(f"Number of bits parsed ({packet.raw_data.pos}b) did not match "
                              f"the length of data available ({len(packet.raw_data) * 8}b) for packet with APID "
                              f"{packet.raw_data.apid}.")

                if not parse_bad_pkts:
                    logger.warning(f"Skipping (not yielding) bad packet with apid {raw_packet_data.apid}.")
                    continue

            yield packet
