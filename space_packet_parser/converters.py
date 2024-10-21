"""
Convert an Excel file of packet definitions into the XTCE format.

This script reads in an Excel file containing packet definitions and converts
them into an XTCE file.

.. code::
  spp-convert /path/to/excel_file.xlsx --output /path/to/output.xml
"""

import argparse
import xml.etree.ElementTree as Et
from importlib.util import find_spec
from pathlib import Path

try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False

if not find_spec("openpyxl"):
    # Also test for openpyxl which is panda's optional Excel engine
    _HAS_PANDAS = False

_CCSDS_PARAMETERS = [
    {
        "name": "VERSION",
        "lengthInBits": 3,
        "description": "CCSDS Packet Version Number (always 0)",
    },
    {
        "name": "TYPE",
        "lengthInBits": 1,
        "description": "CCSDS Packet Type Indicator (0=telemetry)",
    },
    {
        "name": "SEC_HDR_FLG",
        "lengthInBits": 1,
        "description": "CCSDS Packet Secondary Header Flag (always 1)",
    },
    {
        "name": "PKT_APID",
        "lengthInBits": 11,
        "description": "CCSDS Packet Application Process ID",
    },
    {
        "name": "SEQ_FLGS",
        "lengthInBits": 2,
        "description": "CCSDS Packet Grouping Flags (3=not part of group)",
    },
    {
        "name": "SRC_SEQ_CTR",
        "lengthInBits": 14,
        "description": "CCSDS Packet Sequence Count "
        "(increments with each new packet)",
    },
    {
        "name": "PKT_LEN",
        "lengthInBits": 16,
        "description": "CCSDS Packet Length "
        "(number of bytes after Packet length minus 1)",
    },
]


