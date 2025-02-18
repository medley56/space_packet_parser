"""Tests for parameters"""
import io

import pytest
import lxml.etree as ElementTree

import space_packet_parser.xtce.parameter_types
from space_packet_parser import common, packets
from space_packet_parser.xtce import XTCE_1_2_XMLNS, parameters, encodings, comparisons, calibrators, definitions


def test_invalid_parameter_type_error(test_data_dir):
    """Test proper reporting of an invalid parameter type element"""
    # Test document contains an invalid "InvalidParameterType" element
    test_xtce_document = f"""<?xml version='1.0' encoding='UTF-8'?>
<xtce:SpaceSystem xmlns:xtce="{XTCE_1_2_XMLNS}" name="Space Packet Parser"
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
    x = io.TextIOWrapper(io.BytesIO(test_xtce_document.encode("UTF-8")))
    with pytest.raises(definitions.InvalidParameterTypeError):
        definitions.XtcePacketDefinition.from_xtce(x)


def test_unsupported_parameter_type_error(test_data_dir):
    """Test proper reporting of an unsupported parameter type element"""
    # Test document contains an unsupported array parameter type that is not yet implemented
    test_xtce_document = f"""<?xml version='1.0' encoding='UTF-8'?>
<xtce:SpaceSystem xmlns:xtce="{XTCE_1_2_XMLNS}" name="Space Packet Parser"
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
    x = io.TextIOWrapper(io.BytesIO(test_xtce_document.encode("UTF-8")))
    with pytest.raises(NotImplementedError):
        definitions.XtcePacketDefinition.from_xtce(x)


