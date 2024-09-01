"""Tests for space_packet_parser.xtcedef"""
# Standard
import io
# Installed
import pytest
import lxml.etree as ElementTree
# Local
from space_packet_parser import xtcedef, parser

XTCE_URI = "http://www.omg.org/space/xtce"
TEST_NAMESPACE = {'xtce': XTCE_URI}


def test_invalid_parameter_type_error(test_data_dir):
    """Test proper reporting of an invalid parameter type element"""
    # Test document contains an invalid "InvalidParameterType" element
    test_xtce_document = """<?xml version='1.0' encoding='UTF-8'?>
<xtce:SpaceSystem xmlns:xtce="http://www.omg.org/space/xtce" name="Space Packet Parser"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xsi:schemaLocation="http://www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd">
    <xtce:Header date="2024-03-05T13:36:00MST" version="1.0" author="Gavin Medley"/>
    <xtce:TelemetryMetaData>
        <xtce:ParameterTypeSet>
            <xtce:InvalidParameterType name="TEST_INVALID_Type" signed="false">
                <xtce:UnitSet/>
                <xtce:IntegerDataEncoding sizeInBits="3" encoding="unsigned"/>
            </xtce:InvalidParameterType>
        </xtce:ParameterTypeSet>
        <xtce:ParameterSet>
            <xtce:Parameter name="INVALID" parameterTypeRef="TEST_INVALID_Type"/>
        </xtce:ParameterSet>
        <xtce:ContainerSet>
            <xtce:SequenceContainer name="TEST_CONTAINER" shortDescription="Test container">
                <xtce:EntryList>
                    <xtce:ParameterRefEntry parameterRef="INVALID"/>
                </xtce:EntryList>
            </xtce:SequenceContainer>
        </xtce:ContainerSet>
    </xtce:TelemetryMetaData>
</xtce:SpaceSystem>
"""
    x = io.TextIOWrapper(io.BytesIO(test_xtce_document.encode("utf-8")))
    with pytest.raises(xtcedef.InvalidParameterTypeError):
        xtcedef.XtcePacketDefinition(x)


def test_unsupported_parameter_type_error(test_data_dir):
    """Test proper reporting of an unsupported parameter type element"""
    # Test document contains an unsupported array parameter type that is not yet implemented
    test_xtce_document = """<?xml version='1.0' encoding='UTF-8'?>
<xtce:SpaceSystem xmlns:xtce="http://www.omg.org/space/xtce" name="Space Packet Parser"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xsi:schemaLocation="http://www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd">
    <xtce:Header date="2024-03-05T13:36:00MST" version="1.0" author="Gavin Medley"/>
    <xtce:TelemetryMetaData>
        <xtce:ParameterTypeSet>
            <xtce:ArrayParameterType name="TEST_ARRAY_Type" arrayTypeRef="TYPE_Type">
                <xtce:DimensionList>
                    <xtce:Dimension>
                        <xtce:StartingIndex>
                            <xtce:FixedValue>0</xtce:FixedValue>
                        </xtce:StartingIndex>
                        <xtce:EndingIndex>
                            <xtce:FixedValue>4</xtce:FixedValue>
                        </xtce:EndingIndex>
                    </xtce:Dimension>
                </xtce:DimensionList>
            </xtce:ArrayParameterType>
        </xtce:ParameterTypeSet>
        <xtce:ParameterSet>
            <xtce:Parameter name="ARRAY" parameterTypeRef="TEST_ARRAY_Type"/>
        </xtce:ParameterSet>
        <xtce:ContainerSet>
            <xtce:SequenceContainer name="TEST_CONTAINER" shortDescription="Test container">
                <xtce:EntryList>
                    <xtce:ParameterRefEntry parameterRef="ARRAY"/>
                </xtce:EntryList>
            </xtce:SequenceContainer>
        </xtce:ContainerSet>
    </xtce:TelemetryMetaData>
</xtce:SpaceSystem>
"""
    x = io.TextIOWrapper(io.BytesIO(test_xtce_document.encode("utf-8")))
    with pytest.raises(NotImplementedError):
        xtcedef.XtcePacketDefinition(x)


def test_attr_comparable():
    """Test abstract class that allows comparisons based on all non-callable attributes"""
    class TestClass(xtcedef.AttrComparable):
        """Test Class"""
        def __init__(self, public, private, dunder):
            self.public = public
            self._private = private
            self.__dunder = dunder  # Dundered attributes are ignored (they get mangled by class name on construction)

        @property
        def entertained(self):
            """Properties are compared"""
            return 10 * self.public

        def ignored(self, x):
            """Methods are ignored"""
            return 2*x

    a = TestClass(1, 2, 9)
    a.__doc__ = "foobar"  # Ignored dunder method
    b = TestClass(1, 2, 10)
    assert a == b
    a.public += 1  # Change an attribute that _does_ get compared
    with pytest.raises(AssertionError):
        assert a == b


@pytest.mark.parametrize(
    ('xml_string', 'test_parsed_data', 'current_parsed_value', 'expected_comparison_result'),
    [
        ("""
<xtce:Comparison xmlns:xtce="http://www.omg.org/space/xtce" 
    comparisonOperator="==" value="678" parameterRef="MSN__PARAM"/>
""",
         {'MSN__PARAM': parser.ParsedDataItem('MSN__PARAM', 3, None, 678)}, None, True),
        ("""
<xtce:Comparison xmlns:xtce="http://www.omg.org/space/xtce" 
    comparisonOperator="eq" value="678" parameterRef="MSN__PARAM"/>
""",
         {'MSN__PARAM': parser.ParsedDataItem('MSN__PARAM', 3, None, 668)}, None, False),
        ("""
<xtce:Comparison xmlns:xtce="http://www.omg.org/space/xtce" 
    comparisonOperator="!=" value="678" parameterRef="MSN__PARAM"/>
""",
         {'MSN__PARAM': parser.ParsedDataItem('MSN__PARAM', 3, None, 678)}, None, False),
        ("""
<xtce:Comparison xmlns:xtce="http://www.omg.org/space/xtce" 
    comparisonOperator="neq" value="678" parameterRef="MSN__PARAM"/>
""",
         {'MSN__PARAM': parser.ParsedDataItem('MSN__PARAM', 3, None, 658)}, None, True),
        ("""
<xtce:Comparison xmlns:xtce="http://www.omg.org/space/xtce" 
    comparisonOperator="&lt;" value="678" parameterRef="MSN__PARAM"/>
""",
         {'MSN__PARAM': parser.ParsedDataItem('MSN__PARAM', 3, None, 679)}, None, False),
        ("""
<xtce:Comparison xmlns:xtce="http://www.omg.org/space/xtce" 
    comparisonOperator="lt" value="678" parameterRef="MSN__PARAM"/>
""",
         {'MSN__PARAM': parser.ParsedDataItem('MSN__PARAM', 3, None, 670)}, None, True),
        ("""
<xtce:Comparison xmlns:xtce="http://www.omg.org/space/xtce" 
    comparisonOperator="&gt;" value="678" parameterRef="MSN__PARAM"/>
""",
         {'MSN__PARAM': parser.ParsedDataItem('MSN__PARAM', 3, None, 678)}, None, False),
        ("""
<xtce:Comparison xmlns:xtce="http://www.omg.org/space/xtce" 
    comparisonOperator="gt" value="678" parameterRef="MSN__PARAM"/>
""",
         {'MSN__PARAM': parser.ParsedDataItem('MSN__PARAM', 3, None, 679)}, None, True),
        ("""
<xtce:Comparison xmlns:xtce="http://www.omg.org/space/xtce" 
    comparisonOperator="&lt;=" value="678" parameterRef="MSN__PARAM"/>
""",
         {'MSN__PARAM': parser.ParsedDataItem('MSN__PARAM', 3, None, 660)}, None, True),
        ("""
<xtce:Comparison xmlns:xtce="http://www.omg.org/space/xtce" 
    comparisonOperator="leq" value="678" parameterRef="MSN__PARAM"/>
""",
         {'MSN__PARAM': parser.ParsedDataItem('MSN__PARAM', 3, None, 690)}, None, False),
        ("""
<xtce:Comparison xmlns:xtce="http://www.omg.org/space/xtce" 
    comparisonOperator="&gt;=" value="678" parameterRef="MSN__PARAM"/>
""",
         {'MSN__PARAM': parser.ParsedDataItem('MSN__PARAM', 3, None, 660)}, None, False),
        ("""
<xtce:Comparison xmlns:xtce="http://www.omg.org/space/xtce" 
    comparisonOperator="geq" value="678" parameterRef="MSN__PARAM"/>
""",
         {'MSN__PARAM': parser.ParsedDataItem('MSN__PARAM', 3, None, 690)}, None, True),
        ("""
<xtce:Comparison xmlns:xtce="http://www.omg.org/space/xtce" 
    comparisonOperator="==" value="678" parameterRef="MSN__PARAM" useCalibratedValue="false"/>
""",
         {'MSN__PARAM': parser.ParsedDataItem('MSN__PARAM', 678, None, 690)}, None, True),
        ("""
<xtce:Comparison xmlns:xtce="http://www.omg.org/space/xtce" 
    comparisonOperator="==" value="678" parameterRef="MSN__PARAM" useCalibratedValue="true"/>
""",
         {'MSN__PARAM': parser.ParsedDataItem('MSN__PARAM', 3, None, 678)}, None, True),
        ("""
<xtce:Comparison xmlns:xtce="http://www.omg.org/space/xtce" 
    comparisonOperator="==" value="foostring" parameterRef="MSN__PARAM" useCalibratedValue="false"/>
""",
         {'MSN__PARAM': parser.ParsedDataItem('MSN__PARAM', 'foostring', None, 'calibratedfoostring')}, None, True),
        ("""
<xtce:Comparison xmlns:xtce="http://www.omg.org/space/xtce" 
    comparisonOperator="==" value="3.14" parameterRef="MSN__PARAM"/>
""",
         {'MSN__PARAM': parser.ParsedDataItem('MSN__PARAM', 1, None, 3.14)}, None, True),
        ("""
<xtce:Comparison xmlns:xtce="http://www.omg.org/space/xtce" 
    comparisonOperator="==" value="3.0" parameterRef="REFERENCE_TO_OWN_RAW_VAL"/>
""",
         {}, 3.0, True),
        ("""
<xtce:Comparison xmlns:xtce="http://www.omg.org/space/xtce" 
    comparisonOperator="==" value="3" parameterRef="REFERENCE_TO_OWN_RAW_VAL"/>
""",
         {}, 3, True),
        ("""
<xtce:Comparison xmlns:xtce="http://www.omg.org/space/xtce" 
    comparisonOperator="==" value="foostr" parameterRef="REFERENCE_TO_OWN_RAW_VAL"/>
""",
         {}, "foostr", True),
        ("""
<xtce:Comparison xmlns:xtce="http://www.omg.org/space/xtce" 
    comparisonOperator="==" value="3.0" parameterRef="REFERENCE_TO_OWN_RAW_VAL"/>
""",
         {}, 3, xtcedef.ComparisonError("Fails to parse a float string 3.0 into an int")),
    ]
)
def test_comparison(xml_string, test_parsed_data, current_parsed_value, expected_comparison_result):
    """Test Comparison object"""
    element = ElementTree.fromstring(xml_string)
    if isinstance(expected_comparison_result, Exception):
        with pytest.raises(type(expected_comparison_result)):
            comparison = xtcedef.Comparison.from_match_criteria_xml_element(element, TEST_NAMESPACE)
            comparison.evaluate(test_parsed_data, current_parsed_value)
    else:
        comparison = xtcedef.Comparison.from_match_criteria_xml_element(element, TEST_NAMESPACE)
        assert comparison.evaluate(test_parsed_data, current_parsed_value) == expected_comparison_result


