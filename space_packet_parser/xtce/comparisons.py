"""Matching logical objects"""
import warnings
from abc import ABCMeta, abstractmethod
from collections import namedtuple
from typing import Any, Optional, Union

import lxml.etree as ElementTree
from lxml.builder import ElementMaker

from space_packet_parser import common, packets
from space_packet_parser.exceptions import ComparisonError


class MatchCriteria(common.AttrComparable, common.XmlObject, metaclass=ABCMeta):
    """<xtce:MatchCriteriaType>
    This class stores criteria for performing logical operations based on parameter values
    Classes that inherit from this ABC include those that represent <xtce:Comparison>,
    <xtce:BooleanExpression>, and <xtce:CustomAlgorithm> (not supported)
    """

    # Valid operator representations in XML. Note: the XTCE spec only allows for &gt; style representations of < and >
    #   Python's XML parser doesn't appear to support &eq; &ne; &le; or &ge;
    # We have implemented support for bash-style comparisons just in case.
    _valid_operators = {
        "==": "__eq__", "eq": "__eq__",  # equal to
        "!=": "__ne__", "neq": "__ne__",  # not equal to
        "&lt;": "__lt__", "lt": "__lt__", "<": "__lt__",  # less than
        "&gt;": "__gt__", "gt": "__gt__", ">": "__gt__",  # greater than
        "&lt;=": "__le__", "leq": "__le__", "<=": "__le__",  # less than or equal to
        "&gt;=": "__ge__", "geq": "__ge__", ">=": "__ge__",  # greater than or equal to
    }

    @abstractmethod
    def evaluate(self,
                 packet: packets.Packet,
                 current_parsed_value: Optional[Union[int, float]] = None) -> bool:
        """Evaluate match criteria down to a boolean.

        Parameters
        ----------
        packet : packets.Packet
            Packet data used to evaluate truthyness of the match criteria.
        current_parsed_value : any, Optional
            Uncalibrated value that is currently being matched (e.g. as a candidate for calibration).
            Used to resolve comparisons that reference their own raw value as a condition.

        Returns
        -------
        : bool
            Truthyness of this match criteria based on previously parsed values.
        """
        raise NotImplementedError()


