"""Module for parsing XTCE xml files to specify packet format"""
# Standard
from abc import ABCMeta
from collections import namedtuple
import inspect
import logging
from pathlib import Path
from typing import Tuple
import warnings
from xml.etree import ElementTree
# Installed
import bitstring

logger = logging.getLogger(__name__)

# TODO: Improve exceptions for specific failure modes


# Exceptions
class ElementNotFoundError(Exception):
    """Exception for missing XML element"""
    pass


class ComparisonError(Exception):
    """Exception for problems performing comparisons"""
    pass


class FormatStringError(Exception):
    """Error indicating a problem determining how to parse a variable length string."""
    pass


class DynamicLengthBinaryParameterError(Exception):
    """Exception to raise when we try to parse a dynamic length binary field as fixed length"""
    pass


class CalibrationError(Exception):
    """For errors encountered during value calibration"""
    pass


# Common comparable mixin
class AttrComparable(metaclass=ABCMeta):
    """Generic class that provides a notion of equality based on all non-callable, non-dunder attributes"""

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            raise NotImplementedError(f"No method to compare {type(other)} with {self.__class__}")

        compare = inspect.getmembers(self, lambda a: not inspect.isroutine(a))
        compare = [attr[0] for attr in compare
                   if not (attr[0].startswith('__') or attr[0].startswith(f'_{self.__class__.__name__}__'))]
        for attr in compare:
            if getattr(self, attr) != getattr(other, attr):
                print(f'Mismatch was in {attr}. {getattr(self, attr)} != {getattr(other, attr)}')
                return False
        return True


# Matching logical objects
class MatchCriteria(AttrComparable, metaclass=ABCMeta):
    """<xtce:MatchCriteriaType>
    This class stores criteria for performing logical operations based on parameter values
    Classes that inherit from this ABC include those that represent <xtce:Comparison>, <xtce:ComparisonList>,
    <xtce:BooleanExpression> (not supported), and <xtce:CustomAlgorithm> (not supported)
    """

    # Valid operator representations in XML. Note: the XTCE spec only allows for &gt; style representations of < and >
    #   Python's XML parser doesn't appear to support &eq; &ne; &le; or &ge;
    # We have implemented support for bash-style comparisons just in case.
    _valid_operators = {
        "==": "==", "eq": "==",  # equal to
        "!=": "!=", "neq": "!=",  # not equal to
        "&lt;": "<", "lt": "<",  # less than
        "&gt;": ">", "gt": ">",  # greater than
        "&lt;=": "<=", "leq": "<=",  # less than or equal to
        "&gt;=": ">=", "geq": ">=",  # greater than or equal to
    }

    @classmethod
    def from_match_criteria_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Abstract classmethod to create a match criteria object from an XML element.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        : cls
        """
        raise NotImplementedError()

    def evaluate(self, parsed_data: dict, current_parsed_value: int or float = None) -> bool:
        """Evaluate match criteria down to a boolean.

        Parameters
        ----------
        parsed_data : dict
            Dictionary of parsed parameter data so far. Used to evaluate truthyness of the match criteria.
        current_parsed_value : any, Optional
            Uncalibrated value that is currently being matched (e.g. as a candidate for calibration).
            Used to resolve comparisons that reference their own raw value as a condition.

        Returns
        -------
        : bool
            Truthyness of this match criteria based on parsed_data values.
        """
        raise NotImplementedError()


class Comparison(MatchCriteria):
    """<xtce:Comparison>"""

    def __init__(self, required_value: any, referenced_parameter: str,
                 operator: str = "==", use_calibrated_value: bool = True):
        """Constructor

        Parameters
        ----------
        operator : str
            String representation of the comparison operation. e.g. "<=" or "leq"
        required_value : any
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
        return f"<{self.__class__.__name__} {self.referenced_parameter}{self.operator}{self.required_value}>"

    def _validate(self):
        """Validate state as logically consistent.

        Returns
        -------
        None
        """
        if not (self.operator in self._valid_operators or self.operator in self._valid_operators.values()):
            raise ValueError(f"Unrecognized operator syntax {self.operator}. "
                             f"Must be one of "
                             f"{set(list(self._valid_operators.values()) + list(self._valid_operators.keys()))}")

    @classmethod
    def from_match_criteria_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Create

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        : cls
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

    def evaluate(self, parsed_data: dict, current_parsed_value: int or float = None) -> bool:
        """Evaluate comparison down to a boolean. If the parameter to compare is not present in the parsed_data dict,
        we assume that we are comparing against the current raw value in current_parsed_value.

        Parameters
        ----------
        parsed_data : dict
            Dictionary of parsed parameter data so far. Used to evaluate truthyness of the match criteria.
        current_parsed_value : int or float
            Optional. Uncalibrated value that is currently a candidate for calibration and so has not yet been added
            to the parsed_data dict. Used to resolve calibrator conditions that reference their own
            raw value as a comparate.

        Returns
        -------
        : bool
            Truthyness of this match criteria based on parsed_data values.
        """
        if self.referenced_parameter in parsed_data:
            if self.use_calibrated_value:
                parsed_value = parsed_data[self.referenced_parameter].derived_value
                if not parsed_value:
                    raise ComparisonError(f"Comparison {self} was instructed to useCalibratedValue (the default)"
                                          f"but {self.referenced_parameter} does not appear to have a derived value.")
            else:
                parsed_value = parsed_data[self.referenced_parameter].raw_value
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

        operator = (self.operator
                    if self.operator in self._valid_operators.values()
                    else self._valid_operators[self.operator])
        t_comparate = type(parsed_value)
        try:
            required_value = t_comparate(self.required_value)
        except ValueError as err:
            raise ComparisonError(f"Unable to coerce {self.required_value} of type {type(self.required_value)} to "
                                  f"type {t_comparate} for comparison evaluation.") from err
        if required_value is None or parsed_value is None:
            raise ValueError(f"Error in Comparison. Cannot compare {required_value} with {parsed_value}. "
                             "Neither should be None.")
        if isinstance(required_value, str):
            parsed_value = f"'{parsed_value}'"
            required_value = f"'{required_value}'"
        return eval(f"{parsed_value} {operator} {required_value}")  # pylint: disable=eval-used


class Condition(MatchCriteria):
    """<xtce:Condition>
    Note: This xtce model doesn't actually inherit from MatchCriteria in the UML model
    but it's functionally close enough that we inherit the class here.
    """

    def __init__(self, left_param: str, operator: str, right_param: str = None, right_value=None,
                 left_use_calibrated_value: bool = True, right_use_calibrated_value: bool = True):
        """Constructor

        Parameters
        ----------
        left_param : str
            Parameter name on the LH side of the comparison
        operator : str
            Member of MatchCriteria._valid_operators.
        right_param : str
            Parameter name on the RH side of the comparison.
        right_value: any, Optional
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

    def _validate(self):
        """Check that the instantiated object actually makes logical sense.

        Returns
        -------
        None
        """
        if not (self.operator in self._valid_operators or self.operator in self._valid_operators.values()):
            raise ValueError(f"Unrecognized operator syntax {self.operator}. "
                             f"Must be one of "
                             f"{set(list(self._valid_operators.values()) + list(self._valid_operators.keys()))}")
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
    def from_match_criteria_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Classmethod to create a Condition object from an XML element.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        : cls
        """
        operator = element.find('xtce:ComparisonOperator', ns).text
        params = element.findall('xtce:ParameterInstanceRef', ns)
        if len(params) == 1:
            left_param, use_calibrated_value = cls._parse_parameter_instance_ref(params[0])
            right_value = element.find('xtce:Value', ns).text
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

    def evaluate(self, parsed_data: dict, current_parsed_value: int or float = None) -> bool:
        """Evaluate match criteria down to a boolean.

        Parameters
        ----------
        parsed_data : dict
            Dictionary of parsed parameter data so far. Used to evaluate truthyness of the match criteria.
        current_parsed_value : int or float, Optional
            Current value being parsed. NOTE: This is currently ignored. See the TODO item below.

        Returns
        -------
        : bool
            Truthyness of this match criteria based on parsed_data values.
        """
        def _get_parsed_value(parameter_name: str, use_calibrated: bool):
            """Retrieves the previously parsed value from the passed in parsed_data"""
            try:
                return parsed_data[parameter_name].derived_value if use_calibrated \
                    else parsed_data[parameter_name].raw_value
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
        # Convert XML operator representation to a python-compatible operator (e.g. '&gt;' to '>')
        operator = (self.operator
                    if self.operator in self._valid_operators.values()
                    else self._valid_operators[self.operator])

        if self.right_param is not None:
            right_value = _get_parsed_value(self.right_param, self.right_use_calibrated_value)
        elif self.right_value is not None:
            t_left_param = type(left_value)  # Coerce right value xml representation to correct type
            right_value = t_left_param(self.right_value)
        else:
            raise ValueError(f"Error when evaluating condition {self}. Neither right_param nor right_value is set.")
        if left_value is None or right_value is None:
            raise ComparisonError(f"Error comparing {left_value} and {right_value}. Neither should be None.")
        if isinstance(left_value, str):
            left_value = f"'{left_value}'"
            right_value = f"'{right_value}'"
        return eval(f"{left_value} {operator} {right_value}")  # pylint: disable=eval-used


Anded = namedtuple('Anded', ['conditions', 'ors'])
Ored = namedtuple('Ored', ['conditions', 'ands'])


