"""XTCE module

This module contains Python object representations of XTCE UML/XML models
"""
DEFAULT_XTCE_NS_PREFIX = "xtce"  # Standard XTCE prefix using in xmlns:prefix="url" attribute

XTCE_1_2_XSD_URL = "https://www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd"
XTCE_1_2_XMLNS = "https://www.omg.org/spec/XTCE/20180204"

XTCE_1_1_XSD_URL = "https://www.omg.org/spec/XTCE/20061101/06-11-06.xsd"
XTCE_1_1_XMLNS = "https://www.omg.org/spec/XTCE/20061101"

# Note: There is no XSD available from omg.org for XTCE 1.0

XTCE_URI = XTCE_1_2_XMLNS
DEFAULT_XTCE_NSMAP = {
    DEFAULT_XTCE_NS_PREFIX: XTCE_1_2_XMLNS,
    "xsi": 'http://www.w3.org/2001/XMLSchema-instance'
}


