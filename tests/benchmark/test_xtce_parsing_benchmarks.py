"""Benchmark test for how fast we can parse a large XTCE definition file"""
import pytest

from space_packet_parser.xtce import definitions


@pytest.mark.benchmark
def test_benchmark_ctim_xtce_parsing(ctim_test_data_dir, benchmark):
    """This XTCE file is quite large and at one point took several seconds to parse.

    We've got that number to under .1s and aim to keep it that way
    """
    xtce_document = ctim_test_data_dir / "ctim_xtce_v1.xml"
    packet_definition = benchmark(definitions.XtcePacketDefinition.from_xtce, xtce_document)
    print("Number of containers:", len(packet_definition.containers))
    print("Number of parameters:", len(packet_definition.parameters))
    print("Number of parameter types:", len(packet_definition.parameter_types))
