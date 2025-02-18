"""Space Packet Parser"""
from pathlib import Path
from typing import Union

from space_packet_parser.xtce.definitions import XtcePacketDefinition


def load_xml(filename: Union[str, Path]) -> XtcePacketDefinition:
    """Create an XtcePacketDefinition object from an XTCE XML file

    Parameters
    ----------
    filename : Union[str, Path]
        XTCE XML file

    Returns
    -------
    : definitions.XtcePacketDefinition
    """
    return XtcePacketDefinition.from_xtce(filename)
