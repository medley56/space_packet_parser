"""Tests for packets"""
# Standard
import pytest
# Local
from space_packet_parser import definitions, packets


@pytest.mark.parametrize(("input_var", "input_value"),
                         [("version_number", 0), ("version_number", 7),
                          ("type", 0), ("type", 1),
                          ("secondary_header_flag", 0), ("secondary_header_flag", 1),
                          ("apid", 0), ("apid", 2**11 - 1),
                          ("sequence_flags", 0), ("sequence_flags", 3),
                          ("sequence_count", 0), ("sequence_count", 2**14 - 1),
                          ("data", bytes(1)), pytest.param("data", bytes(65536), id="max-bytes")])
def test_create_ccsds_packet_input_range(input_var, input_value):
    """Validate the min/max integer inputs"""
    p = packets.create_ccsds_packet(**{input_var: input_value})
    if input_var == "data":
        assert p[6:] == input_value
    else:
        assert getattr(p, input_var) == input_value


@pytest.mark.parametrize(("input_var", "input_value"),
                         [("version_number", -1), ("version_number", 8),
                          ("type", -1), ("type", 2),
                          ("secondary_header_flag", -1), ("secondary_header_flag", 2),
                          ("apid", -1), ("apid", 2**11),
                          ("sequence_flags", -1), ("sequence_flags", 4),
                          ("sequence_count", -1), ("sequence_count", 2**14),
                          ("data", bytes(0)), pytest.param("data", bytes(65537), id="max-bytes")])
def test_create_ccsds_packet_value_range_error(input_var, input_value):
    """Validate the min/max integer inputs"""
    with pytest.raises(ValueError):
        packets.create_ccsds_packet(**{input_var: input_value})

@pytest.mark.parametrize("input_var", ["version_number", "type", "secondary_header_flag", "apid",
                                       "sequence_flags", "sequence_count", "data"])
@pytest.mark.parametrize("input_value", [1.0, "1", 0.5])
def test_create_ccsds_packet_type_validation(input_var, input_value):
    """Only integers are allowed for the header fields and bytes for the data field."""
    with pytest.raises(TypeError):
        packets.create_ccsds_packet(**{input_var: input_value})


def test_raw_packet_attributes():
    p = packets.create_ccsds_packet(data=b"123", version_number=3, type=1, secondary_header_flag=1, 
                                    apid=1234, sequence_flags=2, sequence_count=5)
    assert p.version_number == 3
    assert p.type == 1
    assert p.secondary_header_flag == 1
    assert p.apid == 1234
    assert p.sequence_flags == 2
    assert p.sequence_count == 5
    assert len(p) == 6 + 3
    assert p[6:] == b"123"


@pytest.mark.parametrize(("raw_value", "start", "nbits", "expected"),
                         [(0b11000000, 0, 2, 0b11),
                          (0b11000000, 1, 2, 0b10),
                          (0b11000000, 2, 2, 0b00),
                          (0b11000011, 6, 2, 0b11),
                          (0b11000011, 7, 1, 0b1),
                          # Go across byte boundaries
                          (0b1100001111000011, 6, 4, 0b1111),
                          (0b1100001111000011, 6, 6, 0b111100),
                          (0b1100001111000011, 8, 6, 0b110000),
                          (0b1100001111000011, 8, 8, 0b11000011),
                          # Multiple bytes
                          (0b110000111100001100000000, 8, 10, 0b1100001100),
                          (0b110000111100001100000000, 0, 24, 0b110000111100001100000000)])
