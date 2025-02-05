"""
This example demonstrates how to convert CCSDSPy CSV files to XTCE using the Space Packet Parser
XtcePacketDefinition object and assorted Python object representations of XTCE UML objects (e.g. Parameters,
ParameterTypes, and SequenceContainers).
"""
import csv
from pathlib import Path
import re
import warnings

from space_packet_parser import definitions, encodings, packets, parameters

# This regex is for detecting a dynamically sized field where its bit_length is
# the integer value of another field. If you need byte -> bit conversion consider manually editing the
# resulting XTCE file to add a LinearAdjuster to the packet size reference.
# This behavior has not been tested yet but the generated XTCE appears valid in tests.
dynamic_length_ref_pattern = re.compile(r'^(?:uint|int|str|fill)\((?P<len_ref>[A-Za-z_\-]*)\)$')

# This regex is for detecting Array valued packet fields but has not been tested.
array_param_pattern = re.compile(r'^int\((?P<dims>\d+(?:,\s*\d+)*)\)$')


def generate_ccsds_header() -> list[parameters.Parameter]:
    """Create the Parameter objects necessary for a CCSDS header, in order.

    This is necessary because CCSDSPy internally hardcodes CCSDS header definitions so they are not included
    in CCSDSPy-style CSV files.

    Returns
    -------
    : list[Parameter]
        List of header parameters, in order, including their parameter types defined internally
    """

    def _uint_type(bits: int):
        return parameters.IntegerParameterType(
        name=f"UINT{bits}_Type",
        encoding=encodings.IntegerDataEncoding(
            size_in_bits=bits,
            encoding="unsigned"
        )
    )

    return [
        parameters.Parameter(
            name="VERSION",
            parameter_type=_uint_type(3),
            short_description="CCSDS header version"
        ),
        parameters.Parameter(
            name="TYPE",
            parameter_type=_uint_type(1),
            short_description="CCSDS header type"
        ),
        parameters.Parameter(
            name="SEC_HDR_FLG",
            parameter_type=_uint_type(1),
            short_description="CCSDS header secondary header flag"
        ),
        parameters.Parameter(
            name="APID",
            parameter_type=_uint_type(11),
            short_description="CCSDS header APID"
        ),
        parameters.Parameter(
            name="SEQ_FLGS",
            parameter_type=_uint_type(2),
            short_description="CCSDS header sequence flags"
        ),
        parameters.Parameter(
            name="SRC_SEQ_CTR",
            parameter_type=_uint_type(14),
            short_description="CCSDS header source sequence counter"
        ),
        parameters.Parameter(
            name="PKT_LEN",
            parameter_type=_uint_type(16),
            short_description="CCSDS header packet length"
        )
    ]


def convert_ccsdspy_to_xtce(csv_path: Path) -> definitions.XtcePacketDefinition:
    """
    Converts a CCSDSPy CSV definition into an XTCE XML file.

    Parameters
    ----------
    csv_path : Path
        Path to the CCSDSPy CSV file.
    """
    with csv_path.open(newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        ccsdspy_rows = [row for row in reader]

    # Initialize our parameter list with a hard-coded generation of a CCSDS header since CCSDSPy CSVs are not
    # expected to contain the header fields.
    packet_parameters = generate_ccsds_header()

    if len(ccsdspy_rows[0]) >= 4:
        warnings.warn("The CSV file you supplied has more than 3 columns (possibly a CCSDSPy extended layout CSV?)."
                      "This tool will ignore the bit_offset column.")

    if not all(x in ccsdspy_rows[0] for x in ("name", "data_type", "bit_length")):
        raise ValueError("The CCSDSPy CSV must contain the header fields 'name', 'data_type', and 'bit_length'.")

    for row in ccsdspy_rows:
        match = dynamic_length_ref_pattern.match(row["data_type"])
        if match:
            len_parameter_ref = match.group("len_ref")
        else:
            len_parameter_ref = None

        array_match = array_param_pattern.match(row["data_type"])
        if array_match:
            raise ValueError("This tool doesn't support array shaped parameters from CCSDSPy yet")

        if row["data_type"] == "uint":
            parameter = parameters.Parameter(
                name=row["name"],
                parameter_type=parameters.IntegerParameterType(
                    name=f"{row['name']}_Type",
                    encoding=encodings.IntegerDataEncoding(
                        size_in_bits=int(row["bit_length"]),
                        encoding="unsigned"
                    )
                )
            )
        elif row["data_type"] == "int":
            parameter = parameters.Parameter(
                name=row["name"],
                parameter_type=parameters.IntegerParameterType(
                    name=f"{row['name']}_Type",
                    encoding=encodings.IntegerDataEncoding(
                        size_in_bits=int(row["bit_length"]),
                        encoding="signed"
                    )
                )
            )
        elif row["data_type"] == "fill":
            if len_parameter_ref:
                encoding = encodings.BinaryDataEncoding(
                    size_reference_parameter=len_parameter_ref
                )
            else:
                encoding = encodings.BinaryDataEncoding(
                    fixed_size_in_bits=int(row["bit_length"])
                )

            parameter = parameters.Parameter(
                name=row["name"],
                parameter_type=parameters.BinaryParameterType(
                    name=f"{row['name']}_Type",
                    encoding=encoding
                )
            )
        elif row["data_type"] == "str":
            if len_parameter_ref:
                encoding = encodings.StringDataEncoding(
                    dynamic_length_reference=len_parameter_ref
                )
            else:
                encoding = encodings.StringDataEncoding(
                    fixed_raw_length=int(row["bit_length"])
                )

            parameter = parameters.Parameter(
                name=row["name"],
                parameter_type=parameters.StringParameterType(
                    name=f"{row['name']}_Type",
                    encoding=encoding
                )
            )
        elif row["data_type"] == "float":
            parameter = parameters.Parameter(
                name=row["name"],
                parameter_type=parameters.FloatParameterType(
                    name=f"{row['name']}_Type",
                    encoding=encodings.FloatDataEncoding(
                        size_in_bits=int(row["bit_length"])
                    )
                )
            )
        else:
            raise ValueError(f"Unrecognized CCSDSPy data type: {row['data_type']}")

        packet_parameters.append(parameter)

    sequence_containers = [packets.SequenceContainer(name="CCSDSPacket", entry_list=packet_parameters)]

    return definitions.XtcePacketDefinition(
        sequence_container_list=sequence_containers,
        root_container_name="CCSDSPacket"
    )


if __name__ == "__main__":
    jpss_test_data_dir = Path("../tests/test_data/jpss")
    xtce_definition = convert_ccsdspy_to_xtce(jpss_test_data_dir / "ccsdspy_jpss1_geolocation.csv")

    packet_file = jpss_test_data_dir / "J01_G011_LZ_2021-04-09T00-00-00Z_V01.DAT1"
    with packet_file.open("rb") as packet_fh:
        packets = list(xtce_definition.packet_generator(packet_fh))

    assert len(packets) == 7200
    print(packets[3])
    print(len(packets))
