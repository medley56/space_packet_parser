"""Tests for space_packet_parser.parser"""
# Installed
import pytest
# Local
from space_packet_parser import parser


@pytest.mark.parametrize(
    ('name', 'raw_value', 'unit', 'derived_value', 'short_description', 'long_description', 'valid'),
    [
        ('TEST', 0, 'smoots', 10, "short", "long", True),
        ('TEST', 10, None, None, None, None, True),
        (None, 10, 'foo', 10, None, None, False),
        ('TEST', None, None, None, None, None, False)
    ]
)
def test_parsed_data_item(name, raw_value, unit, derived_value, short_description, long_description, valid):
    """Test ParsedDataItem"""
    pdi = parser.ParsedDataItem(name, raw_value, unit, derived_value, short_description, long_description)
    assert pdi.name == name
    assert pdi.raw_value == raw_value
    assert pdi.unit == unit
    assert pdi.derived_value == derived_value
    assert pdi.short_description == short_description
    assert pdi.long_description == long_description
