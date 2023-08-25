# User Documentation
## Installation
This package is distributed via PyPI. To install it with pip, run:

```shell
pip install space_packet_parser
```

## Basic Usage
Usage with XTCE packet definition:

```python
from pathlib import Path
from space_packet_parser import xtcedef, parser

packet_file = Path('my_packets.pkts')
xtce_document = Path('my_xtce_document.xml')
packet_definition = xtcedef.XtcePacketDefinition(xtce_document)
my_parser = parser.PacketParser(packet_definition)

with packet_file.open("rb") as binary_data:
    packet_generator = my_parser.generator(binary_data)

    for packet in packet_generator:
        # Do something with the packet data
        print(packet.header['PKT_APID'])
        print(packet.data)
```

Usage with CSV packet definition:

```python
from pathlib import Path
from space_packet_parser import csvdef, parser

packet_file = Path('my_packets.pkts')
csv_document = Path('my_csv_file.csv')
packet_definition = csvdef.CsvPacketDefinition(csv_document)
my_parser = parser.PacketParser(packet_definition)

with packet_file.open("rb") as binary_data:
    packet_generator = my_parser.generator(binary_data)

    for packet in packet_generator:
        # Do something with the packet data
        print(packet.header['PKT_APID'])
        print(packet.data)
```

## Examples
As part of our integration testing, we aim to provide examples of usage patterns. Please see the `examples` directory
in the Github repo.

## Troubleshooting Packet Parsing
Parsing binary packets is error-prone and getting the XTCE definition correct can be a challenge at first. 
Most flight software teams can export XTCE from their command and telemetry database but these exports usually require 
some fine-tuning. 

`UnrecognizedPacketError`s are raised during parsing of an individual packet when either:

- a) multiple child containers are valid inheritors of the current sequence container based on 
   restriction criteria evaluated against the data parsed so far
- b) no child containers are valid inheritors of the current sequence container based on 
  restriction criteria evaluated against the data parsed so far 
  and the current container is abstract

To aid you during development, `UnrecognizedPacketError` exceptions generated during parsing can be returned 
alongside any valid packet objects by setting `yield_unrecognized_packet_errors=True`. 
These exception objects are not raised so that the generator may keep parsing. Instead, they 
are yielded from the generator with a `partial_data` attribute for user examination. This partial data allows you to 
see how far it got through a container inheritance structure before failing to determine the rest of the structure. 

## Optimizing for Performance
The logic evaluated during packet parsing is largely reflective of the XTCE configuration being used 
to define packet structures. The more logic in the XTCE, the more logic must be evaluated during 
parsing. Below are some common ways to reduce complexity and speed up parsing:

1. **Remove `RestrictionCriteria` Elements:** If your packet stream is a single packet structure, 
    there is no reason to require the evaluation of a restriction criteria for each packet. 
2. **Remove Unnecessary Packet Definitions:** Even in a packet stream with multiple packet formats, if you only
    care about one packet type, you can remove the definitions for the other. By default the packet `Parser` will 
    catch unrecognized packet errors and skip to the next packet. This skips the parsing of packets 
    for which a valid definition cannot be determined.
3. **Reduce Container Inheritance:** A flat container definition structure will evaluate restriction criteria
    faster than a nested structure. Each instance of nesting requires an additional `MatchCriteria.evaluate()`
    call for each packet being parsed. 
4. **Reduce Complex Items:** Parameter type definitions that contain calibrators or complex string parsing 
    (especially variable length termination character defined strings) add significant evaluation logic to 
    the parsing of each parameter, as does any parameter type that is variable length. 
    Removing them can speed up parsing.