@pytest.mark.parametrize(
    ('parameter_type', 'raw_data', 'current_pos', 'expected_raw', 'expected_derived'),
    [
        # Fixed length test
        (space_packet_parser.xtce.parameter_types.StringParameterType(
            'TEST_STRING',
            encodings.StringDataEncoding(fixed_raw_length=24)),
         # This still 123X456
         b'123X456',
         0,
         b'123',
         '123'),
        # Dynamic reference length
        (space_packet_parser.xtce.parameter_types.StringParameterType(
            'TEST_STRING',
            encodings.StringDataEncoding(dynamic_length_reference='STR_LEN',
                                         use_calibrated_value=False,
                                         length_linear_adjuster=lambda x: 8 * x)),
         b'BAD WOLFABCD',
         0,
         b'BAD WOLF',
         'BAD WOLF'),
        # Discrete lookup test
        (space_packet_parser.xtce.parameter_types.StringParameterType(
            'TEST_STRING',
            encodings.StringDataEncoding(
                discrete_lookup_length=[
                    comparisons.DiscreteLookup([
                        comparisons.Comparison(7, 'P1', '>'),
                        comparisons.Comparison(99, 'P2', '==', use_calibrated_value=False)
                    ], lookup_value=64)
                ]
            )),
         b'BAD WOLF',
         0,
         b'BAD WOLF',
         'BAD WOLF'),
        # Termination character tests
        (space_packet_parser.xtce.parameter_types.StringParameterType(
            'TEST_STRING',
            encodings.StringDataEncoding(
                fixed_raw_length=64,
                encoding='UTF-8',
                termination_character='58')),
         # 123X456 + extra characters, termination character is X
         b'123X456000000000000000000000000000000000000000000000',
         0,
         b'123X4560',
         '123'),
        (space_packet_parser.xtce.parameter_types.StringParameterType(
            'TEST_STRING',
            encodings.StringDataEncoding(
                fixed_raw_length=128,
                encoding='UTF-8',
                termination_character='58')),
         # 56bits + 123X456 + extra characters, termination character is X
         b'9090909123X456000000000000000000000000000000000000000000000',
         56,
         b'123X456000000000',
         '123'),
        (space_packet_parser.xtce.parameter_types.StringParameterType(
            'TEST_STRING',
            encodings.StringDataEncoding(
                fixed_raw_length=48,
                encoding='UTF-8',
                termination_character='58')),
         # 53bits + 123X456 + extra characters, termination character is X
         # This is the same string as above but bit-shifted left by 3 bits
         b'\x03K;s{\x93)\x89\x91\x9a\xc1\xa1\xa9\xb3K;s{\x93(',
         53,
         b'123X45',
         '123'),
        (space_packet_parser.xtce.parameter_types.StringParameterType(
            "TEST_STRING",
            encodings.StringDataEncoding(
                fixed_raw_length=160,
                encoding="UTF-8",
                termination_character='00')),
         "false_is_truthy".encode("UTF-8") + b'\x00ABCD',
         0,
         b'false_is_truthy\x00ABCD',
         'false_is_truthy'),
        (space_packet_parser.xtce.parameter_types.StringParameterType(
            "TEST_STRING",
            encodings.StringDataEncoding(
                fixed_raw_length=19*16,
                encoding="UTF-16BE",
                termination_character='0021')),
         "false_is_truthy".encode("UTF-16BE") + b'\x00\x21ignoreme',
         0,
         "false_is_truthy".encode("UTF-16BE") + b'\x00\x21ignore',
         'false_is_truthy'),
        (space_packet_parser.xtce.parameter_types.StringParameterType(
            'TEST_STRING',
            encodings.StringDataEncoding(
                fixed_raw_length=16*6,
                encoding='UTF-16LE',
                termination_character='5800')),
         # 123X456, termination character is X
         '123X456'.encode('UTF-16LE'),
         0,
         '123X45'.encode('UTF-16LE'),
         '123'),
        (space_packet_parser.xtce.parameter_types.StringParameterType(
            'TEST_STRING',
            encodings.StringDataEncoding(
                fixed_raw_length=16*5,
                encoding='UTF-16BE',
                termination_character='0058')),
         '123X456'.encode('UTF-16BE'),
         0,
         '123X4'.encode('UTF-16BE'),
         '123'),
        # Leading length test
        (space_packet_parser.xtce.parameter_types.StringParameterType(
            'TEST_STRING',
            encodings.StringDataEncoding(
                fixed_raw_length=29,
                leading_length_size=5)),
         # This is still 123X456 but with 11000 prepended (a 5-bit representation of the number 24)
         # This represents a string length (in bits) of 24 bits.
         0b1100000110001001100100011001101011000001101000011010100110110000.to_bytes(8, byteorder="big"),
         0,
         0b11000001100010011001000110011000.to_bytes(4, byteorder="big"),
         '123'),
    ]
)
def test_string_parameter_parsing(parameter_type, raw_data, current_pos, expected_raw, expected_derived):
    """Test parsing a string parameter"""
    # pre parsed data to reference for lookups
    packet = packets.Packet(raw_data=raw_data, **{'P1': common.FloatParameter(7.55, 7),
                                                       'P2': common.IntParameter(100, 99),
                                                       'STR_LEN': common.IntParameter(8)})
    # Artificially set the current position of the packet data read so far
    packet.raw_data.pos = current_pos
    value = parameter_type.parse_value(packet)
    assert value == expected_derived
    assert value.raw_value == expected_raw


