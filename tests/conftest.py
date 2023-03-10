"""Test fixtures"""
# Standard library
from pathlib import Path
import sys
# External modules
import pytest


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
