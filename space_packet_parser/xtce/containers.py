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
            ns: dict,
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
        ns : dict
            XML namespace dict
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
            base_container, restriction_criteria = cls._get_base_container_element(tree, element, ns)
            base_container_name = base_container.attrib['name']
            if base_container_name not in container_lookup:
                base_sequence_container = cls.from_xml(
                    base_container,
                    tree=tree,
                    parameter_lookup=parameter_lookup,
                    container_lookup=container_lookup,
                    ns=ns
                )
                container_lookup[base_sequence_container.name] = base_sequence_container
        except ElementNotFoundError:
            base_container_name = None
            restriction_criteria = None

        # TODO: These hardcoded namespace prefixes need to be made dynamic according to the namespace uri
        #  This probably means passing xtce_namespace_uri into this
        container_contents = element.find('xtce:EntryList', ns).findall('*', ns)

        for entry in container_contents:
            if entry.tag == '{{{xtce}}}ParameterRefEntry'.format(**ns):
                parameter_name = entry.attrib['parameterRef']
                entry_list.append(parameter_lookup[parameter_name])  # KeyError if parameter is not in the lookup

            elif entry.tag == '{{{xtce}}}ContainerRefEntry'.format(
                    **ns):

                # This container may not have been parsed yet. We need to parse it now so we might as well
                # add it to the container lookup dict.
                if entry.attrib['containerRef'] in container_lookup:
                    nested_container = container_lookup[entry.attrib['containerRef']]
                else:
                    nested_container_element = cls._get_container_element(
                        tree,
                        name=entry.attrib['containerRef'],
                        ns=ns
                    )
                    nested_container = cls.from_xml(
                            nested_container_element,
                            tree=tree,
                            parameter_lookup=parameter_lookup,
                            container_lookup=container_lookup,
                            ns=ns
                        )
                entry_list.append(
                    nested_container
                )

        short_description = element.attrib.get('shortDescription', None)

        if (long_description_element := element.find('xtce:LongDescription', ns)) is not None:
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
            name: str,
            ns: dict
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
        containers = tree.getroot().findall(
            f"xtce:TelemetryMetaData/xtce:ContainerSet/xtce:SequenceContainer[@name='{name}']",
            ns
        )
        if len(containers) != 1:
            raise ValueError(f"Found {len(containers)} matching container_set with name {name}. "
                             f"Container names are expected to exist and be unique.")
        return containers[0]

    @staticmethod
    def _get_base_container_element(
            tree: ElementTree.Element,
            container_element: ElementTree.Element,
            ns: dict
    ) -> tuple[ElementTree.Element, list[comparisons.MatchCriteria]]:
        """Finds the referenced base container of an existing XTCE container element,
        including its inheritance restrictions.

        Parameters
        ----------
        container_element : ElementTree.Element
            The container element for which to find its base container.

        Returns
        -------
        : tuple[ElementTree.Element, list[comparisons.MatchCriteria]]
            The base container element of the input container_element.
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
                    comparisons.Comparison.from_xml(comp, ns=ns) for comp in comparison_items]
            elif single_comparison_element is not None:
                restrictions = [
                    comparisons.Comparison.from_xml(single_comparison_element, ns=ns)]
            elif boolean_expression_element is not None:
                restrictions = [
                    comparisons.BooleanExpression.from_xml(boolean_expression_element, ns=ns)]
            else:
                raise ValueError("Detected a RestrictionCriteria element containing no "
                                 "Comparison, ComparisonList, BooleanExpression or CustomAlgorithm.")
            # TODO: Implement NextContainer support inside RestrictionCriteria. This might make the parser much
            #    more complicated.
        else:
            restrictions = []
        return (
            SequenceContainer._get_container_element(tree, base_container_element.attrib['containerRef'], ns),
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