@pytest.mark.parametrize(
    ('parameter_type', 'raw_data', 'current_pos', 'expected'),
    [
        # 16-bit unsigned starting at byte boundary
        (space_packet_parser.xtce.parameter_types.IntegerParameterType('TEST_INT', encodings.IntegerDataEncoding(16, 'unsigned')),
         0b1000000000000000.to_bytes(length=2, byteorder='big'),
         0,
         32768),
        # 16-bit unsigned little endian at byte boundary
        (space_packet_parser.xtce.parameter_types.IntegerParameterType(
            'TEST_INT',
            encodings.IntegerDataEncoding(16, 'unsigned', byte_order="leastSignificantByteFirst")),
         0b1000000000000000.to_bytes(length=2, byteorder='big'),
         0,
         128),
        # 16-bit signed starting at byte boundary
        (space_packet_parser.xtce.parameter_types.IntegerParameterType('TEST_INT', encodings.IntegerDataEncoding(16, 'signed')),
         0b1111111111010110.to_bytes(length=2, byteorder='big'),
         0,
         -42),
        # 16-bit signed little endian starting at byte boundary
        (space_packet_parser.xtce.parameter_types.IntegerParameterType(
            'TEST_INT',
            encodings.IntegerDataEncoding(16, 'signed', byte_order="leastSignificantByteFirst")),
         0b1101011011111111.to_bytes(length=2, byteorder='big'),
         0,
         -42),
        # 16-bit signed integer starting at a byte boundary,
        # calibrated by a polynomial y = (x*2 + 5); x = -42; y = -84 + 5 = -79
        (space_packet_parser.xtce.parameter_types.IntegerParameterType(
            'TEST_INT',
            encodings.IntegerDataEncoding(
                16, 'signed',
                context_calibrators=[
                    calibrators.ContextCalibrator([
                        comparisons.Condition(left_param='PKT_APID', operator='==',
                                              right_value=1101, left_use_calibrated_value=False,
                                              right_use_calibrated_value=False)],
                        calibrators.PolynomialCalibrator([calibrators.PolynomialCoefficient(5, 0),
                                                          calibrators.PolynomialCoefficient(2, 1)]))
                ])),
         0b1111111111010110.to_bytes(length=2, byteorder='big'),
         0,
         -79),
        # 12-bit unsigned integer starting at bit 4 of the first byte
        (space_packet_parser.xtce.parameter_types.IntegerParameterType('TEST_INT', encodings.IntegerDataEncoding(12, 'unsigned')),
         # 11111000 00000000
         #     |--uint:12--|
         0b1111100000000000.to_bytes(length=2, byteorder='big'),
         4,
         2048),
        # 13-bit unsigned integer starting on bit 2 of the second byte
        (space_packet_parser.xtce.parameter_types.IntegerParameterType('TEST_INT', encodings.IntegerDataEncoding(13, 'unsigned')),
         # 10101010 11100000 00000001
         #            |--uint:13---|
         0b101010101110000000000001.to_bytes(length=3, byteorder='big'),
         10,
         4096),
        # 16-bit unsigned integer starting on bit 2 of the first byte
        (space_packet_parser.xtce.parameter_types.IntegerParameterType('TEST_INT', encodings.IntegerDataEncoding(16, 'unsigned')),
         # 10101010 11100000 00000001
         #   |----uint:16-----|
         0b101010101110000000000001.to_bytes(length=3, byteorder='big'),
         2,
         43904),
        # 12-bit signed integer starting on bit 4 of the first byte
        (space_packet_parser.xtce.parameter_types.IntegerParameterType('TEST_INT', encodings.IntegerDataEncoding(12, 'signed')),
         # 11111000 00000000
         #     |---int:12--|
         0b1111100000000000.to_bytes(length=2, byteorder='big'),
         4,
         -2048),
        # 12-bit signed integer starting on bit 6 of the first byte
        (space_packet_parser.xtce.parameter_types.IntegerParameterType('TEST_INT', encodings.IntegerDataEncoding(12, 'signed')),
         # 12-bit signed integer starting on bit 4 of the first byte
         #  11111110 00000000 00111111 10101010
         #        |---int:12---|
         0b11111110000000000011111110101010.to_bytes(length=4, byteorder='big'),
         6,
         -2048),
        # 12-bit signed little endian integer starting on bit 6 of the first byte
        (space_packet_parser.xtce.parameter_types.IntegerParameterType(
            'TEST_INT',
            encodings.IntegerDataEncoding(12, 'signed', byte_order='leastSignificantByteFirst')),
         # 12-bit signed little endian integer starting on bit 4 of the first byte. The LSB of the integer comes first
         #  11111100 00000010 00111111 10101010
         #        |---int:12---|
         0b11111100000000100011111110101010.to_bytes(length=4, byteorder='big'),
         6,
         -2048),
        (space_packet_parser.xtce.parameter_types.IntegerParameterType('TEST_INT', encodings.IntegerDataEncoding(3, 'twosComplement')),
         # 3-bit signed integer starting at bit 7 of the first byte
         #  00000001      11000000       00000000
         #         |-int:3-|
         0b000000011100000000000000.to_bytes(length=3, byteorder='big'),
         7,
         -1),
    ]
)
def test_integer_parameter_parsing(parameter_type, raw_data, current_pos, expected):
    """Testing parsing an integer parameters"""
    # pre parsed data to reference for lookups
    packet = packets.Packet(raw_data=raw_data, PKT_APID=common.IntParameter(1101))
    packet.raw_data.pos = current_pos
    value = parameter_type.parse_value(packet)
    assert value == expected


