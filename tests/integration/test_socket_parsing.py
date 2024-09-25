"""Mock socket streaming and listener that decodes on the fly"""
# Standard
from multiprocessing import Process
import random
import socket
import time
# Installed
import pytest
# Local
from space_packet_parser.definitions import XtcePacketDefinition


def send_data(sender: socket.socket, file: str):
    """Send data from a file as bytes via a socket with random chunk sizes and random waits between sending chunks

    Parameters
    ----------
    sender : socket.socket
        Socket over which to send the data.
    file : str
        File to send as bytes over a socket connection
    """
    # Read binary file
    with open(file, 'rb') as fh:
        stream = fh.read()
        pos = 0
        while pos < len(stream):
            time.sleep(random.random() * .1)  # Random sleep up to 1s
            # Send binary data to socket in random chunk sizes
            min_n_bytes = 4096
            max_n_bytes = 4096*2
            random_n_bytes = int(random.random()) * (max_n_bytes - min_n_bytes)
            n_bytes_to_send = 8 * (min_n_bytes + random_n_bytes)
            if pos + n_bytes_to_send > len(stream):
                n_bytes_to_send = len(stream) - pos
            chunk_to_send = stream[pos:pos + n_bytes_to_send]
            sender.send(chunk_to_send)
            pos += n_bytes_to_send
        print("\nFinished sending data.")


def test_parsing_from_socket(jpss_test_data_dir):
    # Create packet def
    xdef = XtcePacketDefinition(jpss_test_data_dir / 'jpss1_geolocation_xtce_v1.xml')
    # Create socket
    sender, receiver = socket.socketpair()
    receiver.settimeout(3)
    file = jpss_test_data_dir / 'J01_G011_LZ_2021-04-09T00-00-00Z_V01.DAT1'
    p = Process(target=send_data, args=(sender, file,))
    p.start()

    packet_generator = xdef.packet_generator(receiver, buffer_read_size_bytes=4096, show_progress=True)
    with pytest.raises(socket.timeout):
        packets = []
        for p in packet_generator:
            packets.append(p)

    assert len(packets) == 7200
