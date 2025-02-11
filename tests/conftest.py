"""Test fixtures"""
from pathlib import Path
import sys

import pytest
from lxml import etree
from lxml.builder import ElementMaker

from space_packet_parser import common
from space_packet_parser.xtce import DEFAULT_XTCE_NSMAP, DEFAULT_XTCE_NS_PREFIX, XTCE_1_2_XMLNS


@pytest.fixture(scope="session")
def elmaker():
    """ElementMaker for testing XML element creation"""
    return ElementMaker(namespace=XTCE_1_2_XMLNS, nsmap=DEFAULT_XTCE_NSMAP)


@pytest.fixture
def xtce_parser():
    """Parser for testing that knows about the standard testing namespace we use"""
    el = common.NamespaceAwareElement
    el.set_nsmap(DEFAULT_XTCE_NSMAP)
    el.set_ns_prefix(DEFAULT_XTCE_NS_PREFIX)
    xtce_element_lookup = etree.ElementDefaultClassLookup(element=el)
    xtce_parser = etree.XMLParser()
    xtce_parser.set_element_class_lookup(xtce_element_lookup)
    return xtce_parser


@pytest.fixture
def test_data_dir():
    """Returns the test data directory"""
    return Path(sys.modules[__name__.split('.')[0]].__file__).parent / 'test_data'


@pytest.fixture
def ctim_test_data_dir(test_data_dir):
    """CTIM test data directory"""
    return test_data_dir / 'ctim'


@pytest.fixture
def jpss_test_data_dir(test_data_dir):
    """JPSS test data directory"""
    return test_data_dir / 'jpss'


@pytest.fixture
def clarreo_test_data_dir(test_data_dir):
    """CLARREO test data directory"""
    return test_data_dir / 'clarreo'


@pytest.fixture
def suda_test_data_dir(test_data_dir):
    """SUDA test data directory"""
    return test_data_dir / 'suda'


@pytest.fixture
def idex_test_data_dir(test_data_dir):
    """IDEX test data directory"""
    return test_data_dir / 'idex'
