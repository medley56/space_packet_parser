# Space Packet Parser
This is a package for decoding CCSDS telemetry packets according to an XTCE or CSV format specification. 
It is based on the UML model of the XTCE spec and aims to support all but the most esoteric elements of the 
XTCE telemetry packet specification.

Resources:
- [XTCE (Green Book - Informational Report)](https://public.ccsds.org/Pubs/660x2g2.pdf)
- [XTCE Element Description (Green Book - Informational Report)](https://public.ccsds.org/Pubs/660x1g2.pdf)
- [XTCE (Blue Book - Recommended Standard)](https://public.ccsds.org/Pubs/660x0b2.pdf)

## Installation
```bash
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

with packet_file.open() as binary_data:
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

with packet_file.open() as binary_data:
    packet_generator = my_parser.generator(binary_data)

    for packet in packet_generator:
        # Do something with the packet data
        print(packet.header['PKT_APID'])
        print(packet.data)
```

### Examples
As part of our integration testing, we have provided examples for several packet types.
The simplest is the JPSS parsing, which parses fixed length invariantly structured packets. 
The most complex is SUDA, which uses a polymorphic packet structure 
based on the value of `SCIFETCHTYPE` (for APID 1425) or `SCI0TYPE` (for APID 1424).

The only example for CSV parsing is CTIM.

### Debugging Packet Parsing
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

### Optimizing for Performance
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

## Developer Documentation
### Installing Development Dependencies
Poetry installs dev dependencies by default from the `poetry.lock` or `pyproject.toml` files. Just run 
```bash
poetry install
```

### Testing
Testing is run with `pytest` and the order is randomized by `pytest-randomly`. 
To run all tests, run
```bash
pytest tests
```

To run all tests in docker containers (tests against many versions of python), run
```bash
docker-compose up --build && docker-compose down
```

### Release Process
Reference: [https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow]()

1. Create a release candidate branch named according to the version to be released. This branch is used to polish
   the release while work continues on dev (towards the next release). The naming convention is `release/X.Y.Z`

2. Bump the version of the package to the version you are about to release, either manually by editing `pyproject.toml`
   or by running `poetry version X.Y.Z` or bumping according to a valid bump rule like `poetry version minor`
   (see poetry docs: https://python-poetry.org/docs/cli/#version).

3. Update the version identifier in CITATION.cff.

4. Update `CHANGES.md` to reflect that the version is now "released" and revisit `README.md` to keep it up to date.
   
5. Open a PR to merge the release branch into master. This informs the rest of the team how the release 
   process is progressing as you polish the release branch.

6. When you are satisfied that the release branch is ready, merge the PR into `master`. 

7. Check out the `master` branch, pull the merged changes, and tag the newly created merge commit with the 
   desired version `X.Y.Z` and push the tag upstream. 
   
   ```bash
   git tag -a X.Y.Z -m "version release X.Y.Z"
   git push origin X.Y.Z
   ```
   
8. Ensure that you have `master` checked out and build the package (see below).
   Check that the version of the built artifacts is as you expect (should match the version git tag and the 
   output from `poetry version --short`).
   
9. Optionally distribute the artifacts to PyPI/Nexus if desired (see below).
   
10. Open a PR to merge `master` back into `dev` so that any changes made during the release process are also captured
    in `dev`. 


### Building and Distribution
1. Ensure that `poetry` is installed by running `poetry --version`.
   
2. To build the distribution archives, run `poetry build`.
   
3. To upload the wheel to Nexus, run `poetry publish`. You will need credentials to sign into PyPI.