class Comparison(MatchCriteria):
    """<xtce:Comparison>"""

    def __init__(self, required_value: str, referenced_parameter: str,
                 operator: str = "==", use_calibrated_value: bool = True):
        """Constructor

        Parameters
        ----------
        operator : str
            String representation of the comparison operation. e.g. "<=" or "leq"
        required_value : str
            Value with which to compare the referenced parameter using the operator. This value is dynamically
            coerced to the referenced parameter type during evaluation.
        referenced_parameter : str
            Name of the parameter to compare with the value.
        use_calibrated_value : bool
            Whether or not to calibrate the value before performing the comparison.
        """
        self.required_value = required_value
        self.referenced_parameter = referenced_parameter
        self.operator = operator
        self.use_calibrated_value = use_calibrated_value
        self._validate()

    def __repr__(self):
        return f"{self.__class__.__name__}({self.referenced_parameter} {self.operator} {self.required_value})"

    def _validate(self):
        """Validate state as logically consistent.

        Returns
        -------
        None
        """
        if self.operator not in self._valid_operators:
            raise ValueError(f"Unrecognized operator syntax {self.operator}. "
                             f"Must be one of "
                             f"{set(self._valid_operators.keys())}")

    @classmethod
    def from_xml(
            cls,
            element: ElementTree.Element,
            *,
            tree: Optional[ElementTree.Element] = None,
            parameter_lookup: Optional[dict[str, any]] = None,
            parameter_type_lookup: Optional[dict[str, any]] = None,
            container_lookup: Optional[dict[str, any]] = None
    ) -> 'Comparison':
        """Create

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        tree: Optional[ElementTree.Element]
            Ignored
        parameter_lookup: Optional[dict]
            Ignored
        parameter_type_lookup: Optional[dict]
            Ignored
        container_lookup: Optional[dict[str, SequenceContainer]]
            Ignored

        Returns
        -------
        : Comparison
        """
        use_calibrated_value = True  # Default
        if 'useCalibratedValue' in element.attrib:
            use_calibrated_value = element.attrib['useCalibratedValue'].lower() == 'true'

        value = element.attrib['value']

        parameter_name = element.attrib['parameterRef']
        operator = '=='
        if 'comparisonOperator' in element.attrib:
            operator = element.attrib['comparisonOperator']

        return cls(value, parameter_name, operator=operator, use_calibrated_value=use_calibrated_value)

    def to_xml(self, *, elmaker: ElementMaker) -> ElementTree.Element:
        """Create a Comparison XML element

        Parameters
        ----------
        elmaker : ElementMaker
            Element factory with predefined namespace

        Returns
        -------
        : ElementTree.Element
        """
        return elmaker.Comparison(
            parameterRef=self.referenced_parameter,
            useCalibratedValue=str(self.use_calibrated_value).lower(),
            comparisonOperator=self.operator,
            value=str(self.required_value)
        )

    def evaluate(self,
                 packet: packets.Packet,
                 current_parsed_value: Optional[Union[int, float]] = None) -> bool:
        """Evaluate comparison down to a boolean. If the parameter to compare is not present in the parsed_data dict,
        we assume that we are comparing against the current raw value in current_parsed_value.

        Parameters
        ----------
        packet : packets.Packet
            Packet data used to evaluate truthyness of the match criteria.
        current_parsed_value : Union[int, float]
            Optional. Uncalibrated value that is currently a candidate for calibration and so has not yet been added
            to the packet. Used to resolve calibrator conditions that reference their own
            raw value as a comparate.

        Returns
        -------
        : bool
            Truthyness of this match criteria based on previously parsed values.
        """
        if self.referenced_parameter in packet:
            if self.use_calibrated_value:
                parsed_value = packet[self.referenced_parameter]
                if not parsed_value:
                    raise ComparisonError(f"Comparison {self} was instructed to useCalibratedValue (the default)"
                                          f"but {self.referenced_parameter} does not appear to have a derived value.")
            else:
                parsed_value = packet[self.referenced_parameter].raw_value
        elif current_parsed_value is not None:
            # Assume then that the comparison is a reference to its own uncalibrated value
            parsed_value = current_parsed_value
            if self.use_calibrated_value:
                warnings.warn("Performing a comparison against a current value (e.g. a Comparison within a "
                              "context calibrator contains a reference to its own uncalibrated value but use_"
                              "calibrated_value is set to true. This is nonsensical. Using the uncalibrated value...")
        else:
            raise ValueError("Attempting to resolve a Comparison expression but the referenced parameter does not "
                             "appear in the parsed data so far and no current raw value was passed "
                             "to compare with.")

        operator = self._valid_operators[self.operator]
        t_comparate = type(parsed_value)
        try:
            required_value = t_comparate(self.required_value)
        except ValueError as err:
            raise ComparisonError(f"Unable to coerce {self.required_value} of type {type(self.required_value)} to "
                                  f"type {t_comparate} for comparison evaluation.") from err
        if required_value is None or parsed_value is None:
            raise ValueError(f"Error in Comparison. Cannot compare {required_value} with {parsed_value}. "
                             "Neither should be None.")

        # x.__le__(y) style call
        return getattr(parsed_value, operator)(required_value)


