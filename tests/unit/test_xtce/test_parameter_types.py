"""Parameter Type tests"""
import pytest
import lxml.etree as ElementTree

from space_packet_parser.xtce import XTCE_1_2_XMLNS, parameter_types, encodings, calibrators


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        (f"""
<xtce:StringParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_STRING_Type">
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
         parameter_types.StringParameterType(name='TEST_STRING_Type',
                                                                      encoding=encodings.StringDataEncoding(fixed_raw_length=40))),
        (f"""
<xtce:StringParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_STRING_Type">
    <xtce:StringDataEncoding>
        <xtce:SizeInBits>
            <xtce:Fixed>
                <xtce:FixedValue>40</xtce:FixedValue>
            </xtce:Fixed>
            <xtce:LeadingSize sizeInBitsOfSizeTag="17"/>
        </xtce:SizeInBits>
    </xtce:StringDataEncoding>
</xtce:StringParameterType>
""",
         parameter_types.StringParameterType(name='TEST_STRING_Type',
                                                                      encoding=encodings.StringDataEncoding(fixed_raw_length=40,
                                                                              leading_length_size=17))),
        (f"""
<xtce:StringParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_STRING_Type">
    <xtce:StringDataEncoding>
        <xtce:SizeInBits>
            <xtce:Fixed>
                <xtce:FixedValue>40</xtce:FixedValue>
            </xtce:Fixed>
            <xtce:TerminationChar>00</xtce:TerminationChar>
        </xtce:SizeInBits>
    </xtce:StringDataEncoding>
</xtce:StringParameterType>
""",
         parameter_types.StringParameterType(name='TEST_STRING_Type',
                                                                      encoding=encodings.StringDataEncoding(fixed_raw_length=40,
                                                                              termination_character='00'))),
    ]
)
def test_string_parameter_type(elmaker, xtce_parser, xml_string: str, expectation):
    """Test parsing an StringParameterType from an XML string"""
    element = ElementTree.fromstring(xml_string, xtce_parser)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            parameter_types.StringParameterType.from_xml(element)
    else:
        result = parameter_types.StringParameterType.from_xml(element)
        assert result == expectation
        # Recover XML and re-parse it to check it's recoverable
        result_string = ElementTree.tostring(result.to_xml(elmaker=elmaker), pretty_print=True).decode()
        full_circle = parameter_types.StringParameterType.from_xml(ElementTree.fromstring(result_string, parser=xtce_parser))
        assert full_circle == expectation


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        (f"""
<xtce:IntegerParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_INT_Type">
    <xtce:UnitSet>
        <xtce:Unit>m/s</xtce:Unit>
    </xtce:UnitSet>
    <xtce:IntegerDataEncoding sizeInBits="16" encoding="unsigned"/>
</xtce:IntegerParameterType>
""",
         parameter_types.IntegerParameterType(name='TEST_INT_Type', unit='m/s',
                                                                       encoding=encodings.IntegerDataEncoding(size_in_bits=16, encoding='unsigned'))),
        (f"""
<xtce:IntegerParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_INT_Type">
    <xtce:UnitSet>
        <xtce:Unit>m/s</xtce:Unit>
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
         parameter_types.IntegerParameterType(name='TEST_INT_Type', unit='m/s',
                                                                       encoding=encodings.IntegerDataEncoding(
                                             size_in_bits=16, encoding='unsigned',
                                             default_calibrator=calibrators.PolynomialCalibrator([
                                                 calibrators.PolynomialCoefficient(2772.24, 0),
                                                 calibrators.PolynomialCoefficient(-41.6338, 1),
                                                 calibrators.PolynomialCoefficient(-0.185486, 2)
                                             ])
                                         ))),
        (f"""
<xtce:IntegerParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_INT_Type">
    <xtce:UnitSet>
        <xtce:Unit>m/s</xtce:Unit>
    </xtce:UnitSet>
    <xtce:IntegerDataEncoding sizeInBits="16" encoding="unsigned">
        <xtce:DefaultCalibrator>
            <xtce:SplineCalibrator order="0">
                <xtce:SplinePoint raw="1" calibrated="10"/>
                <xtce:SplinePoint raw="2" calibrated="100"/>
                <xtce:SplinePoint raw="3" calibrated="500"/>
            </xtce:SplineCalibrator>
        </xtce:DefaultCalibrator>
    </xtce:IntegerDataEncoding>
</xtce:IntegerParameterType>
""",
         parameter_types.IntegerParameterType(name='TEST_INT_Type', unit='m/s',
                                                                       encoding=encodings.IntegerDataEncoding(
                                             size_in_bits=16, encoding='unsigned',
                                             default_calibrator=calibrators.SplineCalibrator(
                                                 order=0, extrapolate=False,
                                                 points=[
                                                     calibrators.SplinePoint(raw=1, calibrated=10),
                                                     calibrators.SplinePoint(raw=2, calibrated=100),
                                                     calibrators.SplinePoint(raw=3, calibrated=500),
                                                 ]
                                             )))),
    ]
)
def test_integer_parameter_type(elmaker, xtce_parser, xml_string: str, expectation):
    """Test parsing an IntegerParameterType from an XML string"""
    element = ElementTree.fromstring(xml_string, xtce_parser)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            parameter_types.IntegerParameterType.from_xml(element)
    else:
        result = parameter_types.IntegerParameterType.from_xml(element)
        assert result == expectation
        # Recover XML and re-parse it to check it's recoverable
        result_string = ElementTree.tostring(result.to_xml(elmaker=elmaker), pretty_print=True).decode()
        full_circle = parameter_types.IntegerParameterType.from_xml(
            ElementTree.fromstring(result_string, parser=xtce_parser))
        assert full_circle == expectation


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        (f"""
<xtce:FloatParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_INT_Type">
    <xtce:UnitSet>
        <xtce:Unit>m/s</xtce:Unit>
    </xtce:UnitSet>
    <xtce:FloatDataEncoding sizeInBits="16"/>
</xtce:FloatParameterType>
""",
         parameter_types.FloatParameterType(name='TEST_INT_Type', unit='m/s',
                                                                     encoding=encodings.FloatDataEncoding(size_in_bits=16, encoding='IEEE754'))),
        (f"""
<xtce:FloatParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_INT_Type">
    <xtce:UnitSet>
        <xtce:Unit>m/s</xtce:Unit>
    </xtce:UnitSet>
    <xtce:IntegerDataEncoding sizeInBits="16" encoding="unsigned"/>
</xtce:FloatParameterType>
""",
         parameter_types.FloatParameterType(name='TEST_INT_Type', unit='m/s',
                                                                     encoding=encodings.IntegerDataEncoding(size_in_bits=16, encoding='unsigned'))),
        (f"""
<xtce:FloatParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_INT_Type">
    <xtce:UnitSet>
        <xtce:Unit>m/s</xtce:Unit>
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
         parameter_types.FloatParameterType(name='TEST_INT_Type', unit='m/s',
                                                                     encoding=encodings.IntegerDataEncoding(
                                           size_in_bits=16, encoding='unsigned',
                                           default_calibrator=calibrators.PolynomialCalibrator([
                                               calibrators.PolynomialCoefficient(2772.24, 0),
                                               calibrators.PolynomialCoefficient(-41.6338, 1),
                                               calibrators.PolynomialCoefficient(-0.185486, 2)
                                           ])
                                       ))),
        (f"""
<xtce:FloatParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_INT_Type">
    <xtce:UnitSet>
        <xtce:Unit>m/s</xtce:Unit>
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
         parameter_types.FloatParameterType(name='TEST_INT_Type', unit='m/s',
                                                                     encoding=encodings.IntegerDataEncoding(
                                           size_in_bits=16, encoding='unsigned',
                                           default_calibrator=calibrators.SplineCalibrator(
                                               order=0, extrapolate=False,
                                               points=[
                                                   calibrators.SplinePoint(raw=1, calibrated=10.),
                                                   calibrators.SplinePoint(raw=2, calibrated=100.),
                                                   calibrators.SplinePoint(raw=3, calibrated=500.),
                                               ]
                                           )))),
    ]
)
def test_float_parameter_type(elmaker, xtce_parser, xml_string: str, expectation):
    """Test parsing an FloatParameterType from an XML string"""
    element = ElementTree.fromstring(xml_string, xtce_parser)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            parameter_types.FloatParameterType.from_xml(element)
    else:
        result = parameter_types.FloatParameterType.from_xml(element)
        assert result == expectation
        # Recover XML and re-parse it to check it's recoverable
        result_string = ElementTree.tostring(result.to_xml(elmaker=elmaker), pretty_print=True).decode()
        full_circle = parameter_types.FloatParameterType.from_xml(
            ElementTree.fromstring(result_string, parser=xtce_parser))
        assert full_circle == expectation


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        (f"""
<xtce:EnumeratedParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_ENUM_Type">
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
         parameter_types.EnumeratedParameterType(name='TEST_ENUM_Type',
                                                                          encoding=encodings.IntegerDataEncoding(size_in_bits=2, encoding='unsigned'),
                                                                          # NOTE: Duplicate final value is on purpose to make sure we handle that case
                                                                          enumeration={0: 'BOOT_POR', 1: 'BOOT_RETURN', 2: 'OP_LOW', 3: 'OP_HIGH',
                                                         4: 'OP_HIGH'})),
        (f"""
<xtce:EnumeratedParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_ENUM_Type">
    <xtce:UnitSet/>
    <xtce:FloatDataEncoding sizeInBits="32" encoding="IEEE754"/>
    <xtce:EnumerationList>
        <xtce:Enumeration label="BOOT_POR" value="0.0"/>
        <xtce:Enumeration label="BOOT_RETURN" value="1.1"/>
        <xtce:Enumeration label="OP_LOW" value="2.2"/>
        <xtce:Enumeration label="OP_HIGH" value="3.3"/>
        <xtce:Enumeration label="OP_HIGH" value="4.4"/>
    </xtce:EnumerationList>
</xtce:EnumeratedParameterType>
""",
         parameter_types.EnumeratedParameterType(name='TEST_ENUM_Type',
                                                                          encoding=encodings.FloatDataEncoding(size_in_bits=32, encoding='IEEE754'),
                                                                          # NOTE: Duplicate final value is on purpose to make sure we handle that case
                                                                          enumeration={0.0: 'BOOT_POR', 1.1: 'BOOT_RETURN', 2.2: 'OP_LOW', 3.3: 'OP_HIGH',
                                                         4.4: 'OP_HIGH'})),
        (f"""
<xtce:EnumeratedParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_ENUM_Type">
    <xtce:UnitSet/>
    <xtce:StringDataEncoding>
        <xtce:SizeInBits>
            <xtce:Fixed>
                <xtce:FixedValue>16</xtce:FixedValue>
            </xtce:Fixed>
        </xtce:SizeInBits>
    </xtce:StringDataEncoding>
    <xtce:EnumerationList>
        <xtce:Enumeration label="BOOT_POR" value="AA"/>
        <xtce:Enumeration label="BOOT_RETURN" value="BB"/>
        <xtce:Enumeration label="OP_LOW" value="CC"/>
        <xtce:Enumeration label="OP_HIGH" value="DD"/>
        <xtce:Enumeration label="OP_HIGH" value="EE"/>
    </xtce:EnumerationList>
</xtce:EnumeratedParameterType>
""",
         parameter_types.EnumeratedParameterType(name='TEST_ENUM_Type',
                                                                          encoding=encodings.StringDataEncoding(fixed_raw_length=16),
                                                                          # NOTE: Duplicate final value is on purpose to make sure we handle that case
                                                                          enumeration={b"AA": 'BOOT_POR',
                                                         b"BB": 'BOOT_RETURN',
                                                         b"CC": 'OP_LOW',
                                                         b"DD": 'OP_HIGH',
                                                         b"EE": 'OP_HIGH'})),
        (f"""
<xtce:EnumeratedParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_ENUM_Type">
    <xtce:UnitSet/>
    <xtce:StringDataEncoding encoding="UTF-16BE">
        <xtce:SizeInBits>
            <xtce:Fixed>
                <xtce:FixedValue>16</xtce:FixedValue>
            </xtce:Fixed>
        </xtce:SizeInBits>
    </xtce:StringDataEncoding>
    <xtce:EnumerationList>
        <xtce:Enumeration label="BOOT_POR" value="AA"/>
        <xtce:Enumeration label="BOOT_RETURN" value="BB"/>
        <xtce:Enumeration label="OP_LOW" value="CC"/>
        <xtce:Enumeration label="OP_HIGH" value="DD"/>
        <xtce:Enumeration label="OP_HIGH" value="EE"/>
    </xtce:EnumerationList>
</xtce:EnumeratedParameterType>
""",
         parameter_types.EnumeratedParameterType(name='TEST_ENUM_Type',
                                                                          encoding=encodings.StringDataEncoding(fixed_raw_length=16, encoding='UTF-16BE'),
                                                                          # NOTE: Duplicate final value is on purpose to make sure we handle that case
                                                                          enumeration={b"\x00A\x00A": 'BOOT_POR',
                                                         b"\x00B\x00B": 'BOOT_RETURN',
                                                         b"\x00C\x00C": 'OP_LOW',
                                                         b"\x00D\x00D": 'OP_HIGH',
                                                         b"\x00E\x00E": 'OP_HIGH'})),
    ]
)
def test_enumerated_parameter_type(elmaker, xtce_parser, xml_string: str, expectation):
    """Test parsing an EnumeratedParameterType from an XML string"""
    element = ElementTree.fromstring(xml_string, xtce_parser)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            parameter_types.EnumeratedParameterType.from_xml(element)
    else:
        result = parameter_types.EnumeratedParameterType.from_xml(element)
        assert result == expectation
        # Recover XML and re-parse it to check it's recoverable
        result_string = ElementTree.tostring(result.to_xml(elmaker=elmaker), pretty_print=True).decode()
        full_circle = parameter_types.EnumeratedParameterType.from_xml(
            ElementTree.fromstring(result_string, parser=xtce_parser))
        assert full_circle == expectation


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        (f"""
<xtce:BinaryParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_PARAM_Type">
    <xtce:UnitSet>
        <xtce:Unit>m/s</xtce:Unit>
    </xtce:UnitSet>
    <xtce:BinaryDataEncoding>
        <xtce:SizeInBits>
            <xtce:FixedValue>256</xtce:FixedValue>
        </xtce:SizeInBits>
    </xtce:BinaryDataEncoding>
</xtce:BinaryParameterType>
""",
         parameter_types.BinaryParameterType(name='TEST_PARAM_Type', unit='m/s',
                                                                      encoding=encodings.BinaryDataEncoding(fixed_size_in_bits=256))),
        (f"""
<xtce:BinaryParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_PARAM_Type">
    <xtce:UnitSet/>
    <xtce:BinaryDataEncoding>
        <xtce:SizeInBits>
            <xtce:FixedValue>128</xtce:FixedValue>
        </xtce:SizeInBits>
    </xtce:BinaryDataEncoding>
</xtce:BinaryParameterType>
""",
         parameter_types.BinaryParameterType(name='TEST_PARAM_Type', unit=None,
                                                                      encoding=encodings.BinaryDataEncoding(fixed_size_in_bits=128))),
        (f"""
<xtce:BinaryParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_PARAM_Type">
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
         parameter_types.BinaryParameterType(name='TEST_PARAM_Type',
                                                                      encoding=encodings.BinaryDataEncoding(
                                            size_reference_parameter='SizeFromThisParameter',
                                            use_calibrated_value=False,
                                            linear_adjuster=lambda x: x))),
        (f"""
<xtce:BinaryParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_PARAM_Type">
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
         parameter_types.BinaryParameterType(name='TEST_PARAM_Type', unit=None,
                                                                      encoding=encodings.BinaryDataEncoding(
                                            size_reference_parameter='SizeFromThisParameter'))),
    ]
)
def test_binary_parameter_type(elmaker, xtce_parser, xml_string: str, expectation):
    """Test parsing an BinaryParameterType from an XML string"""
    element = ElementTree.fromstring(xml_string, xtce_parser)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            parameter_types.BinaryParameterType.from_xml(element)
    else:
        result = parameter_types.BinaryParameterType.from_xml(element)
        assert result == expectation
        # Recover XML and re-parse it to check it's recoverable
        result_string = ElementTree.tostring(result.to_xml(elmaker=elmaker), pretty_print=True).decode()
        full_circle = parameter_types.BinaryParameterType.from_xml(
            ElementTree.fromstring(result_string, parser=xtce_parser))
        assert full_circle == expectation


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        (f"""
<xtce:BooleanParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_PARAM_Type">
    <xtce:UnitSet>
        <xtce:Unit>m/s</xtce:Unit>
    </xtce:UnitSet>
    <xtce:BinaryDataEncoding>
        <xtce:SizeInBits>
            <xtce:FixedValue>1</xtce:FixedValue>
        </xtce:SizeInBits>
    </xtce:BinaryDataEncoding>
</xtce:BooleanParameterType>
""",
         parameter_types.BooleanParameterType(name='TEST_PARAM_Type', unit='m/s',
                                                                       encoding=encodings.BinaryDataEncoding(fixed_size_in_bits=1))),
        (f"""
<xtce:BooleanParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_PARAM_Type">
    <xtce:UnitSet>
        <xtce:Unit>m/s</xtce:Unit>
    </xtce:UnitSet>
    <xtce:IntegerDataEncoding encoding="unsigned" sizeInBits="1"/>
</xtce:BooleanParameterType>
""",
         parameter_types.BooleanParameterType(name='TEST_PARAM_Type', unit='m/s',
                                                                       encoding=encodings.IntegerDataEncoding(size_in_bits=1, encoding="unsigned"))),
        (f"""
<xtce:BooleanParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_PARAM_Type">
    <xtce:UnitSet>
        <xtce:Unit>m/s</xtce:Unit>
    </xtce:UnitSet>
    <xtce:StringDataEncoding encoding="UTF-8">
        <xtce:SizeInBits>
            <xtce:Fixed>
                <xtce:FixedValue>40</xtce:FixedValue>
            </xtce:Fixed>
            <xtce:TerminationChar>00</xtce:TerminationChar>
        </xtce:SizeInBits>
    </xtce:StringDataEncoding>
</xtce:BooleanParameterType>
""",
         parameter_types.BooleanParameterType(name='TEST_PARAM_Type', unit='m/s',
                                                                       encoding=encodings.StringDataEncoding(fixed_raw_length=40,
                                                                               termination_character='00'))),
    ]
)
def test_boolean_parameter_type(elmaker, xtce_parser, xml_string, expectation):
    """Test parsing a BooleanParameterType from an XML string"""
    element = ElementTree.fromstring(xml_string, xtce_parser)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            parameter_types.BooleanParameterType.from_xml(element)
    else:
        result = parameter_types.BooleanParameterType.from_xml(element)
        assert result == expectation
        # Recover XML and re-parse it to check it's recoverable
        result_string = ElementTree.tostring(result.to_xml(elmaker=elmaker), pretty_print=True).decode()
        full_circle = parameter_types.BooleanParameterType.from_xml(
            ElementTree.fromstring(result_string, parser=xtce_parser))
        assert full_circle == expectation


@pytest.mark.parametrize(
    ('xml_string', 'expectation'),
    [
        (f"""
<xtce:AbsoluteTimeParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_PARAM_Type">
    <xtce:Encoding units="seconds">
        <xtce:IntegerDataEncoding sizeInBits="32"/>
    </xtce:Encoding>
    <xtce:ReferenceTime>
        <xtce:OffsetFrom parameterRef="MilliSeconds"/>
        <xtce:Epoch>TAI</xtce:Epoch>
    </xtce:ReferenceTime>
</xtce:AbsoluteTimeParameterType>
""",
         parameter_types.AbsoluteTimeParameterType(name='TEST_PARAM_Type', unit='seconds',
                                                                            encoding=encodings.IntegerDataEncoding(size_in_bits=32,
                                                                                     encoding="unsigned"),
                                                                            epoch="TAI", offset_from="MilliSeconds")),
        (f"""
<xtce:AbsoluteTimeParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_PARAM_Type">
    <xtce:Encoding scale="1E-6" offset="0" units="s">
        <xtce:IntegerDataEncoding sizeInBits="32"/>
    </xtce:Encoding>
    <xtce:ReferenceTime>
        <xtce:OffsetFrom parameterRef="MilliSeconds"/>
        <xtce:Epoch>2009-10-10T12:00:00-05:00</xtce:Epoch>
    </xtce:ReferenceTime>
</xtce:AbsoluteTimeParameterType>
""",
         parameter_types.AbsoluteTimeParameterType(
             name='TEST_PARAM_Type', unit='s',
             encoding=encodings.IntegerDataEncoding(
                 size_in_bits=32, encoding="unsigned",
                 default_calibrator=calibrators.PolynomialCalibrator(
                     coefficients=[
                         calibrators.PolynomialCoefficient(0, 0),
                         calibrators.PolynomialCoefficient(1E-6, 1)
                     ])),
             epoch="2009-10-10T12:00:00-05:00", offset_from="MilliSeconds")),
        (f"""
<xtce:AbsoluteTimeParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_PARAM_Type">
    <xtce:Encoding scale="1.31E-6" units="s">
        <xtce:IntegerDataEncoding sizeInBits="32"/>
    </xtce:Encoding>
</xtce:AbsoluteTimeParameterType>
""",
         parameter_types.AbsoluteTimeParameterType(
             name='TEST_PARAM_Type', unit='s',
             encoding=encodings.IntegerDataEncoding(
                 size_in_bits=32, encoding="unsigned",
                 default_calibrator=calibrators.PolynomialCalibrator(
                     coefficients=[
                         calibrators.PolynomialCoefficient(1.31E-6, 1)
                     ]))
         )),
        (f"""
<xtce:AbsoluteTimeParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_PARAM_Type">
    <xtce:Encoding offset="147.884" units="s">
        <xtce:IntegerDataEncoding sizeInBits="32"/>
    </xtce:Encoding>
</xtce:AbsoluteTimeParameterType>
""",
         parameter_types.AbsoluteTimeParameterType(
             name='TEST_PARAM_Type', unit='s',
             encoding=encodings.IntegerDataEncoding(
                 size_in_bits=32, encoding="unsigned",
                 default_calibrator=calibrators.PolynomialCalibrator(
                     coefficients=[
                         calibrators.PolynomialCoefficient(147.884, 0),
                         calibrators.PolynomialCoefficient(1, 1)
                     ]))
         )),
        (f"""
<xtce:AbsoluteTimeParameterType xmlns:xtce="{XTCE_1_2_XMLNS}" name="TEST_PARAM_Type">
    <xtce:Encoding offset="147.884" units="s">
        <xtce:FloatDataEncoding sizeInBits="32"/>
    </xtce:Encoding>
</xtce:AbsoluteTimeParameterType>
""",
         parameter_types.AbsoluteTimeParameterType(
             name='TEST_PARAM_Type', unit='s',
             encoding=encodings.FloatDataEncoding(
                 size_in_bits=32, encoding="IEEE754",
                 default_calibrator=calibrators.PolynomialCalibrator(
                     coefficients=[
                         calibrators.PolynomialCoefficient(147.884, 0),
                         calibrators.PolynomialCoefficient(1, 1)
                     ]))
         )),
    ]
)
def test_absolute_time_parameter_type(elmaker, xtce_parser, xml_string, expectation):
    """Test parsing an AbsoluteTimeParameterType from an XML string."""
    element = ElementTree.fromstring(xml_string, xtce_parser)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            parameter_types.AbsoluteTimeParameterType.from_xml(element)
    else:
        result = parameter_types.AbsoluteTimeParameterType.from_xml(element)
        assert result == expectation
        # Recover XML and re-parse it to check it's recoverable
        result_string = ElementTree.tostring(result.to_xml(elmaker=elmaker), pretty_print=True).decode()
        full_circle = parameter_types.AbsoluteTimeParameterType.from_xml(
            ElementTree.fromstring(result_string, parser=xtce_parser))
        assert full_circle == expectation