class BooleanExpression(MatchCriteria):
    """<xtce:BooleanExpression>"""

    def __init__(self, expression: Condition or Anded or Ored):
        self.expression = expression

    @classmethod
    def from_match_criteria_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Abstract classmethod to create a match criteria object from an XML element.

        Parameters
        ----------
        element : ElementTree.Element
           XML element
        ns : dict
           XML namespace dict

        Returns
        -------
        : cls
        """
        def _parse_anded(anded_el: ElementTree.Element):
            """Create an Anded object from an xtce:ANDedConditions element

            Parameters
            ----------
            anded_el: ElementTree.Element
                xtce:ANDedConditions element

            Returns
            -------
            : Anded
            """
            conditions = [Condition.from_match_criteria_xml_element(el, ns)
                          for el in anded_el.findall('xtce:Condition', ns)]
            anded_ors = [_parse_ored(anded_or) for anded_or in anded_el.findall('xtce:ORedConditions', ns)]
            return Anded(conditions, anded_ors)

        def _parse_ored(ored_el: ElementTree.Element):
            """Create an Ored object from an xtce:ARedConditions element

            Parameters
            ----------
            ored_el: ElementTree.Element
                xtce:ORedConditions element

            Returns
            -------
            : Ored
            """
            conditions = [Condition.from_match_criteria_xml_element(el, ns)
                          for el in ored_el.findall('xtce:Condition', ns)]
            ored_ands = [_parse_anded(ored_and) for ored_and in ored_el.findall('xtce:ANDedConditions', ns)]
            return Ored(conditions, ored_ands)

        if element.find('xtce:Condition', ns) is not None:
            condition = Condition.from_match_criteria_xml_element(element.find('xtce:Condition', ns), ns)
            return cls(expression=condition)
        if element.find('xtce:ANDedConditions', ns) is not None:
            return cls(expression=_parse_anded(element.find('xtce:ANDedConditions', ns)))
        if element.find('xtce:ORedConditions', ns) is not None:
            return cls(expression=_parse_ored(element.find('xtce:ORedConditions', ns)))
        raise ValueError(f"Failed to parse {element}")

    def evaluate(self, parsed_data: dict, current_parsed_value: int or float = None) -> bool:
        """Evaluate the criteria in the BooleanExpression down to a single boolean.

        Parameters
        ----------
        parsed_data : dict
            Dictionary of parsed parameter data so far. Used to evaluate truthyness of the match criteria.
        current_parsed_value : int or float, Optional
            Current value being parsed.

        Returns
        -------
        : bool
            Truthyness of this match criteria based on parsed_data values.
        """

        def _or(ored: Ored):
            for condition in ored.conditions:
                if condition.evaluate(parsed_data) is True:
                    return True
            for anded in ored.ands:
                if _and(anded):
                    return True
            return False

        def _and(anded: Anded):
            for condition in anded.conditions:
                if condition.evaluate(parsed_data) is False:
                    return False
            for ored in anded.ors:
                if not _or(ored):
                    return False
            return True

        if isinstance(self.expression, Condition):
            return self.expression.evaluate(parsed_data)
        if isinstance(self.expression, Anded):
            return _and(self.expression)
        if isinstance(self.expression, Ored):
            return _or(self.expression)

        raise ValueError(f"Error evaluating an unknown expression {self.expression}.")


class DiscreteLookup(AttrComparable):
    """<xtce:DiscreteLookup>"""

    def __init__(self, match_criteria: list, lookup_value: int or float):
        """Constructor

        Parameters
        ----------
        match_criteria : list
            List of criteria to determine if the lookup value should be returned during evaluation.
        lookup_value : int or float
            Value to return from the lookup if the criteria evaluate true
        """
        self.match_criteria = match_criteria
        self.lookup_value = lookup_value

    @classmethod
    def from_discrete_lookup_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Create a DiscreteLookup object from an <xtce:DiscreteLookup> XML element

        Parameters
        ----------
        element : ElementTree.Element
            <xtce:DiscreteLookup> XML element from which to parse the DiscreteLookup object.
        ns : dict
            Namespace dict for XML parsing

        Returns
        -------
        : cls
        """
        lookup_value = float(element.attrib['value'])
        if element.find('xtce:ComparisonList', ns) is not None:
            match_criteria = [Comparison.from_match_criteria_xml_element(el, ns)
                              for el in element.findall('xtce:ComparisonList/xtce:Comparison', ns)]
        elif element.find('xtce:Comparison', ns) is not None:
            match_criteria = [Comparison.from_match_criteria_xml_element(
                element.find('xtce:Comparison', ns), ns)]
        else:
            raise NotImplementedError("Only Comparison and ComparisonList are implemented for DiscreteLookup.")

        return cls(match_criteria, lookup_value)

    def evaluate(self, parsed_data: dict, current_parsed_value: int or float = None):
        """Evaluate the lookup to determine if it is valid.

        Parameters
        ----------
        parsed_data : dict
            Data parsed so far (for referencing during criteria evaluation).
        current_parsed_value: int or float, Optional
            If referenced parameter in criterion isn't in parsed_data dict, we assume we are comparing against this
            currently parsed value.

        Returns
        -------
        : any
            Return the lookup value if the match criteria evaluate true. Return None otherwise.
        """
        if all(criterion.evaluate(parsed_data, current_parsed_value) for criterion in self.match_criteria):
            # If the parsed data so far satisfy all the match criteria
            return self.lookup_value
        return None


# Calibrator definitions
class Calibrator(AttrComparable, metaclass=ABCMeta):
    """Abstract base class for XTCE calibrators"""

    @classmethod
    def from_calibrator_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Abstract classmethod to create a default_calibrator object from an XML element.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        cls
        """
        return NotImplemented

    def calibrate(self, uncalibrated_value: int):
        """Takes an integer-encoded value and returns a calibrated version.

        Returns
        -------
        : int or float
            Calibrated value
        """
        raise NotImplementedError


SplinePoint = namedtuple('SplinePoint', ['raw', 'calibrated'])


class SplineCalibrator(Calibrator):
    """<xtce:SplineCalibrator>"""
    _order_mapping = {'zero': 0, 'first': 1, 'second': 2, 'third': 3}

    def __init__(self, points: list, order: int = 0, extrapolate: bool = False):
        """Constructor

        Parameters
        ----------
        points : list
            List of SplinePoint objects. These points are sorted by their raw values on instantiation.
        order : int
            Spline order. Only zero and first order splines are supported.
        extrapolate : bool
            Whether or not to allow extrapolation outside the bounds of the spline points. If False, raises an
            error when calibrate is called for a query point outside the bounds of the spline points.
        """
        if order > 1:
            raise NotImplementedError("Spline calibrators of order > 1 are not implemented. Consider contributing "
                                      "if you need this functionality. It does not appear to be commonly used but "
                                      "it probably would not be too hard to implement.")
        self.order = order
        self.points = sorted(points, key=lambda point: point.raw)  # Sort points before storing
        self.extrapolate = extrapolate

    @classmethod
    def from_calibrator_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Create a spline default_calibrator object from an <xtce:SplineCalibrator> XML element."""
        point_elements = element.findall('xtce:SplinePoint', ns)
        spline_points = [
            SplinePoint(raw=float(p.attrib['raw']), calibrated=float(p.attrib['calibrated']))
            for p in point_elements
        ]
        order = int(cls._order_mapping[element.attrib['order']]) if 'order' in element.attrib else 0
        extrapolate = element.attrib['extrapolate'].lower() == 'true' if 'extrapolate' in element.attrib else False
        return cls(order=order, points=spline_points, extrapolate=extrapolate)

    def calibrate(self, uncalibrated_value: float):
        """Take an integer-encoded value and returns a calibrated version according to the spline points.

        Parameters
        ----------
        uncalibrated_value : float
            Query point.

        Returns
        -------
        : float
            Calibrated value
        """
        if self.order == 0:
            return self._zero_order_spline_interp(uncalibrated_value)
        if self.order == 1:
            return self._first_order_spline_interp(uncalibrated_value)
        raise NotImplementedError(f"SplineCalibrator is not implemented for spline order {self.order}.")

    def _zero_order_spline_interp(self, query_point: float):
        """Abstraction for zero order spline interpolation. If extrapolation is set to a truthy value, we use
        the nearest point to extrapolate outside the range of the given spline points. Within the range of spline
        points, we use nearest lower point interpolation.

        Parameters
        ----------
        query_point : float
            Query point.

        Returns
        -------
        : float
            Calibrated value.
        """
        x = [float(p.raw) for p in self.points]
        y = [float(p.calibrated) for p in self.points]
        if min(x) <= query_point <= max(x):
            first_greater = [p.raw > query_point for p in self.points].index(True)
            return y[first_greater - 1]
        if query_point > max(x) and self.extrapolate:
            return y[-1]
        if query_point < min(x) and self.extrapolate:
            return y[0]
        raise CalibrationError(f"Extrapolation is set to a falsy value ({self.extrapolate}) but query value "
                               f"{query_point} falls outside the range of spline points {self.points}")

    def _first_order_spline_interp(self, query_point: float):
        """Abstraction for first order spline interpolation. If extrapolation is set to a truthy value, we use the
        end points to make a linear function and use it to extrapolate.

        Parameters
        ----------
        query_point : float
            Query point.

        Returns
        -------
        float
            Calibrated value.
        """

        def linear_func(xq: float, x0: float, x1: float, y0: float, y1: float):
            """Evaluate a linear function through points (x0, y0), (x1, y1) at point xq

            Parameters
            ----------
            xq : float
            x0 : float
            x1 : float
            y0 : float
            y1 : float

            Returns
            -------
            yq : float
                Interpolated point
            """
            slope = (y1 - y0) / (x1 - x0)
            return (slope * (xq - x0)) + y0

        x = [p.raw for p in self.points]
        y = [p.calibrated for p in self.points]
        if min(x) <= query_point <= max(x):
            first_greater = [p.raw > query_point for p in self.points].index(True)
            return linear_func(query_point,
                               x[first_greater - 1], x[first_greater],
                               y[first_greater - 1], y[first_greater])
        if query_point > max(x) and self.extrapolate:
            return linear_func(query_point, x[-2], x[-1], y[-2], y[-1])
        if query_point < min(x) and self.extrapolate:
            return linear_func(query_point, x[0], x[1], y[0], y[1])
        raise CalibrationError(f"Extrapolation is set to a falsy value ({self.extrapolate}) but query value "
                               f"{query_point} falls outside the range of spline points {self.points}")