class Condition(MatchCriteria):
    """<xtce:Condition>
    Note: This xtce model doesn't actually inherit from MatchCriteria in the UML model,
    but it's functionally close enough that we inherit the class here.
    """

    def __init__(self,
                 left_param: str,
                 operator: str,
                 *,
                 right_param: Optional[str] = None,
                 right_value: Optional[Any] = None,
                 left_use_calibrated_value: bool = True,
                 right_use_calibrated_value: bool = True):
        """Constructor

        Parameters
        ----------
        left_param : str
            Parameter name on the LH side of the comparison
        operator : str
            Member of MatchCriteria._valid_operators.
        right_param : Optional[str]
            Parameter name on the RH side of the comparison.
        right_value: Optional[Any]
            Used in case of comparison with a fixed xtce:Value on the RH side.
        left_use_calibrated_value : bool, Optional
            Default is True. If False, comparison is made against the uncalibrated value.
        right_use_calibrated_value: bool, Optional
            Default is True. If False, comparison is made against the uncalibrated value.
        """
        self.left_param = left_param
        self.right_param = right_param
        self.right_value = right_value
        self.operator = operator
        self.right_use_calibrated_value = right_use_calibrated_value
        self.left_use_calibrated_value = left_use_calibrated_value
        self._validate()

    def __repr__(self):
        return f"{self.__class__.__name__}({self.left_param} {self.operator} {self.right_param or self.right_value})"

    def _validate(self):
        """Check that the instantiated object actually makes logical sense.

        Returns
        -------
        None
        """
        if self.operator not in self._valid_operators:
            raise ValueError(f"Unrecognized operator syntax {self.operator}. "
                             f"Must be one of "
                             f"{set(self._valid_operators.keys())}")
        if self.right_param and self.right_value:
            raise ComparisonError(f"Received both a right_value and a right_param reference to Condition {self}.")
        if self.right_value and self.right_use_calibrated_value:
            raise ComparisonError(f"Unable to use calibrated form of a fixed value in Condition {self}.")

    @staticmethod
    def _parse_parameter_instance_ref(element: ElementTree.Element):
        """Parse an xtce:ParameterInstanceRef element

        Parameters
        ----------
        element: ElementTree.Element
            xtce:ParameterInstanceRef element

        Returns
        -------
        parameter_name: str
            Name of referenced parameter
        use_calibrated_value: bool
            Whether to use the calibrated form of the referenced parameter
        """
        parameter_name = element.attrib['parameterRef']
        use_calibrated_value = True  # Default
        if 'useCalibratedValue' in element.attrib:
            use_calibrated_value = element.attrib['useCalibratedValue'].lower() == 'true'
        return parameter_name, use_calibrated_value

    @classmethod
    def from_xml(
            cls,
            element: ElementTree.Element,
            *,
            tree: Optional[ElementTree.Element] = None,
            parameter_lookup: Optional[dict[str, any]] = None,
            parameter_type_lookup: Optional[dict[str, any]] = None,
            container_lookup: Optional[dict[str, any]] = None
    ) -> 'Condition':
        """Classmethod to create a Condition object from an XML element.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        tree: Optional[ElementTree.Element]
            Ignored
        parameter_lookup: Optional[dict]
            Ignored
        parameter_type_lookup: Optional[dict]
            Ignored
        container_lookup: Optional[dict[str, SequenceContainer]]
            Ignored

        Returns
        -------
        : cls
        """
        operator = element.find('ComparisonOperator').text
        params = element.findall('ParameterInstanceRef')
        if len(params) == 1:
            # XTCE green book Figure 3-5 specifies if only one ParameterInstanceRef, it is the LHS of the operator
            left_param, use_calibrated_value = cls._parse_parameter_instance_ref(params[0])
            right_value = element.find('Value').text
            return cls(left_param, operator, right_value=right_value,
                       left_use_calibrated_value=use_calibrated_value,
                       right_use_calibrated_value=False)
        if len(params) == 2:
            left_param, left_use_calibrated_value = cls._parse_parameter_instance_ref(params[0])
            right_param, right_use_calibrated_value = cls._parse_parameter_instance_ref(params[1])
            return cls(left_param, operator, right_param=right_param,
                       left_use_calibrated_value=left_use_calibrated_value,
                       right_use_calibrated_value=right_use_calibrated_value)
        raise ValueError(f'Failed to parse a Condition element {element}. '
                         'See 3.4.3.4.2 of XTCE Green Book CCSDS 660.1-G-2')

    def to_xml(self, *, elmaker: ElementMaker) -> ElementTree.Element:
        """Create a Condition XML element

        Parameters
        ----------
        elmaker : ElementMaker
            Element factory with predefined namespace

        Returns
        -------
        : ElementTree.Element
        """
        condition = elmaker.Condition(
            elmaker.ParameterInstanceRef(
                parameterRef=self.left_param,
                useCalibratedValue=str(self.left_use_calibrated_value).lower(),
            ),
            elmaker.ComparisonOperator(self.operator)
        )

        if self.right_param:
            condition.append(
                elmaker.ParameterInstanceRef(
                    parameterRef=self.right_param,
                    useCalibratedValue=str(self.right_use_calibrated_value).lower(),
                )
            )
        else:
            condition.append(
                elmaker.Value(str(self.right_value))
            )

        return condition

    def evaluate(self,
                 packet: packets.Packet,
                 current_parsed_value: Optional[Union[int, float]] = None) -> bool:
        """Evaluate match criteria down to a boolean.

        Parameters
        ----------
        packet : packets.Packet
            Packet data used to evaluate truthyness of the match criteria.
        current_parsed_value : Optional[Union[int, float]]
            Current value being parsed. NOTE: This is currently ignored. See the TODO item below.

        Returns
        -------
        : bool
            Truthyness of this match criteria based on previously parsed values.
        """

        def _get_parsed_value(parameter_name: str, use_calibrated: bool):
            """Retrieves the previously parsed value from the passed in packet"""
            try:
                return packet[parameter_name] if use_calibrated \
                    else packet[parameter_name].raw_value
            except KeyError as e:
                raise ComparisonError(f"Attempting to perform a Condition evaluation on {self.left_param} but "
                                      "the referenced parameter does not appear in the hitherto parsed data passed to "
                                      "the evaluate method. If you intended a comparison against the raw value of the "
                                      "parameter currently being parsed, unfortunately that is not currently supported."
                                      ) from e

        # TODO: Consider allowing one of the parameters to be the parameter currently being evaluated.
        #    This isn't explicitly provided for in the XTCE spec but it seems reasonable to be able to
        #    perform conditionals against the current raw value of a parameter, e.g. while determining if it
        #    should be calibrated. Note that only one of the parameters can be used this way and it must reference
        #    an uncalibrated value so the logic and error handling must be done carefully.
        left_value = _get_parsed_value(self.left_param, self.left_use_calibrated_value)
        # Convert XML operator representation to a python-compatible operator (e.g. '&gt;' to '__gt__')
        operator = self._valid_operators[self.operator]

        if self.right_param is not None:
            right_value = _get_parsed_value(self.right_param, self.right_use_calibrated_value)
        elif self.right_value is not None:
            t_left_param = type(left_value)  # Coerce right value xml representation to correct type
            right_value = t_left_param(self.right_value)
        else:
            raise ValueError(f"Error when evaluating condition {self}. Neither right_param nor right_value is set.")
        if left_value is None or right_value is None:
            raise ComparisonError(f"Error comparing {left_value} and {right_value}. Neither should be None.")

        # x.__le__(y) style call
        return getattr(left_value, operator)(right_value)


