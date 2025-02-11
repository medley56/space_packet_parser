"""Calibrator definitions"""
from abc import ABCMeta, abstractmethod
from collections import namedtuple
from typing import Optional, Union

import lxml.etree as ElementTree
from lxml.builder import ElementMaker

from space_packet_parser import common, exceptions
from space_packet_parser.xtce import comparisons


class Calibrator(common.AttrComparable, common.XmlObject, metaclass=ABCMeta):
    """Abstract base class for XTCE calibrators"""

    @classmethod
    @abstractmethod
    def from_xml(
            cls,
            element: ElementTree.Element,
            *,
            tree: Optional[ElementTree.Element] = None,
            parameter_lookup: Optional[dict[str, any]] = None,
            parameter_type_lookup: Optional[dict[str, any]] = None,
            container_lookup: Optional[dict[str, any]] = None,
    ) -> 'Calibrator':
        """Abstract classmethod to create a default_calibrator object from an XML element.

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
        : Calibrator
        """
        return NotImplemented

    @abstractmethod
    def calibrate(self, uncalibrated_value: Union[int, float]) -> float:
        """Takes an integer-encoded or float-encoded value and returns a calibrated version.

        Parameters
        ----------
        uncalibrated_value : Union[int, float]
            The uncalibrated, raw encoded value

        Returns
        -------
        : float
            Calibrated value
        """
        raise NotImplementedError


SplinePoint = namedtuple('SplinePoint', ['raw', 'calibrated'])


class SplineCalibrator(Calibrator):
    """<xtce:SplineCalibrator>"""

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
    def from_xml(
            cls,
            element: ElementTree.Element,
            *,
            tree: Optional[ElementTree.Element] = None,
            parameter_lookup: Optional[dict[str, any]] = None,
            parameter_type_lookup: Optional[dict[str, any]] = None,
            container_lookup: Optional[dict[str, any]] = None
    ) -> 'SplineCalibrator':
        """Create a spline default_calibrator object from an <xtce:SplineCalibrator> XML element.

        Parameters
        ----------
        element : ElementTree.Element
            The XML element from which to create the object.
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

        """
        spline_points = [
            SplinePoint(raw=float(p.attrib['raw']), calibrated=float(p.attrib['calibrated']))
            for p in element.iterfind('*')
        ]
        order = int(element.attrib['order']) if 'order' in element.attrib else 0
        extrapolate = element.attrib['extrapolate'].lower() == 'true' if 'extrapolate' in element.attrib else False
        return cls(order=order, points=spline_points, extrapolate=extrapolate)

    def to_xml(self, *, elmaker: ElementMaker) -> ElementTree.Element:
        """Create a SplineCalibrator XML element

        Parameters
        ----------
        elmaker : ElementMaker
            Element factory with predefined namespace

        Returns
        -------
        : ElementTree.Element
        """
        return elmaker.SplineCalibrator(
            *(elmaker.SplinePoint(raw=str(p.raw), calibrated=str(p.calibrated)) for p in self.points),
            order=str(self.order),
            extrapolate=str(self.extrapolate).lower(),
        )

    def calibrate(self, uncalibrated_value: float) -> float:
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

    def _zero_order_spline_interp(self, query_point: float) -> float:
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
        raise exceptions.CalibrationError(f"Extrapolation is set to a falsy value ({self.extrapolate}) but query value "
                                          f"{query_point} falls outside the range of spline points {self.points}")

    def _first_order_spline_interp(self, query_point: float) -> float:
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

        def linear_func(xq: float, x0: float, x1: float, y0: float, y1: float) -> float:
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
        raise exceptions.CalibrationError(f"Extrapolation is set to a falsy value ({self.extrapolate}) but query value "
                                          f"{query_point} falls outside the range of spline points {self.points}")


PolynomialCoefficient = namedtuple('PolynomialCoefficient', ['coefficient', 'exponent'])


class PolynomialCalibrator(Calibrator):
    """<xtce:PolynomialCalibrator>"""

    def __init__(self, coefficients: list[PolynomialCoefficient]):
        """Constructor

        Parameters
        ----------
        coefficients : list
            List of PolynomialCoefficient objects that define the polynomial.
        """
        self.coefficients = coefficients  # Coefficients should be a list of PolynomialCoefficients

    @classmethod
    def from_xml(
            cls,
            element: ElementTree.Element,
            *,
            tree: Optional[ElementTree.Element] = None,
            parameter_lookup: Optional[dict[str, any]] = None,
            parameter_type_lookup: Optional[dict[str, any]] = None,
            container_lookup: Optional[dict[str, any]] = None
    ) -> 'PolynomialCalibrator':
        """Create a polynomial default_calibrator object from an <xtce:PolynomialCalibrator> XML element.

        Parameters
        ----------
        element : ElementTree.Element
            <xtce:PolynomialCalibrator> XML element
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

        """
        coefficients = [
            PolynomialCoefficient(coefficient=float(term.attrib['coefficient']), exponent=int(term.attrib['exponent']))
            for term in element.findall('*')
        ]
        return cls(coefficients=coefficients)

    def to_xml(self, elmaker: ElementMaker) -> ElementTree.Element:
        """Create a PolynomialCalibrator XML element

        Parameters
        ----------
        elmaker : ElementMaker
            Element factory with predefined namespace

        Returns
        -------
        : ElementTree.Element
        """
        return elmaker.PolynomialCalibrator(
            *(elmaker.Term(exponent=str(coeff.exponent), coefficient=str(coeff.coefficient))
              for coeff in self.coefficients)
        )

    def calibrate(self, uncalibrated_value: float) -> float:
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
    def from_xml(
            cls,
            element: ElementTree.Element,
            *,
            tree: Optional[ElementTree.Element] = None,
            parameter_lookup: Optional[dict[str, any]] = None,
            parameter_type_lookup: Optional[dict[str, any]] = None,
            container_lookup: Optional[dict[str, any]] = None
    ) -> 'MathOperationCalibrator':
        """Create a math operation default_calibrator from an <xtce:MathOperationCalibrator> XML element.

        Parameters
        ----------
        element : ElementTree.Element
            The XML element from which to create the object.
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
        : MathOperationCalibrator
        """
        raise NotImplementedError(cls.err_msg)

    def to_xml(self, elmaker: dict) -> ElementTree.Element:
        """Create a MathOperationsCalibrator XML element

        Parameters
        ----------
        elmaker : dict
            XML namespace dict

        Returns
        -------
        : ElementTree.Element
        """
        raise NotImplementedError(self.err_msg)

    def calibrate(self, uncalibrated_value: int):
        """Stub

        Parameters
        ----------
        uncalibrated_value

        Returns
        -------

        """
        raise NotImplementedError(self.err_msg)