@pytest.mark.parametrize(
    ('parameter_type', 'raw_data', 'expected'),
    [
        # Test big endion 32-bit IEEE float
        (space_packet_parser.xtce.parameter_types.FloatParameterType('TEST_FLOAT', encodings.FloatDataEncoding(32)),
         0b01000000010010010000111111010000.to_bytes(length=4, byteorder='big'),
         3.14159),
        # Test little endian 32-bit IEEE float
        (space_packet_parser.xtce.parameter_types.FloatParameterType(
            'TEST_FLOAT',
            encodings.FloatDataEncoding(32, byte_order='leastSignificantByteFirst')),
         0b01000000010010010000111111010000.to_bytes(length=4, byteorder='little'),
         3.14159),
        # Test big endian 64-bit float
        (space_packet_parser.xtce.parameter_types.FloatParameterType('TEST_FLOAT', encodings.FloatDataEncoding(64)),
         b'\x3F\xF9\xE3\x77\x9B\x97\xF4\xA8',  # 64-bit IEEE 754 value of Phi
         1.6180339),
        # Test float parameter type encoded as big endian 16-bit integer with contextual polynomial calibrator
        (space_packet_parser.xtce.parameter_types.FloatParameterType(
            'TEST_FLOAT',
            encodings.IntegerDataEncoding(
                16, 'signed',
                context_calibrators=[
                    calibrators.ContextCalibrator([
                        comparisons.Condition(left_param='PKT_APID', operator='==',
                                              right_value=1101, left_use_calibrated_value=False,
                                              right_use_calibrated_value=False)],
                        calibrators.PolynomialCalibrator([calibrators.PolynomialCoefficient(5.6, 0),
                                                          calibrators.PolynomialCoefficient(2.1, 1)]))
                ])),
         0b1111111111010110.to_bytes(length=2, byteorder='big'),
         -82.600000),
        # Test MIL 1750A encoded floats.
        # Test values taken from: https://www.xgc-tek.com/manuals/mil-std-1750a/c191.html#AEN324
        (space_packet_parser.xtce.parameter_types.FloatParameterType(
            'MIL_1750A_FLOAT',
            encodings.FloatDataEncoding(32, encoding="MILSTD_1750A")),
         b'\x7f\xff\xff\x7f',
         0.9999998 * (2 ** 127)),
        (space_packet_parser.xtce.parameter_types.FloatParameterType(
            'MIL_1750A_FLOAT',
            encodings.FloatDataEncoding(32, encoding="MILSTD_1750A")),
         b'\x40\x00\x00\x7f',
         0.5 * (2 ** 127)),
        (space_packet_parser.xtce.parameter_types.FloatParameterType(
            'MIL_1750A_FLOAT',
            encodings.FloatDataEncoding(32, encoding="MILSTD_1750A")),
         b'\x50\x00\x00\x04',
         0.625 * (2 ** 4)),
        (space_packet_parser.xtce.parameter_types.FloatParameterType(
            'MIL_1750A_FLOAT',
            encodings.FloatDataEncoding(32, encoding="MILSTD_1750A")),
         b'\x40\x00\x00\x01',
         0.5 * (2 ** 1)),
        (space_packet_parser.xtce.parameter_types.FloatParameterType(
            'MIL_1750A_FLOAT',
            encodings.FloatDataEncoding(32, encoding="MILSTD_1750A")),
         b'\x40\x00\x00\x00',
         0.5 * (2 ** 0)),
        (space_packet_parser.xtce.parameter_types.FloatParameterType(
            'MIL_1750A_FLOAT',
            encodings.FloatDataEncoding(32, encoding="MILSTD_1750A")),
         b'\x40\x00\x00\xff',
         0.5 * (2 ** -1)),
        (space_packet_parser.xtce.parameter_types.FloatParameterType(
            'MIL_1750A_FLOAT',
            encodings.FloatDataEncoding(32, encoding="MILSTD_1750A")),
         b'\x40\x00\x00\x80',
         0.5 * (2 ** -128)),
        (space_packet_parser.xtce.parameter_types.FloatParameterType(
            'MIL_1750A_FLOAT',
            encodings.FloatDataEncoding(32, encoding="MILSTD_1750A")),
         b'\x00\x00\x00\x00',
         0.0 * (2 ** 0)),
        (space_packet_parser.xtce.parameter_types.FloatParameterType(
            'MIL_1750A_FLOAT',
            encodings.FloatDataEncoding(32, encoding="MILSTD_1750A")),
         b'\x80\x00\x00\x00',
         -1.0 * (2 ** 0)),
        (space_packet_parser.xtce.parameter_types.FloatParameterType(
            'MIL_1750A_FLOAT',
            encodings.FloatDataEncoding(32, encoding="MILSTD_1750A")),
         b'\xBF\xFF\xFF\x80',
         -0.5000001 * (2 ** -128)),
        (space_packet_parser.xtce.parameter_types.FloatParameterType(
            'MIL_1750A_FLOAT',
            encodings.FloatDataEncoding(32, encoding="MILSTD_1750A")),
         b'\x9F\xFF\xFF\x04',
         -0.7500001 * (2 ** 4)),
        # Little endian version of previous test
        (space_packet_parser.xtce.parameter_types.FloatParameterType(
            'MIL_1750A_FLOAT',
            encodings.FloatDataEncoding(32, encoding="MILSTD_1750A", byte_order="leastSignificantByteFirst")),
         b'\x04\xFF\xFF\x9F',
         -0.7500001 * (2 ** 4)),
    ]
)
def test_float_parameter_parsing(parameter_type, raw_data, expected):
    """Test parsing float parameters"""
    # pre parsed data to reference for lookups
    packet = packets.Packet(raw_data=raw_data, **{'PKT_APID': common.IntParameter(1101)})
    value = parameter_type.parse_value(packet)
    # NOTE: These results are compared with a relative tolerance due to the imprecise storage of floats
    assert value == pytest.approx(expected, rel=1E-7)