class Anded(namedtuple('Anded', ['conditions', 'ors'])):
    """Tuple object for AND operations in BooleanExpression"""
    def __repr__(self):
        return " && ".join(str(c) for c in self.conditions)


class Ored(namedtuple('Ored', ['conditions', 'ands'])):
    """Tuple object for OR operations in BooleanExpression"""
    def __repr__(self):
        return " || ".join(str(c) for c in self.conditions)


class BooleanExpression(MatchCriteria):
    """<xtce:BooleanExpression>"""

    def __init__(self, expression: Union[Condition, Anded, Ored]):
        self.expression = expression

    def __repr__(self):
        return f"BooleanExpression({self.expression})"

    @classmethod
    def from_xml(
            cls,
            element: ElementTree.Element,
            *,
            tree: Optional[ElementTree.Element] = None,
            parameter_lookup: Optional[dict[str, any]] = None,
            parameter_type_lookup: Optional[dict[str, any]] = None,
            container_lookup: Optional[dict[str, any]] = None
    ) -> 'BooleanExpression':
        """Abstract classmethod to create a match criteria object from an XML element.

        Parameters
        ----------
        element : ElementTree.Element
           XML element
        tree: Optional[ElementTree.Element]
            Ignored
        parameter_lookup: Optional[dict]
            Ignored
        parameter_type_lookup: Optional[dict]
            Ignored
        container_lookup: Optional[dict[str, SequenceContainer]]
            Ignored

        Returns
        -------
        : BooleanExpression
        """

        def _parse_anded(anded_el: ElementTree.Element) -> Anded:
            """Create an Anded object from an xtce:ANDedConditions element

            Parameters
            ----------
            anded_el: ElementTree.Element
                xtce:ANDedConditions element

            Returns
            -------
            : Anded
            """
            conditions = [Condition.from_xml(el)
                          for el in anded_el.iterfind('Condition')]
            anded_ors = [_parse_ored(anded_or) for anded_or in anded_el.iterfind('ORedConditions')]
            return Anded(conditions, anded_ors)

        def _parse_ored(ored_el: ElementTree.Element) -> Ored:
            """Create an Ored object from an xtce:ARedConditions element

            Parameters
            ----------
            ored_el: ElementTree.Element
                xtce:ORedConditions element

            Returns
            -------
            : Ored
            """
            conditions = [Condition.from_xml(el)
                          for el in ored_el.iterfind('Condition')]
            ored_ands = [_parse_anded(ored_and) for ored_and in ored_el.iterfind('ANDedConditions')]
            return Ored(conditions, ored_ands)

        if (condition_element := element.find('Condition')) is not None:
            condition = Condition.from_xml(condition_element)
            return cls(expression=condition)
        if (anded_conditions_element := element.find('ANDedConditions')) is not None:
            return cls(expression=_parse_anded(anded_conditions_element))
        if (ored_conditions_element := element.find('ORedConditions')) is not None:
            return cls(expression=_parse_ored(ored_conditions_element))
        raise ValueError(f"Failed to parse {element}")

    def evaluate(self,
                 packet: packets.Packet,
                 current_parsed_value: Optional[Union[int, float]] = None) -> bool:
        """Evaluate the criteria in the BooleanExpression down to a single boolean.

        Parameters
        ----------
        packet : packets.Packet
            Packet data used to evaluate truthyness of the match criteria.
        current_parsed_value : Optional[Union[int, float]]
            Current value being parsed.

        Returns
        -------
        : bool
            Truthyness of this match criteria based on previously parsed values.
        """

        def _or(ored: Ored):
            for condition in ored.conditions:
                if condition.evaluate(packet) is True:
                    return True
            for anded in ored.ands:
                if _and(anded):
                    return True
            return False

        def _and(anded: Anded):
            for condition in anded.conditions:
                if condition.evaluate(packet) is False:
                    return False
            for ored in anded.ors:
                if not _or(ored):
                    return False
            return True

        if isinstance(self.expression, Condition):
            return self.expression.evaluate(packet)
        if isinstance(self.expression, Anded):
            return _and(self.expression)
        if isinstance(self.expression, Ored):
            return _or(self.expression)

        raise ValueError(f"Error evaluating an unknown expression {self.expression}.")

    def to_xml(self, *, elmaker: ElementMaker) -> ElementTree.Element:
        """Create a Condition XML element

        Parameters
        ----------
        elmaker : ElementMaker
            Element factory with predefined namespace

        Returns
        -------
        : ElementTree.Element
        """
        def _serialize_anded(anded: Anded) -> ElementTree.Element:
            return elmaker.ANDedConditions(
                *(cond.to_xml(elmaker=elmaker) for cond in anded.conditions),
                *(_serialize_ored(ored) for ored in anded.ors)
            )

        def _serialize_ored(ored: Ored) -> ElementTree.Element:
            return elmaker.ORedConditions(
                *(cond.to_xml(elmaker=elmaker) for cond in ored.conditions),
                *(_serialize_anded(anded) for anded in ored.ands)
            )

        element = elmaker.BooleanExpression()

        if isinstance(self.expression, Condition):
            element.append(self.expression.to_xml(elmaker=elmaker))
        elif isinstance(self.expression, Anded):
            element.append(_serialize_anded(self.expression))
        else:
            element.append(_serialize_ored(self.expression))

        return element

