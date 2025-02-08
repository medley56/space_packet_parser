"""Module with XTCE models related to SequenceContainers"""
from dataclasses import dataclass, field
from typing import Optional

from lxml import etree as ElementTree

from space_packet_parser.common import Parseable
from space_packet_parser.packets import CCSDSPacket


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
    inheritors: Optional[list['SequenceContainer']] = field(default_factory=lambda: [])

    def __post_init__(self):
        # Handle the explicit None passing for default values
        self.restriction_criteria = self.restriction_criteria or []
        self.inheritors = self.inheritors or []

    def parse(self, packet: CCSDSPacket) -> None:
        """Parse the entry list of parameters/containers in the order they are expected in the packet.

        This could be recursive if the entry list contains SequenceContainers.
        """
        for entry in self.entry_list:
            entry.parse(packet=packet)

    def to_sequence_container_xml_element(self, ns: dict) -> ElementTree.Element:
        """Create a SequenceContainer XML element

        Parameters
        ----------
        ns : dict
            XML namespace dict

        Returns
        -------
        : ElementTree.Element
        """
        _, xtce_uri = next(iter(ns.items()))
        xtce = f"{{{xtce_uri}}}"
        element = ElementTree.Element(xtce + "SequenceContainer",
                                      attrib={
                                          "abstract": str(self.abstract).lower(),
                                          "name": self.name
                                      },
                                      nsmap=ns)
        if self.short_description:
            element.attrib["shortDescription"] = self.short_description

        if self.long_description:
            ld = ElementTree.SubElement(element, xtce + "LongDescription", nsmap=ns)
            ld.text = self.long_description

        if self.base_container_name:
            base_container = ElementTree.SubElement(element,
                                                    xtce + "BaseContainer",
                                                    attrib={"containerRef": self.base_container_name},
                                                    nsmap=ns)
            if self.restriction_criteria:
                restriction_criteria = ElementTree.SubElement(base_container,
                                                              xtce + "RestrictionCriteria",
                                                              nsmap=ns)
                if len(self.restriction_criteria) == 1:
                    restriction_criteria.append(self.restriction_criteria[0].to_match_criteria_xml_element())
                else:
                    comp_list = ElementTree.SubElement(restriction_criteria, xtce + "ComparisonList", nsmap=ns)
                    for comp in self.restriction_criteria:
                        comp_list.append(comp.to_match_criteria_xml_element(ns))

        entry_list = ElementTree.SubElement(element, xtce + "EntryList", nsmap=ns)
        for entry in self.entry_list:
            ElementTree.SubElement(entry_list,
                                   xtce + "ParameterRefEntry",
                                   attrib={"parameterRef": entry.name},
                                   nsmap=ns)

        return element