class Excel:
    """
    Automatically generate XTCE files from an Excel spreadsheet definition file.

    There must be a sheet named "Packets" that contains a mapping from packetName to apId.
    Each packet definition is contained in its own sheet named "packetName".

    The packet definition sheets must have the following columns:
      * mnemonic
      * lengthInBits
      * dataType
    with optional extra columns:
      * convertAs (ANALOG, STATE)
      * shortDescription
      * longDescription

    Some names can be duplicated across packet definitions, but have different
    lengths or data types (i.e. SPARE/FILL). To disambiguate these, the XTCE parameterRef
    is created by combining the packetName and mnemonic with a period: `packetName.mnemonic`.

    Parameters
    ----------
    path_to_excel_file : Path
        Path to the excel file.

    Usage
    -----
    Excel("/path/to/definition.xlsx").to_xtce("/path/to/xtce-definition.xml")
    """

    def __init__(self, path_to_excel_file: Path, namespace="http://www.omg.org/space/xtce"):
        if not _HAS_PANDAS:
            raise ImportError(
                "The pandas and openpyxl packages are required to convert an Excel sheet to XTCE. "
                "Please install them using 'pip install pandas openpyxl'."
            )
        # Read in all sheets from the excel file
        self.sheets = pd.read_excel(path_to_excel_file, sheet_name=None)
        if "Packets" not in self.sheets:
            raise ValueError(
                "The excel file must contain a sheet named 'Packets' that contains a mapping "
                "from packetName to apId."
            )
        # Set up the packet mapping from packetName to Apid
        packet_sheet = self.sheets["Packets"]
        if "packetName" not in packet_sheet.columns:
            raise ValueError(
                "The excel file must contain a column named 'packetName' in the 'Packets' sheet."
            )
        if "apId" not in packet_sheet.columns:
            if "apIdHex" not in packet_sheet.columns:
                raise ValueError(
                    "The excel file must contain a column named 'apId' or 'apIdHex' in the 'Packets' sheet."
                )
            # Create the apId column from the apIdHex (base=0 works with the 0x prefix)
            packet_sheet["apId"] = packet_sheet["apIdHex"].apply(int, base=0)
        self._packet_mapping = packet_sheet.set_index("packetName")["apId"].to_dict()

        self._namespace = namespace
        # Create the XML containers that will be populated later
        self._setup_xml_containers()
        # Add the CCSDS Header information to the containers
        self._setup_ccsds_header()
        # Create the sequence containers (also adding parameters within)
        self._create_container_sets()

    def _setup_xml_containers(self) -> None:
        """Create an XML representation of telemetry data."""
        # Create the root element and add namespaces
        self._root = root = Et.Element("xtce:SpaceSystem")
        root.attrib["xmlns:xtce"] = self._namespace
        if "Subsystem" in self.sheets:
            # Subsystem sheet name is used as the base name for this XTCE definition
            subsystem = self.sheets["Subsystem"]
            root.attrib["name"] = str(
                subsystem.loc[subsystem["infoField"] == "subsystem", "infoValue"].values[0]
            )
            # Create the Header element with attributes 'date', 'version', and 'author'
            # Versioning is used to keep track of changes to the XML file.
            header = Et.SubElement(root, "xtce:Header")
            header.attrib["date"] = str(
                subsystem.loc[
                    subsystem["infoField"] == "sheetReleaseDate", "infoValue"
                ].values[0]
            )
            header.attrib["version"] = str(
                subsystem.loc[
                    subsystem["infoField"] == "sheetReleaseRev", "infoValue"
                ].values[0]
            )
            header.attrib["author"] = "Space Packet Parser"

        # Create the TelemetryMetaData element
        self._telemetry_metadata = Et.SubElement(root, "xtce:TelemetryMetaData")

        # Create the ParameterTypeSet element
        self._parameter_type_set = Et.SubElement(
            self._telemetry_metadata, "xtce:ParameterTypeSet"
        )

        # Create the ParameterSet element
        self._parameter_set = Et.SubElement(
            self._telemetry_metadata, "xtce:ParameterSet"
        )

        # Create ContainerSet element
        self._container_sets = Et.SubElement(
            self._telemetry_metadata, "xtce:ContainerSet"
        )

    def _setup_ccsds_header(self) -> None:
        """Fill in the default CCSDS header information."""
        # Create CCSDSPacket SequenceContainer
        ccsds_container = Et.SubElement(self._container_sets, "xtce:SequenceContainer")
        ccsds_container.attrib["name"] = "CCSDSPacket"
        ccsds_container.attrib["abstract"] = "true"
        ccsds_entry_list = Et.SubElement(ccsds_container, "xtce:EntryList")

        # Populate EntryList for CCSDSPacket SequenceContainer
        for parameter_data in _CCSDS_PARAMETERS:
            parameter_ref_entry = Et.SubElement(
                ccsds_entry_list, "xtce:ParameterRefEntry"
            )
            name = str(parameter_data["name"])

            parameter_ref_entry.attrib["parameterRef"] = name

            # Add the parameter to the ParameterSet
            parameter = Et.SubElement(self._parameter_set, "xtce:Parameter")
            parameter.attrib["name"] = name
            parameter.attrib["parameterTypeRef"] = name

            description = Et.SubElement(parameter, "xtce:LongDescription")
            description.text = str(parameter_data["description"])

            # Add the typeref to the parameter type set
            parameter_type = Et.SubElement(
                self._parameter_type_set, "xtce:IntegerParameterType"
            )
            parameter_type.attrib["name"] = name
            parameter_type.attrib["signed"] = "false"

            encoding = Et.SubElement(parameter_type, "xtce:IntegerDataEncoding")
            encoding.attrib["sizeInBits"] = str(parameter_data["lengthInBits"])
            encoding.attrib["encoding"] = "unsigned"

    def _create_container_sets(self) -> None:
        """Create a container set for each packet in the Excel file."""
        # Iterate over all packets and create Packet SequenceContainers
        for packet_name, apid in self._packet_mapping.items():
            # Populate EntryList for packet SequenceContainers
            # The sheets are sometimes prefixed with P_, so we need to try both options
            packet_df = self.sheets.get(packet_name, self.sheets.get(f"P_{packet_name}"))
            if packet_df is None:
                print(
                    f"Packet definition for {packet_name} "
                    "not found in the excel file as a separate tab, skipping the XTCE creation."
                )
                continue
            if any(x not in packet_df.columns for x in ["mnemonic", "lengthInBits", "dataType"]):
                print(
                    f"Packet definition for {packet_name}  does not contain the required columns "
                    "(mnemonic, lengthInBits, dataType), skipping the XTCE creation."
                )
                continue
            # Create Packet SequenceContainer that use the CCSDSPacket SequenceContainer
            # as the base container
            science_container = Et.SubElement(
                self._container_sets, "xtce:SequenceContainer"
            )
            science_container.attrib["name"] = packet_name

            # Every container should inherit from the base container, CCSDSPacket
            base_container = Et.SubElement(science_container, "xtce:BaseContainer")
            base_container.attrib["containerRef"] = "CCSDSPacket"

            # Add RestrictionCriteria element to use the given APID for comparison
            restriction_criteria = Et.SubElement(
                base_container, "xtce:RestrictionCriteria"
            )
            comparison = Et.SubElement(restriction_criteria, "xtce:Comparison")
            comparison.attrib["parameterRef"] = "PKT_APID"
            comparison.attrib["value"] = str(apid)
            comparison.attrib["useCalibratedValue"] = "false"

            packet_entry_list = Et.SubElement(science_container, "xtce:EntryList")
            # Needed for dynamic binary packet length
            total_packet_bits = int(packet_df["lengthInBits"].sum())
            for i, row in packet_df.iterrows():
                if i < 7:
                    # Skip first 7 rows as they are the CCSDS header elements
                    # TODO: Do we want to leave these in for explicit (non-abstract) containers?
                    continue
                if pd.isna(row.get("packetName")):
                    # This is a poorly formatted row, skip it
                    continue
                # separate the packet name and mnemonic with a period
                # a hyphen is sometimes in the packet name or mnemonic already
                name = f"{row['packetName']}.{row['mnemonic']}"
                parameter_ref_entry = Et.SubElement(
                    packet_entry_list, "xtce:ParameterRefEntry"
                )
                parameter_ref_entry.attrib["parameterRef"] = name
                # Add this parameter to the ParameterSet too
                self._add_parameter(row, total_packet_bits)

    def _add_parameter(self, row: 'pd.Series', total_packet_bits: int) -> None:  # pylint: disable=too-many-statements
        """
        Row from a packet definition to be added to the XTCE file.

        Parameters
        ----------
        row : pandas.Row
            Row to be added to the XTCE file, containing mnemonic, lengthInBits, ...
        total_packet_bits : int
            Total number of bits in the packet, as summed from the lengthInBits column.
        """
        parameter = Et.SubElement(self._parameter_set, "xtce:Parameter")
        # Combine the packet name and mnemonic to create a unique parameter name
        name = f"{row['packetName']}.{row['mnemonic']}"
        parameter.attrib["name"] = name
        parameter.attrib["parameterTypeRef"] = name

        # Add descriptions if they exist
        if pd.notna(row.get("shortDescription")):
            parameter.attrib["shortDescription"] = row.get("shortDescription")
        if pd.notna(row.get("longDescription")):
            description = Et.SubElement(parameter, "xtce:LongDescription")
            description.text = row.get("longDescription")

        length_in_bits = int(row["lengthInBits"])

        # Add the parameterTypeRef for this row
        if "UINT" in row["dataType"] or "FILL" in row["dataType"]:
            parameter_type = Et.SubElement(
                self._parameter_type_set, "xtce:IntegerParameterType"
            )
            parameter_type.attrib["name"] = name
            parameter_type.attrib["signed"] = "false"

            encoding = Et.SubElement(parameter_type, "xtce:IntegerDataEncoding")
            encoding.attrib["sizeInBits"] = str(length_in_bits)
            encoding.attrib["encoding"] = "unsigned"

        elif any(x in row["dataType"] for x in ["SINT", "INT"]):
            parameter_type = Et.SubElement(
                self._parameter_type_set, "xtce:IntegerParameterType"
            )
            parameter_type.attrib["name"] = name
            parameter_type.attrib["signed"] = "true"
            encoding = Et.SubElement(parameter_type, "xtce:IntegerDataEncoding")
            encoding.attrib["sizeInBits"] = str(length_in_bits)
            encoding.attrib["encoding"] = "signed"

        elif "FLOAT" in row["dataType"]:
            parameter_type = Et.SubElement(
                self._parameter_type_set, "xtce:FloatParameterType"
            )
            parameter_type.attrib["name"] = name
            encoding = Et.SubElement(parameter_type, "xtce:FloatDataEncoding")
            encoding.attrib["sizeInBits"] = str(length_in_bits)
            encoding.attrib["encoding"] = "IEEE-754"

        elif "BYTE" in row["dataType"]:
            parameter_type = Et.SubElement(
                self._parameter_type_set, "xtce:BinaryParameterType"
            )
            parameter_type.attrib["name"] = name

            encoding = Et.SubElement(parameter_type, "xtce:BinaryDataEncoding")
            encoding.attrib["bitOrder"] = "mostSignificantBitFirst"

            size_in_bits = Et.SubElement(encoding, "xtce:SizeInBits")

            # If it is a byte field consider it a dynamic value.
            dynamic_value = Et.SubElement(size_in_bits, "xtce:DynamicValue")
            param_ref = Et.SubElement(dynamic_value, "xtce:ParameterInstanceRef")
            param_ref.attrib["parameterRef"] = "PKT_LEN"
            linear_adjustment = Et.SubElement(dynamic_value, "xtce:LinearAdjustment")
            linear_adjustment.attrib["slope"] = str(8)
            # The length of all other variables (other than this specific one)
            other_variable_bits = total_packet_bits - length_in_bits
            # PKT_LEN == number of bytes in the packet data field - 1
            # So we need to subtract the header bytes plus 1 to get the offset
            # The amount to subtract to get the intercept is then:
            # number of other bits in the packet - (6 + 1) * 8
            linear_adjustment.attrib["intercept"] = str(-int(other_variable_bits - 56))

            # TODO: Do we want to allow fixed length values?
            # fixed_value = Et.SubElement(size_in_bits, "xtce:FixedValue")
            # fixed_value.text = str(row["lengthInBits"])
        else:
            raise ValueError(f"Unknown data type for {name}: {row['dataType']}")

        if "convertAs" in row:
            if row["convertAs"] == "ANALOG":
                # Go look up the conversion in the AnalogConversions tab
                # and add it to the encoding
                self._add_analog_conversion(row, encoding)
            elif row["convertAs"] == "STATE":
                # Go look up the states in the States tab
                # and add them to the parameter type
                self._add_state_conversion(row, parameter_type)

    def _add_analog_conversion(self, row: 'pd.Series', encoding: Et.Element) -> None:
        """
        Add an analog conversion to the encoding element.

        Parameters
        ----------
        row : pandas.Row
            Row to be added to the XTCE file, containing mnemonic, packetName.
        encoding : Element
            The encoding element to add the conversion to.
        """
        # Look up the conversion in the AnalogConversions tab
        analog_conversion = self.sheets["AnalogConversions"]
        # conversion is a row from the AnalogConversions sheet
        conversion = analog_conversion.loc[
            (analog_conversion["mnemonic"] == row["mnemonic"])
            & (analog_conversion["packetName"] == row["packetName"])
        ].iloc[0]

        # Create the Conversion element
        default_calibrator = Et.SubElement(encoding, "xtce:DefaultCalibrator")
        polynomial_calibrator = Et.SubElement(
            default_calibrator, "xtce:PolynomialCalibrator"
        )
        # FIXME: Use lowValue / highValue from the conversion sheet
        # FIXME: Handle segmented polynomials (only using first segment now)
        for i in range(8):
            col = f"c{i}"
            if conversion[col] != 0:
                term = Et.SubElement(polynomial_calibrator, "xtce:Term")
                term.attrib["coefficient"] = str(conversion[col])
                term.attrib["exponent"] = str(i)

    def _add_state_conversion(self, row: 'pd.Series', parameter_type: Et.Element) -> None:
        """
        Add a state conversion to the parameter type.

        Changing from an IntegerParameterType to an EnumeratedParameterType. Adding
        the list of state mappings to the parameter type.

        Parameters
        ----------
        row : pandas.Row
            Row to be added to the XTCE file, containing mnemonic, packetName.
        parameter_type : Element
            The parameter type element to add the conversion to.
        """
        # It is an EnumeratedParameterType rather than an IntegerParameterType
        parameter_type.tag = "xtce:EnumeratedParameterType"
        enumeration_list = Et.SubElement(parameter_type, "xtce:EnumerationList")
        # Lookup the enumeration states for this parameter from the States sheet
        state_sheet = self.sheets["States"]
        state_sheet = state_sheet.loc[
            (state_sheet["packetName"] == row["packetName"])
            & (state_sheet["mnemonic"] == row["mnemonic"])
        ]
        for _, state_row in state_sheet.iterrows():
            enumeration = Et.SubElement(enumeration_list, "xtce:Enumeration")
            enumeration.attrib["value"] = str(state_row["value"])
            enumeration.attrib["label"] = str(state_row["state"])

    def to_xtce(self, output_xtce_path: Path) -> None:
        """
        Create and output an XTCE file from the Element Tree representation.

        Parameters
        ----------
        output_xml_path : Path
            Path to the output XML file.
        """
        # Create the XML tree and save the document
        tree = Et.ElementTree(self._root)
        Et.indent(tree, space="\t")

        # Use the provided output_xtce_path
        tree.write(output_xtce_path, encoding="utf-8", xml_declaration=True)


