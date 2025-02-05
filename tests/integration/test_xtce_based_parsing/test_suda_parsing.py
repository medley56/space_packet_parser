"""Integration tests on SUDA data

The packet definition used here is intended for IDEX, which is basically a rebuild of the SUDA instrument.
The data used here is SUDA data but the fields are parsed using IDEX naming conventions.
"""
# Local
from space_packet_parser import definitions
from space_packet_parser import packets


def parse_hg_waveform(waveform_raw: str):
    """Parse a binary string representing a high gain waveform"""
    ints = []
    for i in range(0, len(waveform_raw), 32):
        # 32 bit chunks, divided up into 2, 10, 10, 10
        # skip first two bits
        ints += [
            int(waveform_raw[i + 2 : i + 12], 2),
            int(waveform_raw[i + 12 : i + 22], 2),
            int(waveform_raw[i + 22 : i + 32], 2),
        ]
    return ints


def parse_lg_waveform(waveform_raw: str):
    """Parse a binary string representing a low gain waveform"""
    ints = []
    for i in range(0, len(waveform_raw), 32):
        ints += [
            int(waveform_raw[i + 8 : i + 20], 2),
            int(waveform_raw[i + 20 : i + 32], 2),
        ]
    return ints


def parse_waveform_data(waveform: str, scitype: int):
    """Parse the binary string that represents a waveform"""
    print(f'Parsing waveform for scitype={scitype}')
    if scitype in (2, 4, 8):
        return parse_hg_waveform(waveform)
    else:
        return parse_lg_waveform(waveform)


def test_suda_xtce_packet_parsing(suda_test_data_dir):
    """Test parsing a real XTCE document"""
    suda_xtce = suda_test_data_dir / 'suda_combined_science_definition.xml'
    suda_definition = definitions.XtcePacketDefinition.from_document(xtce_document=suda_xtce)
    assert isinstance(suda_definition, definitions.XtcePacketDefinition)
    suda_packet_file = suda_test_data_dir / 'sciData_2022_130_17_41_53.spl'

    with suda_packet_file.open('rb') as suda_binary_data:
        suda_packet_generator = suda_definition.packet_generator(suda_binary_data,
                                                                 skip_header_bytes=4,
                                                                 show_progress=True)
        for suda_packet in suda_packet_generator:
            assert isinstance(suda_packet, packets.CCSDSPacket)
            assert suda_packet.header['PKT_APID'].raw_value == 1425, "APID is not as expected."
            assert suda_packet.header['VERSION'].raw_value == 0, "CCSDS header VERSION incorrect."

        suda_binary_data.pos = 0
        suda_packet_generator = suda_definition.packet_generator(suda_binary_data,
                                                                 skip_header_bytes=4)

        try:
            p = next(suda_packet_generator)
            while True:
                if 'IDX__SCIFETCHTYPE' in p:
                    scitype = p['IDX__SCIFETCHTYPE'].raw_value
                    print(scitype)
                    if scitype == 1:  # beginning of an event
                        data = {}
                        event_header = p
                        # Each time we encounter a new scitype, we create a new array.
                        p = next(suda_packet_generator)
                        scitype = p['IDX__SCIFETCHTYPE'].raw_value
                        print(scitype, end=", ")
                        data[scitype] = p['IDX__SCIFETCHRAW'].raw_value
                        while True:
                            # If we run into the end of the file, this will raise StopIteration
                            p_next = next(suda_packet_generator)
                            next_scitype = p_next['IDX__SCIFETCHTYPE'].raw_value
                            print(next_scitype, end=", ")
                            if next_scitype == scitype:
                                # If the scitype is the same as the last packet, then concatenate them
                                data[scitype] += p_next['IDX__SCIFETCHRAW'].raw_value
                            else:
                                # Otherwise check if we are at the end of the event (next scitype==1)
                                if next_scitype == 1:
                                    break
                                scitype = next_scitype
                                data[scitype] = p_next['IDX__SCIFETCHRAW'].raw_value
                        p = p_next
                        # If you have more than one event in a file (i.e. scitype 1, 2, 4, 8, 16, 32, 64),
                        # this loop would continue.
                        # For this example, we only have one full event so we have already hit a StopIteration by
                        # this point.
        except StopIteration:
            print("\nEncountered the end of the binary file.")
            pass

    expectations = {
        2: {'len': 8193, 'mean': 511.8518247284267},
        4: {'len': 8193, 'mean': 510.84450140363725},
        8: {'len': 8193, 'mean': 510.99353106310264},
        16: {'len': 512, 'mean': 2514.470703125},
        32: {'len': 512, 'mean': 1989.7421875},
        64: {'len': 512, 'mean': 2078.119140625}
    }

    # Parse the waveforms according to the scitype present (HG/LG channels encode waveform data differently)
    for scitype, waveform in data.items():
        # Convert the binary data to an integer so we can then convert it to a binary string
        int_val = int.from_bytes(waveform, byteorder="big")
        data[scitype] = parse_waveform_data(f"{int_val:0{len(waveform)*8}b}", scitype)
        print(f"{len(data[scitype])} points")
        mean = sum(data[scitype]) / len(data[scitype])
        print(f"mean value = {mean}")
        assert len(data[scitype]) == expectations[scitype]['len'], "Length of parsed waveform data does not match."
        assert mean == expectations[scitype]['mean'], "Mean value does not match expectation"

    assert set(data.keys()) == {2, 4, 8, 16, 32, 64}, "Missing a scitype value."