class ContextCalibrator(common.AttrComparable, common.XmlObject):
    """<xtce:ContextCalibrator>"""

    def __init__(self, match_criteria: list, calibrator: Calibrator):
        """Constructor

        Parameters
        ----------
        match_criteria : Union[MatchCriteria, list]
            Object representing the logical operations to be performed to determine whether to use this
            calibrator. This can be a Comparison, a ComparsonList (a list of Comparison objects),
            a BooleanExpression, or a CustomAlgorithm (not supported)
        calibrator : Calibrator
            Calibrator to use if match criteria evaluates to True
        """
        self.match_criteria = match_criteria
        self.calibrator = calibrator

    @staticmethod
    def get_context_match_criteria(element: ElementTree.Element) -> list[comparisons.MatchCriteria]:
        """Parse contextual requirements from a Comparison, ComparisonList, or BooleanExpression

        Parameters
        ----------
        element : ElementTree.Element
            <xtce:ContextCalibrator> XML element from which to parse the ContextCalibrator object.

        Returns
        -------
        : List[MatchCriteria]
            List of Comparisons that can be evaluated to determine whether this calibrator should be used.
        """
        context_match_element = element.find('ContextMatch')
        if (comparison_list_element := context_match_element.find('ComparisonList')) is not None:
            return [comparisons.Comparison.from_xml(el)
                    for el in comparison_list_element.iterfind('Comparison')]
        if (comparison_element := context_match_element.find('Comparison')) is not None:
            return [comparisons.Comparison.from_xml(comparison_element)]
        if (boolean_expression_element := context_match_element.find('BooleanExpression')) is not None:
            return [comparisons.BooleanExpression.from_xml(boolean_expression_element)]
        raise NotImplementedError("ContextCalibrator doesn't contain Comparison, ComparisonList, or BooleanExpression. "
                                  "This probably means the match criteria is an unsupported type "
                                  "(CustomAlgorithm).")

    @classmethod
    def from_xml(
            cls,
            element: ElementTree.Element,
            *,
            tree: Optional[ElementTree.Element] = None,
            parameter_lookup: Optional[dict[str, any]] = None,
            parameter_type_lookup: Optional[dict[str, any]] = None,
            container_lookup: Optional[dict[str, any]] = None
    ) -> 'ContextCalibrator':
        """Create a ContextCalibrator object from an <xtce:ContextCalibrator> XML element

        Parameters
        ----------
        element : ElementTree.Element
            <xtce:ContextCalibrator> XML element from which to parse the ContextCalibrator object.
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
        match_criteria = cls.get_context_match_criteria(element)

        if (cal_element := element.find('Calibrator/SplineCalibrator')) is not None:
            calibrator = SplineCalibrator.from_xml(cal_element)
        elif (cal_element := element.find('Calibrator/PolynomialCalibrator')) is not None:
            calibrator = PolynomialCalibrator.from_xml(cal_element)
        else:
            raise NotImplementedError(
                "Unsupported default_calibrator type. space_packet_parser only supports Polynomial and Spline"
                "calibrators for ContextCalibrators.")

        return cls(match_criteria=match_criteria, calibrator=calibrator)

    def to_xml(self, *, elmaker: ElementMaker) -> ElementTree.Element:
        """Create a MathOperationsCalibrator XML element

        Parameters
        ----------
        elmaker : ElementMaker
            Element factory with predefined namespace

        Returns
        -------
        : ElementTree.Element
        """
        context_match_element = elmaker.ContextMatch()

        if len(self.match_criteria) > 1:
            comparison_list_element = elmaker.ComparisonList(
                *(comp.to_xml(elmaker=elmaker) for comp in self.match_criteria)
            )
            context_match_element.append(comparison_list_element)
        elif isinstance(self.match_criteria[0], comparisons.Comparison):
            context_match_element.append(self.match_criteria[0].to_xml(elmaker=elmaker))
        elif isinstance(self.match_criteria[0], comparisons.BooleanExpression):
            context_match_element.append(self.match_criteria[0].to_xml(elmaker=elmaker))
        else:
            raise ValueError("Unsupported ContextMatch contents in match_criteria attribute")

        return elmaker.ContextCalibrator(
            context_match_element,
            elmaker.Calibrator(self.calibrator.to_xml(elmaker=elmaker))
        )

    def calibrate(self, parsed_value: Union[int, float]) -> float:
        """Wrapper method for the internal `Calibrator.calibrate`

        Parameters
        ----------
        parsed_value : Union[int, float]
            Uncalibrated value.

        Returns
        -------
        : float
            Calibrated value
        """
        return self.calibrator.calibrate(parsed_value)
