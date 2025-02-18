"""Tests for space_packet_parser.xtcedef"""
import io

import pytest
from lxml import etree as ElementTree

import space_packet_parser.xtce.parameter_types
from space_packet_parser.xtce import containers, definitions, encodings, parameters, comparisons


@pytest.mark.parametrize(
    ("xtcedoc", "xtce_ns_prefix"),
    [
        ("test_xtce.xml", "xtce"),
        ("test_xtce_default_namespace.xml", None),
        ("test_xtce_no_namespace.xml", None)
    ]
)
def test_parsing_xtce_document(test_data_dir, xtcedoc, xtce_ns_prefix):
    """Tests parsing an entire XTCE document and makes assertions about the contents"""
    with open(test_data_dir / xtcedoc) as x:
        xdef = definitions.XtcePacketDefinition.from_xtce(x, xtce_ns_prefix=xtce_ns_prefix)

    # Test Parameter Types
    ptname = "USEC_Type"
    pt = xdef.parameter_types[ptname]
    assert pt.name == ptname
    assert pt.unit == "us"
    assert isinstance(pt.encoding, encodings.IntegerDataEncoding)

    # Test Parameters
    pname = "ADAET1DAY"  # Named parameter
    p = xdef.parameters[pname]
    assert p.name == pname
    assert p.short_description == "Ephemeris Valid Time, Days Since 1/1/1958"
    assert p.long_description is None

    pname = "USEC"
    p = xdef.parameters[pname]
    assert p.name == pname
    assert p.short_description == "Secondary Header Fine Time (microsecond)"
    assert p.long_description == "CCSDS Packet 2nd Header Fine Time in microseconds."

    # Test Sequence Containers
    scname = "SecondaryHeaderContainer"
    sc = xdef.containers[scname]
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
    uint1 = space_packet_parser.xtce.parameter_types.IntegerParameterType(
        name=f"UINT1_Type",
        encoding=encodings.IntegerDataEncoding(
            size_in_bits=1,
            encoding="unsigned"
        )
    )

    uint2 = space_packet_parser.xtce.parameter_types.IntegerParameterType(
        name=f"UINT2_Type",
        encoding=encodings.IntegerDataEncoding(
            size_in_bits=2,
            encoding="unsigned"
        )
    )

    uint3 = space_packet_parser.xtce.parameter_types.IntegerParameterType(
        name=f"UINT3_Type",
        encoding=encodings.IntegerDataEncoding(
            size_in_bits=3,
            encoding="unsigned"
        )
    )

    uint11 = space_packet_parser.xtce.parameter_types.IntegerParameterType(
        name=f"UINT11_Type",
        encoding=encodings.IntegerDataEncoding(
            size_in_bits=11,
            encoding="unsigned"
        )
    )

    uint14 = space_packet_parser.xtce.parameter_types.IntegerParameterType(
        name=f"UINT14_Type",
        encoding=encodings.IntegerDataEncoding(
            size_in_bits=14,
            encoding="unsigned"
        )
    )

    uint16 = space_packet_parser.xtce.parameter_types.IntegerParameterType(
        name=f"UINT16_Type",
        encoding=encodings.IntegerDataEncoding(
            size_in_bits=16,
            encoding="unsigned"
        )
    )

    multiply_nested_container = containers.SequenceContainer(
        name="NestedContainer",
        abstract=True,
        entry_list=[
            parameters.Parameter(
                name="REPEATABLY_NESTED",
                parameter_type=space_packet_parser.xtce.parameter_types.IntegerParameterType(
                    name="REPEATABLY_NESTED_Type",
                    encoding=encodings.IntegerDataEncoding(
                        size_in_bits=32,
                        encoding="unsigned"
                    )
                )
            )
        ]
    )

    apid_filtered_container = containers.SequenceContainer(
        name="APID_3200",
        abstract=False,
        base_container_name="RootContainer",
        restriction_criteria=[
            comparisons.Comparison(
                required_value="3200",
                referenced_parameter="APID",
                operator="==",
                use_calibrated_value=True
            )
        ],
        entry_list=[
            multiply_nested_container,
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
        inheritors=[apid_filtered_container.name],
        entry_list=[
            parameters.Parameter(
                name="VERSION",
                parameter_type=uint3,
                short_description="CCSDS header version"
            ),
            parameters.Parameter(
                name="TYPE",
                parameter_type=uint1,
                short_description="CCSDS header type"
            ),
            parameters.Parameter(
                name="SEC_HDR_FLG",
                parameter_type=uint1,
                short_description="CCSDS header secondary header flag"
            ),
            parameters.Parameter(
                name="APID",
                parameter_type=uint11,
                short_description="CCSDS header APID"
            ),
            parameters.Parameter(
                name="SEQ_FLGS",
                parameter_type=uint2,
                short_description="CCSDS header sequence flags"
            ),
            parameters.Parameter(
                name="SRC_SEQ_CTR",
                parameter_type=uint14,
                short_description="CCSDS header source sequence counter"
            ),
            parameters.Parameter(
                name="PKT_LEN",
                parameter_type=uint16,
                short_description="CCSDS header packet length"
            ),
            multiply_nested_container
        ]
    )

    # This list of sequence containers internally contains all parameters and parameter types
    sequence_containers = [root_container, apid_filtered_container, multiply_nested_container]

    # Create the definition object
    definition = definitions.XtcePacketDefinition(
        container_set=sequence_containers,
        root_container_name=root_container.name,
        date="2025-01-01T01:01:01",
        space_system_name="Test Space System Name"
    )

    # Serialize it to an XML string
    xtce_string = ElementTree.tostring(definition.to_xml_tree(), pretty_print=True).decode()

    # Reparse that string into a new definition object using from_document
    reparsed_definition = definitions.XtcePacketDefinition.from_xtce(
        io.StringIO(xtce_string),
        root_container_name=root_container.name
    )

    assert reparsed_definition == definition


@pytest.mark.parametrize(
    ("xml", "ns_prefix", "uri", "ns", "new_ns_prefix", "new_uri", "new_ns"),
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
         "custom",
         "http://www.fake-test.org/space/xtce",
         {"custom": "http://www.fake-test.org/space/xtce"},
         "xtcenew",
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
         None,
         "http://www.fake-test.org/space/xtce",
         {None: "http://www.fake-test.org/space/xtce"},
         "xtce",
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
         "custom",
         "http://www.fake-test.org/space/xtce",
         {"custom": "http://www.fake-test.org/space/xtce"},
         None,
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
         None,
         {},
         "xtcenew",
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
         "custom",
         "http://www.fake-test.org/space/xtce",
         {"custom": "http://www.fake-test.org/space/xtce"},
         None,
         None,
         {}),
    ]
)
def test_custom_namespacing(xml, ns_prefix, uri, ns, new_ns_prefix, new_uri, new_ns):
    """Test parsing XTCE with various namespace configurations"""
    # Parse directly from string, inferring the namespace mapping
    xdef = definitions.XtcePacketDefinition.from_xtce(io.StringIO(xml), xtce_ns_prefix=ns_prefix)
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