@pytest.mark.parametrize(
    ('xml_string', 'test_parsed_data', 'expected_condition_result'),
    [
        ("""
<xtce:Condition xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:ParameterInstanceRef parameterRef="P1"/>
    <xtce:ComparisonOperator>&gt;=</xtce:ComparisonOperator>
    <xtce:ParameterInstanceRef parameterRef="P2"/>
</xtce:Condition>
""",
         {'P1': parser.ParsedDataItem('P1', 4, None, 700),
          'P2': parser.ParsedDataItem('P2', 3, None, 678)}, True),
        ("""
<xtce:Condition xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:ParameterInstanceRef parameterRef="P1"/>
    <xtce:ComparisonOperator>&gt;=</xtce:ComparisonOperator>
    <xtce:Value>4</xtce:Value>
</xtce:Condition>
""",
         {'P1': parser.ParsedDataItem('P1', 4, None, 700)}, True),
        ("""
<xtce:Condition xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:ParameterInstanceRef parameterRef="P1"/>
    <xtce:ComparisonOperator>==</xtce:ComparisonOperator>
    <xtce:ParameterInstanceRef parameterRef="P2"/>
</xtce:Condition>
""",
         {'P1': parser.ParsedDataItem('P1', 4, None, 700),
          'P2': parser.ParsedDataItem('P2', 3, None, 678)}, False),
        ("""
<xtce:Condition xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:ParameterInstanceRef parameterRef="P1" useCalibratedValue="false"/>
    <xtce:ComparisonOperator>==</xtce:ComparisonOperator>
    <xtce:ParameterInstanceRef parameterRef="P2" useCalibratedValue="false"/>
</xtce:Condition>
""",
         {'P1': parser.ParsedDataItem('P1', 'abcd', None),
          'P2': parser.ParsedDataItem('P2', 'abcd', None)}, True),
        ("""
<xtce:Condition xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:ParameterInstanceRef parameterRef="P1"/>
    <xtce:ComparisonOperator>==</xtce:ComparisonOperator>
    <xtce:ParameterInstanceRef parameterRef="P2"/>
</xtce:Condition>
""",
         {'P1': parser.ParsedDataItem('P1', 1, None, 3.14),
          'P2': parser.ParsedDataItem('P2', 180, None, 3.14)}, True),
    ]
)
def test_condition(xml_string, test_parsed_data, expected_condition_result):
    """Test Condition object"""
    element = ElementTree.fromstring(xml_string)
    condition = xtcedef.Condition.from_match_criteria_xml_element(element, TEST_NAMESPACE)
    assert condition.evaluate(test_parsed_data, None) == expected_condition_result


@pytest.mark.parametrize(
    ('xml_string', 'test_parsed_data', 'expected_result'),
    [
        ("""
<xtce:BooleanExpression xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:ORedConditions>
        <xtce:Condition>
            <xtce:ParameterInstanceRef parameterRef="P"/>
            <xtce:ComparisonOperator>==</xtce:ComparisonOperator>
            <xtce:Value>100</xtce:Value>
        </xtce:Condition>
        <xtce:ANDedConditions>
            <xtce:Condition>
                <xtce:ParameterInstanceRef parameterRef="P2"/>
                <xtce:ComparisonOperator>&lt;=</xtce:ComparisonOperator>
                <xtce:ParameterInstanceRef parameterRef="P3"/>
            </xtce:Condition>
            <xtce:Condition>
                <xtce:ParameterInstanceRef parameterRef="P4"/>
                <xtce:ComparisonOperator>!=</xtce:ComparisonOperator>
                <xtce:Value>99</xtce:Value>
            </xtce:Condition>
        </xtce:ANDedConditions>
    </xtce:ORedConditions>
</xtce:BooleanExpression>
""",
         {'P': parser.ParsedDataItem('P', 4, None, 0),
          'P2': parser.ParsedDataItem('P2', 4, None, 700),
          'P3': parser.ParsedDataItem('P3', 4, None, 701),
          'P4': parser.ParsedDataItem('P4', 4, None, 98)}, True),
        ("""
<xtce:BooleanExpression xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:ANDedConditions>
        <xtce:Condition>
            <xtce:ParameterInstanceRef parameterRef="P"/>
            <xtce:ComparisonOperator>==</xtce:ComparisonOperator>
            <xtce:Value>100</xtce:Value>
        </xtce:Condition>
        <xtce:Condition>
            <xtce:ParameterInstanceRef parameterRef="P0"/>
            <xtce:ComparisonOperator>&gt;=</xtce:ComparisonOperator>
            <xtce:ParameterInstanceRef parameterRef="P1"/>
        </xtce:Condition>
        <xtce:ORedConditions>
            <xtce:Condition>
                <xtce:ParameterInstanceRef parameterRef="P2"/>
                <xtce:ComparisonOperator>&lt;=</xtce:ComparisonOperator>
                <xtce:ParameterInstanceRef parameterRef="P3"/>
            </xtce:Condition>
            <xtce:Condition>
                <xtce:ParameterInstanceRef parameterRef="P4"/>
                <xtce:ComparisonOperator>!=</xtce:ComparisonOperator>
                <xtce:Value>99</xtce:Value>
            </xtce:Condition>
        </xtce:ORedConditions>
    </xtce:ANDedConditions>
</xtce:BooleanExpression>
""",
         {'P': parser.ParsedDataItem('P', 4, None, 100),
          'P0': parser.ParsedDataItem('P0', 4, None, 678),
          'P1': parser.ParsedDataItem('P1', 4, None, 500),
          'P2': parser.ParsedDataItem('P2', 4, None, 700),
          'P3': parser.ParsedDataItem('P3', 4, None, 701),
          'P4': parser.ParsedDataItem('P4', 4, None, 99)}, True),
    ]
)
def test_boolean_expression(xml_string, test_parsed_data, expected_result):
    """Test BooleanExpression object"""
    element = ElementTree.fromstring(xml_string)
    if isinstance(expected_result, Exception):
        with pytest.raises(type(expected_result)):
            xtcedef.BooleanExpression.from_match_criteria_xml_element(element, TEST_NAMESPACE)
    else:
        expression = xtcedef.BooleanExpression.from_match_criteria_xml_element(element, TEST_NAMESPACE)
        assert expression.evaluate(test_parsed_data, current_parsed_value=None) == expected_result


@pytest.mark.parametrize(
    ('xml_string', 'test_parsed_data', 'expected_lookup_result'),
    [
        ("""
<xtce:DiscreteLookup value="10" xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:Comparison useCalibratedValue="false" parameterRef="P1" value="1"/>
</xtce:DiscreteLookup>
""",
         {'P1': parser.ParsedDataItem('P1', 1, None, 678)}, 10),
        ("""
<xtce:DiscreteLookup value="10" xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:Comparison useCalibratedValue="false" parameterRef="P1" value="1"/>
</xtce:DiscreteLookup>
""",
         {'P1': parser.ParsedDataItem('P1', 0, None, 678)}, None),
        ("""
<xtce:DiscreteLookup value="11" xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:ComparisonList>
        <xtce:Comparison comparisonOperator="&gt;=" value="678" parameterRef="MSN__PARAM1"/>
        <xtce:Comparison comparisonOperator="&lt;" value="4096" parameterRef="MSN__PARAM2"/>
    </xtce:ComparisonList>
</xtce:DiscreteLookup>
""",
         {
             'MSN__PARAM1': parser.ParsedDataItem('MSN__PARAM1', 3, None, 680),
             'MSN__PARAM2': parser.ParsedDataItem('MSN__PARAM2', 3, None, 3000)
         }, 11),
    ]
)
def test_discrete_lookup(xml_string, test_parsed_data, expected_lookup_result):
    """Test DiscreteLookup object"""
    element = ElementTree.fromstring(xml_string)
    discrete_lookup = xtcedef.DiscreteLookup.from_discrete_lookup_xml_element(element, TEST_NAMESPACE)
    assert discrete_lookup.evaluate(test_parsed_data, current_parsed_value=None) == expected_lookup_result


