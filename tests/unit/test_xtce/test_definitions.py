"""Tests for space_packet_parser.xtcedef"""
import io

import pytest
from lxml import etree as ElementTree

import space_packet_parser.xtce.parameter_types
from space_packet_parser.xtce import containers, definitions, encodings, parameters, comparisons


def test_parsing_xtce_document(test_data_dir):
    """Tests parsing an entire XTCE document and makes assertions about the contents"""
    with open(test_data_dir / "test_xtce.xml") as x:
        xdef = definitions.XtcePacketDefinition.from_xtce(x)

    # Test Parameter Types
    ptname = "USEC_Type"
    pt = xdef.get_parameter_types(ptname)
    assert pt.name == ptname
    assert pt.unit == "us"
    assert isinstance(pt.encoding, encodings.IntegerDataEncoding)

    # Test Parameters
    pname = "ADAET1DAY"  # Named parameter
    p = xdef.get_parameters(pname)
    assert p.name == pname
    assert p.short_description == "Ephemeris Valid Time, Days Since 1/1/1958"
    assert p.long_description is None

    pname = "USEC"
    p = xdef.get_parameters(pname)
    assert p.name == pname
    assert p.short_description == "Secondary Header Fine Time (microsecond)"
    assert p.long_description == "CCSDS Packet 2nd Header Fine Time in microseconds."

    # Test Sequence Containers
    scname = "SecondaryHeaderContainer"
    sc = xdef.get_containers(scname)
    assert sc.name == scname
    assert sc == containers.SequenceContainer(
        name=scname,
        entry_list=[
            parameters.Parameter(
                name="DOY",
                parameter_type=space_packet_parser.xtce.parameter_types.FloatParameterType(
                    name="DOY_Type",
                    encoding=encodings.IntegerDataEncoding(
                        size_in_bits=16, encoding="unsigned"
                    ),
                    unit="day"
                ),
                short_description="Secondary Header Day of Year",
                long_description="CCSDS Packet 2nd Header Day of Year in days."
            ),
            parameters.Parameter(
                name="MSEC",
                parameter_type=space_packet_parser.xtce.parameter_types.FloatParameterType(
                    name="MSEC_Type",
                    encoding=encodings.IntegerDataEncoding(
                        size_in_bits=32, encoding="unsigned"
                    ),
                    unit="ms"
                ),
                short_description="Secondary Header Coarse Time (millisecond)",
                long_description="CCSDS Packet 2nd Header Coarse Time in milliseconds."
            ),
            parameters.Parameter(
                name="USEC",
                parameter_type=space_packet_parser.xtce.parameter_types.FloatParameterType(
                    name="USEC_Type",
                    encoding=encodings.IntegerDataEncoding(
                        size_in_bits=16, encoding="unsigned"
                    ),
                    unit="us"
                ),
                short_description="Secondary Header Fine Time (microsecond)",
                long_description="CCSDS Packet 2nd Header Fine Time in microseconds."
            )
        ],
        short_description=None,
        long_description="Container for telemetry secondary header items",
        base_container_name=None,
        restriction_criteria=None,
        abstract=True,
        inheritors=None
    )