PolynomialCoefficient = namedtuple('PolynomialCoefficient', ['coefficient', 'exponent'])


class PolynomialCalibrator(Calibrator):
    """<xtce:PolynomialCalibrator>"""

    def __init__(self, coefficients: list):
        """Constructor

        Parameters
        ----------
        coefficients : list
            List of PolynomialCoefficient objects that define the polynomial.
        """
        self.coefficients = coefficients  # Coefficients should be a list of PolynomialCoefficients

    @classmethod
    def from_calibrator_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Create a polynomial default_calibrator object from an <xtce:PolynomialCalibrator> XML element.

        Parameters
        ----------
        element : ElementTree.Element
            <xtce:PolynomialCalibrator> XML element
        ns : dict
            Namespace dict

        Returns
        -------

        """
        terms = element.findall('xtce:Term', ns)
        coefficients = [
            PolynomialCoefficient(coefficient=float(term.attrib['coefficient']), exponent=int(term.attrib['exponent']))
            for term in terms
        ]
        return cls(coefficients=coefficients)

    def calibrate(self, uncalibrated_value: float):
        """Evaluate the polynomial defined by object coefficients at the specified uncalibrated point.

        Parameters
        ----------
        uncalibrated_value : float
            Query point.

        Returns
        -------
        float
            Calibrated value
        """
        return sum(a * (uncalibrated_value ** n) for a, n in self.coefficients)


class MathOperationCalibrator(Calibrator):
    """<xtce:MathOperationCalibrator>"""
    err_msg = "The MathOperationCalibrator element is not supported in this package but pull requests are welcome!"

    def __init__(self):
        """Constructor

        Not implemented.
        """
        raise NotImplementedError(self.err_msg)

    @classmethod
    def from_calibrator_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Create a math operation default_calibrator from an <xtce:MathOperationCalibrator> XML element."""
        raise NotImplementedError(cls.err_msg)

    def calibrate(self, uncalibrated_value: int):
        """Stub

        Parameters
        ----------
        uncalibrated_value

        Returns
        -------

        """
        raise NotImplementedError(self.err_msg)


class ContextCalibrator(AttrComparable):
    """<xtce:ContextCalibrator>"""

    def __init__(self, match_criteria: list, calibrator: Calibrator):
        """Constructor

        Parameters
        ----------
        match_criteria : MatchCriteria or list
            Object representing the logical operations to be performed to determine whether to use this
            default_calibrator. This can be a Comparison, a ComparsonList (a list of Comparison objects),
            a BooleanExpression (not supported), or a CustomAlgorithm (not supported)
        calibrator : Calibrator
            Calibrator to use if match criteria evaluates to True
        """
        self.match_criteria = match_criteria
        self.calibrator = calibrator

    @staticmethod
    def get_context_match_criteria(element: ElementTree.Element, ns: dict):
        """Parse contextual requirements from a Comparison, ComparisonList, or BooleanExpression

        Parameters
        ----------
        element : ElementTree.Element
            <xtce:ContextCalibrator> XML element from which to parse the ContextCalibrator object.
        ns : dict
            Namespace dict for XML parsing

        Returns
        -------
        : list
            List of Comparisons that can be evaluated to determine whether this calibrator should be used.
        """
        context_match_element = element.find('xtce:ContextMatch', ns)
        if context_match_element.find('xtce:ComparisonList', ns) is not None:
            return [Comparison.from_match_criteria_xml_element(el, ns)
                    for el in context_match_element.findall('xtce:ComparisonList/xtce:Comparison', ns)]
        if context_match_element.find('xtce:Comparison', ns) is not None:
            return [Comparison.from_match_criteria_xml_element(
                context_match_element.find('xtce:Comparison', ns), ns)]
        if context_match_element.find('xtce:BooleanExpression', ns) is not None:
            return [BooleanExpression.from_match_criteria_xml_element(
                context_match_element.find('xtce:BooleanExpression', ns), ns)]
        raise NotImplementedError("ContextCalibrator doesn't contain Comparison, ComparisonList, or BooleanExpression. "
                                  "This probably means the match criteria is an unsupported type "
                                  "(CustomAlgorithm).")

    @classmethod
    def from_context_calibrator_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Create a ContextCalibrator object from an <xtce:ContextCalibrator> XML element

        Parameters
        ----------
        element : ElementTree.Element
            <xtce:ContextCalibrator> XML element from which to parse the ContextCalibrator object.
        ns : dict
            Namespace dict for XML parsing

        Returns
        -------
        : cls
        """
        match_criteria = cls.get_context_match_criteria(element, ns)

        if element.find('xtce:Calibrator/xtce:SplineCalibrator', ns) is not None:
            calibrator = SplineCalibrator.from_calibrator_xml_element(
                element.find('xtce:Calibrator/xtce:SplineCalibrator', ns), ns)
        elif element.find('xtce:Calibrator/xtce:PolynomialCalibrator', ns):
            calibrator = PolynomialCalibrator.from_calibrator_xml_element(
                element.find('xtce:Calibrator/xtce:PolynomialCalibrator', ns), ns)
        else:
            raise NotImplementedError(
                "Unsupported default_calibrator type. space_packet_parser only supports Polynomial and Spline"
                "calibrators for ContextCalibrators.")

        return cls(match_criteria=match_criteria, calibrator=calibrator)

    def calibrate(self, parsed_value):
        """Wrapper method for the internal Calibrator.calibrate

        Parameters
        ----------
        parsed_value : int or float
            Uncalibrated value.

        Returns
        -------
        : int or float
            Calibrated value
        """
        return self.calibrator.calibrate(parsed_value)


# DataEncoding definitions
class DataEncoding(AttrComparable, metaclass=ABCMeta):
    """Abstract base class for XTCE data encodings"""
    @classmethod
    def from_data_encoding_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Abstract classmethod to create a data encoding object from an XML element.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        cls
        """
        return NotImplemented

    @staticmethod
    def get_default_calibrator(data_encoding_element: ElementTree.Element, ns: dict):
        """Gets the default_calibrator for the data encoding element

        Parameters
        ----------
        data_encoding_element : ElementTree.Element
            The data encoding element which should contain the default_calibrator
        ns : dict
            XML namespace dict

        Returns
        -------
        Calibrator
        """
        for calibrator in [SplineCalibrator, PolynomialCalibrator, MathOperationCalibrator]:
            # Try to find each type of data encoding element. If we find one, we assume it's the only one.
            element = data_encoding_element.find(f"xtce:DefaultCalibrator/xtce:{calibrator.__name__}", ns)
            if element is not None:
                return calibrator.from_calibrator_xml_element(element, ns)
        return None

    @staticmethod
    def get_context_calibrators(data_encoding_element: ElementTree.Element, ns: dict) -> list or None:
        """Get the context default_calibrator(s) for the data encoding element

        Parameters
        ----------
        data_encoding_element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        : list
            List of ContextCalibrator objects.
        """
        if data_encoding_element.find('xtce:ContextCalibratorList', ns):
            context_calibrators_elements = data_encoding_element.findall(
                'xtce:ContextCalibratorList/xtce:ContextCalibrator', ns)
            return [ContextCalibrator.from_context_calibrator_xml_element(el, ns)
                    for el in context_calibrators_elements]
        return None

    @staticmethod
    def _get_linear_adjuster(parent_element: ElementTree.Element, ns: dict) -> callable or None:
        """Examine a parent (e.g. a <xtce:DynamicValue>) element and find a LinearAdjustment if present,
        creating and returning a function that evaluates the adjustment.

        Parameters
        ----------
        parent_element : ElementTree.Element
            Parent element which may contain a LinearAdjustment
        ns : dict
            XML namespace dict

        Returns
        -------
        adjuster : callable
            Function object that adjusts a SizeInBits value by a linear function
        """
        linear_adjustment_element = parent_element.find('xtce:LinearAdjustment', ns)
        if linear_adjustment_element is not None:
            slope = (int(linear_adjustment_element.attrib['slope'])
                     if 'slope' in linear_adjustment_element.attrib else 0)
            intercept = (int(linear_adjustment_element.attrib['intercept'])
                         if 'intercept' in linear_adjustment_element.attrib else 0)

            def adjuster(x: int) -> int:
                """Perform a linear adjustment to a size parameter

                Parameters
                ----------
                x : int
                    Unadjusted size parameter.

                Returns
                -------
                : int
                    Adjusted size parameter
                """
                adjusted = (slope * float(x)) + intercept
                if not adjusted.is_integer():
                    raise ValueError(f"Error when adjusting a value with a LinearAdjustment. Got y=mx + b as "
                                     f"{adjusted}={slope}*{x}+{intercept} returned a float. "
                                     f"Should have been an int.")
                return int(adjusted)

            return adjuster
        return None

    def _get_format_string(self, packet_data: bitstring.ConstBitStream, parsed_data: dict):
        """Infer a bitstring format string, possibly using previously parsed data. This is called by parse_value only
        so it's private.

        Parameters
        ----------
        parsed_data: dict
            Dictionary of previously parsed data items for use in determining the format string if necessary.

        Returns
        -------
        : str
            Format string in the bitstring format. e.g. uint:16
        """
        raise NotImplementedError()

    def parse_value(self, packet_data: bitstring.ConstBitStream, parsed_data: dict, **kwargs):
        """Parse a value from packet data, possibly using previously parsed data items to inform parsing.

        Parameters
        ----------
        packet_data: bitstring.ConstBitStream
            Binary data coming up next in the packet.
        parsed_data: dict
            Previously parsed data items from which to infer parsing details (e.g. length of a field).

        Returns
        -------
        : any
            Raw value
        : any
            Calibrated value
        """
        raise NotImplementedError()


