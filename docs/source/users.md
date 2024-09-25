# User Documentation (Getting Started)
## Installation
This package is distributed via PyPI. To install it with pip, run:

```shell
pip install space_packet_parser
```

## Basic Usage
Usage with XTCE packet definition:

```python
from pathlib import Path
from space_packet_parser import definitions

packet_file = Path('my_packets.pkts')
xtce_document = Path('my_xtce_document.xml')
packet_definition = definitions.XtcePacketDefinition(xtce_document)

# You can introspect the packet definition to learn about what was parsed
# Look up a type (includes unit and encoding info)
pt = packet_definition.named_parameter_types["MY_PARAM_Type"]
# Look up a parameter (includes short and long descriptions)
p = packet_definition.named_parameters['MY_PARAM']
# Look up a sequence container (includes inheritance)
sc = packet_definition.named_containers['SecondaryHeaderContainer']
# See the API docs for more information about the ParameterType, Parameter, and SequenceContainer classes

with packet_file.open("rb") as binary_data:
    packet_generator = packet_definition.packet_generator(binary_data)

    for packet in packet_generator:
        # Do something with the packet data, which behaves like a dict
        print(packet['PKT_APID'])
        print(packet.header)  # subset of packet
        print(packet.user_data)  # subset of packet
```

We aim to provide examples of usage patterns. Please see the `examples` directory in the GitHub repo. If there is 
a specific example you want to see demonstrated, please open a GitHub Issue or Discussion for support.

## Parsing from a Socket
The input data object to `XtcePacketDefinition.packet_generator` need only be a binary filelike object from which 
bytes can be read. This means the packet generator is not limited to parsing data from files! In an effort to support
development of quicklook type tools, we provide an example of parsing data streaming through a socket in 
`parsing_and_plotting_idex_waveforms_from_socket.py`. 

The example mocks the behavior of an instrument sending packet data asynchronously 
through a socket in chunks of inconsistent size. The packet parser reads bytes from the receiver side of the socket 
and will read data repeatedly until there is sufficient data for the full packet. Once it has a full packet 
(as determined by the packet length in the CCSDS header), it cranks the generator and yields a parsed packet. 

You'll notice that the example ends with a timeout error. This timeout can be controlled when creating the socket 
connection with `receiver.settimeout(timeout_seconds)`.

## Variable Length Packet Fields of Explicit Length
Flight software engineers often need to downlink data (usually binary blobs) of variable length. The length of these 
fields is often specified in a _previous_ telemetry point in the same packet, and you have to fetch 
the length by referencing that previous field. 

### Explicit Variable Length Example
Suppose the variable length field is called `SCI_DATA` and is a binary blob (e.g. of compressed data).
The length of this field is specified earlier in the packet in a field called `SCI_DATA_BYTELEN`, specified in
number of bytes. To define the type for `SCI_DATA` in XTCE, you could use the following (snippet):

```xml
<xtce:BinaryParameterType>
    <xtce:BinaryDataEncoding>
        <xtce:SizeInBits>
            <xtce:DynamicValue>
                <xtce:ParameterInstanceRef parameterRef="SCI_DATA_BYTELEN" useCalibratedValue="false"/>
                <xtce:LinearAdjustment intercept="0" slope="8"/>
            </xtce:DynamicValue>
        </xtce:SizeInBits>
    </xtce:BinaryDataEncoding>
</xtce:BinaryParameterType>
```

This tells the parser that the size in bits of data type `SCI_DATA_Type` (the type of `SCI_DATA`) is the raw value 
encoded in the parameter `SCI_DATA_BYTELEN`, multiplied by 8 (to convert number of bytes to number of bits).

## Variable Length Packet Fields of Implicit Length
In some circumstances, flight software teams define a packet field that simply fills up the "remaining space" in the 
packet. The length of this field is usually implicit but can be computed by subtracting the combined length of all 
fixed length fields in the packet from the total length of the packet specified in the CCSDS header.

The `PKT_LEN` field is the length of the packet user data, in bytes. This field: 
- counts from zero
- does not include the header data (always 6 bytes)

Thus, you can determine the length of your field dynamically from the packet length in the CCSDS header:

$$len_{var} = 8 \times (len_{packet} + 1) - \sum_n len_{fixed,n}$$

where 
- $len_{var}$ is the length, in bits, of the variable length field
- $len_{packet}$ is the packet user data length in bytes (from the CCSDS header)
- $\sum_n len_{fixed,n}$ is the combined length of all fixed length fields in the packet user data

There are some limitations to this. If your FSW team is violating these limitations, they are making your life 
extremely difficult, and you have my condolences.
- You can only have a _single_ "remaining packet length" field in a given packet definition. Encoding more than one 
  such field makes it impossible to determine the length of the fields.
