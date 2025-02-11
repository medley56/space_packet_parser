"""Extras package that supports generating an `xarray.DataSet` directly"""
# Extras import first since it might fail
try:
    import numpy as np
    import xarray as xr
except ImportError as ie:
    raise ImportError(
        "Failed to import dependencies for xarray extra. Did you install the [xarray] extras package?"
    ) from ie

import collections
from collections.abc import Iterable
from pathlib import Path
from typing import Optional, Union

from space_packet_parser.xtce import definitions, encodings, parameter_types


def _min_dtype_for_encoding(data_encoding: encodings.DataEncoding):
    """Find the minimum data type capaable of representing an XTCE data encoding.

    This only works for raw values and does not apply to calibrated or otherwise derived values.

    Parameters
    ----------
    data_encoding : encodings.DataEncoding
        The raw data encoding.

    Returns
    -------
    : str
        The numpy dtype string for the minimal representation of the data encoding.
    """
    if isinstance(data_encoding, encodings.IntegerDataEncoding):
        nbits = data_encoding.size_in_bits
        datatype = "int"
        if data_encoding.encoding == "unsigned":
            datatype = "uint"
        if nbits <= 8:
            datatype += "8"
        elif nbits <= 16:
            datatype += "16"
        elif nbits <= 32:
            datatype += "32"
        else:
            datatype += "64"
    elif isinstance(data_encoding, encodings.FloatDataEncoding):
        nbits = data_encoding.size_in_bits
        datatype = "float"
        if nbits == 32:
            datatype += "32"
        else:
            datatype += "64"
    elif isinstance(data_encoding, encodings.BinaryDataEncoding):
        datatype = "bytes"
    elif isinstance(data_encoding, encodings.StringDataEncoding):
        datatype = "str"
    else:
        raise ValueError(f"Unrecognized data encoding type {data_encoding}.")

    return datatype


def _get_minimum_numpy_datatype(
        name: str,
        definition: definitions.XtcePacketDefinition,
        use_raw_value: bool = False
) -> Optional[str]:
    """
    Get the minimum datatype for a given variable.

    Parameters
    ----------
    name : str
        The variable name.
    definition : definitions.XtcePacketDefinition
        The XTCE packet definition. Used to examine data types to infer their niminal numpy representation.
    use_raw_value : bool
        Default False. If True, uses the data type of the raw value for each parameter.

    Returns
    -------
    datatype : Optional[str]
        The minimum numpy dtype for the parameter.
        Returns None to indicate that numpy should use default dtype inference.
    """
    parameter_type = definition.get_parameters(name).parameter_type
    data_encoding = parameter_type.encoding

    if use_raw_value:
        # If we are using raw values, we can determine the minimal dtype from the parameter data encoding
        return _min_dtype_for_encoding(data_encoding)

    if isinstance(data_encoding, encodings.NumericDataEncoding):
        if not (data_encoding.context_calibrators is not None or data_encoding.default_calibrator is not None):
            # If there are no calibrators attached to the encoding, then we can proceed as if we're using
            # raw values
            return _min_dtype_for_encoding(data_encoding)
        # If there are calibrators present, we really can't know the size of the resulting values.
        # Let numpy infer the datatype as best it can
        return None

    if isinstance(data_encoding, encodings.BinaryDataEncoding):
        return "bytes"

    if isinstance(parameter_type, parameter_types.EnumeratedParameterType):
        # Enums are always strings in their derived state
        return "str"

    if isinstance(data_encoding, encodings.StringDataEncoding):
        return "str"

    raise ValueError(f"Unsupported data encoding: {data_encoding}")


def create_dataset(
        packet_files: Union[str, Path, Iterable[Union[str, Path]]],
        xtce_packet_definition: Union[str, Path, definitions.XtcePacketDefinition],
        use_raw_values: bool = False,
        **packet_generator_kwargs: any
):
    """Create an xarray dataset from an iterable of parsed packet objects

    # TODO: Filter by APID to handle muxed streams?

    Notes
    -----
    This function only handles packet definitions with the same variable structure
    across all packets with the same ApId. For example, this cannot be used for polymorphic
    packets whose structure changes based on previously parsed values.

    Parameters
    ----------
    packet_files : Union[str, Path, Iterable[Union[str, Path]]]
        Packet files
    xtce_packet_definition : Union[str, Path, XtcePacketDefinition]
        Packet definition for parsing the packet data
    use_raw_values: bool
        Default False. If True, saves parameter raw values to the resulting DataSet.
        e.g. enumerated lookups will be saved as their encoded integer values.
    packet_generator_kwargs : Optional[dict]
        Keyword arguments passed to `XtcePacketDefinition.packet_generator()`

    Returns
    -------
    : xarray.DataSet
        DataSet object parsed from the iterable of packets.
    """
    packet_generator_kwargs = packet_generator_kwargs or {}

    if not isinstance(xtce_packet_definition, definitions.XtcePacketDefinition):
        xtce_packet_definition = definitions.XtcePacketDefinition.from_xtce(xtce_packet_definition)

    if isinstance(packet_files, (str, Path)):
        packet_files = [packet_files]

    # Set up containers to store our data
    # We are getting a packet file that may contain multiple apids
    # Each apid is expected to contain consistent data fields, so we want to create a
    # dataset per apid.
    # {apid1: dataset1, apid2: dataset2, ...}
    data_dict: dict[int, dict] = {}
    # Also keep track of the datatype mapping for each field
    datatype_mapping: dict[int, dict] = {}
    # Keep track of which variables (keys) are in the dataset
    variable_mapping: dict[int, set] = {}

    for packet_file in packet_files:
        with open(packet_file, "rb") as f:
            packet_generator = list(xtce_packet_definition.packet_generator(f, **packet_generator_kwargs))

        for packet in packet_generator:
            apid = packet.raw_data.apid
            if apid not in data_dict:
                # This is the first packet for this APID
                data_dict[apid] = collections.defaultdict(list)
                datatype_mapping[apid] = {}
                variable_mapping[apid] = packet.keys()

            if variable_mapping[apid] != packet.keys():
                raise ValueError(
                    f"Packet fields do not match for APID {apid}. This could be "
                    f"due to a conditional (polymorphic) packet definition in the XTCE, while this "
                    f"function currently only supports flat packet definitions."
                    f"\nExpected: {variable_mapping[apid]},\ngot: {list(packet.keys())}"
                )

            for key, value in packet.items():
                if use_raw_values:
                    # Use the derived value if it exists, otherwise use the raw value
                    val = value.raw_value
                else:
                    val = value

                data_dict[apid][key].append(val)
                if key not in datatype_mapping[apid]:
                    # Add this datatype to the mapping
                    datatype_mapping[apid][key] = _get_minimum_numpy_datatype(
                        key, xtce_packet_definition, use_raw_value=use_raw_values
                    )

    # Turn the dict into an xarray dataset
    dataset_by_apid = {}

    for apid, data in data_dict.items():
        ds = xr.Dataset(
            data_vars={
                key: (["packet"], np.asarray(list_of_values, dtype=datatype_mapping[apid][key]))
                for key, list_of_values in data.items()
            }
        )

        dataset_by_apid[apid] = ds

    return dataset_by_apid