# ----------------
# Calibrator Tests
# ----------------
@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        ("""
<xtce:ContextCalibrator xmlns:xtce="http://www.omg.org/space/xtce">
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
         xtcedef.ContextCalibrator(
             match_criteria=[
                 xtcedef.Comparison(required_value='678', referenced_parameter='EXI__FPGAT', operator='>=',
                                    use_calibrated_value=True),
                 xtcedef.Comparison(required_value='4096', referenced_parameter='EXI__FPGAT', operator='<',
                                    use_calibrated_value=True),
             ],
             calibrator=xtcedef.PolynomialCalibrator(coefficients=[
                 xtcedef.PolynomialCoefficient(coefficient=0.5, exponent=0),
                 xtcedef.PolynomialCoefficient(coefficient=1.5, exponent=1),
                 xtcedef.PolynomialCoefficient(coefficient=-0.045, exponent=2),
                 xtcedef.PolynomialCoefficient(coefficient=1.25, exponent=3),
                 xtcedef.PolynomialCoefficient(coefficient=0.0025, exponent=4)
             ]))),
        ("""
<xtce:ContextCalibrator xmlns:xtce="http://www.omg.org/space/xtce">
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
         xtcedef.ContextCalibrator(
             match_criteria=[
                 xtcedef.Comparison(required_value='3.14', referenced_parameter='EXI__FPGAT', operator='!=',
                                    use_calibrated_value=True),
             ],
             calibrator=xtcedef.PolynomialCalibrator(coefficients=[
                 xtcedef.PolynomialCoefficient(coefficient=0.5, exponent=0),
                 xtcedef.PolynomialCoefficient(coefficient=1.5, exponent=1),
                 xtcedef.PolynomialCoefficient(coefficient=-0.045, exponent=2),
                 xtcedef.PolynomialCoefficient(coefficient=1.25, exponent=3),
                 xtcedef.PolynomialCoefficient(coefficient=0.0025, exponent=4)
             ]))),
        ("""
<xtce:ContextCalibrator xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:ContextMatch>
        <xtce:BooleanExpression xmlns:xtce="http://www.omg.org/space/xtce">
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
         xtcedef.ContextCalibrator(
             match_criteria=[
                 xtcedef.BooleanExpression(
                     expression=xtcedef.Anded(
                         conditions=[
                             xtcedef.Condition(left_param='P1', operator='==', right_value='100',
                                               right_use_calibrated_value=False),
                             xtcedef.Condition(left_param='P4', operator='!=', right_value='99',
                                               right_use_calibrated_value=False)
                         ],
                         ors=[]
                     )
                 ),
             ],
             calibrator=xtcedef.PolynomialCalibrator(coefficients=[
                 xtcedef.PolynomialCoefficient(coefficient=0.5, exponent=0),
                 xtcedef.PolynomialCoefficient(coefficient=1.5, exponent=1),
             ]))),
    ]
)
def test_context_calibrator(xml_string, expectation):
    """Test parsing a ContextCalibrator from an XML element"""
    element = ElementTree.fromstring(xml_string)

    result = xtcedef.ContextCalibrator.from_context_calibrator_xml_element(element, TEST_NAMESPACE)
    assert result == expectation


@pytest.mark.parametrize(
    ('context_calibrator', 'parsed_data', 'parsed_value', 'match_expectation', 'expectation'),
    [
        (xtcedef.ContextCalibrator(
             match_criteria=[
                 xtcedef.Comparison(required_value='678', referenced_parameter='EXI__FPGAT', operator='>=',
                                    use_calibrated_value=True),
                 xtcedef.Comparison(required_value='4096', referenced_parameter='EXI__FPGAT', operator='<',
                                    use_calibrated_value=True),
             ],
             calibrator=xtcedef.PolynomialCalibrator(coefficients=[
                 xtcedef.PolynomialCoefficient(coefficient=0.5, exponent=0),
                 xtcedef.PolynomialCoefficient(coefficient=1.5, exponent=1)
             ])),
            {"EXI__FPGAT": parser.ParsedDataItem("EXI__FPGAT", 600, derived_value=700)},
            42, True, 63.5),
        (xtcedef.ContextCalibrator(
             match_criteria=[
                 xtcedef.Comparison(required_value='3.14', referenced_parameter='EXI__FPGAT', operator='!=',
                                    use_calibrated_value=True),
             ],
             calibrator=xtcedef.PolynomialCalibrator(coefficients=[
                 xtcedef.PolynomialCoefficient(coefficient=0.5, exponent=0),
                 xtcedef.PolynomialCoefficient(coefficient=1.5, exponent=1),
             ])),
         {"EXI__FPGAT": parser.ParsedDataItem("EXI__FPGAT", 3.14, derived_value=700.0)},
         42, True, 63.5),
        (xtcedef.ContextCalibrator(
             match_criteria=[
                 xtcedef.BooleanExpression(
                     expression=xtcedef.Anded(
                         conditions=[
                             xtcedef.Condition(left_param='P1', operator='==', right_value='700',
                                               right_use_calibrated_value=False),
                             xtcedef.Condition(left_param='P2', operator='!=', right_value='99',
                                               right_use_calibrated_value=False)
                         ],
                         ors=[]
                     )
                 ),
             ],
             calibrator=xtcedef.PolynomialCalibrator(coefficients=[
                 xtcedef.PolynomialCoefficient(coefficient=0.5, exponent=0),
                 xtcedef.PolynomialCoefficient(coefficient=1.5, exponent=1),
             ])),
         {"P1": parser.ParsedDataItem("P1", 100.0, derived_value=700.0),
          "P2": parser.ParsedDataItem("P2", 99, derived_value=700.0)},
         42, True, 63.5),
        (xtcedef.ContextCalibrator(
             match_criteria=[
                 xtcedef.BooleanExpression(
                     expression=xtcedef.Ored(
                         conditions=[  # Neither of these are true given the parsed data so far
                             xtcedef.Condition(left_param='P1', operator='==', right_value='700',
                                               left_use_calibrated_value=False,
                                               right_use_calibrated_value=False),
                             xtcedef.Condition(left_param='P2', operator='!=', right_value='700',
                                               right_use_calibrated_value=False)
                         ],
                         ands=[]
                     )
                 ),
             ],
             calibrator=xtcedef.PolynomialCalibrator(coefficients=[
                 xtcedef.PolynomialCoefficient(coefficient=0.5, exponent=0),
                 xtcedef.PolynomialCoefficient(coefficient=1.5, exponent=1),
             ])),
         {"P1": parser.ParsedDataItem("P1", 100.0, derived_value=700.0),
          "P2": parser.ParsedDataItem("P2", 99, derived_value=700.0)},
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
        ("""
<xtce:SplineCalibrator xmlns:xtce="http://www.omg.org/space/xtce" order="zero" extrapolate="true">
    <xtce:SplinePoint raw="1" calibrated="10"/>
    <xtce:SplinePoint raw="2.7" calibrated="100.948"/>
    <xtce:SplinePoint raw="3" calibrated="5E2"/>
</xtce:SplineCalibrator> 
""",
         xtcedef.SplineCalibrator(order=0, extrapolate=True, points=[
             xtcedef.SplinePoint(raw=1, calibrated=10),
             xtcedef.SplinePoint(raw=2.7, calibrated=100.948),
             xtcedef.SplinePoint(raw=3, calibrated=500),
         ])),
        ("""
<xtce:SplineCalibrator xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:SplinePoint raw="1" calibrated="10"/>
    <xtce:SplinePoint raw="2.7" calibrated="100.948"/>
    <xtce:SplinePoint raw="3" calibrated="5E2"/>
</xtce:SplineCalibrator> 
""",
         xtcedef.SplineCalibrator(order=0, extrapolate=False, points=[
             xtcedef.SplinePoint(raw=1, calibrated=10),
             xtcedef.SplinePoint(raw=2.7, calibrated=100.948),
             xtcedef.SplinePoint(raw=3, calibrated=500),
         ])),
        ]
)
def test_spline_calibrator(xml_string: str, expectation):
    """Test parsing a StringDataEncoding from an XML string"""
    element = ElementTree.fromstring(xml_string)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            xtcedef.SplineCalibrator.from_calibrator_xml_element(element, TEST_NAMESPACE)
    else:
        result = xtcedef.SplineCalibrator.from_calibrator_xml_element(element, TEST_NAMESPACE)
        assert result == expectation


@pytest.mark.parametrize(
    ('xq', 'order', 'extrapolate', 'expectation'),
    [
        # Zero order
        (-10, 0, True, 0.),
        (-10, 0, False, xtcedef.CalibrationError()),
        (-1, 0, True, 0.),
        (-1, 0, False, 0.),
        (1.5, 0, False, 3.),
        (5., 0, False, xtcedef.CalibrationError()),
        (5., 0, True, 2.),
        # First order
        (-10, 1, True, -27.),
        (-10, 1, False, xtcedef.CalibrationError()),
        (-1, 1, True, 0.),
        (-1, 1, False, 0.),
        (1.5, 1, False, 2.25),
        (5., 1, False, xtcedef.CalibrationError()),
        (5., 1, True, 0.5),
    ],
)
def test_spline_calibrator_calibrate(xq, order, extrapolate, expectation):
    """Test spline default_calibrator interpolation routines"""
    spline_points = [
        xtcedef.SplinePoint(-1., 0.),
        xtcedef.SplinePoint(0., 3.),
        xtcedef.SplinePoint(2., 2),
    ]
    calibrator = xtcedef.SplineCalibrator(spline_points, order=order, extrapolate=extrapolate)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            calibrator.calibrate(xq)
    else:
        result = calibrator.calibrate(xq)
        assert result == expectation


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        ("""
<xtce:PolynomialCalibrator xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:Term exponent="0" coefficient="0.5"/>
    <xtce:Term exponent="1" coefficient="1.5"/>
    <xtce:Term exponent="2" coefficient="-0.045"/>
    <xtce:Term exponent="3" coefficient="1.25"/>
    <xtce:Term exponent="4" coefficient="2.5E-3"/>
</xtce:PolynomialCalibrator> 
""",
         xtcedef.PolynomialCalibrator(coefficients=[
             xtcedef.PolynomialCoefficient(coefficient=0.5, exponent=0),
             xtcedef.PolynomialCoefficient(coefficient=1.5, exponent=1),
             xtcedef.PolynomialCoefficient(coefficient=-0.045, exponent=2),
             xtcedef.PolynomialCoefficient(coefficient=1.25, exponent=3),
             xtcedef.PolynomialCoefficient(coefficient=0.0025, exponent=4),
         ])),
        ]
)
def test_polynomial_calibrator(xml_string: str, expectation):
    """Test parsing a StringDataEncoding from an XML string"""
    element = ElementTree.fromstring(xml_string)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            xtcedef.PolynomialCalibrator.from_calibrator_xml_element(element, TEST_NAMESPACE)
    else:
        result = xtcedef.PolynomialCalibrator.from_calibrator_xml_element(element, TEST_NAMESPACE)
        assert result == expectation


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
        xtcedef.PolynomialCoefficient(1.5, 0),
        xtcedef.PolynomialCoefficient(0, 1),
        xtcedef.PolynomialCoefficient(1., 2)
    ]
    calibrator = xtcedef.PolynomialCalibrator(polynomial_coefficients)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            calibrator.calibrate(xq)
    else:
        result = calibrator.calibrate(xq)
        assert result == expectation


# ------------------
# DataEncoding Tests
# ------------------
@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        ("""
<xtce:StringDataEncoding encoding="utf-16-be" xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:SizeInBits>
        <xtce:TerminationChar>0058</xtce:TerminationChar>
    </xtce:SizeInBits>
</xtce:StringDataEncoding>
""",
         xtcedef.StringDataEncoding(termination_character='0058', encoding='utf-16-be')),
        ("""
<xtce:StringDataEncoding xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:SizeInBits>
        <xtce:Fixed>
            <xtce:FixedValue>17</xtce:FixedValue>
        </xtce:Fixed>
    </xtce:SizeInBits>
</xtce:StringDataEncoding>
""",
         xtcedef.StringDataEncoding(fixed_length=17)),
        ("""
<xtce:StringDataEncoding xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:SizeInBits>
        <xtce:Fixed>
            <xtce:DynamicValue>
                <xtce:ParameterInstanceRef parameterRef="SizeFromThisParameter"/>
                <xtce:LinearAdjustment intercept="25" slope="8"/> 
            </xtce:DynamicValue> 
        </xtce:Fixed>
    </xtce:SizeInBits>
</xtce:StringDataEncoding>
""",
         xtcedef.StringDataEncoding(dynamic_length_reference='SizeFromThisParameter',
                                    length_linear_adjuster=object())),
        ("""
<xtce:StringDataEncoding xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:SizeInBits>
        <xtce:Fixed>
            <xtce:DiscreteLookupList>
                <xtce:DiscreteLookup value="10">
                    <xtce:Comparison parameterRef="P1" value="1"/>
                </xtce:DiscreteLookup>
                <xtce:DiscreteLookup value="25">
                    <xtce:Comparison parameterRef="P1" value="2"/>
                </xtce:DiscreteLookup>
            </xtce:DiscreteLookupList> 
        </xtce:Fixed>
    </xtce:SizeInBits>
</xtce:StringDataEncoding>
""",
         xtcedef.StringDataEncoding(
             discrete_lookup_length=[
                 xtcedef.DiscreteLookup([xtcedef.Comparison('1', 'P1')], 10),
                 xtcedef.DiscreteLookup([xtcedef.Comparison('2', 'P1')], 25)
             ])),
        ("""
<xtce:StringDataEncoding xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:SizeInBits>
        <xtce:Fixed>
            <xtce:InvalidTag>9000</xtce:InvalidTag>
        </xtce:Fixed>
    </xtce:SizeInBits>
</xtce:StringDataEncoding>
""",
         xtcedef.ElementNotFoundError())
        ]
)
def test_string_data_encoding(xml_string: str, expectation):
    """Test parsing a StringDataEncoding from an XML string"""
    element = ElementTree.fromstring(xml_string)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            xtcedef.StringDataEncoding.from_data_encoding_xml_element(element, TEST_NAMESPACE)
    else:
        result = xtcedef.StringDataEncoding.from_data_encoding_xml_element(element, TEST_NAMESPACE)
        assert result == expectation


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        ("""
<xtce:IntegerDataEncoding xmlns:xtce="http://www.omg.org/space/xtce" sizeInBits="4" encoding="unsigned"/>
""",
         xtcedef.IntegerDataEncoding(size_in_bits=4, encoding='unsigned')),
        ("""
<xtce:IntegerDataEncoding xmlns:xtce="http://www.omg.org/space/xtce" sizeInBits="4"/>
""",
         xtcedef.IntegerDataEncoding(size_in_bits=4, encoding='unsigned')),
        ("""
<xtce:IntegerDataEncoding xmlns:xtce="http://www.omg.org/space/xtce" sizeInBits="16" encoding="unsigned">
    <xtce:DefaultCalibrator>
        <xtce:PolynomialCalibrator>
            <xtce:Term exponent="1" coefficient="1.215500e-02"/>
            <xtce:Term exponent="0" coefficient="2.540000e+00"/>
        </xtce:PolynomialCalibrator>
    </xtce:DefaultCalibrator>
</xtce:IntegerDataEncoding>
""",
         xtcedef.IntegerDataEncoding(
             size_in_bits=16, encoding='unsigned',
             default_calibrator=xtcedef.PolynomialCalibrator([
                 xtcedef.PolynomialCoefficient(0.012155, 1), xtcedef.PolynomialCoefficient(2.54, 0)
             ]))),
        ("""
<xtce:IntegerDataEncoding xmlns:xtce="http://www.omg.org/space/xtce" sizeInBits="12" encoding="unsigned">
    <xtce:ContextCalibratorList>
        <xtce:ContextCalibrator>
            <xtce:ContextMatch>
                <xtce:ComparisonList>
                    <xtce:Comparison comparisonOperator="&gt;=" value="0" parameterRef="MSN__PARAM"/>
                    <xtce:Comparison comparisonOperator="&lt;" value="678" parameterRef="MSN__PARAM"/>
                </xtce:ComparisonList>
            </xtce:ContextMatch>
            <xtce:Calibrator>
                <xtce:PolynomialCalibrator>
                    <xtce:Term exponent="0" coefficient="142.998"/>
                    <xtce:Term exponent="1" coefficient="-0.349712"/>
                </xtce:PolynomialCalibrator>
            </xtce:Calibrator>
        </xtce:ContextCalibrator>
        <xtce:ContextCalibrator>
            <xtce:ContextMatch>
                <xtce:ComparisonList>
                    <xtce:Comparison comparisonOperator="&gt;=" value="678" parameterRef="MSN__PARAM"/>
                    <xtce:Comparison comparisonOperator="&lt;=" value="4096" parameterRef="MSN__PARAM"/>
                </xtce:ComparisonList>
            </xtce:ContextMatch>
            <xtce:Calibrator>
                <xtce:PolynomialCalibrator>
                    <xtce:Term exponent="0" coefficient="100.488"/>
                    <xtce:Term exponent="1" coefficient="-0.110197"/>
                </xtce:PolynomialCalibrator>
            </xtce:Calibrator>
        </xtce:ContextCalibrator>
    </xtce:ContextCalibratorList>
    </xtce:IntegerDataEncoding>
""",
         xtcedef.IntegerDataEncoding(size_in_bits=12, encoding='unsigned',
                                     default_calibrator=None,
                                     context_calibrators=[
                                         xtcedef.ContextCalibrator(
                                             match_criteria=[xtcedef.Comparison(required_value='0', operator=">=",
                                                                                referenced_parameter='MSN__PARAM'),
                                                             xtcedef.Comparison(required_value='678', operator="<",
                                                                                referenced_parameter='MSN__PARAM')],
                                             calibrator=xtcedef.PolynomialCalibrator(
                                                 coefficients=[xtcedef.PolynomialCoefficient(142.998, 0),
                                                               xtcedef.PolynomialCoefficient(-0.349712, 1)])),
                                         xtcedef.ContextCalibrator(
                                             match_criteria=[xtcedef.Comparison(required_value='678', operator=">=",
                                                                                referenced_parameter='MSN__PARAM'),
                                                             xtcedef.Comparison(required_value='4096', operator="<=",
                                                                                referenced_parameter='MSN__PARAM')],
                                             calibrator=xtcedef.PolynomialCalibrator(
                                                 coefficients=[xtcedef.PolynomialCoefficient(100.488, 0),
                                                               xtcedef.PolynomialCoefficient(-0.110197, 1)]))
                                     ])),
    ]
)
def test_integer_data_encoding(xml_string: str, expectation):
    """Test parsing an IntegerDataEncoding from an XML string"""
    element = ElementTree.fromstring(xml_string)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            xtcedef.IntegerDataEncoding.from_data_encoding_xml_element(element, TEST_NAMESPACE)
    else:
        result = xtcedef.IntegerDataEncoding.from_data_encoding_xml_element(element, TEST_NAMESPACE)
        assert result == expectation


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        ("""
<xtce:FloatDataEncoding xmlns:xtce="http://www.omg.org/space/xtce" sizeInBits="4" encoding="IEEE-754"/>
""",
         ValueError()),
        ("""
<xtce:FloatDataEncoding xmlns:xtce="http://www.omg.org/space/xtce" sizeInBits="16">
    <xtce:DefaultCalibrator>
        <xtce:PolynomialCalibrator>
            <xtce:Term exponent="1" coefficient="1.215500e-02"/>
            <xtce:Term exponent="0" coefficient="2.540000e+00"/>
        </xtce:PolynomialCalibrator>
    </xtce:DefaultCalibrator>
</xtce:FloatDataEncoding>
""",
         xtcedef.FloatDataEncoding(
             size_in_bits=16, encoding='IEEE-754',
             default_calibrator=xtcedef.PolynomialCalibrator([
                 xtcedef.PolynomialCoefficient(0.012155, 1), xtcedef.PolynomialCoefficient(2.54, 0)
             ]))),
        ("""
<xtce:FloatDataEncoding xmlns:xtce="http://www.omg.org/space/xtce" sizeInBits="16">
    <xtce:ContextCalibratorList>
        <xtce:ContextCalibrator>
            <xtce:ContextMatch>
                <xtce:ComparisonList>
                    <xtce:Comparison comparisonOperator="&gt;=" value="0" parameterRef="MSN__PARAM"/>
                    <xtce:Comparison comparisonOperator="&lt;" value="678" parameterRef="MSN__PARAM"/>
                </xtce:ComparisonList>
            </xtce:ContextMatch>
            <xtce:Calibrator>
                <xtce:PolynomialCalibrator>
                    <xtce:Term exponent="0" coefficient="142.998"/>
                    <xtce:Term exponent="1" coefficient="-0.349712"/>
                </xtce:PolynomialCalibrator>
            </xtce:Calibrator>
        </xtce:ContextCalibrator>
        <xtce:ContextCalibrator>
            <xtce:ContextMatch>
                <xtce:ComparisonList>
                    <xtce:Comparison comparisonOperator="&gt;=" value="678" parameterRef="MSN__PARAM"/>
                    <xtce:Comparison comparisonOperator="&lt;=" value="4096" parameterRef="MSN__PARAM"/>
                </xtce:ComparisonList>
            </xtce:ContextMatch>
            <xtce:Calibrator>
                <xtce:PolynomialCalibrator>
                    <xtce:Term exponent="0" coefficient="100.488"/>
                    <xtce:Term exponent="1" coefficient="-0.110197"/>
                </xtce:PolynomialCalibrator>
            </xtce:Calibrator>
        </xtce:ContextCalibrator>
    </xtce:ContextCalibratorList>
    <xtce:DefaultCalibrator>
        <xtce:PolynomialCalibrator>
            <xtce:Term exponent="1" coefficient="1.215500e-02"/>
            <xtce:Term exponent="0" coefficient="2.540000e+00"/>
        </xtce:PolynomialCalibrator>
    </xtce:DefaultCalibrator>
</xtce:FloatDataEncoding>
""",
         xtcedef.FloatDataEncoding(
             size_in_bits=16, encoding='IEEE-754',
             default_calibrator=xtcedef.PolynomialCalibrator([
                 xtcedef.PolynomialCoefficient(0.012155, 1), xtcedef.PolynomialCoefficient(2.54, 0)
             ]),
             context_calibrators=[
                 xtcedef.ContextCalibrator(
                     match_criteria=[xtcedef.Comparison(required_value='0', operator=">=",
                                                        referenced_parameter='MSN__PARAM'),
                                     xtcedef.Comparison(required_value='678', operator="<",
                                                        referenced_parameter='MSN__PARAM')],
                     calibrator=xtcedef.PolynomialCalibrator(
                         coefficients=[xtcedef.PolynomialCoefficient(142.998, 0),
                                       xtcedef.PolynomialCoefficient(-0.349712, 1)])),
                 xtcedef.ContextCalibrator(
                     match_criteria=[xtcedef.Comparison(required_value='678', operator=">=",
                                                        referenced_parameter='MSN__PARAM'),
                                     xtcedef.Comparison(required_value='4096', operator="<=",
                                                        referenced_parameter='MSN__PARAM')],
                     calibrator=xtcedef.PolynomialCalibrator(
                         coefficients=[xtcedef.PolynomialCoefficient(100.488, 0),
                                       xtcedef.PolynomialCoefficient(-0.110197, 1)]))
             ]
         )),
    ]
)
def test_float_data_encoding(xml_string: str, expectation):
    """Test parsing an FloatDataEncoding from an XML string"""
    element = ElementTree.fromstring(xml_string)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            xtcedef.FloatDataEncoding.from_data_encoding_xml_element(element, TEST_NAMESPACE)
    else:
        result = xtcedef.FloatDataEncoding.from_data_encoding_xml_element(element, TEST_NAMESPACE)
        assert result == expectation


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        ("""
<xtce:BinaryDataEncoding xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:SizeInBits>
        <xtce:FixedValue>256</xtce:FixedValue>
    </xtce:SizeInBits>
</xtce:BinaryDataEncoding>
""",
         xtcedef.BinaryDataEncoding(fixed_size_in_bits=256)),
        ("""
<xtce:BinaryDataEncoding xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:SizeInBits>
        <xtce:DynamicValue>
            <xtce:ParameterInstanceRef parameterRef="SizeFromThisParameter"/>
            <xtce:LinearAdjustment intercept="25" slope="8"/>
        </xtce:DynamicValue>
    </xtce:SizeInBits>
</xtce:BinaryDataEncoding>
""",
         xtcedef.BinaryDataEncoding(
             size_reference_parameter='SizeFromThisParameter',
             linear_adjuster=lambda x: 25 + 8*x)),
        ("""
<xtce:BinaryDataEncoding xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:SizeInBits>
        <xtce:DiscreteLookupList>
            <xtce:DiscreteLookup value="10">
                <xtce:Comparison parameterRef="P1" value="1"/>
            </xtce:DiscreteLookup>
            <xtce:DiscreteLookup value="25">
                <xtce:Comparison parameterRef="P1" value="2"/>
            </xtce:DiscreteLookup>
        </xtce:DiscreteLookupList>
    </xtce:SizeInBits>
</xtce:BinaryDataEncoding>
""",
         xtcedef.BinaryDataEncoding(size_discrete_lookup_list=[
                 xtcedef.DiscreteLookup([xtcedef.Comparison('1', 'P1')], 10),
                 xtcedef.DiscreteLookup([xtcedef.Comparison('2', 'P1')], 25)
             ])),
    ]
)
def test_binary_data_encoding(xml_string: str, expectation):
    """Test parsing an BinaryDataEncoding from an XML string"""
    element = ElementTree.fromstring(xml_string)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            xtcedef.BinaryDataEncoding.from_data_encoding_xml_element(element, TEST_NAMESPACE)
    else:
        result = xtcedef.BinaryDataEncoding.from_data_encoding_xml_element(element, TEST_NAMESPACE)
        assert result == expectation


# -------------------
# ParameterType Tests
# -------------------
@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        ("""
<xtce:StringParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_STRING_Type">
    <xtce:UnitSet/>
    <xtce:StringDataEncoding>
        <xtce:SizeInBits>
            <xtce:Fixed>
                <xtce:FixedValue>40</xtce:FixedValue>
            </xtce:Fixed>
        </xtce:SizeInBits>
    </xtce:StringDataEncoding>
</xtce:StringParameterType> 
""",
         xtcedef.StringParameterType(name='TEST_STRING_Type',
                                     encoding=xtcedef.StringDataEncoding(fixed_length=40))),
        ("""
<xtce:StringParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_STRING_Type">
    <xtce:StringDataEncoding>
        <xtce:SizeInBits>
            <xtce:LeadingSize sizeInBitsOfSizeTag="17"/>
        </xtce:SizeInBits>
    </xtce:StringDataEncoding>
</xtce:StringParameterType> 
""",
         xtcedef.StringParameterType(name='TEST_STRING_Type',
                                     encoding=xtcedef.StringDataEncoding(leading_length_size=17))),
        ("""
<xtce:StringParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_STRING_Type">
    <xtce:StringDataEncoding>
        <xtce:SizeInBits>
            <xtce:TerminationChar>00</xtce:TerminationChar>
        </xtce:SizeInBits>
    </xtce:StringDataEncoding>
</xtce:StringParameterType> 
""",
         xtcedef.StringParameterType(name='TEST_STRING_Type',
                                     encoding=xtcedef.StringDataEncoding(termination_character='00'))),
    ]
)
def test_string_parameter_type(xml_string: str, expectation):
    """Test parsing an StringParameterType from an XML string"""
    element = ElementTree.fromstring(xml_string)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            xtcedef.StringParameterType.from_parameter_type_xml_element(element, TEST_NAMESPACE)
    else:
        result = xtcedef.StringParameterType.from_parameter_type_xml_element(element, TEST_NAMESPACE)
        assert result == expectation


@pytest.mark.parametrize(
    ('parameter_type', 'parsed_data', 'packet_data', 'expected'),
    [
        # Fixed length test
        (xtcedef.StringParameterType(
            'TEST_STRING',
            xtcedef.StringDataEncoding(fixed_length=3,  # Giving length in bytes
                                       length_linear_adjuster=lambda x: 8*x)),
         {},  # Don't need parsed_data for leading length parsing
         # This still 123X456
         xtcedef.PacketData(b'123X456'),
         '123'),
        # Dynamic reference length
        (xtcedef.StringParameterType(
            'TEST_STRING',
            xtcedef.StringDataEncoding(dynamic_length_reference='STR_LEN',
                                       use_calibrated_value=False,
                                       length_linear_adjuster=lambda x: 8*x)),
         {'STR_LEN': parser.ParsedDataItem('STR_LEN', 8, None)},
         xtcedef.PacketData(b'BAD WOLF'),
         'BAD WOLF'),
        # Discrete lookup test
        (xtcedef.StringParameterType(
            'TEST_STRING',
            xtcedef.StringDataEncoding(discrete_lookup_length=[
                xtcedef.DiscreteLookup([
                    xtcedef.Comparison(7, 'P1', '>'),
                    xtcedef.Comparison(99, 'P2', '==', use_calibrated_value=False)
                ], lookup_value=8)
            ], length_linear_adjuster=lambda x: 8*x)),
         {'P1': parser.ParsedDataItem('P1', 7, None, 7.55), 'P2': parser.ParsedDataItem('P2', 99, None, 100)},
         xtcedef.PacketData(b'BAD WOLF'),
         'BAD WOLF'),
        # Termination character tests
        (xtcedef.StringParameterType(
            'TEST_STRING',
            xtcedef.StringDataEncoding(encoding='utf-8',
                                       termination_character='58')),
         {},  # Don't need parsed_data for termination character
         # 123X456 + extra characters, termination character is X
         xtcedef.PacketData(b'123X456000000000000000000000000000000000000000000000'),
         '123'),
        (xtcedef.StringParameterType(
            'TEST_STRING',
            xtcedef.StringDataEncoding(encoding='utf-8',
                                       termination_character='58')),
         {},  # Don't need parsed_data for termination character
         # 56bits + 123X456 + extra characters, termination character is X
         xtcedef.PacketData(b'9090909123X456000000000000000000000000000000000000000000000', pos=56),
         '123'),
        (xtcedef.StringParameterType(
            'TEST_STRING',
            xtcedef.StringDataEncoding(encoding='utf-8',
                                       termination_character='58')),
         {},  # Don't need parsed_data for termination character
         # 53bits + 123X456 + extra characters, termination character is X
         # This is the same string as above but bit-shifted left by 3 bits
         xtcedef.PacketData(b'\x03K;s{\x93)\x89\x91\x9a\xc1\xa1\xa9\xb3K;s{\x93(', pos=53),
         '123'),
        (xtcedef.StringParameterType(
            "TEST_STRING",
            xtcedef.StringDataEncoding(encoding="utf-8",
                                       termination_character='00')),
         {},
         xtcedef.PacketData("false_is_truthy".encode("utf-8") + b'\x00ABCD'),
         'false_is_truthy'),
        (xtcedef.StringParameterType(
            "TEST_STRING",
            xtcedef.StringDataEncoding(encoding="utf-16-be",
                                       termination_character='0021')),
         {},
         xtcedef.PacketData("false_is_truthy".encode("utf-16-be") + b'\x00\x21ignoreme'),
         'false_is_truthy'),
        (xtcedef.StringParameterType(
            'TEST_STRING',
            xtcedef.StringDataEncoding(encoding='utf-16-le',
                                       termination_character='5800')),
         {},  # Don't need parsed_data for termination character
         # 123X456, termination character is X
         xtcedef.PacketData('123X456'.encode('utf-16-le')),
         '123'),
        (xtcedef.StringParameterType(
            'TEST_STRING',
            xtcedef.StringDataEncoding(encoding='utf-16-be',
                                       termination_character='0058')),
         {},  # Don't need parsed_data for termination character
         xtcedef.PacketData('123X456'.encode('utf-16-be')),
         '123'),
        # Leading length test
        (xtcedef.StringParameterType(
            'TEST_STRING',
            xtcedef.StringDataEncoding(leading_length_size=5)),
         {},  # Don't need parsed_data for leading length parsing
         # This is still 123X456 but with 11000 prepended (a 5-bit representation of the number 24)
         # This represents a string length (in bits) of 24 bits.
         xtcedef.PacketData(0b1100000110001001100100011001101011000001101000011010100110110000.to_bytes(8, byteorder="big")),
         '123'),
    ]
)
def test_string_parameter_parsing(parameter_type, parsed_data, packet_data, expected):
    """Test parsing a string parameter"""
    raw, _ = parameter_type.parse_value(packet_data, parsed_data)
    assert raw == expected


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        ("""
<xtce:IntegerParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_INT_Type">
    <xtce:UnitSet>
        <xtce:Unit>smoot</xtce:Unit>
    </xtce:UnitSet>
    <xtce:IntegerDataEncoding sizeInBits="16" encoding="unsigned"/>
</xtce:IntegerParameterType>
""",
         xtcedef.IntegerParameterType(name='TEST_INT_Type', unit='smoot',
                                      encoding=xtcedef.IntegerDataEncoding(size_in_bits=16, encoding='unsigned'))),
        ("""
<xtce:IntegerParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_INT_Type">
    <xtce:UnitSet>
        <xtce:Unit>smoot</xtce:Unit>
    </xtce:UnitSet>
    <xtce:IntegerDataEncoding sizeInBits="16" encoding="unsigned">
        <xtce:DefaultCalibrator>
            <xtce:PolynomialCalibrator>
                <xtce:Term exponent="0" coefficient="2772.24"/>
                <xtce:Term exponent="1" coefficient="-41.6338"/>
                <xtce:Term exponent="2" coefficient="-0.185486"/>
            </xtce:PolynomialCalibrator>
        </xtce:DefaultCalibrator>
    </xtce:IntegerDataEncoding>
</xtce:IntegerParameterType>
""",
         xtcedef.IntegerParameterType(name='TEST_INT_Type', unit='smoot',
                                      encoding=xtcedef.IntegerDataEncoding(
                                       size_in_bits=16, encoding='unsigned',
                                       default_calibrator=xtcedef.PolynomialCalibrator([
                                           xtcedef.PolynomialCoefficient(2772.24, 0),
                                           xtcedef.PolynomialCoefficient(-41.6338, 1),
                                           xtcedef.PolynomialCoefficient(-0.185486, 2)
                                       ])
                                   ))),
        ("""
<xtce:IntegerParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_INT_Type">
    <xtce:UnitSet>
        <xtce:Unit>smoot</xtce:Unit>
    </xtce:UnitSet>
    <xtce:IntegerDataEncoding sizeInBits="16" encoding="unsigned">
        <xtce:DefaultCalibrator>
            <xtce:SplineCalibrator order="zero">
                <xtce:SplinePoint raw="1" calibrated="10"/>
                <xtce:SplinePoint raw="2" calibrated="100"/>
                <xtce:SplinePoint raw="3" calibrated="500"/>
            </xtce:SplineCalibrator>
        </xtce:DefaultCalibrator>
    </xtce:IntegerDataEncoding>
</xtce:IntegerParameterType>
""",
         xtcedef.IntegerParameterType(name='TEST_INT_Type', unit='smoot',
                                      encoding=xtcedef.IntegerDataEncoding(
                                       size_in_bits=16, encoding='unsigned',
                                       default_calibrator=xtcedef.SplineCalibrator(
                                           order=0, extrapolate=False,
                                           points=[
                                               xtcedef.SplinePoint(raw=1, calibrated=10),
                                               xtcedef.SplinePoint(raw=2, calibrated=100),
                                               xtcedef.SplinePoint(raw=3, calibrated=500),
                                           ]
                                       )))),
    ]
)
def test_integer_parameter_type(xml_string: str, expectation):
    """Test parsing an IntegerParameterType from an XML string"""
    element = ElementTree.fromstring(xml_string)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            xtcedef.IntegerParameterType.from_parameter_type_xml_element(element, TEST_NAMESPACE)
    else:
        result = xtcedef.IntegerParameterType.from_parameter_type_xml_element(element, TEST_NAMESPACE)
        assert result == expectation


@pytest.mark.parametrize(
    ('parameter_type', 'parsed_data', 'packet_data', 'expected'),
    [
        # 16-bit unsigned starting at byte boundary
        (xtcedef.IntegerParameterType('TEST_INT', xtcedef.IntegerDataEncoding(16, 'unsigned')),
         {},
         xtcedef.PacketData(0b1000000000000000.to_bytes(length=2, byteorder='big')),
         32768),
        # 16-bit signed starting at byte boundary
        (xtcedef.IntegerParameterType('TEST_INT', xtcedef.IntegerDataEncoding(16, 'signed')),
         {},
         xtcedef.PacketData(0b1111111111010110.to_bytes(length=2, byteorder='big')),
         -42),
        # 16-bit signed integer starting at a byte boundary,
        # calibrated by a polynomial y = (x*2 + 5); x = -42; y = -84 + 5 = -79
        (xtcedef.IntegerParameterType(
            'TEST_INT',
            xtcedef.IntegerDataEncoding(
                16, 'signed',
                context_calibrators=[
                    xtcedef.ContextCalibrator([
                        xtcedef.Condition(left_param='PKT_APID', operator='==',
                                          right_value=1101, left_use_calibrated_value=False,
                                          right_use_calibrated_value=False)],
                        xtcedef.PolynomialCalibrator([xtcedef.PolynomialCoefficient(5, 0),
                                                      xtcedef.PolynomialCoefficient(2, 1)]))
                ])),
         {'PKT_APID': parser.ParsedDataItem('PKT_APID', 1101)},
         xtcedef.PacketData(0b1111111111010110.to_bytes(length=2, byteorder='big')),
         -79),
        # 12-bit unsigned integer starting at bit 4 of the first byte
        (xtcedef.IntegerParameterType('TEST_INT', xtcedef.IntegerDataEncoding(12, 'unsigned')),
         {},
         # 11111000 00000000
         #     |--uint:12--|
         xtcedef.PacketData(0b1111100000000000.to_bytes(length=2, byteorder='big'), pos=4),
         2048),
        # 13-bit unsigned integer starting on bit 2 of the second byte
        (xtcedef.IntegerParameterType('TEST_INT', xtcedef.IntegerDataEncoding(13, 'unsigned')),
         {},
         # 10101010 11100000 00000001
         #            |--uint:13---|
         xtcedef.PacketData(0b101010101110000000000001.to_bytes(length=3, byteorder='big'), pos=10),
         4096),
        # 16-bit unsigned integer starting on bit 2 of the first byte
        (xtcedef.IntegerParameterType('TEST_INT', xtcedef.IntegerDataEncoding(16, 'unsigned')),
         {},
         # 10101010 11100000 00000001
         #   |----uint:16-----|
         xtcedef.PacketData(0b101010101110000000000001.to_bytes(length=3, byteorder='big'), pos=2),
         43904),
        # 12-bit signed integer starting on bit 4 of the first byte
        (xtcedef.IntegerParameterType('TEST_INT', xtcedef.IntegerDataEncoding(12, 'signed')),
         {},
         # 11111000 00000000
         #     |---int:12--|
         xtcedef.PacketData(0b1111100000000000.to_bytes(length=2, byteorder='big'), pos=4),
         -2048),
        # 12-bit signed integer starting on bit 6 of the first byte
        (xtcedef.IntegerParameterType('TEST_INT', xtcedef.IntegerDataEncoding(12, 'signed')),
         {},
         # 12-bit signed integer starting on bit 4 of the first byte
         #  11111110 00000000 00111111 10101010
         #        |---int:12---|
         xtcedef.PacketData(0b11111110000000000011111110101010.to_bytes(length=4, byteorder='big'), pos=6),
         -2048),
        (xtcedef.IntegerParameterType('TEST_INT', xtcedef.IntegerDataEncoding(3, 'twosComplement')),
         {},
         # 3-bit signed integer starting at bit 7 of the first byte
         #  00000001      11000000       00000000
         #         |-int:3-|
         xtcedef.PacketData(0b000000011100000000000000.to_bytes(length=3, byteorder='big'), pos=7),
         -1),
    ]
)
def test_integer_parameter_parsing(parameter_type, parsed_data, packet_data, expected):
    """Testing parsing an integer parameters"""
    raw, derived = parameter_type.parse_value(packet_data, parsed_data)
    if derived:
        assert derived == expected
    else:
        assert raw == expected


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        ("""
<xtce:FloatParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_INT_Type">
    <xtce:UnitSet>
        <xtce:Unit>smoot</xtce:Unit>
    </xtce:UnitSet>
    <xtce:FloatDataEncoding sizeInBits="16"/>
</xtce:FloatParameterType>
""",
         xtcedef.FloatParameterType(name='TEST_INT_Type', unit='smoot',
                                    encoding=xtcedef.FloatDataEncoding(size_in_bits=16, encoding='IEEE-754'))),
        ("""
<xtce:FloatParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_INT_Type">
    <xtce:UnitSet>
        <xtce:Unit>smoot</xtce:Unit>
    </xtce:UnitSet>
    <xtce:IntegerDataEncoding sizeInBits="16" encoding="unsigned"/>
</xtce:FloatParameterType>
""",
         xtcedef.FloatParameterType(name='TEST_INT_Type', unit='smoot',
                                    encoding=xtcedef.IntegerDataEncoding(size_in_bits=16, encoding='unsigned'))),
        ("""
<xtce:FloatParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_INT_Type">
    <xtce:UnitSet>
        <xtce:Unit>smoot</xtce:Unit>
    </xtce:UnitSet>
    <xtce:IntegerDataEncoding sizeInBits="16" encoding="unsigned">
        <xtce:DefaultCalibrator>
            <xtce:PolynomialCalibrator>
                <xtce:Term exponent="0" coefficient="2772.24"/>
                <xtce:Term exponent="1" coefficient="-41.6338"/>
                <xtce:Term exponent="2" coefficient="-0.185486"/>
            </xtce:PolynomialCalibrator>
        </xtce:DefaultCalibrator>
    </xtce:IntegerDataEncoding>
</xtce:FloatParameterType>
""",
         xtcedef.FloatParameterType(name='TEST_INT_Type', unit='smoot',
                                    encoding=xtcedef.IntegerDataEncoding(
                                     size_in_bits=16, encoding='unsigned',
                                     default_calibrator=xtcedef.PolynomialCalibrator([
                                         xtcedef.PolynomialCoefficient(2772.24, 0),
                                         xtcedef.PolynomialCoefficient(-41.6338, 1),
                                         xtcedef.PolynomialCoefficient(-0.185486, 2)
                                     ])
                                    ))),
        ("""
<xtce:FloatParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_INT_Type">
    <xtce:UnitSet>
        <xtce:Unit>smoot</xtce:Unit>
    </xtce:UnitSet>
    <xtce:IntegerDataEncoding sizeInBits="16" encoding="unsigned">
        <xtce:DefaultCalibrator>
            <xtce:SplineCalibrator>
                <xtce:SplinePoint raw="1" calibrated="10"/>
                <xtce:SplinePoint raw="2" calibrated="100"/>
                <xtce:SplinePoint raw="3" calibrated="500"/>
            </xtce:SplineCalibrator>
        </xtce:DefaultCalibrator>
    </xtce:IntegerDataEncoding>
</xtce:FloatParameterType>
""",
         xtcedef.FloatParameterType(name='TEST_INT_Type', unit='smoot',
                                    encoding=xtcedef.IntegerDataEncoding(
                                     size_in_bits=16, encoding='unsigned',
                                     default_calibrator=xtcedef.SplineCalibrator(
                                         order=0, extrapolate=False,
                                         points=[
                                             xtcedef.SplinePoint(raw=1, calibrated=10.),
                                             xtcedef.SplinePoint(raw=2, calibrated=100.),
                                             xtcedef.SplinePoint(raw=3, calibrated=500.),
                                         ]
                                     )))),
    ]
)
def test_float_parameter_type(xml_string: str, expectation):
    """Test parsing an FloatParameterType from an XML string"""
    element = ElementTree.fromstring(xml_string)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            xtcedef.FloatParameterType.from_parameter_type_xml_element(element, TEST_NAMESPACE)
    else:
        result = xtcedef.FloatParameterType.from_parameter_type_xml_element(element, TEST_NAMESPACE)
        assert result == expectation


@pytest.mark.parametrize(
    ('parameter_type', 'parsed_data', 'packet_data', 'expected'),
    [
        (xtcedef.FloatParameterType('TEST_FLOAT', xtcedef.FloatDataEncoding(32)),
         {},
         xtcedef.PacketData(0b01000000010010010000111111010000.to_bytes(length=4, byteorder='big')),
         3.14159),
        (xtcedef.FloatParameterType('TEST_FLOAT', xtcedef.FloatDataEncoding(64)),
         {},
         xtcedef.PacketData(b'\x3F\xF9\xE3\x77\x9B\x97\xF4\xA8'),  # 64-bit IEEE 754 value of Phi
         1.61803),
        (xtcedef.FloatParameterType(
            'TEST_FLOAT',
            xtcedef.IntegerDataEncoding(
                16, 'signed',
                context_calibrators=[
                    xtcedef.ContextCalibrator([
                        xtcedef.Condition(left_param='PKT_APID', operator='==',
                                          right_value=1101, left_use_calibrated_value=False,
                                          right_use_calibrated_value=False)],
                        xtcedef.PolynomialCalibrator([xtcedef.PolynomialCoefficient(5.6, 0),
                                                      xtcedef.PolynomialCoefficient(2.1, 1)]))
                ])),
         {'PKT_APID': parser.ParsedDataItem('PKT_APID', 1101)},
         xtcedef.PacketData(0b1111111111010110.to_bytes(length=2, byteorder='big')),
         -82.600000),
    ]
)
def test_float_parameter_parsing(parameter_type, parsed_data, packet_data, expected):
    """Test parsing float parameters"""
    raw, derived = parameter_type.parse_value(packet_data, parsed_data)
    if derived:
        # NOTE: These results are rounded due to the imprecise storage of floats
        assert round(derived, 5) == expected
    else:
        assert round(raw, 5) == expected


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        ("""
<xtce:EnumeratedParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_ENUM_Type">
    <xtce:UnitSet/>
    <xtce:IntegerDataEncoding sizeInBits="2" encoding="unsigned"/>
    <xtce:EnumerationList>
        <xtce:Enumeration label="BOOT_POR" value="0"/>
        <xtce:Enumeration label="BOOT_RETURN" value="1"/>
        <xtce:Enumeration label="OP_LOW" value="2"/>
        <xtce:Enumeration label="OP_HIGH" value="3"/>
        <xtce:Enumeration label="OP_HIGH" value="4"/>
    </xtce:EnumerationList>
</xtce:EnumeratedParameterType>
""",
         xtcedef.EnumeratedParameterType(name='TEST_ENUM_Type',
                                         encoding=xtcedef.IntegerDataEncoding(size_in_bits=2, encoding='unsigned'),
                                         # NOTE: Duplicate final value is on purpose to make sure we handle that case
                                         enumeration={0: 'BOOT_POR', 1: 'BOOT_RETURN', 2: 'OP_LOW', 3: 'OP_HIGH', 4: 'OP_HIGH'})),
    ]
)
def test_enumerated_parameter_type(xml_string: str, expectation):
    """Test parsing an EnumeratedParameterType from an XML string"""
    element = ElementTree.fromstring(xml_string)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            xtcedef.EnumeratedParameterType.from_parameter_type_xml_element(element, TEST_NAMESPACE)
    else:
        result = xtcedef.EnumeratedParameterType.from_parameter_type_xml_element(element, TEST_NAMESPACE)
        assert result == expectation


@pytest.mark.parametrize(
    ('parameter_type', 'parsed_data', 'packet_data', 'expected'),
    [
        (xtcedef.EnumeratedParameterType(
            'TEST_ENUM',
            xtcedef.IntegerDataEncoding(16, 'unsigned'), {32768: 'NOMINAL'}),
         {},
         xtcedef.PacketData(0b1000000000000000.to_bytes(length=2, byteorder='big')),
         'NOMINAL'),
        (xtcedef.EnumeratedParameterType(
            'TEST_FLOAT',
            xtcedef.IntegerDataEncoding(16, 'signed'),  {-42: 'VAL_LOW'}),
         {},
         xtcedef.PacketData(0b1111111111010110.to_bytes(length=2, byteorder='big')),
         'VAL_LOW'),
    ]
)
def test_enumerated_parameter_parsing(parameter_type, parsed_data, packet_data, expected):
    """"Test parsing enumerated parameters"""
    raw, derived = parameter_type.parse_value(packet_data, parsed_data)
    if derived:
        # NOTE: These results are rounded due to the imprecise storage of floats
        assert derived == expected
    else:
        assert raw == expected


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        ("""
<xtce:BinaryParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_PARAM_Type">
    <xtce:UnitSet>
        <xtce:Unit>smoot</xtce:Unit>
    </xtce:UnitSet>
    <xtce:BinaryDataEncoding>
        <xtce:SizeInBits>
            <xtce:FixedValue>256</xtce:FixedValue>
        </xtce:SizeInBits>
    </xtce:BinaryDataEncoding>
</xtce:BinaryParameterType>
""",
         xtcedef.BinaryParameterType(name='TEST_PARAM_Type', unit='smoot',
                                     encoding=xtcedef.BinaryDataEncoding(fixed_size_in_bits=256))),
        ("""
<xtce:BinaryParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_PARAM_Type">
    <xtce:UnitSet/>
    <xtce:BinaryDataEncoding>
        <xtce:SizeInBits>
            <xtce:FixedValue>128</xtce:FixedValue>
        </xtce:SizeInBits>
    </xtce:BinaryDataEncoding>
</xtce:BinaryParameterType>
""",
         xtcedef.BinaryParameterType(name='TEST_PARAM_Type', unit=None,
                                     encoding=xtcedef.BinaryDataEncoding(fixed_size_in_bits=128))),
        ("""
<xtce:BinaryParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_PARAM_Type">
    <xtce:UnitSet/>
    <xtce:BinaryDataEncoding>
        <xtce:SizeInBits>
            <xtce:DynamicValue>
                <xtce:ParameterInstanceRef useCalibratedValue="false" parameterRef="SizeFromThisParameter"/>
                <xtce:LinearAdjustment intercept="25" slope="8"/>
            </xtce:DynamicValue>
        </xtce:SizeInBits>
    </xtce:BinaryDataEncoding>
</xtce:BinaryParameterType>
""",
         xtcedef.BinaryParameterType(name='TEST_PARAM_Type',
                                     encoding=xtcedef.BinaryDataEncoding(
                                         size_reference_parameter='SizeFromThisParameter',
                                         use_calibrated_value=False,
                                         linear_adjuster=lambda x: x))),
        ("""
<xtce:BinaryParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_PARAM_Type">
    <xtce:UnitSet/>
    <xtce:BinaryDataEncoding>
        <xtce:SizeInBits>
            <xtce:DynamicValue>
                <xtce:ParameterInstanceRef parameterRef="SizeFromThisParameter"/>
            </xtce:DynamicValue>
        </xtce:SizeInBits>
    </xtce:BinaryDataEncoding>
</xtce:BinaryParameterType>
""",
         xtcedef.BinaryParameterType(name='TEST_PARAM_Type', unit=None,
                                     encoding=xtcedef.BinaryDataEncoding(
                                         size_reference_parameter='SizeFromThisParameter'))),
    ]
)
def test_binary_parameter_type(xml_string: str, expectation):
    """Test parsing an BinaryParameterType from an XML string"""
    element = ElementTree.fromstring(xml_string)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            xtcedef.BinaryParameterType.from_parameter_type_xml_element(element, TEST_NAMESPACE)
    else:
        result = xtcedef.BinaryParameterType.from_parameter_type_xml_element(element, TEST_NAMESPACE)
        assert result == expectation