def test_uniqueness_of_parsed_xtce_objects():
    """When we parse a document, we expect a singleton reference to each parameter, parameter type and sequence
    container definition. This test proves that these references are all unique
    """
    xtce = """
<xtce:SpaceSystem xmlns:xtce="http://www.omg.org/space/xtce" name="Libera">
    <xtce:Header date="2021-06-08T14:11:00MST" version="1.0" author="Gavin Medley"/>
    <xtce:TelemetryMetaData>
        <xtce:ParameterTypeSet>
            <xtce:IntegerParameterType name="UINT3_Type" signed="false">
                <xtce:IntegerDataEncoding sizeInBits="3" encoding="unsigned"/>
            </xtce:IntegerParameterType>
            <xtce:IntegerParameterType name="UINT1_Type" signed="false">
                <xtce:IntegerDataEncoding sizeInBits="1" encoding="unsigned"/>
            </xtce:IntegerParameterType>
        </xtce:ParameterTypeSet>
        <xtce:ParameterSet>
            <xtce:Parameter name="PARAM_1" parameterTypeRef="UINT3_Type"/>
            <xtce:Parameter name="PARAM_2" parameterTypeRef="UINT3_Type"/>
            <xtce:Parameter name="PARAM_3" parameterTypeRef="UINT1_Type"/>
            <xtce:Parameter name="PARAM_4" parameterTypeRef="UINT1_Type"/>
        </xtce:ParameterSet>
        <xtce:ContainerSet>
            <xtce:SequenceContainer name="CCSDSPacket" abstract="true">
                <xtce:EntryList>
                    <xtce:ParameterRefEntry parameterRef="PARAM_1"/>
                    <xtce:ParameterRefEntry parameterRef="PARAM_2"/>
                </xtce:EntryList>
            </xtce:SequenceContainer>
            <xtce:SequenceContainer name="CCSDSTelemetryPacket" abstract="true">
                <xtce:LongDescription>Super-container for all telemetry packets</xtce:LongDescription>
                <xtce:EntryList/>
                <xtce:BaseContainer containerRef="CCSDSPacket">
                    <xtce:RestrictionCriteria>
                        <xtce:Comparison parameterRef="PARAM_1" value="0" useCalibratedValue="false"/>
                    </xtce:RestrictionCriteria>
                </xtce:BaseContainer>
            </xtce:SequenceContainer>
            <xtce:SequenceContainer name="SecondaryHeaderContainer" abstract="true">
                <xtce:EntryList>
                    <xtce:ParameterRefEntry parameterRef="PARAM_3"/>
                </xtce:EntryList>
            </xtce:SequenceContainer>
            <xtce:SequenceContainer name="USES_SecondaryHeaderContainer">
                <xtce:EntryList>
                    <xtce:ContainerRefEntry containerRef="SecondaryHeaderContainer"/>
                    <xtce:ParameterRefEntry parameterRef="PARAM_4"/>
                </xtce:EntryList>
                <xtce:BaseContainer containerRef="CCSDSTelemetryPacket">
                    <xtce:RestrictionCriteria>
                        <xtce:Comparison parameterRef="PARAM_2" value="11" useCalibratedValue="false"/>
                    </xtce:RestrictionCriteria>
                </xtce:BaseContainer>
            </xtce:SequenceContainer>
            <xtce:SequenceContainer name="ALSO_USES_SecondaryHeaderContainer">
                <xtce:EntryList>
                    <xtce:ContainerRefEntry containerRef="SecondaryHeaderContainer"/>
                    <xtce:ParameterRefEntry parameterRef="PARAM_1"/>
                </xtce:EntryList>
            </xtce:SequenceContainer>
        </xtce:ContainerSet>
    </xtce:TelemetryMetaData>
</xtce:SpaceSystem>
"""
    xdef = definitions.XtcePacketDefinition.from_xtce(io.StringIO(xtce))

    def_param_ids = [id(p) for p in xdef.parameters.values()]
    def_param_type_ids = [id(pt) for pt in xdef.parameter_types.values()]
    def_cont_ids = [id(sc) for sc in xdef.containers.values()]

    def _flatten_container(container: containers.SequenceContainer):
        for entry in container.entry_list:
            if isinstance(entry, containers.SequenceContainer):
                if id(entry) not in def_cont_ids:
                    raise AssertionError(f"{entry.name} object not in def.containers")
                _flatten_container(entry)
            else:
                if id(entry.parameter_type) not in def_param_type_ids:
                    raise AssertionError(f"{entry.parameter_type.name} not in definition.parameter_types")
                if id(entry) not in def_param_ids:
                    raise AssertionError(f"{entry.name} not in definition.parameters")

    for sc in xdef.containers.values():
        _flatten_container(sc)


