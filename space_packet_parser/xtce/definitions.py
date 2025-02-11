"""Module for parsing XTCE xml files to specify packet format"""
import logging
import socket
import warnings
from collections.abc import Iterable, Iterator
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Optional, TextIO, Union

import lxml.etree as ElementTree
from lxml.builder import ElementMaker

from space_packet_parser import common, packets
from space_packet_parser.exceptions import InvalidParameterTypeError, UnrecognizedPacketTypeError
from space_packet_parser.xtce import XTCE_NSMAP, XTCE_URI, containers, parameters

logger = logging.getLogger(__name__)

DEFAULT_ROOT_CONTAINER = "CCSDSPacket"

TAG_TO_TYPE_TEMPLATE = {
        'StringParameterType': parameters.StringParameterType,
        'IntegerParameterType': parameters.IntegerParameterType,
        'FloatParameterType': parameters.FloatParameterType,
        'EnumeratedParameterType': parameters.EnumeratedParameterType,
        'BinaryParameterType': parameters.BinaryParameterType,
        'BooleanParameterType': parameters.BooleanParameterType,
        'AbsoluteTimeParameterType': parameters.AbsoluteTimeParameterType,
        'RelativeTimeParameterType': parameters.RelativeTimeParameterType,
    }


class XtcePacketDefinition(common.AttrComparable):
    """Object representation of the XTCE definition of a CCSDS packet object"""

    # TODO: Allow user to specify the XML schema instance for the XTCE XSD as well
    #  e.g.
    #                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    #                   xsi:schemaLocation="http://www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd"
    #  This will require an additional namespace dict entry for xsi (in this example)
    def __init__(
            self,
            sequence_container_list: Optional[list[containers.SequenceContainer]] = None,
            *,
            ns: dict = XTCE_NSMAP,
            xtce_schema_uri: str = XTCE_URI,
            root_container_name: Optional[str] = DEFAULT_ROOT_CONTAINER,
            space_system_name: Optional[str] = None,
            xtce_version: str = "1.0",
            date: str = None,
            author: Optional[str] = None
    ):
        f"""

        Parameters
        ----------
        sequence_container_list : Optional[list[space_packet_parser.containers.SequenceContainer]]
            List of SequenceContainer objects, containing entry lists of Parameter objects, which contain their
            ParameterTypes. This is effectively the entire XTCE document in one list of objects.
        ns : dict
            XML namespace, expected as a single entry dictionary with the key being the namespace label and the
            value being the namespace URI. Default {XTCE_NSMAP}.
        xtce_schema_uri : str
            XTCE schema URI. This is required in addition to the ns in order to know _which_ ns key corresponds to XTCE.
            Default {XTCE_URI}. When creating XTCE elements from objects, this is the namespace that is used.
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
        if sequence_container_list:
            for sc in sequence_container_list:
                self._parameter_type_cache.update({p.parameter_type.name: p.parameter_type for p in sc.entry_list})
                self._parameter_cache.update({p.name: p for p in sc.entry_list})
            self._sequence_container_cache.update({sc.name: sc for sc in sequence_container_list})

        self.ns = ns  # Default ns dict used when creating XML elements
        self.xtce_schema_uri = xtce_schema_uri  # XTCE schema URI
        self.root_container_name = root_container_name
        self.space_system_name = space_system_name
        self.xtce_version = xtce_version
        self.date = date
        self.author = author

    def write_xml(self, filepath: Union[str, Path]) -> None:
        """Write out the XTCE XML for this packet definition object to the specified path

        Parameters
        ----------
        filepath : Union[str, Path]
            Location to write this packet definition
        """
        self.to_xml_tree().write(filepath.absolute(), pretty_print=True, xml_declaration=True, encoding="utf-8")

    def to_xml_tree(self) -> ElementTree.ElementTree:
        """Initializes and returns an ElementTree object based on parameter type, parameter, and container information

        Returns
        -------
        : ElementTree.ElementTree
        """
        # ElementMaker element factory with predefined namespace and namespace mapping
        # The XTCE namespace actually defines the XTCE elements
        # The ns mapping just affects the serialization of XTCE elements
        # Both can be None, resulting in no namespace awareness
        elmaker = ElementMaker(namespace=self.xtce_schema_uri, nsmap=self.ns)

        space_system_attrib = {}
        if self.space_system_name:
            space_system_attrib["name"] = self.space_system_name

        header_attrib = {
            "date": self.date or datetime.now().isoformat(),
            "version": self.xtce_version
        }
        if self.author:
            header_attrib["author"] = self.author

        tree = ElementTree.ElementTree(
            elmaker.SpaceSystem(
                elmaker.Header(**header_attrib),
                elmaker.TelemetryMetaData(
                    elmaker.ParameterTypeSet(
                        # TODO: Pass elmaker instead of self.ns to to_xml
                        *(ptype.to_xml(elmaker=elmaker) for ptype in self._parameter_type_cache.values()),
                    ),
                    elmaker.ParameterSet(
                        *(param.to_xml(elmaker=elmaker) for param in self._parameter_cache.values()),
                    ),
                    elmaker.ContainerSet(
                        *(sc.to_xml(elmaker=elmaker) for sc in self._sequence_container_cache.values()),
                    )
                ),
                **space_system_attrib
            )
        )

        return tree

    @classmethod
    def from_xtce(
            cls,
            xtce_document: Union[str, Path, TextIO],
            *,
            xtce_schema_uri: Optional[str] = XTCE_URI,
            root_container_name: Optional[str] = DEFAULT_ROOT_CONTAINER
    ) -> 'XtcePacketDefinition':
        f"""Instantiate an object representation of a CCSDS packet definition,
        according to a format specified in an XTCE
        XML document. The parser iteratively builds sequences of parameters according to the
        SequenceContainers specified in the XML document's ContainerSet element. The notions of container inheritance
        (via BaseContainer) and nested container (by including a SequenceContainer within a SequenceContainer) are
        supported. Exclusion of containers based on topLevelPacket in AncillaryData is not supported, so all
        containers are examined and returned.

        Parameters
        ----------
        xtce_document : TextIO
            Path to XTCE XML document containing packet definition.
        xtce_schema_uri : Optional[str]
            The URI associated with XTCE. Default is {XTCE_URI}. None means no namespace awareness.
        root_container_name : Optional[str]
            Optional override to the root container name. Default is {DEFAULT_ROOT_CONTAINER}.
        """
        tree = ElementTree.parse(xtce_document)  # noqa: S320
        space_system = tree.getroot()
        ns = tree.getroot().nsmap
        header = space_system.find(f"{{{xtce_schema_uri}}}" + "Header")
        if header is not None:
            author = header.attrib.get("author", None)
            date = header.attrib.get("date", None)
        else:
            author = None
            date = None

        xtce_definition = cls(
            ns=ns,
            xtce_schema_uri=xtce_schema_uri,
            root_container_name=root_container_name,
            author=author,
            date=date,
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

    @staticmethod
    def _get_sequence_containers(
            tree: ElementTree.Element,
            parameter_lookup: dict[str, parameters.Parameter],
            ns: dict
    ) -> dict[str, containers.SequenceContainer]:
        """Parse the <xtce:ContainerSet> element into a dictionary of SequenceContainer objects

        Parameters
        ----------
        tree : ElementTree.Element
            Full XTCE tree
        parameter_lookup : dict[str, parameters.Parameter]
            Parameters that are contained in container entry lists
        ns : dict
            XTCE namespace dict

        Returns
        -------

        """
        if ns:
            xtce_label, xtce_uri = next(iter(ns.items()))
        else:
            xtce_uri = ""
        xtce = f"{{{xtce_uri}}}"
        sequence_container_dict = {}
        for sequence_container in tree.getroot().iterfind(
                f'{xtce}TelemetryMetaData/{xtce}ContainerSet/{xtce}SequenceContainer',
                ns
        ):
            sequence_container_dict[
                sequence_container.attrib['name']
            ] = containers.SequenceContainer.from_xml(
                sequence_container, tree=tree, parameter_lookup=parameter_lookup, ns=ns
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
        if ns:
            xtce_label, xtce_uri = next(iter(ns.items()))
        else:
            xtce_uri = ""
        xtce = f"{{{xtce_uri}}}"
        type_tag_to_object = {xtce + k: v for k, v in TAG_TO_TYPE_TEMPLATE.items()}

        parameter_type_dict = {}
        for parameter_type_element in tree.getroot().iterfind(f'{xtce}TelemetryMetaData/{xtce}ParameterTypeSet/*', ns):
            # TODO: This should really be a call to a ParameterType.from_xml() method. Adding a ParameterType class
            #  will also make it more feasible to add array parameter types and aggregate parameter types
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
            parameter_type_object = parameter_type_class.from_xml(
                parameter_type_element, ns=ns)
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
        if ns:
            xtce_label, xtce_uri = next(iter(ns.items()))
        else:
            xtce_uri = ""
        xtce = f"{{{xtce_uri}}}"
        for parameter_element in tree.getroot().iterfind(
                f'{xtce}TelemetryMetaData/{xtce}ParameterSet/{xtce}Parameter', ns):
            parameter_object = parameters.Parameter.from_xml(parameter_element, ns=ns,
                                                             parameter_type_lookup=parameter_type_lookup)
            if parameter_object.name in parameter_dict:
                raise ValueError(f"Found duplicate parameter name {parameter_object.name}. "
                                 f"Parameters are expected to be unique")
            parameter_dict[parameter_object.name] = parameter_object  # Add to cache

        return parameter_dict

    def get_containers(self, *names: str) -> Union[
        containers.SequenceContainer,
        Iterable[containers.SequenceContainer]
    ]:
        """Get one or more items from the dict cache of SequenceContainer objects"""
        if len(names) == 1:
            return self._sequence_container_cache[names[0]]
        if len(names) == 0:
            return self._sequence_container_cache
        return (self._sequence_container_cache[name] for name in names)

    def get_parameters(self, *names: str) -> Union[
        parameters.Parameter,
        Iterable[parameters.Parameter]
    ]:
        """Get one or more items from the dict cache of Parameter objects"""
        if len(names) == 1:
            return self._parameter_cache[names[0]]
        if len(names) == 0:
            return self._parameter_cache
        return (self._parameter_cache[name] for name in names)

    def get_parameter_types(self, *names: str) -> Union[
        parameters.ParameterType,
        Iterable[parameters.ParameterType]
    ]:
        """Get one or more items from the dict cache of ParameterType objects"""
        if len(names) == 1:
            return self._parameter_type_cache[names[0]]
        if len(names) == 0:
            return self._parameter_type_cache
        return (self._parameter_type_cache[name] for name in names)

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
        current_container: containers.SequenceContainer = self._sequence_container_cache[root_container_name]
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
                        f"Detected an abstract container with no valid inheritors by restriction criteria. "
                        f"This might mean this packet type is not accounted for in the provided packet definition. "
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
