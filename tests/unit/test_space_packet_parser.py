"""Tests for main space_packet_parser.__init__ module"""
import space_packet_parser
from space_packet_parser.xtce import definitions


def test_load_xml(jpss_test_data_dir, tmp_path):
    xtcedef = space_packet_parser.load_xml(jpss_test_data_dir / "jpss1_geolocation_xtce_v1.xml")
    assert isinstance(xtcedef, definitions.XtcePacketDefinition)

    outpath = tmp_path / "test_output.xml"
    xtcedef.write_xml(outpath)
    assert outpath.exists()

    with outpath.open('r') as f:
        print(f.read())

    assert space_packet_parser.load_xml(outpath) == xtcedef
