#!/usr/bin/env python3

"""Command line interface to the Space Packet Parsing library.

This module serves as a command line utility to inspect and process packet data.

Use
---
    spp <command> [<args>]
    spp --help
    spp --describe <packet_file>
"""

import logging
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.logging import RichHandler

from space_packet_parser.packets import packet_generator

# Initialize a console instance for rich output
console = Console()

# Maximum number of rows to display
MAX_ROWS = 10
HEAD_ROWS = 5


@click.group()
@click.version_option()
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug output"
)
@click.option(
    "-v", "--verbose", is_flag=True, help="Enable verbose output"
)
def cli(debug, verbose):
    """Command line utility for working with CCSDS packets."""
    # Set logging level
    loglevel = logging.WARNING
    if debug:
        loglevel = logging.DEBUG
    elif verbose:
        loglevel = logging.INFO

    # Configure logging with RichHandler for colorized output
    logging.basicConfig(
        level=loglevel,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)]
    )
    logging.getLogger("rich").setLevel(loglevel)


@cli.command()
@click.argument("packet_file", type=click.Path(exists=True, path_type=Path))
def describe(packet_file: Path) -> None:
    """Describe the contents of a packet file."""
    logging.debug(f"Describing packet file: {packet_file}")
    with open(packet_file, "rb") as f:
        packets = list(packet_generator(f))

    npackets = len(packets)
    if npackets == 0:
        console.print(f"No packets found in {packet_file}")
        return

    # Create table for packet data display
    table = Table(title=f"[bold magenta]{packet_file}: {npackets} packets[/bold magenta]",
                  show_header=True,
                  header_style="bold magenta")

    # Add columns dynamically based on the first packet's keys
    for key in packets[0]:
        table.add_column(key)

    # Determine rows to display (head and tail with ellipsis if necessary)
    if npackets > MAX_ROWS:
        packets_to_show = packets[:HEAD_ROWS] + packets[-HEAD_ROWS:]
    else:
        packets_to_show = packets

    # Add rows to the table
    for packet in packets_to_show[:HEAD_ROWS]:
        table.add_row(*[str(value) for value in packet.values()])

    # Add ellipsis if there are more packets
    if npackets > MAX_ROWS:
        table.add_row(*["..." for _ in packets[0]])

    for packet in packets_to_show[-HEAD_ROWS:]:
        table.add_row(*[str(value) for value in packet.values()])

    # Print the table
    console.print(table, overflow="ellipsis")