def test_raw_packet_reads(raw_value, start, nbits, expected):
    raw_bytes = raw_value.to_bytes((raw_value.bit_length() + 7) // 8, "big")
    raw_packet = packets.RawPacketData(raw_bytes)
    raw_packet.pos = start
    assert raw_packet.read_as_int(nbits) == expected
    assert raw_packet.pos == start + nbits
    # Reset the position and read again but as raw bytes this time
    raw_packet.pos = start
    # the value 0 has a bit_length of 0, so we need to ensure we have at least 1 byte
    assert raw_packet.read_as_bytes(nbits) == expected.to_bytes((max(expected.bit_length(), 1) + 7) // 8, "big")
    assert raw_packet.pos == start + nbits


def test_ccsds_packet_data_lookups():
    packet = packets.CCSDSPacket(raw_data=b"123")
    assert packet.raw_data == b"123"
    # There are no items yet, so it should be an empty dictionary
    assert packet == {}
    assert packet.header == {}
    assert packet.user_data == {}
    # Now populated some packet items
    packet.update({x: x for x in range(10)})
    assert packet[5] == 5
    assert packet == {x: x for x in range(10)}
    # The header is the first 7 items
    assert packet.header == {x: x for x in range(7)}
    assert packet.user_data == {x: x for x in range(7, 10)}

    with pytest.raises(KeyError):
        packet[10]


def test_continuation_packets(test_data_dir):
    # This definition has 65 bytes worth of data
    d = definitions.XtcePacketDefinition(test_data_dir / "test_xtce.xml")
    # We can put that all in one unsegmented packet, just to verify this is working as expected
    raw_bytes = packets.create_ccsds_packet(data=b"0"*65, apid=11, sequence_flags=packets.SequenceFlags.UNSEGMENTED)
    orig_packets = list(d.packet_generator(raw_bytes))
    assert len(orig_packets) == 1
    # Remove the sequence flags, counter, and packet length, as they are expected to vary across tests
    def remove_keys(d):
        d.pop("SEQ_FLGS")
        d.pop("PKT_LEN")
        d.pop("SRC_SEQ_CTR")
    remove_keys(orig_packets[0])

    # Now we will split the data across 2 CCSDS packets, but expect them to be combined into one for parsing purposes
    p0 = packets.create_ccsds_packet(data=b"0"*64, apid=11, sequence_flags=packets.SequenceFlags.FIRST, sequence_count=0)
    p1 = packets.create_ccsds_packet(data=b"0"*1, apid=11, sequence_flags=packets.SequenceFlags.LAST, sequence_count=1)
    raw_bytes = p0 + p1
    result_packets = list(d.packet_generator(raw_bytes, combine_segmented_packets=True))
    remove_keys(result_packets[0])
    assert result_packets == orig_packets

    # Now we will split the data across 3 CCSDS packets and test the sequence_count wrap-around
    p0 = packets.create_ccsds_packet(data=b"0"*63, apid=11, sequence_flags=packets.SequenceFlags.FIRST, sequence_count=16382)
    p1 = packets.create_ccsds_packet(data=b"0"*1, apid=11, sequence_flags=packets.SequenceFlags.CONTINUATION, sequence_count=16383)
    p2 = packets.create_ccsds_packet(data=b"0"*1, apid=11, sequence_flags=packets.SequenceFlags.LAST, sequence_count=0)
    raw_bytes = p0 + p1 + p2
    result_packets = list(d.packet_generator(raw_bytes, combine_segmented_packets=True))
    remove_keys(result_packets[0])
    assert result_packets == orig_packets

    # Test stripping secondary headers (4 bytes per packet), should keep the first packet's header, but skip the following
    # Add in 4 1s to the 2nd and 3rd packet that should be removed
    p0 = packets.create_ccsds_packet(data=b"0"*63, apid=11, sequence_flags=packets.SequenceFlags.FIRST, sequence_count=16382)
    p1 = packets.create_ccsds_packet(data=b"1"*4 + b"0"*1, apid=11, sequence_flags=packets.SequenceFlags.CONTINUATION, sequence_count=16383)
    p2 = packets.create_ccsds_packet(data=b"1"*4 + b"0"*1, apid=11, sequence_flags=packets.SequenceFlags.LAST, sequence_count=0)
    raw_bytes = p0 + p1 + p2
    result_packets = list(d.packet_generator(raw_bytes, combine_segmented_packets=True, secondary_header_bytes=4))
    remove_keys(result_packets[0])
    assert result_packets == orig_packets


def test_continuation_packet_warnings(test_data_dir):
    # This definition has 65 bytes worth of data
    d = definitions.XtcePacketDefinition(test_data_dir / "test_xtce.xml")

    # CONTINUATION / LAST without FIRST
    p0 = packets.create_ccsds_packet(data=b"0"*65, apid=11, sequence_flags=packets.SequenceFlags.CONTINUATION)
    p1 = packets.create_ccsds_packet(data=b"0"*65, apid=11, sequence_flags=packets.SequenceFlags.LAST)
    raw_bytes = p0 + p1
    with pytest.warns(match="Continuation packet found without declaring the start"):
        list(d.packet_generator(raw_bytes, combine_segmented_packets=True))
        # Nothing expected to be returned
        assert len(list(d.packet_generator(raw_bytes, combine_segmented_packets=True))) == 0

    # Out of sequence packets
    p0 = packets.create_ccsds_packet(data=b"0"*65, apid=11, sequence_flags=packets.SequenceFlags.FIRST, sequence_count=1)
    p1 = packets.create_ccsds_packet(data=b"0"*65, apid=11, sequence_flags=packets.SequenceFlags.LAST, sequence_count=0)
    raw_bytes = p0 + p1

    with pytest.warns(match="not in sequence"):
        # Nothing expected to be returned
        assert len(list(d.packet_generator(raw_bytes, combine_segmented_packets=True))) == 0