@pytest.mark.parametrize(
    ('parameter_type', 'raw_data', 'expected_raw', 'expected'),
    [
        (space_packet_parser.xtce.parameter_types.EnumeratedParameterType(
            'TEST_ENUM',
            encodings.IntegerDataEncoding(16, 'unsigned'), {32768: 'NOMINAL'}),
         0b1000000000000000.to_bytes(length=2, byteorder='big'),
         32768,
         'NOMINAL'),
        (space_packet_parser.xtce.parameter_types.EnumeratedParameterType(
            'TEST_FALSY_RAW_ENUM',
            encodings.IntegerDataEncoding(16, 'unsigned'), {0: 'FALSY_LABEL'}),
         0b0000000000000000.to_bytes(length=2, byteorder='big'),
         0,
         'FALSY_LABEL'),
        # Test to prove that enums are never using calibrated values
        (space_packet_parser.xtce.parameter_types.EnumeratedParameterType(
            'TEST_CALIBRATED_ENCODING_ENUM',
            encodings.IntegerDataEncoding(
                16, 'unsigned',
                default_calibrator=calibrators.PolynomialCalibrator([
                    calibrators.PolynomialCoefficient(5, 0),  # 5
                    calibrators.PolynomialCoefficient(2, 1)  # 2x
                ])
            ), {0: 'USES_UNCALIBRATED_VALUE'},),
         0b0000000000000000.to_bytes(length=2, byteorder='big'),
         0,
         'USES_UNCALIBRATED_VALUE'),
        (space_packet_parser.xtce.parameter_types.EnumeratedParameterType(
            'TEST_NEGATIVE_ENUM',
            encodings.IntegerDataEncoding(16, 'signed'), {-42: 'VAL_LOW'}),
         0b1111111111010110.to_bytes(length=2, byteorder='big'),
         -42,
         'VAL_LOW'),
        (space_packet_parser.xtce.parameter_types.EnumeratedParameterType(name='TEST_FLOAT_ENUM',
                                                                          encoding=encodings.FloatDataEncoding(
                                                size_in_bits=32,
                                                encoding='IEEE754',
                                                byte_order="mostSignificantByteFirst"),
                                                                          # NOTE: Duplicate final value is on purpose to make sure we handle that case
                                                                          enumeration={0.0: 'BOOT_POR', 3.5: 'BOOT_RETURN', 2.2: 'OP_LOW',
                                                         3.3: 'OP_HIGH',
                                                         4.4: 'OP_HIGH'}),
         0b01000000011000000000000000000000.to_bytes(length=4, byteorder='big'),
         3.5,
         "BOOT_RETURN"
         ),
        (space_packet_parser.xtce.parameter_types.EnumeratedParameterType(name='TEST_ENUM_Type',
                                                                          encoding=encodings.StringDataEncoding(fixed_raw_length=16),
                                                                          # NOTE: Duplicate final value is on purpose to make sure we handle that case
                                                                          enumeration={b"AA": 'BOOT_POR',
                                                         b"BB": 'BOOT_RETURN',
                                                         b"CC": 'OP_LOW',
                                                         b"DD": 'OP_HIGH',
                                                         b"EE": 'OP_HIGH'}),
         b'CCXXXX',
         b'CC',
         "OP_LOW")
    ]
)
def test_enumerated_parameter_parsing(parameter_type, raw_data, expected_raw, expected):
    """Test parsing enumerated parameters"""
    packet = packets.Packet(raw_data=raw_data)
    value = parameter_type.parse_value(packet)
    assert value == expected
    assert value.raw_value == expected_raw