class StringDataEncoding(DataEncoding):
    """<xtce:StringDataEncoding>"""

    def __init__(self, encoding: str = 'utf-8',
                 termination_character: str = None,
                 fixed_length: int = None,
                 leading_length_size: int = None,
                 dynamic_length_reference: str = None,
                 use_calibrated_value: bool = True,
                 discrete_lookup_length: list = None,
                 length_linear_adjuster: callable = None):
        """Constructor
        Only one of termination_character, fixed_length, or leading_length_size should be set. Setting more than one
        is nonsensical.

        TODO: implement ByteOrderList to inform endianness.
         This can also relax the requirements on the encoding spec since utf-16-le is redundant if endianness
         comes from the ByteOrderList

        Parameters
        ----------
        encoding : str
            One of 'utf-8', 'utf-16-le', or 'utf-16-be'. Describes how to read the characters in the string.
        termination_character : str
            A single hexadecimal character, represented as a string. Must be encoded in the same encoding as the string
            itself. For example, for a utf-8 encoded string, the hex string must be two hex characters (one byte).
            For a utf-16-* encoded string, the hex representation of the termination character must be four characters
            (two bytes).
        fixed_length : int
            Fixed length of the string, in bits.
        leading_length_size : int
            Fixed size in bits of a leading field that contains the length of the subsequent string.
        dynamic_length_reference : str
            Name of referenced parameter for dynamic length. May be combined with a linear_adjuster
        use_calibrated_value: bool
            Whether to use the calibrated value on the referenced parameter in dynamic_length_reference.
            Default is True.
        discrete_lookup_length : DiscreteLookup
            DiscreteLookup object with which to determine string length from another parameter.
        length_linear_adjuster : callable
            Function that linearly adjusts a size. e.g. if the size reference parameter gives a length in bytes, the
            linear adjuster should multiply by 8 to give the size in bits.
        """
        if encoding not in ['utf-8', 'utf-16-le', 'utf-16-be']:
            raise ValueError(
                f"Got encoding={encoding}. Encoding must be one of utf-8, utf-16-le, or utf-16-be (note that"
                f"endianness must be specified for utf-16 encoding.")
        self.encoding = encoding
        if termination_character and len(bytes.fromhex(termination_character).decode(encoding).encode('utf-8')) != 1:
            raise ValueError(f"Termination character {termination_character} appears to be malformed. Expected a "
                             f"hex string representation of a single character, e.g. '58' for character 'X' in utf-8 "
                             f"or '5800' for character 'X' in utf-16-le. Note that variable-width encoding is not "
                             f"yet supported in any encoding.")
        self.termination_character = termination_character  # Always in hex, per 4.3.2.2.5.5.4 of XTCE spec
        self.fixed_length = fixed_length
        self.leading_length_size = leading_length_size
        self.dynamic_length_reference = dynamic_length_reference
        self.use_calibrated_value = use_calibrated_value
        self.discrete_lookup_length = discrete_lookup_length
        self.length_linear_adjuster = length_linear_adjuster

    def _get_format_string(self, packet_data: bitstring.ConstBitStream, parsed_data: dict):
        """Infer a bitstring format string

        Parameters
        ----------
        parsed_data: dict
            Dictionary of previously parsed data items for use in determining the format string if necessary.
        packet_data: bitstring.ConstBitStream
            Packet data, which can be used to determine the string length from a leading value
            or from a termination character.

        Returns
        -------
        : str or None
            Format string in the bitstring format. e.g. uint:16
        : int or None
            Number of bits to skip after parsing the string
        """
        # pylint: disable=too-many-branches
        skip_bits_after = 0  # Gets modified if we have a termination character
        if self.fixed_length:
            strlen_bits = self.fixed_length
        elif self.leading_length_size is not None:  # strlen_bits is determined from a preceding integer
            leading_strlen_bitstring_format = f"uint:{self.leading_length_size}"
            strlen_bits = packet_data.read(leading_strlen_bitstring_format)
        elif self.discrete_lookup_length is not None:
            for discrete_lookup in self.discrete_lookup_length:
                strlen_bits = discrete_lookup.evaluate(parsed_data)
                if strlen_bits is not None:
                    break
            else:
                raise ValueError('List of discrete lookup values being used for determining length of '
                                 f'string {self} found no matches based on {parsed_data}.')
        elif self.dynamic_length_reference is not None:
            if self.use_calibrated_value is True:
                strlen_bits = parsed_data[self.dynamic_length_reference].derived_value
            else:
                strlen_bits = parsed_data[self.dynamic_length_reference].raw_value
            strlen_bits = int(strlen_bits)
        elif self.termination_character is not None:
            termination_char_utf8_bytes = bytes.fromhex(self.termination_character)

            if self.encoding in ['utf-16-le', 'utf-16-be']:
                bytes_per_char = 2
            elif self.encoding == 'utf-8':
                bytes_per_char = 1
            else:
                raise ValueError(
                    f"Got encoding={self.encoding}. Encoding must be one of utf-8, utf-16-le, or utf-16-be (note that"
                    f"endianness must be specified for utf-16 encoding.")

            bits_per_byte = 8
            look_ahead_n_bytes = 0
            while look_ahead_n_bytes <= len(packet_data) - packet_data.pos:
                look_ahead = packet_data.peek(f'bytes:{look_ahead_n_bytes}')  # Outputs UTF-8 encoded byte string
                look_ahead = look_ahead.decode('utf-8').encode(self.encoding)  # Force specified encoding
                if termination_char_utf8_bytes in look_ahead:
                    # Implicit assumption of one termination character in specified encoding
                    tclen_bits = bytes_per_char * bits_per_byte
                    strlen_bits = (look_ahead_n_bytes * bits_per_byte) - tclen_bits
                    skip_bits_after = tclen_bits
                    break
                look_ahead_n_bytes += bytes_per_char
            else:
                raise ValueError(f"Reached end of binary string without finding "
                                 f"termination character {self.termination_character}.")
        else:
            raise ValueError("Unable to parse StringParameterType. "
                             "Didn't contain any way to constrain the length of the string.")
        if self.length_linear_adjuster is not None:
            strlen_bits = self.length_linear_adjuster(strlen_bits)
        return f"bytes:{strlen_bits // 8}", skip_bits_after
        # pylint: enable=too-many-branches

    def parse_value(self, packet_data: bitstring.ConstBitStream, parsed_data: dict, **kwargs):
        """Parse a value from packet data, possibly using previously parsed data items to inform parsing.

        Parameters
        ----------
        packet_data: bitstring.ConstBitStream
            Binary data coming up next in the packet.
        parsed_data: dict, Optional
            Previously parsed data items from which to infer parsing details (e.g. length of a field).

        Returns
        -------
        : any
            Parsed value
        : any
            Calibrated value
        """
        bitstring_format, skip_bits_after = self._get_format_string(packet_data, parsed_data)
        parsed_value = packet_data.read(bitstring_format)
        packet_data.pos += skip_bits_after  # Allows skip over termination character
        return parsed_value.decode(self.encoding), None

    @classmethod
    def from_data_encoding_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Create a data encoding object from an <xtce:StringDataEncoding> XML element.
        Strings in XTCE can be described in three ways:

        1. Using a termination character that marks the end of the string.
        2. Using a fixed length, which may be derived from referenced parameter either directly or via a discrete
           lookup table.
        3. Using a leading size field that describes the size of the following string.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        cls
        """
        try:
            encoding = element.attrib['encoding']
        except KeyError:
            encoding = 'utf-8'

        try:
            termination_character = element.find('xtce:SizeInBits/xtce:TerminationChar', ns).text
            return cls(termination_character=termination_character, encoding=encoding)
        except AttributeError:
            pass

        try:
            leading_length_size = int(
                element.find('xtce:SizeInBits/xtce:LeadingSize', ns).attrib['sizeInBitsOfSizeTag'])
            return cls(leading_length_size=leading_length_size, encoding=encoding)
        except AttributeError:
            pass

        fixed_element = element.find('xtce:SizeInBits/xtce:Fixed', ns)

        discrete_lookup_list_element = fixed_element.find('xtce:DiscreteLookupList', ns)
        if discrete_lookup_list_element is not None:
            discrete_lookup_list = [DiscreteLookup.from_discrete_lookup_xml_element(el, ns)
                                    for el in discrete_lookup_list_element.findall('xtce:DiscreteLookup', ns)]
            return cls(encoding=encoding,
                       discrete_lookup_length=discrete_lookup_list)

        try:
            dynamic_value_element = fixed_element.find('xtce:DynamicValue', ns)
            referenced_parameter = dynamic_value_element.find('xtce:ParameterInstanceRef', ns).attrib['parameterRef']
            use_calibrated_value = True
            if 'useCalibratedValue' in dynamic_value_element.find('xtce:ParameterInstanceRef', ns).attrib:
                use_calibrated_value = dynamic_value_element.find(
                    'xtce:ParameterInstanceRef', ns).attrib['useCalibratedValue'].lower() == "true"
            linear_adjuster = cls._get_linear_adjuster(dynamic_value_element, ns)
            return cls(encoding=encoding,
                       dynamic_length_reference=referenced_parameter, use_calibrated_value=use_calibrated_value,
                       length_linear_adjuster=linear_adjuster)
        except AttributeError:
            pass

        try:
            fixed_length = int(fixed_element.find('xtce:FixedValue', ns).text)
            return cls(fixed_length=fixed_length, encoding=encoding)
        except AttributeError:
            pass

        raise ElementNotFoundError(f"Failed to parse StringDataEncoding for element {ElementTree.tostring(element)}")


class NumericDataEncoding(DataEncoding, metaclass=ABCMeta):
    """Abstract class that is inherited by IntegerDataEncoding and FloatDataEncoding"""

    def __init__(self, size_in_bits: int, encoding: str,
                 default_calibrator: Calibrator = None, context_calibrators: list = None):
        """Constructor

        # TODO: Implement ByteOrderList to inform endianness

        Parameters
        ----------
        size_in_bits : int
            Size of the integer
        encoding : str
            String indicating the type of encoding for the integer. FSW seems to use primarily 'signed' and 'unsigned',
            though 'signed' is not actually a valid specifier according to XTCE. 'twosCompliment' [sic] should be used
            instead, though we support the unofficial 'signed' specifier here.
            For supported specifiers, see XTCE spec 4.3.2.2.5.6.2
        default_calibrator : Calibrator
            Optional Calibrator object, containing information on how to transform the integer-encoded data, e.g. via
            a polynomial conversion or spline interpolation.
        context_calibrators : list
            List of ContextCalibrator objects, containing match criteria and corresponding calibrators to use in
            various scenarios, based on other parameters.
        """
        self.size_in_bits = size_in_bits
        self.encoding = encoding
        self.default_calibrator = default_calibrator
        self.context_calibrators = context_calibrators

    def parse_value(self, packet_data: bitstring.ConstBitStream, parsed_data: dict, **kwargs):
        """Parse a value from packet data, possibly using previously parsed data items to inform parsing.

        Parameters
        ----------
        packet_data: bitstring.ConstBitStream
            Binary data coming up next in the packet.
        parsed_data: dict, Optional
            Previously parsed data items from which to infer parsing details (e.g. length of a field).

        Returns
        -------
        : any
            Parsed value
        : any
            Calibrated value
        """
        bitstring_format = self._get_format_string(packet_data, parsed_data)
        parsed_value = packet_data.read(bitstring_format)
        # Attempt to calibrate
        calibrated_value = parsed_value  # Provides a fall through in case we have no calibrators
        if self.context_calibrators:
            for calibrator in self.context_calibrators:
                match_criteria = calibrator.match_criteria
                if all(criterion.evaluate(parsed_data, parsed_value) for criterion in match_criteria):
                    # If the parsed data so far satisfy all the match criteria
                    calibrated_value = calibrator.calibrate(parsed_value)
                    return parsed_value, calibrated_value
        if self.default_calibrator:  # If no context calibrators or if none apply and there is a default
            calibrated_value = self.default_calibrator.calibrate(parsed_value)
        # Ultimate fallthrough
        return parsed_value, calibrated_value


class IntegerDataEncoding(NumericDataEncoding):
    """<xtce:IntegerDataEncoding>"""

    def _get_format_string(self, packet_data: bitstring.ConstBitStream, parsed_data: dict):
        """Infer a bitstring format string

        Returns
        -------
        str
            Format string in the bitstring format. e.g. uint:16
        """
        if self.encoding == 'unsigned':
            base = 'uint'
        elif self.encoding == 'signed':
            base = 'int'
        elif self.encoding in ('twosCompliment', 'twosComplement'):  # [sic]
            base = 'int'
        else:
            raise NotImplementedError(f"Unrecognized encoding {self.encoding}. "
                                      f"Only signed and unsigned have been implemented.")
        return f"{base}:{self.size_in_bits}"

    @classmethod
    def from_data_encoding_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Create a data encoding object from an <xtce:IntegerDataEncoding> XML element.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        : cls
        """
        size_in_bits = int(element.attrib['sizeInBits'])
        if 'encoding' in element.attrib:
            encoding = element.attrib['encoding']
        else:
            encoding = "unsigned"
        calibrator = cls.get_default_calibrator(element, ns)
        context_calibrators = cls.get_context_calibrators(element, ns)
        return cls(size_in_bits=size_in_bits, encoding=encoding,
                   default_calibrator=calibrator, context_calibrators=context_calibrators)


