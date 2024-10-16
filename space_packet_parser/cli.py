#!/usr/bin/env python3

"""Command line interface to the Space Packet Parsing library.

This module serves as a command line utility to inspect and process packet data.

Use
---
    spp <command> [<args>]
    spp --help
    spp --describe <packet_file>
"""

import argparse
import importlib.metadata
import logging
from pathlib import Path

from space_packet_parser.packets import packet_generator


def _describe_packet_file(packet_file: Path) -> None:
    """Describe the contents of a packet file.

    Parameters
    ----------
    packet_file : Path
        Path to a packet file.
    """
    with open(packet_file, "rb") as f:
        packets = list(packet_generator(f))
    npackets = len(packets)
    print(f"Packet file: {packet_file}")
    print(f"Number of packets: {npackets}")
    if npackets == 0:
        return

    for key in packets[0]:
        print(f"{key:12s}", end="| ")
    print()
    if npackets > 10:
        first_packets = 5
    else:
        first_packets = npackets
    for packet in packets[:first_packets]:
        for value in packet.values():
            print(f"{value:12d}", end="| ")
        print()

    if npackets > 10:
        print("...")
        for packet in packets[-5:]:
            for value in packet.values():
                print(f"{value:12d}", end="| ")
            print()


def main():
    """Entrypoint for the command line program."""
    parser = argparse.ArgumentParser(prog="spp", description="command line utility for working with CCSDS packets")
    parser.add_argument("packet_file", type=Path, help="Path to a packet file")
    parser.add_argument("--describe", action="store_true", required=False, help="Describe a packet file")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {importlib.metadata.version('space_packet_parser')}",
        help="Show programs version number and exit. No other parameters needed.",
    )
    # Logging level
    parser.add_argument(
        "--debug",
        help="Print lots of debugging statements.",
        action="store_const",
        dest="loglevel",
        const=logging.DEBUG,
        default=logging.WARNING,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="Add verbose output",
        action="store_const",
        dest="loglevel",
        const=logging.INFO,
    )

    args = parser.parse_args()

    if args.describe:
        _describe_packet_file(args.packet_file)


if __name__ == "__main__":
    main()
