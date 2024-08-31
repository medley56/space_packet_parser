"""Test parsing of CTIM packet data"""
# Local
from space_packet_parser import csvdef, parser


def test_csv_packet_definition_parsing(ctim_test_data_dir):
    """Test parsing a real csv document"""
    test_csv_file = ctim_test_data_dir / 'ct_tlm.csv'
    csv_pkt_def = csvdef.CsvPacketDefinition(test_csv_file)

    test_packet_file = ctim_test_data_dir / 'ccsds_2021_155_14_39_51'
    parser_inst = parser.PacketParser(csv_pkt_def)
    with open(test_packet_file, 'rb') as pkt_file:
        pkt_gen = parser_inst.generator(pkt_file, show_progress=True)
        packets = list(pkt_gen)

    assert(len(packets) == 1499)
    assert(packets[159].header['PKT_APID'].raw_value == 34)
    assert(packets[159].data['SHCOARSE'].raw_value == 481168702)
