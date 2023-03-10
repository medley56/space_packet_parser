"""Tests for the CSV based packet definition"""
# Installed
import bitstring
import pytest
# Local
from space_packet_parser import csvdef, xtcedef, parser
from space_packet_parser.csvdef import CsvPacketDefinition


@pytest.mark.parametrize(
    ('dtype_str', 'name', 'expectation'),
    [
        ('U11', 'test_uint', xtcedef.IntegerParameterType(name='test_uint',
                                                          encoding=xtcedef.IntegerDataEncoding(11, 'unsigned'),
                                                          unit='foo')),
        ('U5', 'test_uint', xtcedef.IntegerParameterType(name='test_uint',
                                                         encoding=xtcedef.IntegerDataEncoding(5, 'unsigned'),
                                                         unit='foo')),
        ('UINT11', 'test_uint', xtcedef.IntegerParameterType(name='test_uint',
                                                             encoding=xtcedef.IntegerDataEncoding(11, 'unsigned'),
                                                             unit='foo')),
        ('D3', 'test_discrete', xtcedef.IntegerParameterType(name='test_discrete',
                                                             encoding=xtcedef.IntegerDataEncoding(3, 'unsigned'),
                                                             unit='foo')),
        ('INT16', 'test_uint', xtcedef.IntegerParameterType(name='test_uint',
                                                            encoding=xtcedef.IntegerDataEncoding(16, 'signed'),
                                                            unit='foo')),
        ('I16', 'test_uint', xtcedef.IntegerParameterType(name='test_uint',
                                                          encoding=xtcedef.IntegerDataEncoding(16, 'signed'),
                                                          unit='foo')),
        ('F16', 'test_flt', xtcedef.FloatParameterType(name='test_flt',
                                                       encoding=xtcedef.FloatDataEncoding(16),
                                                       unit='foo')),
        ('Float16', 'test_flt', xtcedef.FloatParameterType(name='test_flt',
                                                           encoding=xtcedef.FloatDataEncoding(16),
                                                           unit='foo')),
        ('C12', 'test_str', xtcedef.StringParameterType(name='test_str',
                                                        encoding=xtcedef.StringDataEncoding(fixed_length=12),
                                                        unit='foo'))
    ]
)
def test_get_param_type_from_str(dtype_str: str, name, expectation):
    actual = csvdef.CsvPacketDefinition.get_param_type_from_str(dtype=dtype_str,
                                                                param_type_name=name,
                                                                unit='foo')

    assert (actual == expectation)

# TODO: Test the elements of


def test_csv_packet_definition(ctim_test_data_dir):
    """Test parsing a real csv document"""
    test_csv_file = ctim_test_data_dir / 'ct_tlm.csv'
    csv_pkt_def = CsvPacketDefinition(test_csv_file)
    assert isinstance(csv_pkt_def, CsvPacketDefinition)

    test_packet_file = ctim_test_data_dir / 'ccsds_2021_155_14_39_51'
    pkt_binary_data = bitstring.ConstBitStream(filename=test_packet_file)

    parser_inst = parser.PacketParser(csv_pkt_def)
    pkt_gen = parser_inst.generator(pkt_binary_data)

    packet = next(pkt_gen)
    assert isinstance(packet, parser.Packet)