class FloatDataEncoding(NumericDataEncoding):
    """<xtce:FloatDataEncoding>"""
    _supported_encodings = ['IEEE-754', 'MIL-1750A']

    def __init__(self, size_in_bits: int, encoding: str = 'IEEE-754',
                 default_calibrator: Calibrator = None, context_calibrators: list = None):
        """Constructor

        # TODO: Implement MIL-1650A encoding option

        # TODO: support ByteOrderList to inform endianness. Currently we assume big-endian always.

        Parameters
        ----------
        size_in_bits : int
            Size of the encoded value, in bits.
        encoding : str
            Encoding method of the float data. Must be either 'IEEE-754' or 'MIL-1750A'. Defaults to IEEE-754.
        default_calibrator : Calibrator
            Optional Calibrator object, containing information on how to transform the data, e.g. via
            a polynomial conversion or spline interpolation.
        context_calibrators : list
            List of ContextCalibrator objects, containing match criteria and corresponding calibrators to use in
            various scenarios, based on other parameters.
        """
        if encoding not in self._supported_encodings:
            raise ValueError(f"Invalid encoding type {encoding} for float data. "
                             f"Must be one of {self._supported_encodings}.")
        if encoding == 'MIL-1750A':
            raise NotImplementedError("MIL-1750A encoded floats are not supported by this library yet.")
        if encoding == 'IEEE-754' and size_in_bits not in (16, 32, 64):
            raise ValueError(f"Invalid size_in_bits value for IEEE-754 FloatDataEncoding, {size_in_bits}. "
                             "Must be 16, 32, or 64.")
        super().__init__(size_in_bits, encoding=encoding,
                         default_calibrator=default_calibrator, context_calibrators=context_calibrators)

    def _get_format_string(self, packet_data: bitstring.ConstBitStream, parsed_data: dict):
        """Infer a bitstring format string

        Returns
        -------
        str
            Format string in the bitstring format. e.g. uint:16
        """
        return f"floatbe:{self.size_in_bits}"

    @classmethod
    def from_data_encoding_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Create a data encoding object from an <xtce:FloatDataEncoding> XML element.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        : cls
        """
        size_in_bits = int(element.attrib['sizeInBits'])
        if 'encoding' in element.attrib:
            encoding = element.attrib['encoding']
        else:
            encoding = 'IEEE-754'
        default_calibrator = cls.get_default_calibrator(element, ns)
        context_calibrators = cls.get_context_calibrators(element, ns)
        return cls(size_in_bits=size_in_bits, encoding=encoding,
                   default_calibrator=default_calibrator, context_calibrators=context_calibrators)


class BinaryDataEncoding(DataEncoding):
    """<xtce:BinaryDataEncoding>"""

    def __init__(self, fixed_size_in_bits: int = None,
                 size_reference_parameter: str = None, use_calibrated_value: bool = True,
                 size_discrete_lookup_list: list = None,
                 linear_adjuster: callable = None):
        """Constructor

        Parameters
        ----------
        fixed_size_in_bits : int
            Fixed size for the binary field, in bits.
        size_reference_parameter : str
            Name of a parameter to reference for the binary field length, in bits. Note that space often specifies these
            fields in byte length, not bit length. This should be taken care of by a LinearAdjuster element that simply
            instructs the value to be multiplied by 8 but that hasn't historically been implemented unfortunately.
        use_calibrated_value: bool, Optional
            Default True. If False, the size_reference_parameter is examined for its raw value.
        size_discrete_lookup_list: list
            List of DiscreteLookup objects by which to determine the length of the binary data field. This suffers from
            the same bit/byte conversion problem as size_reference_parameter.
        linear_adjuster : callable
            Function that linearly adjusts a size. e.g. if the size reference parameter gives a length in bytes, the
            linear adjuster should multiply by 8 to give the size in bits.
        """
        self.fixed_size_in_bits = fixed_size_in_bits
        self.size_reference_parameter = size_reference_parameter
        self.use_calibrated_value = use_calibrated_value
        self.size_discrete_lookup_list = size_discrete_lookup_list
        self.linear_adjuster = linear_adjuster

    def _get_format_string(self, packet_data: bitstring.ConstBitStream, parsed_data: dict):
        """Infer a bitstring format string

        Returns
        -------
        : str or None
            Format string in the bitstring format. e.g. bin:1024
        """
        if self.fixed_size_in_bits is not None:
            len_bits = self.fixed_size_in_bits
        elif self.size_reference_parameter is not None:
            field_length_reference = self.size_reference_parameter
            if self.use_calibrated_value:
                len_bits = parsed_data[field_length_reference].derived_value
            else:
                len_bits = parsed_data[field_length_reference].raw_value
        elif self.size_discrete_lookup_list is not None:
            for discrete_lookup in self.size_discrete_lookup_list:
                len_bits = discrete_lookup.evaluate(parsed_data)
                if len_bits is not None:
                    break
            else:
                raise ValueError('List of discrete lookup values being used for determining length of '
                                 f'string {self} found no matches based on {parsed_data}.')
        else:
            raise ValueError("Unable to parse BinaryDataEncoding. "
                             "No fixed size, dynamic size, or dynamic lookup size were provided.")

        if self.linear_adjuster is not None:
            len_bits = self.linear_adjuster(len_bits)
        return f"bin:{len_bits}"

    def parse_value(self, packet_data: bitstring.ConstBitStream, parsed_data: dict, word_size: int = None, **kwargs):
        """Parse a value from packet data, possibly using previously parsed data items to inform parsing.

        Parameters
        ----------
        packet_data: bitstring.ConstBitStream
            Binary data coming up next in the packet.
        parsed_data: dict, Optional
            Previously parsed data items from which to infer parsing details (e.g. length of a field).
        word_size : int, Optional
            Word size for encoded data. This is used to ensure that the cursor ends up at the end of the last word
            and ready to parse the next data field.

        Returns
        -------
        : any
            Parsed value
        : any
            Calibrated value
        """
        bitstring_format = self._get_format_string(packet_data, parsed_data)
        parsed_value = packet_data.read(bitstring_format)
        if word_size:
            cursor_position_in_word = packet_data.pos % word_size
            if cursor_position_in_word != 0:
                logger.debug(f"Adjusting cursor position to the end of a {word_size} bit word.")
                packet_data.pos += word_size - cursor_position_in_word
        return parsed_value, None

    @classmethod
    def from_data_encoding_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Create a data encoding object from an <xtce:BinaryDataEncoding> XML element.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        : cls
        """
        fixed_value_element = element.find('xtce:SizeInBits/xtce:FixedValue', ns)
        if fixed_value_element is not None:
            fixed_size_in_bits = int(fixed_value_element.text)
            return cls(fixed_size_in_bits=fixed_size_in_bits)

        dynamic_value_element = element.find('xtce:SizeInBits/xtce:DynamicValue', ns)
        if dynamic_value_element is not None:
            param_inst_ref = dynamic_value_element.find('xtce:ParameterInstanceRef', ns)
            referenced_parameter = param_inst_ref.attrib['parameterRef']
            use_calibrated_value = True
            if 'useCalibratedValue' in param_inst_ref.attrib:
                use_calibrated_value = param_inst_ref.attrib['useCalibratedValue'].lower() == "true"
            linear_adjuster = cls._get_linear_adjuster(dynamic_value_element, ns)
            return cls(size_reference_parameter=referenced_parameter,
                       use_calibrated_value=use_calibrated_value, linear_adjuster=linear_adjuster)

        discrete_lookup_list_element = element.find('xtce:SizeInBits/xtce:DiscreteLookupList', ns)
        if discrete_lookup_list_element is not None:
            discrete_lookup_list = [DiscreteLookup.from_discrete_lookup_xml_element(el, ns)
                                    for el in discrete_lookup_list_element.findall('xtce:DiscreteLookup', ns)]
            return cls(size_discrete_lookup_list=discrete_lookup_list)

        raise ValueError("Tried parsing a binary parameter length using Fixed, Dynamic, and DiscreteLookupList "
                         "but failed. See 3.4.5 of the XTCE Green Book CCSDS 660.1-G-2.")


