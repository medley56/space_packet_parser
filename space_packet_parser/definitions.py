# NOTE: This entire file is deprecated and here just to maintain backwards compatibility.
# The functionality has been moved to space_packet_parser.xtce.definitions.XtcePacketDefinition
import warnings

from space_packet_parser.xtce import definitions

warnings.warn("The space_packet_parser.definitions module is deprecated. "
              "Use space_packet_parser.xtce.definitions instead (nested under xtce now).")


class XtcePacketDefinition(definitions.XtcePacketDefinition):
    def __init__(self, xtce_document, **kwargs):
        warnings.warn("This class is deprecated. To load a packet definition from a file "
                      "use space_packet_parser.load_xml() or "
                      "space_packet_parser.xtce.definitions.XtcePacketDefinition.from_xtce() instead.")
        other = definitions.XtcePacketDefinition.from_xtce(xtce_document)
        self.__dict__.update(other.__dict__)
