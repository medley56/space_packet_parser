"""DataEncoding Tests"""
import pytest
import lxml.etree as ElementTree

from space_packet_parser import encodings, comparisons, calibrators
from space_packet_parser.xtce import XTCE_NSMAP


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        ("""
<xtce:StringDataEncoding encoding="UTF-16BE" xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:SizeInBits>
        <xtce:Fixed>
            <xtce:FixedValue>32</xtce:FixedValue>
        </xtce:Fixed>
        <xtce:TerminationChar>0058</xtce:TerminationChar>
    </xtce:SizeInBits>
</xtce:StringDataEncoding>
""",
         encodings.StringDataEncoding(fixed_raw_length=32, termination_character='0058', encoding='UTF-16BE')),
        ("""
<xtce:StringDataEncoding xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:SizeInBits>
        <xtce:Fixed>
            <xtce:FixedValue>17</xtce:FixedValue>
        </xtce:Fixed>
        <xtce:LeadingSize sizeInBitsOfSizeTag="3"/>
    </xtce:SizeInBits>
</xtce:StringDataEncoding>
""",
         encodings.StringDataEncoding(fixed_raw_length=17, leading_length_size=3)),
        ("""
<xtce:StringDataEncoding xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:Variable maxSizeInBits="32">
        <xtce:DynamicValue>
            <xtce:ParameterInstanceRef parameterRef="SizeFromThisParameter"/>
            <xtce:LinearAdjustment intercept="25" slope="8"/>
        </xtce:DynamicValue>
        <xtce:TerminationChar>58</xtce:TerminationChar>
    </xtce:Variable>
</xtce:StringDataEncoding>
""",
         encodings.StringDataEncoding(dynamic_length_reference='SizeFromThisParameter',
                                      length_linear_adjuster=object(),
                                      termination_character='58')),
        ("""
<xtce:StringDataEncoding xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:Variable maxSizeInBits="32">
        <xtce:DynamicValue>
            <xtce:ParameterInstanceRef parameterRef="SizeFromThisParameter"/>
            <xtce:LinearAdjustment intercept="25" slope="8"/>
        </xtce:DynamicValue>
        <xtce:LeadingSize sizeInBitsOfSizeTag="3"/>
    </xtce:Variable>
</xtce:StringDataEncoding>
""",
         encodings.StringDataEncoding(dynamic_length_reference='SizeFromThisParameter',
                                      length_linear_adjuster=object(),
                                      leading_length_size=3)),
        ("""
<xtce:StringDataEncoding xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:Variable maxSizeInBits="32">
        <xtce:DiscreteLookupList>
            <xtce:DiscreteLookup value="10">
                <xtce:Comparison parameterRef="P1" value="1"/>
            </xtce:DiscreteLookup>
            <xtce:DiscreteLookup value="25">
                <xtce:Comparison parameterRef="P1" value="2"/>
            </xtce:DiscreteLookup>
        </xtce:DiscreteLookupList>
        <xtce:TerminationChar>58</xtce:TerminationChar>
    </xtce:Variable>
</xtce:StringDataEncoding>
""",
         encodings.StringDataEncoding(
             discrete_lookup_length=[
                 comparisons.DiscreteLookup([comparisons.Comparison('1', 'P1')], 10),
                 comparisons.DiscreteLookup([comparisons.Comparison('2', 'P1')], 25)
             ],
             termination_character="58"
         )),
        ("""
<xtce:StringDataEncoding xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:Variable maxSizeInBits="32">
        <xtce:DiscreteLookupList>
            <xtce:DiscreteLookup value="10">
                <xtce:Comparison parameterRef="P1" value="1"/>
            </xtce:DiscreteLookup>
            <xtce:DiscreteLookup value="25">
                <xtce:Comparison parameterRef="P1" value="2"/>
            </xtce:DiscreteLookup>
        </xtce:DiscreteLookupList>
        <xtce:LeadingSize sizeInBitsOfSizeTag="3"/>
    </xtce:Variable>
</xtce:StringDataEncoding>
""",
         encodings.StringDataEncoding(
             discrete_lookup_length=[
                 comparisons.DiscreteLookup([comparisons.Comparison('1', 'P1')], 10),
                 comparisons.DiscreteLookup([comparisons.Comparison('2', 'P1')], 25)
             ],
             leading_length_size=3
         )),
        ("""
<xtce:StringDataEncoding xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:SizeInBits>
        <xtce:Fixed>
            <xtce:InvalidTag>9000</xtce:InvalidTag>
        </xtce:Fixed>
    </xtce:SizeInBits>
</xtce:StringDataEncoding>
""",
         AttributeError())
    ]
)
def test_string_data_encoding(xml_string: str, expectation):
    """Test parsing a StringDataEncoding from an XML string"""
    element = ElementTree.fromstring(xml_string)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            encodings.StringDataEncoding.from_xml(element, ns=XTCE_NSMAP)
    else:
        result = encodings.StringDataEncoding.from_xml(element, ns=XTCE_NSMAP)
        assert result == expectation
        # Recover XML and re-parse it to check it's recoverable
        result_string = ElementTree.tostring(result.to_xml(ns=XTCE_NSMAP), pretty_print=True).decode()
        full_circle = encodings.StringDataEncoding.from_xml(ElementTree.fromstring(result_string), ns=XTCE_NSMAP)
        assert full_circle == expectation


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        ("""
<xtce:IntegerDataEncoding xmlns:xtce="http://www.omg.org/space/xtce" sizeInBits="4" encoding="unsigned"/>
""",
         encodings.IntegerDataEncoding(size_in_bits=4, encoding='unsigned')),
        ("""
<xtce:IntegerDataEncoding xmlns:xtce="http://www.omg.org/space/xtce" sizeInBits="4"/>
""",
         encodings.IntegerDataEncoding(size_in_bits=4, encoding='unsigned')),
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
         encodings.IntegerDataEncoding(
             size_in_bits=16, encoding='unsigned',
             default_calibrator=calibrators.PolynomialCalibrator([
                 calibrators.PolynomialCoefficient(0.012155, 1), calibrators.PolynomialCoefficient(2.54, 0)
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
         encodings.IntegerDataEncoding(size_in_bits=12, encoding='unsigned',
                                       default_calibrator=None,
                                       context_calibrators=[
                                           calibrators.ContextCalibrator(
                                               match_criteria=[comparisons.Comparison(required_value='0', operator=">=",
                                                                                      referenced_parameter='MSN__PARAM'),
                                                               comparisons.Comparison(required_value='678',
                                                                                      operator="<",
                                                                                      referenced_parameter='MSN__PARAM')],
                                               calibrator=calibrators.PolynomialCalibrator(
                                                   coefficients=[calibrators.PolynomialCoefficient(142.998, 0),
                                                                 calibrators.PolynomialCoefficient(-0.349712, 1)])),
                                           calibrators.ContextCalibrator(
                                               match_criteria=[
                                                   comparisons.Comparison(required_value='678', operator=">=",
                                                                          referenced_parameter='MSN__PARAM'),
                                                   comparisons.Comparison(required_value='4096', operator="<=",
                                                                          referenced_parameter='MSN__PARAM')],
                                               calibrator=calibrators.PolynomialCalibrator(
                                                   coefficients=[calibrators.PolynomialCoefficient(100.488, 0),
                                                                 calibrators.PolynomialCoefficient(-0.110197, 1)]))
                                       ])),
    ]
)
def test_integer_data_encoding(xml_string: str, expectation):
    """Test parsing an IntegerDataEncoding from an XML string"""
    element = ElementTree.fromstring(xml_string)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            encodings.IntegerDataEncoding.from_xml(element, ns=XTCE_NSMAP)
    else:
        result = encodings.IntegerDataEncoding.from_xml(element, ns=XTCE_NSMAP)
        assert result == expectation
        # Recover XML and re-parse it to check it's recoverable
        result_string = ElementTree.tostring(result.to_xml(ns=XTCE_NSMAP), pretty_print=True).decode()
        print(result_string)
        full_circle = encodings.IntegerDataEncoding.from_xml(ElementTree.fromstring(result_string),
                                                             ns=XTCE_NSMAP)
        assert full_circle == expectation


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        ("""
<xtce:FloatDataEncoding xmlns:xtce="http://www.omg.org/space/xtce" sizeInBits="4" encoding="IEEE754"/>
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
         encodings.FloatDataEncoding(
             size_in_bits=16, encoding='IEEE754',
             default_calibrator=calibrators.PolynomialCalibrator([
                 calibrators.PolynomialCoefficient(0.012155, 1), calibrators.PolynomialCoefficient(2.54, 0)
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
         encodings.FloatDataEncoding(
             size_in_bits=16, encoding='IEEE754',
             default_calibrator=calibrators.PolynomialCalibrator([
                 calibrators.PolynomialCoefficient(0.012155, 1), calibrators.PolynomialCoefficient(2.54, 0)
             ]),
             context_calibrators=[
                 calibrators.ContextCalibrator(
                     match_criteria=[comparisons.Comparison(required_value='0', operator=">=",
                                                            referenced_parameter='MSN__PARAM'),
                                     comparisons.Comparison(required_value='678', operator="<",
                                                            referenced_parameter='MSN__PARAM')],
                     calibrator=calibrators.PolynomialCalibrator(
                         coefficients=[calibrators.PolynomialCoefficient(142.998, 0),
                                       calibrators.PolynomialCoefficient(-0.349712, 1)])),
                 calibrators.ContextCalibrator(
                     match_criteria=[comparisons.Comparison(required_value='678', operator=">=",
                                                            referenced_parameter='MSN__PARAM'),
                                     comparisons.Comparison(required_value='4096', operator="<=",
                                                            referenced_parameter='MSN__PARAM')],
                     calibrator=calibrators.PolynomialCalibrator(
                         coefficients=[calibrators.PolynomialCoefficient(100.488, 0),
                                       calibrators.PolynomialCoefficient(-0.110197, 1)]))
             ]
         )),
    ]
)
def test_float_data_encoding(xml_string: str, expectation):
    """Test parsing an FloatDataEncoding from an XML string"""
    element = ElementTree.fromstring(xml_string)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            encodings.FloatDataEncoding.from_xml(element, ns=XTCE_NSMAP)
    else:
        result = encodings.FloatDataEncoding.from_xml(element, ns=XTCE_NSMAP)
        assert result == expectation
        # Recover XML and re-parse it to check it's recoverable
        result_string = ElementTree.tostring(result.to_xml(ns=XTCE_NSMAP), pretty_print=True).decode()
        full_circle = encodings.FloatDataEncoding.from_xml(ElementTree.fromstring(result_string),
                                                           ns=XTCE_NSMAP)
        assert full_circle == expectation


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
         encodings.BinaryDataEncoding(fixed_size_in_bits=256)),
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
         encodings.BinaryDataEncoding(
             size_reference_parameter='SizeFromThisParameter',
             linear_adjuster=lambda x: 25 + 8 * x)),
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
         encodings.BinaryDataEncoding(size_discrete_lookup_list=[
             comparisons.DiscreteLookup([comparisons.Comparison('1', 'P1')], 10),
             comparisons.DiscreteLookup([comparisons.Comparison('2', 'P1')], 25)
         ])),
    ]
)
def test_binary_data_encoding(xml_string: str, expectation):
    """Test parsing an BinaryDataEncoding from an XML string"""
    element = ElementTree.fromstring(xml_string)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            encodings.BinaryDataEncoding.from_xml(element, ns=XTCE_NSMAP)
    else:
        result = encodings.BinaryDataEncoding.from_xml(element, ns=XTCE_NSMAP)
        assert result == expectation
        # Recover XML and re-parse it to check it's recoverable
        result_string = ElementTree.tostring(result.to_xml(ns=XTCE_NSMAP), pretty_print=True).decode()
        print(result_string)
        full_circle = encodings.BinaryDataEncoding.from_xml(ElementTree.fromstring(result_string),
                                                            ns=XTCE_NSMAP)
        assert full_circle == expectation