# ParameterType definitions
class ParameterType(AttrComparable, metaclass=ABCMeta):
    """Abstract base class for XTCE parameter types"""

    def __init__(self, name: str, encoding: DataEncoding, unit: str = None):
        """Constructor

        Parameters
        ----------
        name : str
            Parameter type name. Usually something like 'MSN__PARAM_Type'
        encoding : DataEncoding
            How the data is encoded. e.g. IntegerDataEncoding, StringDataEncoding, etc.
        unit : str
            String describing the unit for the stored value.
        """
        self.name = name
        self.unit = unit
        self.encoding = encoding

    def __repr__(self):
        module = self.__class__.__module__
        qualname = self.__class__.__qualname__
        return f"<{module}.{qualname} {self.name}>"

    @classmethod
    def from_parameter_type_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Create a *ParameterType from an <xtce:*ParameterType> XML element.

        Parameters
        ----------
        element : ElementTree.Element
            The XML element from which to create the object.
        ns: dict
            XML namespace dict

        Returns
        -------
        : ParameterType
        """
        name = element.attrib['name']
        unit = cls.get_units(element, ns)
        encoding = cls.get_data_encoding(element, ns)
        return cls(name, encoding, unit)

    @staticmethod
    def get_units(parameter_type_element: ElementTree.Element, ns: dict) -> str or None:
        """Finds the units associated with a parameter type element and parsed them to return a unit string.
        We assume only one <xtce:Unit> but this could be extended to support multiple units.
        See section 4.3.2.2.4 of CCSDS 660.1-G-1

        Parameters
        ----------
        parameter_type_element : ElementTree.Element
            The parameter type element
        ns : dict
            XML namespace dictionary

        Returns
        -------
        : str or None
        """
        # Assume we are not parsing a Time Parameter Type, which stores units differently
        units = parameter_type_element.findall('xtce:UnitSet/xtce:Unit', ns)
        # TODO: Implement multiple unit elements for compound unit definitions
        assert len(units) <= 1, f"Found {len(units)} <xtce:Unit> elements in a single <xtce:UnitSet>." \
                                f"This is supported in the standard but is rarely used " \
                                f"and is not yet supported by this library."
        if units:
            return " ".join([u.text for u in units])
        # Units are optional so return None if they aren't specified
        return None

    @staticmethod
    def get_data_encoding(parameter_type_element: ElementTree.Element, ns: dict) -> DataEncoding or None:
        """Finds the data encoding XML element associated with a parameter type XML element and parses
        it, returning an object representation of the data encoding.

        Parameters
        ----------
        parameter_type_element : ElementTree.Element
            The parameter type element
        ns : dict
            XML namespace dictionary

        Returns
        -------
        : DataEncoding or None
        """
        for data_encoding in [StringDataEncoding, IntegerDataEncoding, FloatDataEncoding, BinaryDataEncoding]:
            # Try to find each type of data encoding element. If we find one, we assume it's the only one.
            element = parameter_type_element.find(f".//xtce:{data_encoding.__name__}", ns)
            if element is not None:
                return data_encoding.from_data_encoding_xml_element(element, ns)
        return None

    def parse_value(self, packet_data: bitstring.ConstBitStream, parsed_data: dict, **kwargs):
        """Using the parameter type definition and associated data encoding, parse a value from a bit stream starting
        at the current cursor position.

        Parameters
        ----------
        packet_data : bitstring.ConstBitStream
            Binary packet data with cursor at the beginning of this parameter's data field.
        parsed_data: dict
            Previously parsed data to inform parsing.

        Returns
        -------
        parsed_value : any
            Resulting parsed data value.
        """
        return self.encoding.parse_value(packet_data, parsed_data, **kwargs)


class StringParameterType(ParameterType):
    """<xtce:StringParameterType>"""

    def __init__(self, name: str, encoding: StringDataEncoding, unit: str = None):
        """Constructor

        Parameters
        ----------
        name : str
            Parameter type name. Usually something like 'MSN__PARAM_Type'
        encoding : StringDataEncoding
            Must be a StringDataEncoding object since strings can't be encoded other ways.
        unit : str
            String describing the unit for the stored value.
        """
        if not isinstance(encoding, StringDataEncoding):
            raise ValueError("StringParameterType may only be instantiated with a StringDataEncoding encoding.")
        super().__init__(name=name, encoding=encoding, unit=unit)
        self.encoding = encoding  # Clarifies to static analysis tools that self.encoding is type StringDataEncoding


class IntegerParameterType(ParameterType):
    """<xtce:IntegerParameterType>"""
    pass


class FloatParameterType(ParameterType):
    """<xtce:FloatParameterType>"""
    pass


class EnumeratedParameterType(ParameterType):
    """<xtce:EnumeratedParameterType>"""

    def __init__(self, name: str, encoding: DataEncoding, enumeration: dict, unit: str or None = None):
        """Constructor

        Parameters
        ----------
        name : str
            Parameter type name.
        unit : str
            Unit string for stored value.
        encoding : DataEncoding
            How the data is encoded. e.g. IntegerDataEncoding.
        enumeration : dict
            Lookup with label:value pairs matching encoded values to their enum labels.
        """
        super().__init__(name=name, encoding=encoding, unit=unit)
        self.enumeration = enumeration

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.name}>"

    @classmethod
    def from_parameter_type_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Create an EnumeratedParameterType from an <xtce:EnumeratedParameterType> XML element.
        Overrides ParameterType.from_parameter_type_xml_element

        Parameters
        ----------
        element : ElementTree.Element
            The XML element from which to create the object.
        ns: dict
            XML namespace dict

        Returns
        -------
        : EnumeratedParameterType
        """
        name = element.attrib['name']
        unit = cls.get_units(element, ns)
        encoding = cls.get_data_encoding(element, ns)
        enumeration = cls.get_enumeration_list_contents(element, ns)
        return cls(name, encoding, enumeration=enumeration, unit=unit)

    @staticmethod
    def get_enumeration_list_contents(element: ElementTree.Element, ns: dict) -> dict:
        """Finds the <xtce:EnumerationList> element child of an <xtce:EnumeratedParameterType> and parses it,
        returning a dict. This method is confusingly named as if it might return a list. Sorry, XML and python
        semantics are not always compatible. It's called an enumeration list because the XML element is called
        <xtce:EnumerationList> but it contains key value pairs, so it's best represeneted as a dict.

        Parameters
        ----------
        element : ElementTree.Element
            The XML element from which to search for EnumerationList tags
        ns : dict
            XML namespace dict

        Returns
        -------
        : dict
        """
        enumeration_list = element.find('xtce:EnumerationList', ns)
        if enumeration_list is None:
            raise ValueError("An EnumeratedParameterType must contain an EnumerationList.")

        return {
            el.attrib['label']: int(el.attrib['value'])
            for el in enumeration_list.iterfind('xtce:Enumeration', ns)
        }

    def parse_value(self, packet_data: bitstring.ConstBitStream, parsed_data: dict, **kwargs):
        """Using the parameter type definition and associated data encoding, parse a value from a bit stream starting
        at the current cursor position.

        Parameters
        ----------
        packet_data : bitstring.ConstBitStream
            Binary packet data with cursor at the beginning of this parameter's data field.
        parsed_data : dict
            Previously parsed data

        Returns
        -------
        parsed_value : int
            Raw encoded value
        derived_value : str
            Resulting enum label associated with the (usually integer-)encoded data value.
        """
        raw, _ = super().parse_value(packet_data, parsed_data, **kwargs)
        # Note: The enum lookup only operates on raw values. This is specified in 4.3.2.4.3.6 of the XTCE spec "
        # CCSDS 660.1-G-2
        try:
            label = next(key for key, value in self.enumeration.items() if value == raw)
        except StopIteration as exc:
            raise ValueError(f"Failed to find raw value {raw} in enum lookup list {self.enumeration}.") from exc
        return raw, label


