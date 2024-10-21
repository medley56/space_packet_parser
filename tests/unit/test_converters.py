"""Testing for xtce generator template."""

import sys
from pathlib import Path
from unittest import mock

import pytest

from space_packet_parser import converters

pytest.importorskip("pandas", reason="Pandas is required for converting to XTCE format.")
pytest.importorskip("openpyxl", reason="Openpyxl is required for converting to XTCE format.")

import pandas as pd


@pytest.fixture()
def xtce_excel_file(tmp_path):
    """Create an excel file for testing.

    Dataframes for each tab of the spreadsheet that then get written to an excel file.
    """
    # Create a pandas DataFrame for global attributes
    subsystem = {
        "infoField": ["subsystem", "sheetReleaseDate", "sheetReleaseRev"],
        "infoValue": ["Test Instrument", "2024-07-26 00:00:00", "v1.2"],
    }

    packets = {"packetName": ["TEST_PACKET", "TEST_PACKET2"], "apIdHex": ["0x1", "0xF"]}

    test_packet1 = {
        "packetName": ["TEST_PACKET"] * 15,
        "mnemonic": [
            "PHVERNO",
            "PHTYPE",
            "PHSHF",
            "PHAPID",
            "PHGROUPF",
            "PHSEQCNT",
            "PHDLEN",
            "SHCOARSE",
            "VAR_UINT",
            "VAR_INT",
            "VAR_SINT",
            "VAR_BYTE",
            "VAR_FILL",
            "VAR_FLOAT",
            "VAR_STATE",
        ],
        "lengthInBits": [3, 1, 1, 11, 2, 14, 16, 32, 2, 4, 5, 10000, 3, 32, 1],
        "dataType": [
            "UINT",
            "UINT",
            "UINT",
            "UINT",
            "UINT",
            "UINT",
            "UINT",
            "UINT",
            "UINT",
            "INT",
            "SINT",
            "BYTE",
            "FILL",
            "FLOAT",
            "UINT",
        ],
        "convertAs": [
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "ANALOG",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "STATE",
        ],
        "units": [
            "DN",
            "DN",
            "DN",
            "DN",
            "DN",
            "DN",
            "DN",
            "DN",
            "DN",
            "DN",
            "DN",
            "DN",
            "DN",
            "DN",
            "DN",
        ],
        "longDescription": [
            "CCSDS Packet Version Number",
            "CCSDS Packet Type Indicator",
            "CCSDS Packet Secondary Header Flag",
            "CCSDS Packet Application Process ID",
            "CCSDS Packet Grouping Flags",
            "CCSDS Packet Sequence Count",
            "CCSDS Packet Length",
            "Mission elapsed time",
            "Unsgned integer data with conversion",
            "Integer data",
            "Signed integer data",
            "Binary data - variable length",
            "Fill data",
            "Float data",
            "State data",
        ],
    }

    test_packet2 = {
        "packetName": ["TEST_PACKET2"] * 9,
        "mnemonic": [
            "PHVERNO",
            "PHTYPE",
            "PHSHF",
            "PHAPID",
            "PHGROUPF",
            "PHSEQCNT",
            "PHDLEN",
            "SHCOARSE",
            "VAR1",
        ],
        "lengthInBits": [3, 1, 1, 11, 2, 14, 16, 32, 2],
        "dataType": [
            "UINT",
            "UINT",
            "UINT",
            "UINT",
            "UINT",
            "UINT",
            "UINT",
            "UINT",
            "UINT",
        ],
        "convertAs": [
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
            "NONE",
        ],
        "units": ["DN", "DN", "DN", "DN", "DN", "DN", "DN", "DN", "DN"],
        "longDescription": [
            "CCSDS Packet Version Number",
            "CCSDS Packet Type Indicator",
            "CCSDS Packet Secondary Header Flag",
            "CCSDS Packet Application Process ID",
            "CCSDS Packet Grouping Flags",
            "CCSDS Packet Sequence Count",
            "CCSDS Packet Length",
            "Mission elapsed time",
            "Variable 1 long description",
        ],
        "shortDescription": [
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "Variable 1 short description",
        ],
    }

    analog_conversions = {
        "packetName": ["TEST_PACKET"],
        "mnemonic": ["VAR_UINT"],
        "convertAs": ["UNSEGMENTED_POLY"],
        "segNumber": [1],
        "lowValue": [0],
        "highValue": [100],
        "c0": [1.5],
        "c1": [2.5],
        "c2": [0],
        "c3": [0],
        "c4": [0],
        "c5": [0],
        "c6": [0],
        "c7": [0],
    }

    states = {
        "packetName": ["TEST_PACKET"] * 2,
        "mnemonic": ["VAR_STATE"] * 2,
        "value": [0, 1],
        "state": ["OFF", "ON"],
    }

    # Write the DataFrame to an excel file
    excel_path = tmp_path / "excel_to_xtce_test_file.xlsx"
    excel_file = pd.ExcelWriter(excel_path, engine="openpyxl")

    pd.DataFrame(subsystem).to_excel(excel_file, sheet_name="Subsystem", index=False)
    pd.DataFrame(packets).to_excel(excel_file, sheet_name="Packets", index=False)
    pd.DataFrame(test_packet1).to_excel(
        excel_file, sheet_name="TEST_PACKET", index=False
    )
    # Test P_ version of sheet name as well
    pd.DataFrame(test_packet2).to_excel(
        excel_file, sheet_name="P_TEST_PACKET2", index=False
    )
    pd.DataFrame(analog_conversions).to_excel(
        excel_file, sheet_name="AnalogConversions", index=False
    )
    pd.DataFrame(states).to_excel(excel_file, sheet_name="States", index=False)

    # Write the file to disk
    excel_file.close()

    return excel_path


def test_generated_xtce(xtce_excel_file):
    """Make sure we are producing the expected contents within the XML file.
    
    Uncomment the `generator.to_xtce(expected_file)` line to create the expected output file.
    """
    generator = converters.Excel(xtce_excel_file)
    output_file = xtce_excel_file.parent / "output.xml"
    generator.to_xtce(output_file)

    expected_file = Path(__file__).parent.parent / "test_data/expected_excel_xtce.xml"
    # NOTE: Uncomment this line if you want to re-create the expected output file
    # generator.to_xtce(expected_file)
    with open(output_file) as f, open(expected_file) as f_expected:
        assert f.read() == f_expected.read()


@mock.patch("space_packet_parser.converters.Excel")
def test_main_general(mock_input, xtce_excel_file):
    """Valid input should only be called once and not raise any errors."""
    test_args = [
        "spp-convert",
        "--output",
        "test.xml",
        f"{xtce_excel_file}",
    ]
    with mock.patch.object(sys, "argv", test_args):
        converters.main()
        mock_input.assert_called_once()


# Testing without required arguments
def test_main_inval_arg():
    """Raises when no input Excel file is present."""
    test_args = [
        "spp-convert",
        "--output",
        "test.xml",
    ]
    with mock.patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit):
            converters.main()
