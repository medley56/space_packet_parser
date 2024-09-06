"""Tests for the CSV based packet definition"""
import pytest
# Local
from space_packet_parser import csvdef, parameters, encodings, parseables, parser
from space_packet_parser.csvdef import CsvPacketDefinition


@pytest.mark.parametrize(
    ('dtype_str', 'name', 'expectation'),
    [
        ('U11', 'test_uint', parameters.IntegerParameterType(name='test_uint',
                                                          encoding=encodings.IntegerDataEncoding(11, 'unsigned'),
                                                          unit='foo')),
        ('U5', 'test_uint', parameters.IntegerParameterType(name='test_uint',
                                                         encoding=encodings.IntegerDataEncoding(5, 'unsigned'),
                                                         unit='foo')),
        ('UINT11', 'test_uint', parameters.IntegerParameterType(name='test_uint',
                                                             encoding=encodings.IntegerDataEncoding(11, 'unsigned'),
                                                             unit='foo')),
        ('D3', 'test_discrete', parameters.IntegerParameterType(name='test_discrete',
                                                             encoding=encodings.IntegerDataEncoding(3, 'unsigned'),
                                                             unit='foo')),
        ('INT16', 'test_uint', parameters.IntegerParameterType(name='test_uint',
                                                            encoding=encodings.IntegerDataEncoding(16, 'signed'),
                                                            unit='foo')),
        ('I16', 'test_uint', parameters.IntegerParameterType(name='test_uint',
                                                          encoding=encodings.IntegerDataEncoding(16, 'signed'),
                                                          unit='foo')),
        ('F16', 'test_flt', parameters.FloatParameterType(name='test_flt',
                                                       encoding=encodings.FloatDataEncoding(16),
                                                       unit='foo')),
        ('Float16', 'test_flt', parameters.FloatParameterType(name='test_flt',
                                                           encoding=encodings.FloatDataEncoding(16),
                                                           unit='foo')),
        ('C12', 'test_str', parameters.StringParameterType(name='test_str',
                                                        encoding=encodings.StringDataEncoding(fixed_length=12),
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
    with open(test_packet_file, 'rb') as pkt_file:
        parser_inst = parser.PacketParser(csv_pkt_def)
        pkt_gen = parser_inst.generator(pkt_file, show_progress=True)
        packet = next(pkt_gen)
    assert isinstance(packet, parseables.Packet)
