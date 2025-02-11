"""Space Packet Parser"""
from pathlib import Path
from typing import Union

from space_packet_parser.xtce import definitions


def load_xml(filename: Union[str, Path]) -> definitions.XtcePacketDefinition:
    """Create an XtcePacketDefinition object from an XTCE XML file

    Parameters
    ----------
    filename : Union[str, Path]
        XTCE XML file

    Returns
    -------
    : definitions.XtcePacketDefinition
    """
    return definitions.XtcePacketDefinition.from_xtce(filename)
