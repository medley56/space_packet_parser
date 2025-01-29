"""Unit tests for the Space Packet Parser `spp` CLI"""
import pytest

from click.testing import CliRunner
from space_packet_parser import cli


def test_cli():
    runner = CliRunner()
    result = runner.invoke(cli.spp, ["--version"])
    print(result.output)
    assert result.exit_code == 0
    print(result.exit_code)


def test_describe_xtce_jpss(jpss_test_data_dir):
    runner = CliRunner()
    print()
    result = runner.invoke(cli.describe_xtce,
                           [f"{jpss_test_data_dir / 'jpss1_geolocation_xtce_v1.xml'}"])
    print(result.output)
    assert result.exit_code == 0

    result = runner.invoke(cli.describe_xtce,
                           [f"{jpss_test_data_dir / 'contrived_inheritance_structure.xml'}"])
    print(result.output)
    assert result.exit_code == 0


def test_describe_xtce_suda(suda_test_data_dir):
    runner = CliRunner()
    print()
    result = runner.invoke(cli.describe_xtce,
                           [f"{suda_test_data_dir / 'suda_combined_science_definition.xml'}"])
    print(result.output)
    assert result.exit_code == 0


def test_describe_packets_jpss(jpss_test_data_dir):
    runner = CliRunner()
    print()
    result = runner.invoke(cli.describe_packets,
                           [f"{jpss_test_data_dir / 'J01_G011_LZ_2021-04-09T00-00-00Z_V01.DAT1'}"])
    print(result.output)
    assert result.exit_code == 0


def test_parse_jpss(jpss_test_data_dir):
    runner = CliRunner()
    print()
    packet_file = f"{jpss_test_data_dir / 'J01_G011_LZ_2021-04-09T00-00-00Z_V01.DAT1'}"
    definition_file = f"{jpss_test_data_dir / 'jpss1_geolocation_xtce_v1.xml'}"
    result = runner.invoke(cli.parse, [packet_file, definition_file])
    print(result.output)
    assert result.exit_code == 0


def test_parse_suda(suda_test_data_dir):
    runner = CliRunner()
    print()
    packet_file = f"{suda_test_data_dir / 'sciData_2022_130_17_41_53.spl'}"
    definition_file = f"{suda_test_data_dir / 'suda_combined_science_definition.xml'}"
    result = runner.invoke(cli.parse, [packet_file, definition_file, "--skip-header-bytes=4"])
    print(result.output)
    assert result.exit_code == 0