class BinaryParameterType(ParameterType):
    """<xtce:BinaryParameterType>"""

    def __init__(self, name: str, encoding: BinaryDataEncoding, unit: str = None):
        """Constructor

        Parameters
        ----------
        name : str
            Parameter type name. Usually something like 'MSN__PARAM_Type'
        encoding : BinaryDataEncoding
            Must be a BinaryDataEncoding object since binary data can't be encoded other ways.
        unit : str
            String describing the unit for the stored value.
        """
        if not isinstance(encoding, BinaryDataEncoding):
            raise ValueError("BinaryParameterType may only be instantiated with a BinaryDataEncoding encoding.")
        super().__init__(name=name, encoding=encoding, unit=unit)
        self.encoding = encoding


class BooleanParameterType(ParameterType):
    """<xtce:BooleanParameterType>"""

    def __init__(self, name: str, encoding: DataEncoding, unit: str = None):
        """Constructor that just issues a warning if the encoding is String or Binary"""
        if isinstance(encoding, (BinaryDataEncoding, StringDataEncoding)):
            warnings.warn(f"You are encoding a BooleanParameterType with a {type(encoding)} encoding."
                          f"This is almost certainly a very bad idea because the behavior of string and binary "
                          f"encoded booleans is not specified in XTCE. e.g. is the string \"0\" truthy?")
        super().__init__(name, encoding, unit)

    def parse_value(self, packet_data: bitstring.ConstBitStream, parsed_data: dict, **kwargs):
        """Using the parameter type definition and associated data encoding, parse a value from a bit stream starting
        at the current cursor position.

        Parameters
        ----------
        packet_data : bitstring.ConstBitStream
            Binary packet data with cursor at the beginning of this parameter's data field.
        parsed_data : dict
            Previously parsed data

        Returns
        -------
        parsed_value : int
            Raw encoded value
        derived_value : str
            Resulting boolean representation of the encoded raw value
        """
        raw, _ = super().parse_value(packet_data, parsed_data, **kwargs)
        # Note: This behaves very strangely for String and Binary data encodings.
        # Don't use those for Boolean parameters. The behavior isn't specified well in XTCE.
        return raw, bool(raw)


class TimeParameterType(ParameterType, metaclass=ABCMeta):
    """Abstract class for time parameter types"""

    def __init__(self, name: str, encoding: DataEncoding, unit: str = None,
                 epoch: str = None, offset_from: str = None):
        """Constructor

        Parameters
        ----------
        name : str
            Parameter type name. Usually something like 'MSN__PARAM_Type'.
        encoding : DataEncoding
            How the data is encoded. e.g. IntegerDataEncoding, StringDataEncoding, etc.
        unit : str, Optional
            String describing the unit for the stored value. Note that if a scale and offset are provided on
            the Encoding element, the unit applies to the scaled value, not the raw value.
        epoch : str, Optional
            String describing the starting epoch for the date or datetime encoded in the parameter.
            Must be xs:date, xs:dateTime, or one of the following: "TAI", "J2000", "UNIX", "POSIX", "GPS".
        offset_from : str, Optional
            Used to reference another time parameter by name. It allows
            for the stringing together of several dissimilar but related time parameters.

        Notes
        -----
        The XTCE spec is not very clear about OffsetFrom or what it is for. We parse it but don't use it for
        anything.
        """
        super().__init__(name, encoding, unit=unit)
        self.epoch = epoch
        self.offset_from = offset_from

    @classmethod
    def from_parameter_type_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Create a *TimeParameterType from an <xtce:*TimeParameterType> XML element.

        Parameters
        ----------
        element : ElementTree.Element
            The XML element from which to create the object.
        ns: dict
            XML namespace dict

        Returns
        -------
        : TimeParameterType
        """
        name = element.attrib['name']
        unit = cls.get_units(element, ns)
        encoding = cls.get_data_encoding(element, ns)
        encoding_unit_scaler = cls.get_time_unit_linear_scaler(element, ns)
        if encoding_unit_scaler:
            encoding.default_calibrator = encoding_unit_scaler
        epoch = cls.get_epoch(element, ns)
        offset_from = cls.get_offset_from(element, ns)
        return cls(name, encoding, unit, epoch, offset_from)

    @staticmethod
    def get_units(parameter_type_element: ElementTree.Element, ns: dict) -> str or None:
        """Finds the units associated with a parameter type element and parsed them to return a unit string.
        We assume only one <xtce:Unit> but this could be extended to support multiple units.
        See section 4.3.2.2.4 of CCSDS 660.1-G-1

        Parameters
        ----------
        parameter_type_element : ElementTree.Element
            The parameter type element
        ns : dict
            XML namespace dictionary

        Returns
        -------
        : str or None
        """
        encoding_element = parameter_type_element.find('xtce:Encoding', ns)
        if encoding_element and "units" in encoding_element.attrib:
            units = encoding_element.attrib["units"]
            return units
        # Units are optional so return None if they aren't specified
        return None

    @staticmethod
    def get_time_unit_linear_scaler(
            parameter_type_element: ElementTree.Element, ns: dict) -> PolynomialCalibrator or None:
        """Finds the linear calibrator associated with the Encoding element for the parameter type element.
        See section 4.3.2.4.8.3 of CCSDS 660.1-G-2

        Parameters
        ----------
        parameter_type_element : ElementTree.Element
            The parameter type element
        ns : dict
            XML namespace dictionary

        Returns
        -------
        : PolynomialCalibrator or None
        """
        encoding_element = parameter_type_element.find('xtce:Encoding', ns)
        coefficients = []

        if "offset" in encoding_element.attrib:
            offset = encoding_element.attrib["offset"]
            c0 = PolynomialCoefficient(coefficient=float(offset), exponent=0)
            coefficients.append(c0)

        if "scale" in encoding_element.attrib:
            scale = encoding_element.attrib["scale"]
            c1 = PolynomialCoefficient(coefficient=float(scale), exponent=1)
            coefficients.append(c1)
        # If we have an offset but not a scale, we need to add a first order term with coefficient 1
        elif "offset" in encoding_element.attrib:
            c1 = PolynomialCoefficient(coefficient=1, exponent=1)
            coefficients.append(c1)

        if coefficients:
            return PolynomialCalibrator(coefficients=coefficients)
        # If we didn't find offset nor scale, return None (no calibrator)
        return None

    @staticmethod
    def get_epoch(parameter_type_element: ElementTree.Element, ns: dict) -> str or None:
        """Finds the epoch associated with a parameter type element and parses them to return an epoch string.
        See section 4.3.2.4.9 of CCSDS 660.1-G-2

        Parameters
        ----------
        parameter_type_element : ElementTree.Element
            The parameter type element
        ns : dict
            XML namespace dictionary

        Returns
        -------
        : str or None
            The epoch string, which may be a datetime string or a named epoch such as TAI.
        """
        epoch_element = parameter_type_element.find('xtce:ReferenceTime/xtce:Epoch', ns)
        if epoch_element is not None:
            return epoch_element.text
        return None

    @staticmethod
    def get_offset_from(parameter_type_element: ElementTree.Element, ns: dict) -> str or None:
        """Finds the parameter referenced in OffsetFrom in a parameter type element and returns the name of the
        referenced parameter (which must be of type TimeParameterType).
        See section 4.3.2.4.9 of CCSDS 660.1-G-1

        Parameters
        ----------
        parameter_type_element : ElementTree.Element
            The parameter type element
        ns : dict
            XML namespace dictionary

        Returns
        -------
        : str or None
            The named of the referenced parameter.
        """
        offset_from_element = parameter_type_element.find('xtce:ReferenceTime/xtce:OffsetFrom', ns)
        if offset_from_element is not None:
            return offset_from_element.attrib['parameterRef']
        return None


class AbsoluteTimeParameterType(TimeParameterType):
    """<xtce:AbsoluteTimeParameterType>"""
    pass


class RelativeTimeParameterType(TimeParameterType):
    """<xtce:RelativeTimeParameterType>"""
    pass


class Parameter(AttrComparable):
    """<xtce:Parameter>"""

    def __init__(self, name: str, parameter_type: ParameterType,
                 short_description: str = None, long_description: str = None):
        """Constructor

        Parameters
        ----------
        name : str
            Parameter name. Typically something like MSN__PARAMNAME
        parameter_type : ParameterType
            Parameter type object that describes how the parameter is stored.
        short_description : str
            Short description of parameter as parsed from XTCE
        long_description : str
            Long description of parameter as parsed from XTCE
        """
        self.name = name
        self.parameter_type = parameter_type
        self.short_description = short_description
        self.long_description = long_description

    def __repr__(self):
        module = self.__class__.__module__
        qualname = self.__class__.__qualname__
        return f"<{module}.{qualname} {self.name}>"


class SequenceContainer(AttrComparable):
    """<xtce:SequenceContainer>"""

    def __init__(self,
                 name: str,
                 entry_list: list,
                 short_description: str = None,
                 long_description: str = None,
                 base_container_name: str = None,
                 restriction_criteria: list = None,
                 abstract: bool = False,
                 inheritors: list = None):
        """Object representation of <xtce:SequenceContainer>

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
        self.name = name
        self.entry_list = entry_list  # List of Parameter objects, found by reference
        self.short_description = short_description
        self.long_description = long_description
        self.base_container_name = base_container_name
        self.restriction_criteria = restriction_criteria if restriction_criteria else []
        self.abstract = abstract
        self.inheritors = inheritors if inheritors else []

    def __repr__(self):
        module = self.__class__.__module__
        qualname = self.__class__.__qualname__
        return f"<{module}.{qualname} {self.name}>"