# Function to parse command line arguments
def _parse_args() -> argparse.Namespace:
    """
    Parse the command line arguments.

    The expected input format is a required argument of "/path/to/excel_file.xlsx"
    with an optional argument containing the output path for the XTCE file
    "/path/to/output.xml".

    Returns
    -------
    args : argparse.Namespace
        An object containing the parsed arguments and their values.
    """
    description = (
        "This command line program generates an instrument specific XTCE file. "
        "Example usage: spp-convert path/to/excel_packet_file.xlsx --output path/to/output_packet_definition.xml"
    )
    output_help = (
        "Where to save the output XTCE file. "
        "If not provided, the input file name will be used with a .xml extension."
    )
    file_path_help = "Provide the full path to the input excel file."

    parser = argparse.ArgumentParser(prog="spp-convert", description=description)
    parser.add_argument("excel_file", type=Path, help=file_path_help)
    parser.add_argument("--output", type=Path, required=False, help=output_help)

    args = parser.parse_args()

    if not args.excel_file.exists():
        parser.error(f"File not found: {args.excel_file}")

    if not args.output:
        args.output = args.excel_file.with_suffix(".xml")

    return args


def main() -> None:
    """
    Generate xtce file from CLI information given.

    The xtce file will be written in an instrument specific subfolder.
    """
    # Parse arguments from the command line
    args = _parse_args()

    # Initialize the class and process the sheets and then output the XTCE file
    Excel(args.excel_file).to_xtce(args.output)


if __name__ == "__main__":
    main()