@pytest.mark.parametrize(
    ('parameter_type', 'raw_data', 'expected'),
    [
        # fixed size
        (space_packet_parser.xtce.parameter_types.BinaryParameterType(
            'TEST_BIN',
            encodings.BinaryDataEncoding(fixed_size_in_bits=16)),
         0b0011010000110010010100110000000001001011000000000100100100000000.to_bytes(length=8, byteorder='big'),
         b'42'),
        # discrete lookup list size
        (space_packet_parser.xtce.parameter_types.BinaryParameterType(
            'TEST_BIN',
            encodings.BinaryDataEncoding(size_discrete_lookup_list=[
                comparisons.DiscreteLookup([
                    comparisons.Comparison(required_value=7.4, referenced_parameter='P1',
                                           operator='==', use_calibrated_value=True)
                ], lookup_value=2)
            ], linear_adjuster=lambda x: 8 * x)),
         0b0011010000110010010100110000000001001011000000000100100100000000.to_bytes(length=8, byteorder='big'),
         b'42'),
        # dynamic size reference to other parameter
        (space_packet_parser.xtce.parameter_types.BinaryParameterType(
            'TEST_BIN',
            encodings.BinaryDataEncoding(size_reference_parameter='BIN_LEN',
                                         use_calibrated_value=False, linear_adjuster=lambda x: 8 * x)),
         0b0011010000110010010100110000000001001011000000000100100100000000.to_bytes(length=8, byteorder='big'),
         b'42'),
    ]
)
def test_binary_parameter_parsing(parameter_type, raw_data, expected):
    """Test parsing binary parameters"""
    # pre parsed data to reference for lookups
    packet = packets.Packet(raw_data=raw_data, **{
        'P1': common.FloatParameter(7.4, 1),
        'BIN_LEN': common.IntParameter(2)})
    value = parameter_type.parse_value(packet)
    assert value == expected


@pytest.mark.parametrize(
    ('parameter_type', 'raw_data', 'current_pos', 'expected_raw', 'expected_derived'),
    [
        (space_packet_parser.xtce.parameter_types.BooleanParameterType(
            'TEST_BOOL',
            encodings.BinaryDataEncoding(fixed_size_in_bits=1)),
         0b0011010000110010010100110000000001001011000000000100100100000000.to_bytes(length=64, byteorder='big'),
         0,
         b'\x00', True),
        (space_packet_parser.xtce.parameter_types.BooleanParameterType(
            'TEST_BOOL',
            encodings.StringDataEncoding(fixed_raw_length=120, encoding="UTF-8")),
         b'false_is_truthyextradata',
         0,
         b'false_is_truthy', True),
        (space_packet_parser.xtce.parameter_types.BooleanParameterType(
            'TEST_BOOL',
            encodings.IntegerDataEncoding(size_in_bits=2, encoding="unsigned")),
         0b0011.to_bytes(length=1, byteorder='big'),
         0,
         0, False),
        (space_packet_parser.xtce.parameter_types.BooleanParameterType(
            'TEST_BOOL',
            encodings.IntegerDataEncoding(size_in_bits=2, encoding="unsigned")),
         0b00001111.to_bytes(length=1, byteorder='big'),
         4,
         3, True),
        (space_packet_parser.xtce.parameter_types.BooleanParameterType(
            'TEST_BOOL',
            encodings.FloatDataEncoding(size_in_bits=16)),
         0b01010001010000001111111110000000.to_bytes(length=4, byteorder='big'),
         0,
         42.0, True),
        (space_packet_parser.xtce.parameter_types.BooleanParameterType(
            'TEST_BOOL',
            encodings.FloatDataEncoding(size_in_bits=16)),
         0b00000000101000101000000111111111.to_bytes(length=4, byteorder='big'),
         7,
         42.0, True),
    ]
)
def test_boolean_parameter_parsing(parameter_type, raw_data, current_pos, expected_raw, expected_derived):
    """Test parsing boolean parameters"""
    packet = packets.Packet(raw_data=raw_data)
    packet.raw_data.pos = current_pos
    value = parameter_type.parse_value(packet)
    assert value.raw_value == expected_raw
    assert value == expected_derived


