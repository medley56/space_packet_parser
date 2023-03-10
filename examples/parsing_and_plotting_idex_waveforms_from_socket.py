"""Example of parsing and plotting IDEX data from a socket

This is basically a rudimentary quickview tool. It demonstrates how this library can be used, in conjunction with
other tools like matplotlib to parse, organize, and plot data coming through a socket. The low level packet parsing
is done based on the XTCE definition for IDEX but there is significant additional logic that parses and concatenates
the binary blob fields of the packets, which contain the science data arrays.

The packet definition used here is intended for IDEX, which is basically a rebuild of the idex instrument.
The data used here is IDEX data but the fields are parsed using IDEX naming conventions.

Note: This example requires the matplotlib library which is not part of the base dependency spec for space_packet_parser.
"""
# Standard
from multiprocessing import Process
from pathlib import Path
import random
import socket
import time
# Installed
import bitstring
import matplotlib.pyplot as plt
# Local
from space_packet_parser import xtcedef
from space_packet_parser import parser


def send_data(sender: socket.socket, file: Path):
    """Send data from a file as bytes via a socket with random chunk sizes and random waits between sending chunks

    Parameters
    ----------
    sender : socket.socket
        Socket over which to send the data.
    file : Path
        File to send as bytes over a socket connection
    """
    # Read binary file
    with file.open('rb') as fh:
        stream = bitstring.ConstBitStream(fh)
        while stream.pos < len(stream):
            time.sleep(random.random() * .1)  # Random sleep up to 1s
            # Send binary data to socket in random chunk sizes
            random_n_bytes = random.randint(1024, 2048)
            n_bits_to_send = 8 * random_n_bytes
            if stream.pos + n_bits_to_send > len(stream):
                n_bits_to_send = len(stream) - stream.pos
            chunk_to_send = stream[stream.pos:stream.pos + n_bits_to_send]
            print(f"Sending {len(chunk_to_send)} bytes")
            sender.send(chunk_to_send.bytes)
            stream.pos += n_bits_to_send
        print("\nFinished sending data.")


def parse_hg_waveform(waveform_raw: str):
    """Parse a binary string representing a high gain waveform"""
    w = bitstring.ConstBitStream(bin=waveform_raw)
    ints = []
    while w.pos < len(w):
        w.read('pad:2')  # skip 2. Note: for old versions of bitstring, use bits:2, not pad:2.
        ints += w.readlist(['uint:10']*3)
    return ints


def parse_lg_waveform(waveform_raw: str):
    """Parse a binary string representing a low gain waveform"""
    w = bitstring.ConstBitStream(bin=waveform_raw)
    ints = []
    while w.pos < len(w):
        w.read('pad:8')  # skip 8
        ints += w.readlist(['uint:12']*2)
    return ints


def parse_waveform_data(waveform: str, scitype: int):
    """Parse the binary string that represents a waveform"""
    print(f'Parsing waveform for scitype={scitype}')
    if scitype in (2, 4, 8):
        return parse_hg_waveform(waveform)
    else:
        return parse_lg_waveform(waveform)


def plot_full_event(data: dict):
    """Plot a full event (6 channels)"""
    fix, ax = plt.subplots(nrows=6)
    for i, (s0t, d) in enumerate(data.items()):
        ax[i].plot(d)
        ax[i].set_ylabel(s0t)
    plt.show()


if __name__ == "__main__":
    """Parse IDEX data"""
    idex_test_data_dir = Path("../tests/test_data/idex")
    idex_xtce = idex_test_data_dir / 'idex_combined_science_definition.xml'
    idex_definition = xtcedef.XtcePacketDefinition(xtce_document=idex_xtce)
    assert isinstance(idex_definition, xtcedef.XtcePacketDefinition)
    idex_parser = parser.PacketParser(idex_definition)
    idex_packet_file = idex_test_data_dir / 'sciData_2023_052_14_45_05'

    sender, receiver = socket.socketpair()
    receiver.settimeout(3)
    file = '/Users/game1390/Workspace/space/space_packet_parser/tests/test_data/jpss/J01_G011_LZ_2021-04-09T00-00-00Z_V01.DAT1'
    p = Process(target=send_data, args=(sender, idex_packet_file,))
    p.start()

    # Create a packet generator that listens to a socket
    idex_packet_generator = idex_parser.generator(receiver)

    try:
        p = next(idex_packet_generator)
        print(p)
        while True:
            if 'IDX__SCI0TYPE' in p.data:
                scitype = p.data['IDX__SCI0TYPE'].raw_value
                print(scitype)
                if scitype == 1:  # This packet marks the beginning of an "event"
                    data = {}
                    event_header = p
                    # Each time we encounter a new scitype, that represents a new channel so we create a new array.
                    # A single channel of data may be spread between multiple packets, which must be concatenated.
                    p = next(idex_packet_generator)
                    scitype = p.data['IDX__SCI0TYPE'].raw_value
                    print(scitype, end=", ")
                    data[scitype] = p.data['IDX__SCI0RAW'].raw_value
                    while True:
                        # If we run into the end of the file, this will raise StopIteration and break both while loops
                        p_next = next(idex_packet_generator)
                        next_scitype = p_next.data['IDX__SCI0TYPE'].raw_value
                        print(next_scitype, end=", ")
                        if next_scitype == scitype:
                            # If the scitype is the same as the last packet, then concatenate them
                            data[scitype] += p_next.data['IDX__SCI0RAW'].raw_value
                        else:
                            # Otherwise check if we are at the end of the event (next scitype==1)
                            if next_scitype == 1:
                                break
                            scitype = next_scitype
                            data[scitype] = p_next.data['IDX__SCI0RAW'].raw_value
                    p = p_next
                    # If you have more than one complete event in a file (i.e. scitype 1, 2, 4, 8, 16, 32, 64),
                    # this loop would continue.
                    # For this example, we only have one full event so we have already hit a StopIteration by
                    # this point.

                # We denote channels by their scitype value (2, 4, 8, 16, 32, 64) and parse the waveform binary blob
                # data using functions defined above.
                data = {scitype: parse_waveform_data(waveform, scitype) for scitype, waveform in data.items()}
                plot_full_event(data)
    except StopIteration:
        data = {scitype: parse_waveform_data(waveform, scitype) for scitype, waveform in data.items()}
        plot_full_event(data)
        print("\nEncountered the end of the binary file.")
        pass
