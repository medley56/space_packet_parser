"""Benchmarking test suite for Space Packet Parser

Each test in this suite tests a specific metric over time
"""
import pytest
from typing import Iterable

from space_packet_parser import definitions, packets


@pytest.mark.benchmark(
    warmup=True
)
def test_benchmark_complex_xtce_definition_parsing(benchmark, suda_test_data_dir):
    """Benchmark the time it takes to parse a specific, relatively complex XTCE packet definition document"""
    definition: definitions.XtcePacketDefinition = benchmark(
        definitions.XtcePacketDefinition,
        suda_test_data_dir / "suda_combined_science_definition.xml"
    )
    print(definition.named_parameters)
    print(definition.named_parameter_types)


@pytest.mark.benchmark
def test_benchmark_simple_packet_parsing(benchmark, jpss_test_data_dir):
    """Benchmark the time it takes to parse 7200 simple JPSS geolocation packets from a flat packet definition"""
    packet_definition = definitions.XtcePacketDefinition(jpss_test_data_dir / "jpss1_geolocation_xtce_v1.xml")
    packet_data = jpss_test_data_dir / "J01_G011_LZ_2021-04-09T00-00-00Z_V01.DAT1"

    # Open reusable filehandler
    packet_fh = packet_data.open("rb")

    try:
        def _setup():
            """Function that sets up for each benchmark round"""
            packet_fh.seek(0)
            packet_generator = packet_definition.packet_generator(packet_fh)
            return (), {"generator": packet_generator}  # args, kwargs for benchmarked function

        def _make_packet_list(generator: Iterable[packets.CCSDSPacket]):
            """Function wrapper for list that takes the generator as a kwarg"""
            return list(generator)

        # The setup function is run before each "round" so "iterations" is automatically set to 1 and cannot be changed
        packet_list: list = benchmark.pedantic(_make_packet_list, setup=_setup, rounds=20, warmup_rounds=1)

        # Make sure the result actually makes sense
        assert len(packet_list) == 7200
    finally:
        # Ensure filehandler is closed
        packet_fh.close()


@pytest.mark.benchmark
def test_benchmark_complex_packet_parsing(benchmark, idex_test_data_dir):
    """Benchmark the time it takes to parse IDEX packets, which have a polymorphic structure"""
    packet_definition = definitions.XtcePacketDefinition(idex_test_data_dir / "idex_combined_science_definition.xml")
    packet_data = idex_test_data_dir / "sciData_2023_052_14_45_05"

    # Open reusable filehandler
    packet_fh = packet_data.open("rb")

    try:
        def _setup():
            """Function that sets up for each benchmark round"""
            packet_fh.seek(0)
            packet_generator = packet_definition.packet_generator(packet_fh, show_progress=True)
            return (), {"generator": packet_generator}  # args, kwargs for benchmarked function

        def _make_packet_list(generator: Iterable[packets.CCSDSPacket]):
            """Function wrapper for list that takes the generator as a kwarg"""
            return list(generator)

        # The setup function is run before each "round" so "iterations" is automatically set to 1 and cannot be changed
        packet_list: list = benchmark.pedantic(_make_packet_list, setup=_setup, rounds=20, warmup_rounds=1)

        # Make sure the result actually makes sense
        assert len(packet_list) == 78
    finally:
        # Ensure filehandler is closed
        packet_fh.close()
