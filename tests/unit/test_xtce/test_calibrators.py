"""Tests for calibrators"""
import pytest
import lxml.etree as ElementTree

from space_packet_parser import common
from space_packet_parser.exceptions import CalibrationError
from space_packet_parser.xtce import XTCE_1_2_XMLNS, calibrators, comparisons


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        (f"""
<xtce:ContextCalibrator xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:ContextMatch>
        <xtce:ComparisonList>
            <xtce:Comparison comparisonOperator="&gt;=" value="678" parameterRef="EXI__FPGAT"/>
            <xtce:Comparison comparisonOperator="&lt;" value="4096" parameterRef="EXI__FPGAT"/>
        </xtce:ComparisonList>
    </xtce:ContextMatch>
    <xtce:Calibrator>
        <xtce:PolynomialCalibrator>
            <xtce:Term exponent="0" coefficient="0.5"/>
            <xtce:Term exponent="1" coefficient="1.5"/>
            <xtce:Term exponent="2" coefficient="-0.045"/>
            <xtce:Term exponent="3" coefficient="1.25"/>
            <xtce:Term exponent="4" coefficient="2.5E-3"/>
        </xtce:PolynomialCalibrator>
    </xtce:Calibrator>
</xtce:ContextCalibrator>
""",
         calibrators.ContextCalibrator(
             match_criteria=[
                 comparisons.Comparison(required_value='678', referenced_parameter='EXI__FPGAT', operator='>=',
                                        use_calibrated_value=True),
                 comparisons.Comparison(required_value='4096', referenced_parameter='EXI__FPGAT', operator='<',
                                        use_calibrated_value=True),
             ],
             calibrator=calibrators.PolynomialCalibrator(coefficients=[
                 calibrators.PolynomialCoefficient(coefficient=0.5, exponent=0),
                 calibrators.PolynomialCoefficient(coefficient=1.5, exponent=1),
                 calibrators.PolynomialCoefficient(coefficient=-0.045, exponent=2),
                 calibrators.PolynomialCoefficient(coefficient=1.25, exponent=3),
                 calibrators.PolynomialCoefficient(coefficient=0.0025, exponent=4)
             ]))),
        (f"""
<xtce:ContextCalibrator xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:ContextMatch>
        <xtce:Comparison comparisonOperator="!=" value="3.14" parameterRef="EXI__FPGAT"/>
    </xtce:ContextMatch>
    <xtce:Calibrator>
        <xtce:PolynomialCalibrator>
            <xtce:Term exponent="0" coefficient="0.5"/>
            <xtce:Term exponent="1" coefficient="1.5"/>
            <xtce:Term exponent="2" coefficient="-0.045"/>
            <xtce:Term exponent="3" coefficient="1.25"/>
            <xtce:Term exponent="4" coefficient="2.5E-3"/>
        </xtce:PolynomialCalibrator>
    </xtce:Calibrator>
</xtce:ContextCalibrator>
""",
         calibrators.ContextCalibrator(
             match_criteria=[
                 comparisons.Comparison(required_value='3.14', referenced_parameter='EXI__FPGAT', operator='!=',
                                        use_calibrated_value=True),
             ],
             calibrator=calibrators.PolynomialCalibrator(coefficients=[
                 calibrators.PolynomialCoefficient(coefficient=0.5, exponent=0),
                 calibrators.PolynomialCoefficient(coefficient=1.5, exponent=1),
                 calibrators.PolynomialCoefficient(coefficient=-0.045, exponent=2),
                 calibrators.PolynomialCoefficient(coefficient=1.25, exponent=3),
                 calibrators.PolynomialCoefficient(coefficient=0.0025, exponent=4)
             ]))),
        (f"""
<xtce:ContextCalibrator xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:ContextMatch>
        <xtce:BooleanExpression xmlns:xtce="{XTCE_1_2_XMLNS}">
            <xtce:ANDedConditions>
                <xtce:Condition>
                    <xtce:ParameterInstanceRef parameterRef="P1"/>
                    <xtce:ComparisonOperator>==</xtce:ComparisonOperator>
                    <xtce:Value>100</xtce:Value>
                </xtce:Condition>
                <xtce:Condition>
                    <xtce:ParameterInstanceRef parameterRef="P4"/>
                    <xtce:ComparisonOperator>!=</xtce:ComparisonOperator>
                    <xtce:Value>99</xtce:Value>
                </xtce:Condition>
            </xtce:ANDedConditions>
        </xtce:BooleanExpression>
    </xtce:ContextMatch>
    <xtce:Calibrator>
        <xtce:PolynomialCalibrator>
            <xtce:Term exponent="0" coefficient="0.5"/>
            <xtce:Term exponent="1" coefficient="1.5"/>
        </xtce:PolynomialCalibrator>
    </xtce:Calibrator>
</xtce:ContextCalibrator>
""",
         calibrators.ContextCalibrator(
             match_criteria=[
                 comparisons.BooleanExpression(
                     expression=comparisons.Anded(
                         conditions=[
                             comparisons.Condition(left_param='P1', operator='==', right_value='100',
                                                   right_use_calibrated_value=False),
                             comparisons.Condition(left_param='P4', operator='!=', right_value='99',
                                                   right_use_calibrated_value=False)
                         ],
                         ors=[]
                     )
                 ),
             ],
             calibrator=calibrators.PolynomialCalibrator(coefficients=[
                 calibrators.PolynomialCoefficient(coefficient=0.5, exponent=0),
                 calibrators.PolynomialCoefficient(coefficient=1.5, exponent=1),
             ]))),
    ]
)
def test_context_calibrator(elmaker, xtce_parser, xml_string, expectation):
    """Test parsing a ContextCalibrator from an XML element"""
    element = ElementTree.fromstring(xml_string, parser=xtce_parser)

    result = calibrators.ContextCalibrator.from_xml(element)
    assert result == expectation
    # Re parse the serialized form of the context calibrator to make sure we can recover it
    result_string = ElementTree.tostring(result.to_xml(elmaker=elmaker), pretty_print=True).decode()
    full_circle = calibrators.ContextCalibrator.from_xml(ElementTree.fromstring(result_string, parser=xtce_parser))
    assert full_circle == expectation


