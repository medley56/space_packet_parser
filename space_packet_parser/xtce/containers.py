"""Module with XTCE models related to SequenceContainers"""
from dataclasses import dataclass, field
from typing import Optional, Union

from lxml import etree as ElementTree
from lxml.builder import ElementMaker

from space_packet_parser import common, packets
from space_packet_parser.exceptions import ElementNotFoundError
from space_packet_parser.xtce import comparisons, parameter_types, parameters


@dataclass
class SequenceContainer(common.Parseable, common.XmlObject):
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
    inheritors : Optional[list]
        List of SequenceContainer objects that may inherit this one's entry list if their restriction criteria
        are met. Any SequenceContainers with this container as base_container_name should be listed here.
    """
    name: str
    entry_list: list[Union[parameters.Parameter, 'SequenceContainer']]
    short_description: Optional[str] = None
    long_description: Optional[str] = None
    base_container_name: Optional[str] = None
    restriction_criteria: Optional[list[comparisons.MatchCriteria]] = field(default_factory=lambda: [])
    abstract: bool = False
    inheritors: Optional[list[str]] = field(default_factory=lambda: [])

    def __post_init__(self):
        # Handle the explicit None passing for default values
        self.restriction_criteria = self.restriction_criteria or []
        self.inheritors = self.inheritors or []

    def parse(self, packet: packets.CCSDSPacket) -> None:
        """Parse the entry list of parameters/containers in the order they are expected in the packet.

        This could be recursive if the entry list contains SequenceContainers.
        """
        for entry in self.entry_list:
            entry.parse(packet=packet)

    @classmethod
    def from_xml(
            cls,
            element: ElementTree.Element,
            *,
            tree: ElementTree.ElementTree,
            parameter_lookup: dict[str, parameters.Parameter],
            container_lookup: Optional[dict[str, any]],
            parameter_type_lookup: Optional[dict[str, parameter_types.ParameterType]] = None
    ) -> 'SequenceContainer':
        """Parses the list of parameters in a SequenceContainer element, recursively parsing nested SequenceContainers
        to build an entry list of parameters that flattens the nested structure to derive a sequential ordering of
        expected parameters for each SequenceContainer. Note that this also stores entry lists for containers that are
        not intended to stand alone.

        Parameters
        ----------
        tree : ElementTree.ElementTree
            Full XTCE tree
        element : ElementTree.Element
            The SequenceContainer element to parse.
        parameter_lookup : dict[str, parameters.Parameter]
            Parameters contained in the entry lists of sequence containers
        container_lookup: Optional[dict[str, SequenceContainer]]
            Containers already parsed, used to sort out duplicate references
        parameter_type_lookup : Optional[dict[str, parameter_types.ParameterType]]
            Ignored.

        Returns
        -------
        : cls
            SequenceContainer containing an entry_list of SequenceContainers and Parameters with ParameterTypes
            in the order expected in a packet.
        """
        entry_list = []  # List to house Parameters and nested SequenceContainers for the current SequenceContainer
        try:
            base_container, restriction_criteria = cls._get_base_container_element(tree, element)
            base_container_name = base_container.attrib['name']
            if base_container_name not in container_lookup:
                base_sequence_container = cls.from_xml(
                    base_container,
                    tree=tree,
                    parameter_lookup=parameter_lookup,
                    container_lookup=container_lookup,
                )
                container_lookup[base_sequence_container.name] = base_sequence_container
        except ElementNotFoundError:
            base_container_name = None
            restriction_criteria = None

        for entry in element.find('EntryList').iterfind('*'):
            entry_tag_name = ElementTree.QName(entry).localname
            if entry_tag_name == 'ParameterRefEntry':
                parameter_name = entry.attrib['parameterRef']
                entry_list.append(parameter_lookup[parameter_name])  # KeyError if parameter is not in the lookup

            elif entry_tag_name == 'ContainerRefEntry':
                # This container may not have been parsed yet. We need to parse it now so we might as well
                # add it to the container lookup dict.
                if entry.attrib['containerRef'] in container_lookup:
                    nested_container = container_lookup[entry.attrib['containerRef']]
                else:
                    nested_container_element = cls._get_container_element(
                        tree,
                        name=entry.attrib['containerRef']
                    )
                    nested_container = cls.from_xml(
                            nested_container_element,
                            tree=tree,
                            parameter_lookup=parameter_lookup,
                            container_lookup=container_lookup
                        )
                    container_lookup[nested_container.name] = nested_container
                entry_list.append(
                    nested_container
                )

        short_description = element.attrib.get('shortDescription', None)

        if (long_description_element := element.find('LongDescription')) is not None:
            long_description = long_description_element.text
        else:
            long_description = None

        return cls(name=element.attrib['name'],
                   entry_list=entry_list,
                   base_container_name=base_container_name,
                   restriction_criteria=restriction_criteria,
                   abstract=(element.attrib['abstract'].lower() == 'true') if 'abstract' in element.attrib else False,
                   short_description=short_description,
                   long_description=long_description)

    def to_xml(self, *, elmaker: ElementMaker) -> ElementTree.Element:
        """Create a SequenceContainer XML element

        Parameters
        ----------
        elmaker : ElementMaker
            Element factory with predefined namespace

        Returns
        -------
        : ElementTree.Element
        """
        em = elmaker
        sc_attrib = {
            "abstract": str(self.abstract).lower(),
            "name": self.name
        }
        if self.short_description:
            sc_attrib["shortDescription"] = self.short_description

        sc = em.SequenceContainer(**sc_attrib)

        if self.long_description:
            sc.append(
                em.LongDescription(self.long_description)
            )

        if (
                (self.restriction_criteria and not self.base_container_name) or
                (not self.restriction_criteria and self.base_container_name)
        ):
            raise ValueError("The restriction_criteria and base_container_name must be specified together or "
                             "not at all.")

        if len(self.restriction_criteria) == 1:
            restrictions = self.restriction_criteria[0].to_xml(elmaker=elmaker)
        else:
            restrictions = em.ComparisonList(
                *(rc.to_xml(elmaker=elmaker) for rc in self.restriction_criteria)
            )

        if self.base_container_name:
            sc.append(
                em.BaseContainer(
                    em.RestrictionCriteria(restrictions),
                    containerRef=self.base_container_name
                ),
            )

        entry_list = em.EntryList()
        for entry in self.entry_list:
            if isinstance(entry, parameters.Parameter):
                entry_element = em.ParameterRefEntry(parameterRef=entry.name)
            elif isinstance(entry, SequenceContainer):
                entry_element = em.ContainerRefEntry(containerRef=entry.name)
            else:
                raise ValueError(f"Unrecognized element in EntryList for sequence container {self.name}")
            entry_list.append(entry_element)

        sc.append(entry_list)

        return sc

    @staticmethod
    def _get_container_element(
            tree: ElementTree.ElementTree,
            name: str
    ) -> ElementTree.Element:
        """Finds an XTCE container <xtce:SequenceContainer> by name.

        Parameters
        ----------
        name : str
            Name of the container to find

        Returns
        -------
        : ElementTree.Element
        """
        containers = tree.getroot().find("TelemetryMetaData/ContainerSet").findall(f"SequenceContainer[@name='{name}']")
        if len(containers) != 1:
            raise ValueError(f"Found {len(containers)} matching container_set with name {name}. "
                             f"Container names are expected to exist and be unique.")
        return containers[0]

    @staticmethod
    def _get_base_container_element(
            tree: ElementTree.Element,
            container_element: ElementTree.Element
    ) -> tuple[ElementTree.Element, list[comparisons.MatchCriteria]]:
        """Finds the referenced base container of an existing XTCE container element,
        including its inheritance restrictions.

        Parameters
        ----------
        tree : ElementTree.ElementTree
            Full XML tree object, for finding additional referenced containers if necessary.
        container_element : ElementTree.Element
            The container element for which to find its base container.

        Returns
        -------
        : tuple[ElementTree.Element, list[comparisons.MatchCriteria]]
            The base container element of the input container_element.
            The restriction criteria for the inheritance.
        """
        base_container_element = container_element.find('BaseContainer')
        if base_container_element is None:
            raise ElementNotFoundError(
                f"Container element {container_element} does not have a BaseContainer child element.")

        if (restriction_criteria_element := base_container_element.find('RestrictionCriteria')) is not None:
            if (comparison_list_element := restriction_criteria_element.find('ComparisonList')) is not None:
                restrictions = [comparisons.Comparison.from_xml(comp) for comp in comparison_list_element.iterfind('*')]
            elif (comparison_element := restriction_criteria_element.find('Comparison')) is not None:
                restrictions = [comparisons.Comparison.from_xml(comparison_element)]
            elif (boolean_expression_element := restriction_criteria_element.find('BooleanExpression')) is not None:
                restrictions = [comparisons.BooleanExpression.from_xml(boolean_expression_element)]
            elif restriction_criteria_element.find('CustomAlgorithm') is not None:
                raise NotImplementedError("Detected a CustomAlgorithm in a RestrictionCriteria element. "
                                          "This is not implemented.")
            else:
                raise ValueError("Detected a RestrictionCriteria element containing no "
                                 "Comparison, ComparisonList, BooleanExpression or CustomAlgorithm.")
            # TODO: Implement NextContainer support inside RestrictionCriteria. This might make the parser much
            #    more complicated.
        else:
            restrictions = []
        return (
            SequenceContainer._get_container_element(tree, base_container_element.attrib['containerRef']),
            restrictions
        )

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
