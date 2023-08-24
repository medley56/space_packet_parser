# Changes
This is a log of changes made to the library over time

## Long Term To-Do List
- Add frame transfer parsing layer on top of CCSDS parsing layer
- Support BooleanExpression in a ContextCalibrator
- Add ByteOrderList support to encodings in xtcedef (search for TODOs)
- Support multiple `xtce:Unit` elements for compound units

# Version Release Notes
Release notes for the `space_packet_parser` library

## v4.1.0 (unreleased)
- Bugfix in fill_buffer to allow compatibility with Bitstring 4.1.1

## v4.0.2 (released)
- Documentation updates for Read The Docs

## v4.0.1 (released)
- Modify API for `PacketParser.generator` to accept a ConstBitStream or a BufferedReader or a socket
  - This will allow us to keep memory overhead of reading a binary stream to almost zero
- Add examples directory to help users
- Add CITATION.cff
- Add CODE_OF_CONDUCT.md

# Historical Changes (`lasp_packets`)
Changes documented in v3.0 and earlier correspond to development efforts undertaken before this library was
moved to GitHub (it was previously known as `lasp_packets`). 
None of the git history is available for these versions as the git history was truncated 
in preparation for the move to Github to prevent accidental release of non-public example data which may be 
(but probably isn't) present in historical commits.

## v3.0 (released publicly)
- Add a discussion of optimization to the documentation
- Change license to BSD3 and CU copyright
- Add support for Python 3.10 and 3.11
- Remove support for Python 3.6
- Redesign the way the parser interprets the SequenceContainer inheritance structure
  - This allows polymorphic packet structures based on flags in telemetry
  - Previous functionality is preserved
  - csvdef module still uses the legacy flattened_containers representation
- Add Parser.generator kwargs tdocs/source/index.rsto aid in debugging
- Add kwarg to only parse CCSDS headers and skip the user data
- Add optional progress bar that prints to stdout when parsing a packets file.

## v2.1 (released publicly)
- Update documentation on release process

## v2.0 (released internally)
- Add link in readme to v1.2 Aug 2021 of XTCE spec
- Add support for `< xtce:DiscreteLookupList >`
- Add support for `< xtce:Condition >`
- Add support for `< xtce:BooleanExpression >`
- Push the evaluation logic for ParameterTypes down to DataEncodings
- Add option to skip an additional header on each packet
- Modify RestrictionCriteria parser to evaluate MatchCriteria elements
- Add word size as an optional parameter to the parser
- Add an optional header name remapping parameter to the parser
- Add support for BooleanExpression in a RestrictionCriteria element

## v1.3 (released internally)
- Expand version compatiblity for python >=3.6, <4

## v1.2 (released internally)
- Remove unnecessary warning about float data types being IEEE formatted.
- Switch package manager to Poetry.
- Add support for instantiating definitions with pathlib.Path objects.

## v1.1.0 (released internally)
- Add support for CSV-based packet definitions (contribution by Michael Chambliss).

## v1.0 (released internally)
- Add support for all parameter types. 
- Add support for all data encodings.
- Add support for calibrators and contextual calibrators.
- Add support for variable length strings given by termination characters or preceding length fields.
- Add support for variable length binary data fields in utf-8, utf-16-le, and utf-16-be.
- Add build and release documentation to readme.
