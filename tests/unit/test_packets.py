"""Tests for packets"""
# Standard
import pytest
# Local
from space_packet_parser import packets


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
def test_raw_packet_data(raw_value, start, nbits, expected):
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


def test_ccsds_packet():
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
