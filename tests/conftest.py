"""Test fixtures"""
from pathlib import Path
import sys

import pytest
from lxml.builder import ElementMaker

from space_packet_parser.xtce import XTCE_URI, XTCE_NSMAP


@pytest.fixture(scope="session")
def elmaker():
    """ElementMaker for testing XML element creation"""
    return ElementMaker(namespace=XTCE_URI, nsmap=XTCE_NSMAP)


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
