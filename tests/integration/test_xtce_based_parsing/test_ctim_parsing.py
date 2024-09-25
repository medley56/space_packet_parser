"""Test parsing of CTIM instrument data"""
# Local
from space_packet_parser import definitions


def test_ctim_parsing(ctim_test_data_dir):
    """Test parsing CTIM data"""
    print("Loading and parsing packet definition")
    test_xtce = ctim_test_data_dir / 'ctim_xtce_v1.xml'
    pkt_def = definitions.XtcePacketDefinition(test_xtce)
    print("Done")

    print("Loading and parsing data")
    test_packet_file = ctim_test_data_dir / 'ccsds_2021_155_14_39_51'
    with open(test_packet_file, 'rb') as pkt_file:
        pkt_gen = pkt_def.packet_generator(pkt_file,
                                           root_container_name="CCSDSTelemetryPacket",
                                           show_progress=True)
        packets = list(pkt_gen)

    assert len(packets) == 1499
    assert packets[159]['PKT_APID'].raw_value == 34
    assert packets[159]['SHCOARSE'].raw_value == 481168702
    apids = {p["PKT_APID"].raw_value for p in packets}
    print(apids)
