"""Common mixins"""
import inspect
from abc import ABCMeta, abstractmethod
from typing import Optional, Protocol, Union

import lxml.etree as ElementTree
from lxml.builder import ElementMaker

from space_packet_parser import packets


# Common comparable mixin
class AttrComparable(metaclass=ABCMeta):
    """Generic class that provides a notion of equality based on all non-callable, non-dunder attributes"""

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            raise NotImplementedError(f"No method to compare {type(other)} with {self.__class__}")

        compare = inspect.getmembers(self, lambda a: not inspect.isroutine(a))
        compare = [attr[0] for attr in compare
                   if not (attr[0].startswith('__') or attr[0].startswith(f'_{self.__class__.__name__}__'))]
        for attr in compare:
            if getattr(self, attr) != getattr(other, attr):
                print(f'Mismatch was in {attr}. {getattr(self, attr)} != {getattr(other, attr)}')
                return False
        return True


class XmlObject(metaclass=ABCMeta):
    """ABC that requires `to_xml_element` and `from_xml_element` methods for parsing and serializing
    a library object from an XML element object.
    """

    @classmethod
    @abstractmethod
    def from_xml(
            cls,
            element: ElementTree.Element,
            *,
            ns: dict,
            tree: Optional[ElementTree.ElementTree],
            parameter_lookup: Optional[dict[str, any]],
            parameter_type_lookup: Optional[dict[str, any]],
    ) -> 'XmlObject':
        """Create an object from an XML element

        Notes
        -----
        This abstract implementation has a signature that includes all possible parameters to this function
        across our XML object classes in order to satisfy Liskov Substitution. It also makes it clear that you
        _can_ pass this information in to from_xml but depending on the subtype implementation, it may be ignored.

        Parameters
        ----------
        element : ElementTree.Element
            XML element from which to parse the object
        ns : dict
            XML namespace mapping
        tree: Optional[ElementTree.ElementTree]
            Full XML tree for parsing that requires access to other elements
        parameter_lookup: Optional[dict[str, parameters.ParameterType]]
            Parameters dict for parsing that requires knowledge of existing parameters
        parameter_type_lookup: Optional[dict[str, parameters.ParameterType]]
            Parameter type dict for parsing that requires knowledge of existing parameter types

        Returns
        -------
        : cls
        """
        raise NotImplementedError()

    @abstractmethod
    def to_xml(self, *, elmaker: ElementMaker) -> ElementTree.Element:
        """Create an XML element from the object self

        Parameters
        ----------
        elmaker : ElementMaker
            ElementMaker for creating new XML elements with predefined namespace

        Returns
        -------
        : ElementTree.Element
            XML Element object
        """
        raise NotImplementedError()


class Parseable(Protocol):
    """Defines an object that can be parsed from packet data."""
    def parse(self, packet: packets.CCSDSPacket) -> None:
        """Parse this entry from the packet data and add the necessary items to the packet."""



BuiltinDataTypes = Union[bytes, float, int, str]

class _Parameter:
    """Mixin class for storing access to the raw value of a parsed data item.

    The raw value is the closest representation of the data item as it appears in the packet.
    e.g. bytes for binary data, int for integer data, etc. It has not been calibrated or
    adjusted in any way and is an easy way for user's to debug the transformations that
    happened after the fact.

    Notes
    -----
    We need to override the __new__ method to store the raw value of the data item
    on immutable built-in types. So this is just a way of allowing us to inject our
    own attribute into the built-in types.
    """
    def __new__(cls, value: BuiltinDataTypes, raw_value: BuiltinDataTypes = None) -> BuiltinDataTypes:
        obj = super().__new__(cls, value)
        # Default to the same value as the parsed value if it isn't provided
        obj.raw_value = raw_value if raw_value is not None else value
        return obj


class BinaryParameter(_Parameter, bytes):
    """A class to represent a binary data item."""


class BoolParameter(_Parameter, int):
    """A class to represent a parsed boolean data item."""
    # A bool is a subclass of int, so all we are really doing here
    # is making a nice representation using the bool type because
    # bool can't be subclassed directly.
    def __repr__(self) -> str:
        return bool.__repr__(bool(self))


class FloatParameter(_Parameter, float):
    """A class to represent a float data item."""


class IntParameter(_Parameter, int):
    """A class to represent a integer data item."""


class StrParameter(_Parameter, str):
    """A class to represent a string data item."""


ParameterDataTypes = Union[BinaryParameter, BoolParameter, FloatParameter, IntParameter, StrParameter]
