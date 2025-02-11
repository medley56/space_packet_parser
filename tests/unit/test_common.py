"""Tests for common module"""
import pytest

from space_packet_parser import common


def test_attr_comparable():
    """Test abstract class that allows comparisons based on all non-callable attributes"""

    class TestClass(common.AttrComparable):
        """Test Class"""

        def __init__(self, public, private, dunder):
            self.public = public
            self._private = private
            self.__dunder = dunder  # Dundered attributes are ignored (they get mangled by class name on construction)

        @property
        def entertained(self):
            """Properties are compared"""
            return 10 * self.public

        def ignored(self, x):
            """Methods are ignored"""
            return 2 * x

    a = TestClass(1, 2, 9)
    a.__doc__ = "foobar"  # Ignored dunder method
    b = TestClass(1, 2, 10)
    assert a == b
    a.public += 1  # Change an attribute that _does_ get compared
    with pytest.raises(AssertionError):
        assert a == b