def test_uniqueness_of_reused_sequence_container(jpss_test_data_dir):
    """Test that a reused sequence container element (nested into multiple entry lists)
    is still the same object

    This is a rather particular test that tests for regressions on a specific fixed behavior
    """
    jpss_xtce = jpss_test_data_dir / 'contrived_inheritance_structure.xml'
    jpss_definition = definitions.XtcePacketDefinition.from_xtce(xtce_document=jpss_xtce)
    assert isinstance(jpss_definition, definitions.XtcePacketDefinition)

    # Prove that parsed sequence container objects are referencing the same objects, not duplicates
    unused_secondary_header_container_ref = jpss_definition.containers["UNUSED"].entry_list[0]
    assert isinstance(unused_secondary_header_container_ref, containers.SequenceContainer)
    jpss_att_ephem_header_container_ref = jpss_definition.containers["JPSS_ATT_EPHEM"].entry_list[0]
    assert isinstance(jpss_att_ephem_header_container_ref, containers.SequenceContainer)
    assert unused_secondary_header_container_ref in jpss_definition.containers.values()
    assert jpss_att_ephem_header_container_ref in jpss_definition.containers.values()
    assert unused_secondary_header_container_ref is jpss_att_ephem_header_container_ref


def test_deprecated_definition_class(test_data_dir):
    """Test that the deprecated XtcePacketDefinition class still works"""
    with pytest.warns(UserWarning, match="The space_packet_parser.definitions module is deprecated"):
        from space_packet_parser.definitions import XtcePacketDefinition as DeprecatedXtcePacketDefinition

    with pytest.warns(UserWarning, match="This class is deprecated"):
        xtce = DeprecatedXtcePacketDefinition(test_data_dir / "test_xtce.xml")
    assert xtce.containers == definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce.xml").containers