FlattenedContainer = namedtuple('FlattenedContainer', ['entry_list', 'restrictions'])


class XtcePacketDefinition:
    """Object representation of the XTCE definition of a CCSDS packet object"""

    _default_namespace = {'xtce': 'http://www.omg.org/space/xtce'}
    _tag_to_type_template = {
        '{{{xtce}}}StringParameterType': StringParameterType,
        '{{{xtce}}}IntegerParameterType': IntegerParameterType,
        '{{{xtce}}}FloatParameterType': FloatParameterType,
        '{{{xtce}}}EnumeratedParameterType': EnumeratedParameterType,
        '{{{xtce}}}BinaryParameterType': BinaryParameterType,
        '{{{xtce}}}BooleanParameterType': BooleanParameterType,
        '{{{xtce}}}AbsoluteTimeParameterType': AbsoluteTimeParameterType,
        '{{{xtce}}}RelativeTimeParameterType': RelativeTimeParameterType,
    }

    def __init__(self, xtce_document: str or Path, ns: dict = None):
        """Instantiate an object representation of a CCSDS packet definition, according to a format specified in an XTCE
        XML document. The parser iteratively builds sequences of parameters according to the
        SequenceContainers specified in the XML document's ContainerSet element. The notions of container inheritance
        (via BaseContainer) and nested container (by including a SequenceContainer within a SequenceContainer) are
        supported. Exclusion of containers based on topLevelPacket in AncillaryData is not supported, so all
        containers are examined and returned.

        Parameters
        ----------
        xtce_document : str or Path
            Path to XTCE XML document containing packet definition.
        ns : dict
            Optional different namespace than the default xtce namespace.
        """
        self._sequence_container_cache = {}  # Lookup for parsed sequence container objects
        self._parameter_cache = {}  # Lookup for parsed parameter objects
        self._parameter_type_cache = {}  # Lookup for parsed parameter type objects
        self.ns = ns or self._default_namespace
        self.type_tag_to_object = {k.format(**self.ns): v for k, v in
                                   self._tag_to_type_template.items()}
        self.tree = ElementTree.parse(xtce_document)

        for sequence_container in self.container_set.iterfind('xtce:SequenceContainer', self.ns):
            self._sequence_container_cache[
                sequence_container.attrib['name']
            ] = self.parse_sequence_container_contents(sequence_container)

        for name, sc in self._sequence_container_cache.items():
            if sc.base_container_name:
                self._sequence_container_cache[sc.base_container_name].inheritors.append(name)

    def __getitem__(self, item):
        return self._sequence_container_cache[item]

    def parse_sequence_container_contents(self, sequence_container: ElementTree.Element) -> SequenceContainer:
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
                        parameter_type_class = self.type_tag_to_object[parameter_type_element.tag]
                        parameter_type_object = parameter_type_class.from_parameter_type_xml_element(
                            parameter_type_element, self.ns)
                        self._parameter_type_cache[parameter_type_name] = parameter_type_object  # Add to cache

                    parameter_short_description = parameter_element.attrib['shortDescription'] if (
                            'shortDescription' in parameter_element.attrib
                    ) else None
                    parameter_long_description = parameter_element.find('xtce:LongDescription', self.ns).text if (
                            parameter_element.find('xtce:LongDescription', self.ns) is not None
                    ) else None

                    parameter_object = Parameter(
                        name=parameter_name,
                        parameter_type=parameter_type_object,
                        short_description=parameter_short_description,
                        long_description=parameter_long_description
                    )
                    entry_list.append(parameter_object)
                    self._parameter_cache[parameter_name] = parameter_object  # Add to cache
            elif entry.tag == '{{{xtce}}}ContainerRefEntry'.format(**self.ns):  # pylint: disable=consider-using-f-string
                nested_container = self._find_container(name=entry.attrib['containerRef'])
                entry_list.append(self.parse_sequence_container_contents(nested_container))

        short_description = sequence_container.attrib['shortDescription'] if (
                'shortDescription' in sequence_container.attrib
        ) else None
        long_description = sequence_container.find('xtce:LongDescription', self.ns).text if (
                sequence_container.find('xtce:LongDescription', self.ns) is not None
        ) else None

        return SequenceContainer(name=sequence_container.attrib['name'],
                                 entry_list=entry_list,
                                 base_container_name=base_container_name,
                                 restriction_criteria=restriction_criteria,
                                 abstract=self._is_abstract_container(sequence_container),
                                 short_description=short_description,
                                 long_description=long_description)

    @property
    def named_containers(self):
        """Property accessor that returns the dict cache of SequenceContainer objects"""
        return self._sequence_container_cache

    @property
    def named_parameters(self):
        """Property accessor that returns the dict cache of Parameter objects"""
        return self._parameter_cache

    @property
    def named_parameter_types(self):
        """Property accessor that returns the dict cache of ParameterType objects"""
        return self._parameter_type_cache

    @property
    def flattened_containers(self):
        """Accesses a flattened, generic representation of non-abstract packet definitions along with their
        aggregated inheritance
        restrictions.

        Returns
        -------
        : dict
            A modified form of the _sequence_container_cache, flattened out to eliminate nested sequence containers
            and with all restriction logic aggregated together for easy comparisons.
            {
            "PacketNameA": {
            FlattenedContainer(
            entry_list=[Parameter, Parameter, ...],
            restrictions={"ParameterName": value, "OtherParamName": value, ...}
            )
            },
            "PacketNameB": {
            FlattenedContainer(
            entry_list=[Parameter, Parameter, ...],
            restrictions={"ParameterName": value, "OtherParamName": value, ...}
            )
            }, ...
            }
        """

        def flatten_container(sequence_container: SequenceContainer):
            """Flattens the representation of a SequenceContainer object into a list of Parameters (in order) and
            an aggregated dictionary of restriction criteria where the keys are Parameter names and the values are the
            required values of those parameters in order to adopt the SequenceContainer's definition.

            Parameters
            ----------
            sequence_container : SequenceContainer
                SequenceContainer object to flatten, recursively.

            Returns
            -------
            : list
                List of Parameters, in order.
            : dict
                Dictionary of required Parameter values in order to use this definition.
            """
            aggregated_entry_list = []
            aggregated_restrictions = []
            for entry in sequence_container.entry_list:
                if isinstance(entry, SequenceContainer):
                    if entry.restriction_criteria:
                        aggregated_restrictions += entry.restriction_criteria
                    entry_list, restrictions = flatten_container(entry)
                    aggregated_entry_list += entry_list
                    aggregated_restrictions += restrictions
                elif isinstance(entry, Parameter):
                    aggregated_entry_list.append(entry)
            return aggregated_entry_list, aggregated_restrictions

        return {
            name: FlattenedContainer(*flatten_container(sc))
            for name, sc in self._sequence_container_cache.items()
            if not sc.abstract
        }

    @property
    def container_set(self):
        """Property that returns the <xtce:ContainerSet> element, containing all the sequence container elements."""
        return self.tree.getroot().find('xtce:TelemetryMetaData/xtce:ContainerSet', self.ns)

    @property
    def parameter_type_set(self):
        """Property that returns the <xtce:ParameterTypeSet> element, containing all parameter type elements."""
        return self.tree.getroot().find('xtce:TelemetryMetaData/xtce:ParameterTypeSet', self.ns)

    @property
    def parameter_set(self):
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
        matches = self.container_set.findall(f"./xtce:SequenceContainer[@name='{name}']", self.ns)
        assert len(matches) == 1, f"Found {len(matches)} matching container_set with name {name}. " \
                                  f"Container names are expected to exist and be unique."
        return matches[0]

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
        matches = self.parameter_set.findall(f"./xtce:Parameter[@name='{name}']", self.ns)
        assert len(matches) == 1, f"Found {len(matches)} matching parameters with name {name}. " \
                                  f"Parameter names are expected to exist and be unique."
        return matches[0]

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
        matches = self.parameter_type_set.findall(f"./*[@name='{name}']", self.ns)
        assert len(matches) == 1, f"Found {len(matches)} matching parameter types with name {name}. " \
                                  f"Parameter type names are expected to exist and be unique."
        return matches[0]

    def _get_container_base_container(self, container_element: ElementTree.Element) -> Tuple[ElementTree.Element, list]:
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
                comparisons = comparison_list_element.findall('xtce:Comparison', self.ns)
                restrictions = [Comparison.from_match_criteria_xml_element(comp, self.ns) for comp in comparisons]
            elif single_comparison_element is not None:
                restrictions = [Comparison.from_match_criteria_xml_element(single_comparison_element, self.ns)]
            elif boolean_expression_element is not None:
                restrictions = [BooleanExpression.from_match_criteria_xml_element(boolean_expression_element, self.ns)]
            else:
                raise ValueError("Detected a RestrictionCriteria element containing no "
                                 "Comparison, ComparisonList, BooleanExpression or CustomAlgorithm.")
            # TODO: Implement NextContainer support inside RestrictionCriteria. This might make the parser much
            #    more complicated.
        else:
            restrictions = []
        return self._find_container(base_container_element.attrib['containerRef']), restrictions
