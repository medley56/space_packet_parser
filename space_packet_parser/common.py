"""Common mixins"""
import inspect
from abc import ABCMeta, abstractmethod
from typing import Optional, Protocol, Union

import lxml.etree as ElementTree
from lxml.builder import ElementMaker

from space_packet_parser import packets


class NamespaceAwareElement(ElementTree.ElementBase):
    """Custom element that automatically applies namespace mappings."""

    _nsmap: dict[str, str] = {}  # Class level namespace mapping
    _ns_prefix: Union[str, None] = None  # Class level namespace prefix for adding to Xpaths

    @classmethod
    def element_prefix(cls):
        """Create the XPath element prefix

        Notes
        -----
        If the prefix is None,
        it indicates either an implicit namespace such as `<SpaceSystem xmlns="http://xtce-example-ns-uri"/>`,
        where `nsmap` is `{None: "http://xtce-example-ns-uri", ...}`
        or no namespace awareness, such as `<SpaceSystem/>`,
        where `nsmap` does not contain any reference to a URI or prefix for the XTCE namespace
        (but may contain other namespace mappings).

        If the prefix is anything other than None,
        it must be a string and must be present in the namespace mapping dict and represents a prefixed namespace,
        such as `<xtce:SpaceSystem xmlns:xtce="http://xtce-example-ns-uri"/>`
        where `nsmap` would be `{"xtce": "http://xtce-example-ns-uri", ...}` and `ns_prefix` would be `xtce`.
        """
        if cls._ns_prefix is not None:
            if cls._ns_prefix not in cls._nsmap:
                raise ValueError(f"XTCE namespace prefix {cls._ns_prefix} not found in namespace mapping "
                                 f"{cls._nsmap}. If the namespace prefix is not 'None', it must appear as a key in the "
                                 f"namespace mapping dict.")
            return f"{cls._ns_prefix}:"
        return ""

    @classmethod
    def add_namespace_to_xpath(cls, xpath: str) -> str:
        """
        Adds a namespace prefix to each element in an XPath expression.

        Parameters
        ----------
        xpath : str
            The original XPath expression without namespace prefixes.

        Returns
        -------
        str
            The updated XPath expression with namespace prefixes.
        """
        prefix = cls.element_prefix()
        # Regex to match valid XML element names (avoids matching special characters like `@attr`, `.`, `*`, `()`, `::`)
        xpath_parts = xpath.split('/')
        new_parts = []

        for part in xpath_parts:
            # Skip empty parts (handles leading/trailing slashes)
            if not part:
                new_parts.append('')
                continue

            # Handle special cases (wildcards, functions, attributes, self, parent, axes)
            if part is None or part in {'.', '..', '*'} or part.startswith('@') or '::' in part or '(' in part:
                new_parts.append(part)
            else:
                new_parts.append(f"{prefix}{part}")

        new_path = '/'.join(new_parts)
        return new_path

    def find(self, path, namespaces=None):
        """Override find() to automatically use the stored namespace map."""
        if namespaces is None:
            namespaces = self.get_nsmap()
        return super().find(self.add_namespace_to_xpath(path), namespaces=namespaces)

    def findall(self, path, namespaces=None):
        """Override findall() to automatically use the stored namespace map."""
        if namespaces is None:
            namespaces = self.get_nsmap()
        return super().findall(self.add_namespace_to_xpath(path), namespaces=namespaces)

    def iterfind(self, path, namespaces=None):
        """Override iterfind() to automatically use the stored namespace map."""
        if namespaces is None:
            namespaces = self.get_nsmap()
        return super().iterfind(self.add_namespace_to_xpath(path), namespaces=namespaces)

    @classmethod
    def set_nsmap(cls, nsmap: dict):
        """Store the namespace map for all elements of this type."""
        cls._nsmap = nsmap

    def get_nsmap(self):
        """Retrieve the stored namespace map."""
        return self._nsmap

    @classmethod
    def set_ns_prefix(cls, ns_prefix: Union[str, None]):
        """Store the namespace map for all elements of this type."""
        cls._ns_prefix = ns_prefix

    def get_ns_prefix(self):
        """Retrieve the stored namespace map."""
        return self._ns_prefix


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
            tree: Optional[ElementTree.ElementTree],
            parameter_lookup: Optional[dict[str, any]],
            parameter_type_lookup: Optional[dict[str, any]],
            container_lookup: Optional[dict[str, any]],
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
        tree: Optional[ElementTree.ElementTree]
            Full XML tree for parsing that requires access to other elements
        parameter_lookup: Optional[dict[str, parameters.ParameterType]]
            Parameters dict for parsing that requires knowledge of existing parameters
        parameter_type_lookup: Optional[dict[str, parameters.ParameterType]]
            Parameter type dict for parsing that requires knowledge of existing parameter types
        container_lookup: Optional[dict[str, parameters.ContainerType]]
            Container type dict for parsing that requires knowledge of existing containers

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
