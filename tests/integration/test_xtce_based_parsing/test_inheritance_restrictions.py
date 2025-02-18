"""Test RestrictionCriteria being used creatively with JPSS data"""
from space_packet_parser import packets
from space_packet_parser.xtce import definitions, containers


def test_jpss_xtce_packet_parsing(jpss_test_data_dir):
    """Test parsing a real XTCE document"""
    jpss_xtce = jpss_test_data_dir / 'contrived_inheritance_structure.xml'
    jpss_definition = definitions.XtcePacketDefinition.from_xtce(xtce_document=jpss_xtce)
    assert isinstance(jpss_definition, definitions.XtcePacketDefinition)

    jpss_packet_file = jpss_test_data_dir / 'J01_G011_LZ_2021-04-09T00-00-00Z_V01.DAT1'
    with jpss_packet_file.open('rb') as binary_data:
        jpss_packet_generator = jpss_definition.packet_generator(binary_data)
        for _ in range(3):  # Iterate through 3 packets and check that the parsed APID remains the same
            jpss_packet = next(jpss_packet_generator)
            assert isinstance(jpss_packet, packets.Packet)
            assert jpss_packet['PKT_APID'] == 11
            assert jpss_packet['VERSION'] == 0
        jpss_packet_generator.close()
