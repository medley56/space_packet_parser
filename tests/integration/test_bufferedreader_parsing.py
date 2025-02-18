"""Integration test for parsing JPSS packets"""
# Local
from space_packet_parser import packets
from space_packet_parser.xtce import definitions


def test_jpss_xtce_packet_parsing(jpss_test_data_dir):
    """Test parsing a real XTCE document"""
    jpss_xtce = jpss_test_data_dir / 'jpss1_geolocation_xtce_v1.xml'
    jpss_definition = definitions.XtcePacketDefinition.from_xtce(xtce_document=jpss_xtce)
    assert isinstance(jpss_definition, definitions.XtcePacketDefinition)

    jpss_packet_file = jpss_test_data_dir / 'J01_G011_LZ_2021-04-09T00-00-00Z_V01.DAT1'

    with jpss_packet_file.open('rb') as binary_data:
        jpss_packet_generator = jpss_definition.packet_generator(binary_data, show_progress=True)
        n_packets = 0
        for jpss_packet in jpss_packet_generator:
            assert isinstance(jpss_packet, packets.Packet)
            assert jpss_packet['PKT_APID'] == 11
            assert jpss_packet['VERSION'] == 0
            n_packets += 1
        assert n_packets == 7200
