"""Common mixins"""
import inspect
from abc import ABCMeta
from typing import Protocol

from space_packet_parser.packets import CCSDSPacket


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


class Parseable(Protocol):
    """Defines an object that can be parsed from packet data."""
    def parse(self, packet: CCSDSPacket) -> None:
        """Parse this entry from the packet data and add the necessary items to the packet."""
