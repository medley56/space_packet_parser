"""Tests for space_packet_parser.parser"""
# Installed
import bitstring
import pytest
# Local
from space_packet_parser import parser


@pytest.mark.parametrize(
    ('name', 'raw_value', 'unit', 'derived_value', 'valid'),
    [
        ('TEST', 0, 'smoots', 10, True),
        ('TEST', 10, None, None, True),
        (None, 10, 'foo', 10, False),
        ('TEST', None, None, None, False)
    ]
)
def test_parsed_data_item(name, raw_value, unit, derived_value, valid):
    """Test ParsedDataItem"""
    if valid:
        pdi = parser.ParsedDataItem(name, raw_value, unit, derived_value)
    else:
        with pytest.raises(ValueError):
            pdi = parser.ParsedDataItem(name, raw_value, unit, derived_value)