@pytest.mark.parametrize(
    ('context_calibrator', 'parsed_data', 'parsed_value', 'match_expectation', 'expectation'),
    [
        (calibrators.ContextCalibrator(
            match_criteria=[
                comparisons.Comparison(required_value='678', referenced_parameter='EXI__FPGAT', operator='>=',
                                       use_calibrated_value=True),
                comparisons.Comparison(required_value='4096', referenced_parameter='EXI__FPGAT', operator='<',
                                       use_calibrated_value=True),
            ],
            calibrator=calibrators.PolynomialCalibrator(coefficients=[
                calibrators.PolynomialCoefficient(coefficient=0.5, exponent=0),
                calibrators.PolynomialCoefficient(coefficient=1.5, exponent=1)
            ])),
         {"EXI__FPGAT": common.IntParameter(700, 600)},
         42, True, 63.5),
        (calibrators.ContextCalibrator(
            match_criteria=[
                comparisons.Comparison(required_value='3.14', referenced_parameter='EXI__FPGAT', operator='!=',
                                       use_calibrated_value=True),
            ],
            calibrator=calibrators.PolynomialCalibrator(coefficients=[
                calibrators.PolynomialCoefficient(coefficient=0.5, exponent=0),
                calibrators.PolynomialCoefficient(coefficient=1.5, exponent=1),
            ])),
         {"EXI__FPGAT": common.FloatParameter(700.0, 3.14)},
         42, True, 63.5),
        (calibrators.ContextCalibrator(
            match_criteria=[
                comparisons.BooleanExpression(
                    expression=comparisons.Anded(
                        conditions=[
                            comparisons.Condition(left_param='P1', operator='==', right_value='700',
                                                  right_use_calibrated_value=False),
                            comparisons.Condition(left_param='P2', operator='!=', right_value='99',
                                                  right_use_calibrated_value=False)
                        ],
                        ors=[]
                    )
                ),
            ],
            calibrator=calibrators.PolynomialCalibrator(coefficients=[
                calibrators.PolynomialCoefficient(coefficient=0.5, exponent=0),
                calibrators.PolynomialCoefficient(coefficient=1.5, exponent=1),
            ])),
         {"P1": common.FloatParameter(700.0, 100.0),
          "P2": common.FloatParameter(700.0, 99)},
         42, True, 63.5),
        (calibrators.ContextCalibrator(
            match_criteria=[
                comparisons.BooleanExpression(
                    expression=comparisons.Ored(
                        conditions=[  # Neither of these are true given the parsed data so far
                            comparisons.Condition(left_param='P1', operator='==', right_value='700',
                                                  left_use_calibrated_value=False,
                                                  right_use_calibrated_value=False),
                            comparisons.Condition(left_param='P2', operator='!=', right_value='700',
                                                  right_use_calibrated_value=False)
                        ],
                        ands=[]
                    )
                ),
            ],
            calibrator=calibrators.PolynomialCalibrator(coefficients=[
                calibrators.PolynomialCoefficient(coefficient=0.5, exponent=0),
                calibrators.PolynomialCoefficient(coefficient=1.5, exponent=1),
            ])),
         {"P1": common.FloatParameter(700.0, 100.0),
          "P2": common.FloatParameter(700.0, 99)},
         42, False, 63.5),
    ]
)
def test_context_calibrator_calibrate(context_calibrator, parsed_data, parsed_value, match_expectation, expectation):
    """Test context calibrator calibration"""
    # Check if the context match is True or False given the parsed data so far
    match = all(criterion.evaluate(parsed_data, parsed_value) for criterion in context_calibrator.match_criteria)
    if match_expectation:
        assert match
    else:
        assert not match
    # Regardless of the context match, we still test the hypothetical result if the calibrator is evaluated
    assert context_calibrator.calibrate(parsed_value) == expectation


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        (f"""
<xtce:SplineCalibrator xmlns:xtce="{XTCE_1_2_XMLNS}" order="0" extrapolate="true">
    <xtce:SplinePoint raw="1" calibrated="10"/>
    <xtce:SplinePoint raw="2.7" calibrated="100.948"/>
    <xtce:SplinePoint raw="3" calibrated="5E2"/>
</xtce:SplineCalibrator>
""",
         calibrators.SplineCalibrator(order=0, extrapolate=True, points=[
             calibrators.SplinePoint(raw=1, calibrated=10),
             calibrators.SplinePoint(raw=2.7, calibrated=100.948),
             calibrators.SplinePoint(raw=3, calibrated=500),
         ])),
        (f"""
<xtce:SplineCalibrator xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:SplinePoint raw="1" calibrated="10"/>
    <xtce:SplinePoint raw="2.7" calibrated="100.948"/>
    <xtce:SplinePoint raw="3" calibrated="5E2"/>
</xtce:SplineCalibrator>
""",
         calibrators.SplineCalibrator(order=0, extrapolate=False, points=[
             calibrators.SplinePoint(raw=1, calibrated=10),
             calibrators.SplinePoint(raw=2.7, calibrated=100.948),
             calibrators.SplinePoint(raw=3, calibrated=500),
         ])),
    ]
)
def test_spline_calibrator(elmaker, xtce_parser, xml_string: str, expectation):
    """Test parsing a StringDataEncoding from an XML string"""
    element = ElementTree.fromstring(xml_string, parser=xtce_parser)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            calibrators.SplineCalibrator.from_xml(element)
    else:
        result = calibrators.SplineCalibrator.from_xml(element)
        assert result == expectation
        # Re serialize to XML and re parse it to ensure we can reproduce it
        result_string = ElementTree.tostring(result.to_xml(elmaker=elmaker), pretty_print=True).decode()
        full_circle = calibrators.SplineCalibrator.from_xml(
            ElementTree.fromstring(result_string, parser=xtce_parser))
        assert full_circle == expectation


