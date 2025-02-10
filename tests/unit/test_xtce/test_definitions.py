"""Tests for space_packet_parser.xtcedef"""
import io

import pytest
from lxml import etree as ElementTree

from space_packet_parser.xtce import containers, definitions, encodings, parameters, comparisons, XTCE_NSMAP, XTCE_URI


def test_parsing_xtce_document(test_data_dir):
    """Tests parsing an entire XTCE document and makes assertions about the contents"""
    with open(test_data_dir / "test_xtce.xml") as x:
        xdef = definitions.XtcePacketDefinition.from_xtce(x, ns=XTCE_NSMAP)

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
                parameter_type=parameters.FloatParameterType(
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
                parameter_type=parameters.FloatParameterType(
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
                parameter_type=parameters.FloatParameterType(
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
        return parameters.IntegerParameterType(
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
                parameter_type=parameters.IntegerParameterType(
                    name="SCI_DATA_LEN_BYTES_Type",
                    encoding=encodings.IntegerDataEncoding(
                        size_in_bits=8,
                        encoding="unsigned"
                    )
                )
            ),
            parameters.Parameter(
                name="VAR_SCI_DATA",
                parameter_type=parameters.BinaryParameterType(
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
    ("xml", "ns_label", "ns", "new_ns_label", "new_ns"),
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
         "custom", {"custom": "http://www.fake-test.org/space/xtce"},
         "xtcenew", {"xtcenew": "http://www.fake-test.org/space/xtce"}),
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
         None, {None: "http://www.fake-test.org/space/xtce"},
         "xtce", {"xtce": "http://www.fake-test.org/space/xtce"}),
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
         "custom", {"custom": "http://www.fake-test.org/space/xtce"},
         None, {None: "http://www.fake-test.org/space/xtce"}),
        # TODO: This fails due to the way we are handling namespace mappings and finding the XTCE namespace mapping
#         ("""
# <SpaceSystem name="Space Packet Parser">
#     <Header date="2024-03-05T13:36:00MST" version="1.0" author="Gavin Medley"/>
#     <TelemetryMetaData>
#         <ParameterTypeSet/>
#         <ParameterSet/>
#         <ContainerSet/>
#     </TelemetryMetaData>
# </SpaceSystem>
# """,
#          None, {},
#          "xtcenew", {"xtcenew": "http://www.fake-test.org/space/xtce"}),
    ]
)
def test_custom_namespacing(test_data_dir, xml, ns_label, ns, new_ns_label, new_ns):
    """Test parsing XTCE with various namespace configurations"""
    # Parse directly from string, inferring the namespace mapping
    xdef = definitions.XtcePacketDefinition.from_xtce(io.StringIO(xml))
    default_tree = xdef.to_xml_tree()
    # Assert that we know what the inferred mapping is
    assert default_tree.getroot().nsmap == ns
    print(ElementTree.tostring(default_tree.getroot(), pretty_print=True).decode())
    # Prove we can find an element using the ns label prefix
    prefix = f"{ns_label}:" if ns_label else ""
    assert default_tree.find(f"{prefix}TelemetryMetaData", ns) is not None
    # And also using the URI literal
    assert default_tree.find(f"{{{ns[ns_label]}}}TelemetryMetaData", ns) is not None
    
    # Create the XML tree using a custom namespace label for the XTCE schema
    new_tree = xdef.to_xml_tree(ns=new_ns)
    # Assert the new mapping was applied
    assert new_tree.getroot().nsmap == new_ns
    # Prove we can find an element using the ns label prefix
    prefix = f"{new_ns_label}:" if new_ns_label else ""
    assert new_tree.find(f"{prefix}TelemetryMetaData", new_ns) is not None
    # And also using the URI literal
    assert new_tree.find(f"{{{new_ns[new_ns_label]}}}TelemetryMetaData", new_ns) is not None


@pytest.mark.xfail
def test_no_namespace_at_all_definition_parsing():
    """Test using no namespace prefix"""
    custom_namespaced_xtce = """
    <SpaceSystem name="Space Packet Parser">
        <Header date="2024-03-05T13:36:00MST" version="1.0" author="Gavin Medley"/>
        <TelemetryMetaData>
            <ParameterTypeSet/>
            <ParameterSet/>
            <ContainerSet/>
        </TelemetryMetaData>
    </SpaceSystem>
    """
    # Prove we can parse the same definition from an XML string without a namespace prefix
    no_namespace_def = definitions.XtcePacketDefinition.from_xtce(
        io.StringIO(custom_namespaced_xtce))
    assert no_namespace_def.ns == {}
    assert no_namespace_def.to_xml_tree().find("TelemetryMetaData") is not None