@pytest.mark.parametrize(
    ('parameter_type', 'parsed_data', 'packet_data', 'expected'),
    [
        # fixed size
        (xtcedef.BinaryParameterType(
            'TEST_BIN',
            xtcedef.BinaryDataEncoding(fixed_size_in_bits=16)),
         {},
         xtcedef.PacketData(0b0011010000110010010100110000000001001011000000000100100100000000.to_bytes(length=8, byteorder='big')),
         '0011010000110010'),
        # discrete lookup list size
        (xtcedef.BinaryParameterType(
            'TEST_BIN',
            xtcedef.BinaryDataEncoding(size_discrete_lookup_list=[
                xtcedef.DiscreteLookup([
                    xtcedef.Comparison(required_value=7.4, referenced_parameter='P1',
                                       operator='==', use_calibrated_value=True)
                ], lookup_value=2)
            ], linear_adjuster=lambda x: 8*x)),
         {'P1': parser.ParsedDataItem('P1', 1, None, 7.4)},
         xtcedef.PacketData(0b0011010000110010010100110000000001001011000000000100100100000000.to_bytes(length=8, byteorder='big')),
         '0011010000110010'),
        # dynamic size reference to other parameter
        (xtcedef.BinaryParameterType(
            'TEST_BIN',
            xtcedef.BinaryDataEncoding(size_reference_parameter='BIN_LEN',
                                       use_calibrated_value=False, linear_adjuster=lambda x: 8*x)),
         {'BIN_LEN': parser.ParsedDataItem('BIN_LEN', 2, None)},
         xtcedef.PacketData(0b0011010000110010010100110000000001001011000000000100100100000000.to_bytes(length=8, byteorder='big')),
         '0011010000110010'),
    ]
)
def test_binary_parameter_parsing(parameter_type, parsed_data, packet_data, expected):
    """Test parsing binary parameters"""
    raw, _ = parameter_type.parse_value(packet_data, parsed_data)
    assert raw == expected


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        ("""
<xtce:BooleanParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_PARAM_Type">
    <xtce:UnitSet>
        <xtce:Unit>smoot</xtce:Unit>
    </xtce:UnitSet>
    <xtce:BinaryDataEncoding>
        <xtce:SizeInBits>
            <xtce:FixedValue>1</xtce:FixedValue>
        </xtce:SizeInBits>
    </xtce:BinaryDataEncoding>
</xtce:BooleanParameterType>
""",
         xtcedef.BooleanParameterType(name='TEST_PARAM_Type', unit='smoot',
                                      encoding=xtcedef.BinaryDataEncoding(fixed_size_in_bits=1))),
        ("""
<xtce:BooleanParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_PARAM_Type">
    <xtce:UnitSet>
        <xtce:Unit>smoot</xtce:Unit>
    </xtce:UnitSet>
    <xtce:IntegerDataEncoding encoding="unsigned" sizeInBits="1"/>
</xtce:BooleanParameterType>
""",
         xtcedef.BooleanParameterType(name='TEST_PARAM_Type', unit='smoot',
                                      encoding=xtcedef.IntegerDataEncoding(size_in_bits=1, encoding="unsigned"))),
        ("""
<xtce:BooleanParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_PARAM_Type">
    <xtce:UnitSet>
        <xtce:Unit>smoot</xtce:Unit>
    </xtce:UnitSet>
    <xtce:StringDataEncoding encoding="utf-8">
        <xtce:SizeInBits>
            <xtce:TerminationChar>00</xtce:TerminationChar>
        </xtce:SizeInBits>
    </xtce:StringDataEncoding>
</xtce:BooleanParameterType>
""",
         xtcedef.BooleanParameterType(name='TEST_PARAM_Type', unit='smoot',
                                      encoding=xtcedef.StringDataEncoding(termination_character='00'))),
    ]
)
def test_boolean_parameter_type(xml_string, expectation):
    """Test parsing a BooleanParameterType from an XML string"""
    element = ElementTree.fromstring(xml_string)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            xtcedef.BooleanParameterType.from_parameter_type_xml_element(element, TEST_NAMESPACE)
    else:
        result = xtcedef.BooleanParameterType.from_parameter_type_xml_element(element, TEST_NAMESPACE)
        assert result == expectation