@pytest.mark.parametrize(
    ('xq', 'order', 'extrapolate', 'expectation'),
    [
        # Zero order
        (-10, 0, True, 0.),
        (-10, 0, False, CalibrationError()),
        (-1, 0, True, 0.),
        (-1, 0, False, 0.),
        (1.5, 0, False, 3.),
        (5., 0, False, CalibrationError()),
        (5., 0, True, 2.),
        # First order
        (-10, 1, True, -27.),
        (-10, 1, False, CalibrationError()),
        (-1, 1, True, 0.),
        (-1, 1, False, 0.),
        (1.5, 1, False, 2.25),
        (5., 1, False, CalibrationError()),
        (5., 1, True, 0.5),
    ],
)
def test_spline_calibrator_calibrate(xq, order, extrapolate, expectation):
    """Test spline default_calibrator interpolation routines"""
    spline_points = [
        calibrators.SplinePoint(-1., 0.),
        calibrators.SplinePoint(0., 3.),
        calibrators.SplinePoint(2., 2),
    ]
    calibrator = calibrators.SplineCalibrator(spline_points, order=order, extrapolate=extrapolate)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            calibrator.calibrate(xq)
    else:
        result = calibrator.calibrate(xq)
        assert result == expectation


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        (f"""
<xtce:PolynomialCalibrator xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:Term exponent="0" coefficient="0.5"/>
    <xtce:Term exponent="1" coefficient="1.5"/>
    <xtce:Term exponent="2" coefficient="-0.045"/>
    <xtce:Term exponent="3" coefficient="1.25"/>
    <xtce:Term exponent="4" coefficient="2.5E-3"/>
</xtce:PolynomialCalibrator>
""",
         calibrators.PolynomialCalibrator(coefficients=[
             calibrators.PolynomialCoefficient(coefficient=0.5, exponent=0),
             calibrators.PolynomialCoefficient(coefficient=1.5, exponent=1),
             calibrators.PolynomialCoefficient(coefficient=-0.045, exponent=2),
             calibrators.PolynomialCoefficient(coefficient=1.25, exponent=3),
             calibrators.PolynomialCoefficient(coefficient=0.0025, exponent=4),
         ])),
    ]
)
def test_polynomial_calibrator(elmaker, xtce_parser, xml_string: str, expectation):
    """Test parsing a StringDataEncoding from an XML string"""
    element = ElementTree.fromstring(xml_string, parser=xtce_parser)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            calibrators.PolynomialCalibrator.from_xml(element)
    else:
        result = calibrators.PolynomialCalibrator.from_xml(element)
        assert result == expectation
        # Re serialize to XML and re parse it to ensure we can reproduce it
        result_string = ElementTree.tostring(result.to_xml(elmaker=elmaker), pretty_print=True).decode()
        full_circle = calibrators.PolynomialCalibrator.from_xml(
            ElementTree.fromstring(result_string, parser=xtce_parser))
        assert full_circle == expectation

@pytest.mark.parametrize(
    ('xq', 'expectation'),
    [
        (-10., 101.5),
        (0., 1.5),
        (50, 2501.5)
    ],
)
def test_polynomial_calibrator_calibrate(xq, expectation):
    """Test polynomial default_calibrator interpolation routines"""
    polynomial_coefficients = [
        calibrators.PolynomialCoefficient(1.5, 0),
        calibrators.PolynomialCoefficient(0, 1),
        calibrators.PolynomialCoefficient(1., 2)
    ]
    calibrator = calibrators.PolynomialCalibrator(polynomial_coefficients)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            calibrator.calibrate(xq)
    else:
        result = calibrator.calibrate(xq)
        assert result == expectation
