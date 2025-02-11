"""ParameterType definitions"""
from dataclasses import dataclass
from typing import Optional

import lxml.etree as ElementTree
from lxml.builder import ElementMaker

from space_packet_parser import common, packets
from space_packet_parser.xtce import parameter_types


@dataclass
class Parameter(common.Parseable, common.XmlObject):
    """<xtce:Parameter>

    Parameters
    ----------
    name : str
        Parameter name. Typically something like MSN__PARAMNAME
    parameter_type : parameter_types.ParameterType
        Parameter type object that describes how the parameter is stored.
    short_description : str
        Short description of parameter as parsed from XTCE
    long_description : str
        Long description of parameter as parsed from XTCE
    """
    name: str
    parameter_type: parameter_types.ParameterType
    short_description: Optional[str] = None
    long_description: Optional[str] = None

    def parse(self, packet: packets.CCSDSPacket) -> None:
        """Parse this parameter from the packet data.

        Parse the parameter and add it to the packet dictionary.
        """
        packet[self.name] = self.parameter_type.parse_value(packet)

    @classmethod
    def from_xml(
            cls,
            element: ElementTree.Element,
            *,
            parameter_type_lookup: dict[str, parameter_types.ParameterType],
            tree: Optional[ElementTree.ElementTree] = None,
            parameter_lookup: Optional[dict[str, any]] = None,
            container_lookup: Optional[dict[str, any]] = None
    ) -> 'Parameter':
        """Create a Parameter object from an XML element.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        tree: Optional[ElementTree.Element]
            Ignored
        parameter_lookup: Optional[dict]
            Ignored
        parameter_type_lookup: dict[str, ParameterType]
            Ignored
        container_lookup: Optional[dict[str, SequenceContainer]]
            Ignored

        Returns
        -------
        : Parameter
        """
        parameter_name = element.attrib['name']

        parameter_type_name = element.attrib['parameterTypeRef']

        # Lookup from within the parameter type cache
        parameter_type_object = parameter_type_lookup[parameter_type_name]

        parameter_short_description = element.attrib['shortDescription'] if (
                'shortDescription' in element.attrib
        ) else None
        parameter_long_description = element.find('LongDescription').text if (
                element.find('LongDescription') is not None
        ) else None

        return cls(
            name=parameter_name,
            parameter_type=parameter_type_object,
            short_description=parameter_short_description,
            long_description=parameter_long_description
        )

    def to_xml(self, *, elmaker: ElementMaker) -> ElementTree.Element:
        """Create a Parameter XML element

        Parameters
        ----------
        elmaker : ElementMaker
            Element factory with predefined namespace

        Returns
        -------
        : ElementTree.Element
        """
        parameter_attrib = {
            "name": self.name,
            "parameterTypeRef": self.parameter_type.name,
        }
        if self.short_description:
            parameter_attrib["shortDescription"] = self.short_description

        element = elmaker.Parameter(
            **parameter_attrib
        )

        if self.long_description:
            element.append(
                elmaker.LongDescription(self.long_description)
            )

        return element