class DiscreteLookup(common.AttrComparable, common.XmlObject):
    """<xtce:DiscreteLookup>"""

    def __init__(self, match_criteria: list[Comparison], lookup_value: Union[int, float]):
        """Constructor

        Parameters
        ----------
        match_criteria : list[Comparison]
            List of criteria to determine if the lookup value should be returned during evaluation.
        lookup_value : Union[int, float]
            Value to return from the lookup if the criteria evaluate true
        """
        self.match_criteria = match_criteria
        self.lookup_value = lookup_value

    @classmethod
    def from_xml(
            cls,
            element: ElementTree.Element,
            *,
            tree: Optional[ElementTree.ElementTree] = None,
            parameter_lookup: Optional[dict[str, any]] = None,
            parameter_type_lookup: Optional[dict[str, any]] = None,
            container_lookup: Optional[dict[str, any]] = None
    ) -> 'DiscreteLookup':
        """Create a DiscreteLookup object from an <xtce:DiscreteLookup> XML element

        Parameters
        ----------
        element : ElementTree.Element
            <xtce:DiscreteLookup> XML element from which to parse the DiscreteLookup object.
        tree: Optional[ElementTree.Element]
            Ignored
        parameter_lookup: Optional[dict]
            Ignored
        parameter_type_lookup: Optional[dict]
            Ignored
        container_lookup: Optional[dict[str, SequenceContainer]]
            Ignored

        Returns
        -------
        : DiscreteLookup
        """
        lookup_value = float(element.attrib['value'])
        if (comparison_list_element := element.find('ComparisonList')) is not None:
            match_criteria = [Comparison.from_xml(el) for el in comparison_list_element.iterfind("*")]
        elif (comparison_element := element.find('Comparison')) is not None:
            match_criteria = [Comparison.from_xml(comparison_element)]
        else:
            raise NotImplementedError("Only Comparison and ComparisonList are implemented for DiscreteLookup.")

        return cls(match_criteria, lookup_value)

    def to_xml(self, *, elmaker: ElementMaker) -> ElementTree.Element:
        """Create a DiscreteLookup XML element

        Parameters
        ----------
        elmaker : ElementMaker
            ElementMaker factory

        Returns
        -------
        : ElementTree.Element
        """
        match_criteria = (c.to_xml(elmaker=elmaker) for c in self.match_criteria)

        if len(self.match_criteria) > 1:
            dl_contents = (elmaker.ComparisonList(*match_criteria), )
        else:
            dl_contents = match_criteria

        return elmaker.DiscreteLookup(
            *dl_contents,
            value=str(self.lookup_value)
        )

    def evaluate(self, packet: packets.Packet, current_parsed_value: Optional[Union[int, float]] = None) -> Any:
        """Evaluate the lookup to determine if it is valid.

        Parameters
        ----------
        packet : packets.Packet
            Packet data used to evaluate truthyness of the match criteria.
        current_parsed_value: Optional[Union[int, float]]
            If referenced parameter in criterion isn't in the packet, we assume we are comparing against this
            currently parsed value.

        Returns
        -------
        : any
            Return the lookup value if the match criteria evaluate true. Return None otherwise.
        """
        if all(criterion.evaluate(packet, current_parsed_value) for criterion in self.match_criteria):
            # If the parsed data so far satisfy all the match criteria
            return self.lookup_value
        return None