@pytest.mark.parametrize(
    ('parameter_type', 'parsed_data', 'packet_data', 'expected_raw', 'expected_derived'),
    [
        (xtcedef.BooleanParameterType(
            'TEST_BOOL',
            xtcedef.BinaryDataEncoding(fixed_size_in_bits=1)),
         {},
         xtcedef.PacketData(0b0011010000110010010100110000000001001011000000000100100100000000.to_bytes(length=64, byteorder='big')),
         '0', True),
        (xtcedef.BooleanParameterType(
            'TEST_BOOL',
            xtcedef.StringDataEncoding(encoding="utf-8", termination_character='00')),
         {},
         xtcedef.PacketData(0b011001100110000101101100011100110110010101011111011010010111001101011111011101000111001001110101011101000110100001111001000000000010101101010111.to_bytes(length=18, byteorder='big')),
         'false_is_truthy', True),
        (xtcedef.BooleanParameterType(
            'TEST_BOOL',
            xtcedef.IntegerDataEncoding(size_in_bits=2, encoding="unsigned")),
         {},
         xtcedef.PacketData(0b0011.to_bytes(length=1, byteorder='big')),
         0, False),
        (xtcedef.BooleanParameterType(
            'TEST_BOOL',
            xtcedef.IntegerDataEncoding(size_in_bits=2, encoding="unsigned")),
         {},
         xtcedef.PacketData(0b00001111.to_bytes(length=1, byteorder='big'), pos=4),
         3, True),
        (xtcedef.BooleanParameterType(
            'TEST_BOOL',
            xtcedef.FloatDataEncoding(size_in_bits=16)),
         {},
         xtcedef.PacketData(0b01010001010000001111111110000000.to_bytes(length=4, byteorder='big')),
         42.0, True),
        (xtcedef.BooleanParameterType(
            'TEST_BOOL',
            xtcedef.FloatDataEncoding(size_in_bits=16)),
         {},
         xtcedef.PacketData(0b00000000101000101000000111111111.to_bytes(length=4, byteorder='big'), pos=7),
         42.0, True),
    ]
)
def test_boolean_parameter_parsing(parameter_type, parsed_data, packet_data, expected_raw, expected_derived):
    """Test parsing boolean parameters"""
    raw, derived = parameter_type.parse_value(packet_data, parsed_data)
    assert raw == expected_raw
    assert derived == expected_derived


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        ("""
<xtce:AbsoluteTimeParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_PARAM_Type">
    <xtce:Encoding units="seconds">
        <xtce:IntegerDataEncoding sizeInBits="32"/>
    </xtce:Encoding>
    <xtce:ReferenceTime>
        <xtce:OffsetFrom parameterRef="MilliSeconds"/>
        <xtce:Epoch>TAI</xtce:Epoch>
    </xtce:ReferenceTime>
</xtce:AbsoluteTimeParameterType>
""",
         xtcedef.AbsoluteTimeParameterType(name='TEST_PARAM_Type', unit='seconds',
                                           encoding=xtcedef.IntegerDataEncoding(size_in_bits=32, encoding="unsigned"),
                                           epoch="TAI", offset_from="MilliSeconds")),
        ("""
<xtce:AbsoluteTimeParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_PARAM_Type">
    <xtce:Encoding scale="1E-6" offset="0" units="s">
        <xtce:IntegerDataEncoding sizeInBits="32"/>
    </xtce:Encoding>
    <xtce:ReferenceTime>
        <xtce:OffsetFrom parameterRef="MilliSeconds"/>
        <xtce:Epoch>2009-10-10T12:00:00-05:00</xtce:Epoch>
    </xtce:ReferenceTime>
</xtce:AbsoluteTimeParameterType>
""",
         xtcedef.AbsoluteTimeParameterType(
             name='TEST_PARAM_Type', unit='s',
             encoding=xtcedef.IntegerDataEncoding(
                 size_in_bits=32, encoding="unsigned",
                 default_calibrator=xtcedef.PolynomialCalibrator(
                     coefficients=[
                         xtcedef.PolynomialCoefficient(0, 0),
                         xtcedef.PolynomialCoefficient(1E-6, 1)
                     ])),
             epoch="2009-10-10T12:00:00-05:00", offset_from="MilliSeconds")),
        ("""
<xtce:AbsoluteTimeParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_PARAM_Type">
    <xtce:Encoding scale="1.31E-6" units="s">
        <xtce:IntegerDataEncoding sizeInBits="32"/>
    </xtce:Encoding>
</xtce:AbsoluteTimeParameterType>
""",
         xtcedef.AbsoluteTimeParameterType(
             name='TEST_PARAM_Type', unit='s',
             encoding=xtcedef.IntegerDataEncoding(
                 size_in_bits=32, encoding="unsigned",
                 default_calibrator=xtcedef.PolynomialCalibrator(
                     coefficients=[
                         xtcedef.PolynomialCoefficient(1.31E-6, 1)
                     ]))
         )),
        ("""
<xtce:AbsoluteTimeParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_PARAM_Type">
    <xtce:Encoding offset="147.884" units="s">
        <xtce:IntegerDataEncoding sizeInBits="32"/>
    </xtce:Encoding>
</xtce:AbsoluteTimeParameterType>
""",
         xtcedef.AbsoluteTimeParameterType(
             name='TEST_PARAM_Type', unit='s',
             encoding=xtcedef.IntegerDataEncoding(
                 size_in_bits=32, encoding="unsigned",
                 default_calibrator=xtcedef.PolynomialCalibrator(
                     coefficients=[
                         xtcedef.PolynomialCoefficient(147.884, 0),
                         xtcedef.PolynomialCoefficient(1, 1)
                     ]))
         )),
        ("""
<xtce:AbsoluteTimeParameterType xmlns:xtce="http://www.omg.org/space/xtce" name="TEST_PARAM_Type">
    <xtce:Encoding offset="147.884" units="s">
        <xtce:FloatDataEncoding sizeInBits="32"/>
    </xtce:Encoding>
</xtce:AbsoluteTimeParameterType>
""",
         xtcedef.AbsoluteTimeParameterType(
             name='TEST_PARAM_Type', unit='s',
             encoding=xtcedef.FloatDataEncoding(
                 size_in_bits=32, encoding="IEEE-754",
                 default_calibrator=xtcedef.PolynomialCalibrator(
                     coefficients=[
                         xtcedef.PolynomialCoefficient(147.884, 0),
                         xtcedef.PolynomialCoefficient(1, 1)
                     ]))
         )),
    ]
)
def test_absolute_time_parameter_type(xml_string, expectation):
    """Test parsing an AbsoluteTimeParameterType from an XML string."""
    element = ElementTree.fromstring(xml_string)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            xtcedef.AbsoluteTimeParameterType.from_parameter_type_xml_element(element, TEST_NAMESPACE)
    else:
        result = xtcedef.AbsoluteTimeParameterType.from_parameter_type_xml_element(element, TEST_NAMESPACE)
        assert result == expectation