@pytest.mark.parametrize(
    ('parameter_type', 'raw_data', 'current_pos', 'expected_raw', 'expected_derived'),
    [
        (space_packet_parser.xtce.parameter_types.AbsoluteTimeParameterType(name='TEST_PARAM_Type', unit='seconds',
                                                                            encoding=encodings.IntegerDataEncoding(size_in_bits=32,
                                                                                     encoding="unsigned"),
                                                                            epoch="TAI", offset_from="MilliSeconds"),
         # Exactly 64 bits so neatly goes into a bytes object without padding
         0b0011010000110010010100110000000001001011000000000100100100000000.to_bytes(length=8, byteorder='big'),
         0,
         875713280, 875713280),
        (space_packet_parser.xtce.parameter_types.AbsoluteTimeParameterType(
            name='TEST_PARAM_Type', unit='s',
            encoding=encodings.IntegerDataEncoding(
                size_in_bits=32, encoding="unsigned",
                default_calibrator=calibrators.PolynomialCalibrator(
                    coefficients=[
                        calibrators.PolynomialCoefficient(0, 0),
                        calibrators.PolynomialCoefficient(1E-6, 1)
                    ])),
            epoch="2009-10-10T12:00:00-05:00", offset_from="MilliSeconds"),
         # Exactly 64 bits so neatly goes into a bytes object without padding
         0b0011010000110010010100110000000001001011000000000100100100000000.to_bytes(length=8, byteorder='big'),
         0,
         875713280, 875.7132799999999),
        (space_packet_parser.xtce.parameter_types.AbsoluteTimeParameterType(
            name='TEST_PARAM_Type', unit='s',
            encoding=encodings.FloatDataEncoding(
                size_in_bits=32, encoding="IEEE754",
                default_calibrator=calibrators.PolynomialCalibrator(
                    coefficients=[
                        calibrators.PolynomialCoefficient(147.884, 0),
                        calibrators.PolynomialCoefficient(1, 1)
                    ]))),
         # 65 bits, so we need a 9th byte with 7 bits of padding to hold it,
         # which means we need to be starting at pos=7
         0b01000000010010010000111111011011001001011000000000100100100000000.to_bytes(length=9, byteorder='big'),
         7,
         3.1415927, 151.02559269999998),
    ]
)
def test_absolute_time_parameter_parsing(parameter_type, raw_data, current_pos, expected_raw, expected_derived):
    packet = packets.Packet(raw_data=raw_data)
    packet.raw_data.pos = current_pos
    value = parameter_type.parse_value(packet)
    assert value.raw_value == pytest.approx(expected_raw, rel=1E-6)
    # NOTE: derived values are rounded for comparison due to imprecise storage of floats
    assert value == pytest.approx(expected_derived, rel=1E-6)


@pytest.mark.parametrize(
    ("param_xml", "param_object"),
    [
        (f"""
<xtce:Parameter xmlns:xtce="{XTCE_1_2_XMLNS}" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" name="TEST_INT" parameterTypeRef="TEST_INT_Type" shortDescription="Param short desc">
  <xtce:LongDescription>This is a long description of the parameter</xtce:LongDescription>
</xtce:Parameter>
""",
         parameters.Parameter(name='TEST_INT',
                              parameter_type=space_packet_parser.xtce.parameter_types.IntegerParameterType(
                                  name='TEST_INT_Type',
                                  unit='floops',
                                  encoding=encodings.IntegerDataEncoding(size_in_bits=16, encoding='unsigned')),
                              short_description="Param short desc",
                              long_description="This is a long description of the parameter")
         )
    ]
)
def test_parameter(elmaker, xtce_parser, param_xml, param_object):
    """Test Parameter"""
    assert ElementTree.tostring(param_object.to_xml(elmaker=elmaker), pretty_print=True) == ElementTree.tostring(ElementTree.fromstring(param_xml, parser=xtce_parser), pretty_print=True)