- All other fields in the packet _must_ be fixed length. There is no way that I know of in XTCE to calculate a 
  dynamic length that is an arbitrary function of multiple previous length specifier fields.

### Implicit Variable Length Example
Packet Definition:
```text 
"VERSION" : 3 bits  
"TYPE" : 1 bits  
"SEC_HDR_FLG" : 1 bits  
"PKT_APID" : 11 bits  
"SEQ_FLGS" : 2 bits  
"SRC_SEQ_CTR" : 14 bits  
"PKT_LEN" : 16 bits  
"SHCOARSE" : 32 bits  
"SID" : 8 bits  
"SPIN" : 8 bits  
"ABORTFLAG" : 1 bits  
"STARTDELAY" : 15 bits  
"COUNT" : 8 bits  
"EVENTDATA": variable length
```

To calculate the length of `EVENTDATA`:

```{math}
len_{var} &= 8 \times (len_{packet} + 1) - (&&len_{SHCOARSE} + len_{SID} + len_{SPIN} + \\
          &                                 &&len_{ABORTFLAG} + len_{STARTDELAY} + len_{COUNT})\\
          &= 8 \times (len_{packet} + 1) - (&&32 + 8 + 8 + 1 + 15 + 8)\\
          &= 8 \times len_{packet} - 64     &&
```

This equation can be implemented in XTCE by referencing the packet length field as follows:

```xml
<xtce:BinaryParameterType name="EVENTDATA_Type" >
    <xtce:BinaryDataEncoding>
        <xtce:SizeInBits>
            <xtce:DynamicValue>
                <xtce:ParameterInstanceRef parameterRef="PKT_LEN"/>
                <xtce:LinearAdjustment intercept="-64" slope="8"/>
            </xtce:DynamicValue>
        </xtce:SizeInBits>
    </xtce:BinaryDataEncoding>
</xtce:BinaryParameterType>
```

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

## Common Issues and Solutions
### Parser Generator Completes without Yielding a Packet
This can occur if your data file contains only packets that do not match any packet definitions in your XTCE document 
and `yield_unrecognized_packet_errors=False` (the default). This could mean that your data file actually contains only 
APIDs that are not covered in your packet definition, but usually it means you have incorrectly defined 
restriction criteria for SequenceContainer inheritance.

For example a restriction criteria element that requires an APID which does not exist in the data.
```xml
<xtce:RestrictionCriteria>
    <xtce:Comparison parameterRef="PKT_APID" value="-99" useCalibratedValue="false"/>
</xtce:RestrictionCriteria>
```

### Only Packet Headers are Parsed
If you observe that only packet headers are being parsed but no exceptions are being raised (you may be seeing a 
lot of length mismatch warnings if you have logging set up), it likely means that 
you have forgotten to set `abstract="true"` on your non-concrete sequence container elements.

For example
```xml
<xtce:SequenceContainer name="CCSDSPacket">
    <xtce:LongDescription>Super-container for telemetry and command packets</xtce:LongDescription>
    <xtce:EntryList>
        <xtce:ParameterRefEntry parameterRef="VERSION"/>
        <xtce:ParameterRefEntry parameterRef="TYPE"/>
    </xtce:EntryList>
</xtce:SequenceContainer>
```
will parse as a complete packet, containing only `VERSION` and `TYPE` instead of searching for inheriting sequence 
containers. To define the container as abstract, change the first element opening tag to
```xml
<xtce:SequenceContainer name="CCSDSPacket" abstract="true">
...contents
</xtce:SequenceContainer>
```

## Optimizing for Performance
The logic evaluated during packet parsing is largely reflective of the XTCE configuration being used 
to define packet structures. The more logic in the XTCE, the more logic must be evaluated during 
parsing. Below are some common ways to reduce complexity and speed up parsing:

1. **Remove `RestrictionCriteria` Elements:** If your packet stream is a single packet structure, 
    there is no reason to require the evaluation of a restriction criteria for each packet. 
2. **Remove Unnecessary Packet Definitions:** Even in a packet stream with multiple packet formats, if you only
    care about one packet type, you can remove the definitions for the other. By default, the packet `Parser` will 
    catch unrecognized packet errors and skip to the next packet. This skips the parsing of packets 
    for which a valid definition cannot be determined.
3. **Reduce Container Inheritance:** A flat container definition structure will evaluate restriction criteria
    faster than a nested structure. Each instance of nesting requires an additional `MatchCriteria.evaluate()`
    call for each packet being parsed. 
4. **Reduce Complex Items:** Parameter type definitions that contain calibrators or complex string parsing 
    (especially variable length termination character defined strings) add significant evaluation logic to 
    the parsing of each parameter, as does any parameter type that is variable length. 
    Removing them can speed up parsing.