@pytest.mark.parametrize(
    ('parameter_type', 'parsed_data', 'packet_data', 'expected_raw', 'expected_derived'),
    [
        (xtcedef.AbsoluteTimeParameterType(name='TEST_PARAM_Type', unit='seconds',
                                           encoding=xtcedef.IntegerDataEncoding(size_in_bits=32, encoding="unsigned"),
                                           epoch="TAI", offset_from="MilliSeconds"),
         {},
         # Exactly 64 bits so neatly goes into a bytes object without padding
         xtcedef.PacketData(0b0011010000110010010100110000000001001011000000000100100100000000.to_bytes(length=8, byteorder='big')),
         875713280, 875713280),
        (xtcedef.AbsoluteTimeParameterType(
             name='TEST_PARAM_Type', unit='s',
             encoding=xtcedef.IntegerDataEncoding(
                 size_in_bits=32, encoding="unsigned",
                 default_calibrator=xtcedef.PolynomialCalibrator(
                     coefficients=[
                         xtcedef.PolynomialCoefficient(0, 0),
                         xtcedef.PolynomialCoefficient(1E-6, 1)
                     ])),
             epoch="2009-10-10T12:00:00-05:00", offset_from="MilliSeconds"),
         {},
         # Exactly 64 bits so neatly goes into a bytes object without padding
         xtcedef.PacketData(0b0011010000110010010100110000000001001011000000000100100100000000.to_bytes(length=8, byteorder='big')),
         875713280, 875.7132799999999),
        (xtcedef.AbsoluteTimeParameterType(
             name='TEST_PARAM_Type', unit='s',
             encoding=xtcedef.FloatDataEncoding(
                 size_in_bits=32, encoding="IEEE-754",
                 default_calibrator=xtcedef.PolynomialCalibrator(
                     coefficients=[
                         xtcedef.PolynomialCoefficient(147.884, 0),
                         xtcedef.PolynomialCoefficient(1, 1)
                     ]))),
         {},
         # 65 bits, so we need a 9th byte with 7 bits of padding to hold it,
         # which means we need to be starting at pos=7
         xtcedef.PacketData(0b01000000010010010000111111011011001001011000000000100100100000000.to_bytes(length=9, byteorder='big'), pos=7),
         3.1415927, 151.02559269999998),
    ]
)
def test_absolute_time_parameter_parsing(parameter_type, parsed_data, packet_data, expected_raw, expected_derived):
    raw, derived = parameter_type.parse_value(packet_data, parsed_data)
    assert round(raw, 5) == round(expected_raw, 5)
    # NOTE: derived values are rounded for comparison due to imprecise storage of floats
    assert round(derived, 5) == round(expected_derived, 5)