def test_generating_xtce_from_objects():
    """Tests our ability to create an XTCE definition directly from Python objects"""
    def _uint_type(bits: int):
        return space_packet_parser.xtce.parameter_types.IntegerParameterType(
        name=f"UINT{bits}_Type",
        encoding=encodings.IntegerDataEncoding(
            size_in_bits=bits,
            encoding="unsigned"
        )
    )

    apid_filtered_container = containers.SequenceContainer(
        name="APID_3200",
        abstract=False,
        restriction_criteria=[
            comparisons.Comparison(
                required_value=3200,
                referenced_parameter="APID",
                operator="==",
                use_calibrated_value=True
            )
        ],
        entry_list=[
            parameters.Parameter(
                name="SCI_DATA_LEN_BYTES",
                parameter_type=space_packet_parser.xtce.parameter_types.IntegerParameterType(
                    name="SCI_DATA_LEN_BYTES_Type",
                    encoding=encodings.IntegerDataEncoding(
                        size_in_bits=8,
                        encoding="unsigned"
                    )
                )
            ),
            parameters.Parameter(
                name="VAR_SCI_DATA",
                parameter_type=space_packet_parser.xtce.parameter_types.BinaryParameterType(
                    name="VAR_SCI_DATA_Type",
                    encoding=encodings.BinaryDataEncoding(
                        size_reference_parameter="SCI_DATA_LEN_BYTES",
                        linear_adjuster=lambda x: 8*x
                    )
                )
            )
        ]
    )

    root_container = containers.SequenceContainer(
        name="RootContainer",
        abstract=True,
        inheritors=[apid_filtered_container],
        entry_list=[
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
    )

    # This list of sequence containers internally contains all parameters and parameter types
    sequence_containers = [root_container, apid_filtered_container]

    # Create the definition object
    definition = definitions.XtcePacketDefinition(
        sequence_container_list=sequence_containers,
        root_container_name=root_container.name,
        date="2025-01-01T01:01:01",
        author="Test Author",
        space_system_name="Test Space System Name"
    )

    # Serialize it to an XML string
    xtce_string = ElementTree.tostring(definition.to_xml_tree(), pretty_print=True).decode()

    # Reparse that string into a new definition object using from_document
    reparsed_definition = definitions.XtcePacketDefinition.from_xtce(
        io.StringIO(xtce_string),
        root_container_name=root_container.name
    )

    # Serialize the reparsed object and assert that the string is the same as what we started with
    assert ElementTree.tostring(reparsed_definition.to_xml_tree(), pretty_print=True).decode() == xtce_string


@pytest.mark.parametrize(
    ("xml", "uri", "ns", "new_uri", "new_ns"),
    [
        # Custom namespace to new custom namespace
        ("""
<custom:SpaceSystem xmlns:custom="http://www.fake-test.org/space/xtce" name="Space Packet Parser">
    <custom:Header date="2024-03-05T13:36:00MST" version="1.0" author="Gavin Medley"/>
    <custom:TelemetryMetaData>
        <custom:ParameterTypeSet/>
        <custom:ParameterSet/>
        <custom:ContainerSet/>
    </custom:TelemetryMetaData>
</custom:SpaceSystem>
""",
         "http://www.fake-test.org/space/xtce",
         {"custom": "http://www.fake-test.org/space/xtce"},
         "http://www.fake-test.org/space/xtce",
         {"xtcenew": "http://www.fake-test.org/space/xtce"}),
        # No namespace to custom namespace
        ("""
<SpaceSystem xmlns="http://www.fake-test.org/space/xtce" name="Space Packet Parser">
    <Header date="2024-03-05T13:36:00MST" version="1.0" author="Gavin Medley"/>
    <TelemetryMetaData>
        <ParameterTypeSet/>
        <ParameterSet/>
        <ContainerSet/>
    </TelemetryMetaData>
</SpaceSystem>
""",
         "http://www.fake-test.org/space/xtce",
         {None: "http://www.fake-test.org/space/xtce"},
         "http://www.fake-test.org/space/xtce",
         {"xtce": "http://www.fake-test.org/space/xtce"}),
        ("""
<custom:SpaceSystem xmlns:custom="http://www.fake-test.org/space/xtce" name="Space Packet Parser">
    <custom:Header date="2024-03-05T13:36:00MST" version="1.0" author="Gavin Medley"/>
    <custom:TelemetryMetaData>
        <custom:ParameterTypeSet/>
        <custom:ParameterSet/>
        <custom:ContainerSet/>
    </custom:TelemetryMetaData>
</custom:SpaceSystem>
""",
         "http://www.fake-test.org/space/xtce",
         {"custom": "http://www.fake-test.org/space/xtce"},
         "http://www.fake-test.org/space/xtce",
         {None: "http://www.fake-test.org/space/xtce"}),
        ("""
<SpaceSystem name="Space Packet Parser">
    <Header date="2024-03-05T13:36:00MST" version="1.0" author="Gavin Medley"/>
    <TelemetryMetaData>
        <ParameterTypeSet/>
        <ParameterSet/>
        <ContainerSet/>
    </TelemetryMetaData>
</SpaceSystem>
""",
         None,
         {},
         "http://www.fake-test.org/space/xtce",
         {"xtcenew": "http://www.fake-test.org/space/xtce"}),
("""
<custom:SpaceSystem xmlns:custom="http://www.fake-test.org/space/xtce" name="Space Packet Parser">
    <custom:Header date="2024-03-05T13:36:00MST" version="1.0" author="Gavin Medley"/>
    <custom:TelemetryMetaData>
        <custom:ParameterTypeSet/>
        <custom:ParameterSet/>
        <custom:ContainerSet/>
    </custom:TelemetryMetaData>
</custom:SpaceSystem>
""",
         "http://www.fake-test.org/space/xtce",
         {"custom": "http://www.fake-test.org/space/xtce"},
         None,
         {}),
    ]
)
def test_custom_namespacing(test_data_dir, xml, uri, ns, new_uri, new_ns):
    """Test parsing XTCE with various namespace configurations"""
    # Parse directly from string, inferring the namespace mapping
    xdef = definitions.XtcePacketDefinition.from_xtce(io.StringIO(xml), xtce_schema_uri=uri)
    default_tree = xdef.to_xml_tree()
    # Assert that we know what the inferred mapping is
    assert default_tree.getroot().nsmap == ns

    # Prove we can find an element using the ns label prefix, if any
    if ns:
        ns_label = [k for k, v in ns.items() if v == uri][0]
        prefix = f"{ns_label}:" if ns_label else ""
    else:
        prefix = ""
    assert default_tree.find(f"{prefix}TelemetryMetaData", ns) is not None

    # And also using the URI literal, if any
    prefix = f"{{{uri}}}" if uri else ""
    assert default_tree.find(f"{prefix}TelemetryMetaData", ns) is not None
    
    # Create the XML tree using a custom namespace label for the XTCE schema
    xdef.ns = new_ns
    xdef.xtce_schema_uri = new_uri
    new_tree = xdef.to_xml_tree()

    # Assert the new mapping was applied
    assert new_tree.getroot().nsmap == new_ns

    # Prove we can find an element using the ns label prefix, if any
    if new_ns:
        ns_label = [k for k, v in new_ns.items() if v == new_uri][0]
        prefix = f"{ns_label}:" if ns_label else ""
    else:
        prefix = ""
    assert new_tree.find(f"{prefix}TelemetryMetaData", new_ns) is not None

    # And also using the new URI literal, if any
    prefix = f"{{{new_uri}}}" if new_uri else ""
    assert new_tree.find(f"{prefix}TelemetryMetaData", new_ns) is not None