# ---------------
# Parameter Tests
# ---------------
def test_parameter():
    """Test Parameter"""
    xtcedef.Parameter(name='TEST_INT',
                      parameter_type=xtcedef.IntegerParameterType(
                       name='TEST_INT_Type',
                       unit='floops',
                       encoding=xtcedef.IntegerDataEncoding(size_in_bits=16, encoding='unsigned')),
                      short_description="Param short desc",
                      long_description="This is a long description of the parameter")


# -----------------------
# Full XTCE Document Test
# -----------------------
def test_parsing_xtce_document(test_data_dir):
    """Tests parsing an entire XTCE document and makes assertions about the contents"""
    with open(test_data_dir / "test_xtce.xml") as x:
        xdef = xtcedef.XtcePacketDefinition(x, ns=TEST_NAMESPACE)

    # Test Parameter Types
    ptname = "USEC_Type"
    pt = xdef.named_parameter_types[ptname]
    assert pt.name == ptname
    assert pt.unit == "us"
    assert isinstance(pt.encoding, xtcedef.IntegerDataEncoding)

    # Test Parameters
    pname = "ADAET1DAY"  # Named parameter
    p = xdef.named_parameters[pname]
    assert p.name == pname
    assert p.short_description == "Ephemeris Valid Time, Days Since 1/1/1958"
    assert p.long_description is None

    pname = "USEC"
    p = xdef.named_parameters[pname]
    assert p.name == pname
    assert p.short_description == "Secondary Header Fine Time (microsecond)"
    assert p.long_description == "CCSDS Packet 2nd Header Fine Time in microseconds."

    # Test Sequence Containers
    scname = "SecondaryHeaderContainer"
    sc = xdef.named_containers[scname]
    assert sc.name == scname
    assert sc == xtcedef.SequenceContainer(
        name=scname,
        entry_list=[
            xtcedef.Parameter(
                name="DOY",
                parameter_type=xtcedef.FloatParameterType(
                    name="DOY_Type",
                    encoding=xtcedef.IntegerDataEncoding(
                        size_in_bits=16, encoding="unsigned"
                    ),
                    unit="day"
                ),
                short_description="Secondary Header Day of Year",
                long_description="CCSDS Packet 2nd Header Day of Year in days."
            ),
            xtcedef.Parameter(
                name="MSEC",
                parameter_type=xtcedef.FloatParameterType(
                    name="MSEC_Type",
                    encoding=xtcedef.IntegerDataEncoding(
                        size_in_bits=32, encoding="unsigned"
                    ),
                    unit="ms"
                ),
                short_description="Secondary Header Coarse Time (millisecond)",
                long_description="CCSDS Packet 2nd Header Coarse Time in milliseconds."
            ),
            xtcedef.Parameter(
                name="USEC",
                parameter_type=xtcedef.FloatParameterType(
                    name="USEC_Type",
                    encoding=xtcedef.IntegerDataEncoding(
                        size_in_bits=16, encoding="unsigned"
                    ),
                    unit="us"
                ),
                short_description="Secondary Header Fine Time (microsecond)",
                long_description="CCSDS Packet 2nd Header Fine Time in microseconds."
            )
        ],
        short_description=None,
        long_description="Container for telemetry secondary header items",
        base_container_name=None,
        restriction_criteria=None,
        abstract=True,
        inheritors=None
    )


@pytest.mark.parametrize("start, nbits", [(0, 1), (0, 16), (0, 8), (0, 9),
                                        (3, 5), (3, 8), (3, 13),
                                        (7, 1), (7, 2), (7, 8),
                                        (8, 1), (8, 8), (15, 1)])
def test__extract_bits(start, nbits):
    """Test the _extract_bits function with various start and nbits values"""
    # Test extracting bits from a bitstream
    s = '0000111100001111'
    data = int(s, 2).to_bytes(2, byteorder="big")

    assert xtcedef._extract_bits(data, start, nbits) == int(s[start:start+nbits], 2)