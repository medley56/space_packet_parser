"""module for handling CSV-defined packet definitions"""
# Standard
import csv
import re
from collections import namedtuple
from pathlib import Path
# Local
from space_packet_parser.xtcedef import Comparison, Parameter, IntegerDataEncoding, FloatDataEncoding, StringDataEncoding, \
    IntegerParameterType, FloatParameterType, StringParameterType

FlattenedContainer = namedtuple('FlattenedContainer', ['entry_list', 'restrictions'])


class CsvPacketDefinition:
    """Object representation of a space csv definition of a CCSDS packet object"""

    def __init__(self, csv_def_filepath: str or Path, add_checksum=False):
        """Instantiate an object representation of a CCSDS packet definition, from a telemetry packet
        definition csv file. The definition for this format is not as rigorously defined anywhere to my
        knowledge. The definition has been determined from looking at existing files and referring to
        the following confluence page:
        https://confluence.space.colorado.edu/display/OSWHOME/space+CSV+to+XTCE+Conversion.

        Parameters
        ----------
        csv_def_filepath : str or Path
            Path to csv file containing packet definition.
        """

        # TODO: Add configurable checksum length or just have the check_sum_param passed in directly?
        if add_checksum:
            check_sum_type = self.get_param_type_from_str('U16', 'CHECKSUM_Type')
            self.check_sum_param = Parameter('CHECKSUM', check_sum_type)
        else:
            self.check_sum_param = None

        self._csv_def_filepath = csv_def_filepath
        self._csv_def = self.read_and_format_csv_file()
        self._flattened_containers = self.gen_flattened_containers()

    def read_and_format_csv_file(self):
        """Read in csv file and generate a list of RowTuples with each entry representing one row
        from the file. Also rename any columns to conform to the expected names if needed.

        Returns
        -------
        : list of RowTuple
            A list containing all the rows, in order, from the CSV definition file.
        """
        with open(self._csv_def_filepath, encoding='utf-8') as csv_file:
            csv_reader = csv.DictReader(csv_file)
            csv_reader = self.fix_column_names(csv_reader)
            csv_def = list(csv_reader)

        RowTuple = namedtuple('csv_row', csv_def[0].keys())

        def get_tuple_for_row(row_dict):
            row_tuple = RowTuple(**row_dict)
            return row_tuple

        csv_def = list(map(get_tuple_for_row, csv_def))
        return csv_def

    def fix_column_names(self, csv_reader):
        """Checks the names of some required columns and changes them to allow for uniform processing.

        Parameters
        ----------
        csv_reader : csv.DictReader
            The DictReader generated from reading in the csv CCSDS definition.

        Returns
        -------
        : csv.DictReader
            The input DictReader with any non standard column names replaced.
        """
        # TODO: Unify this with the header_name_mappings kwarg used in Parser to allow the user to specify this
        #   on the fly
        # The definition allows the packet name to be labeled as 'Packet' or 'Container'. We will rename
        # this column as 'Container' for consistency with the rest of the container oriented code.
        if 'Packet' in csv_reader.fieldnames:
            # rename packet column to container
            csv_reader.fieldnames[csv_reader.fieldnames.index('Packet')] = 'Container'

        if 'Container' not in csv_reader.fieldnames:
            raise ValueError("According to definition the csv file must contain either Packet or Container column")

        if 'Type' in csv_reader.fieldnames:
            csv_reader.fieldnames[csv_reader.fieldnames.index('Type')] = 'DataType'
            # rename packet column to container
        if 'DataType' not in csv_reader.fieldnames:
            raise ValueError("According to definition the csv file must contain either Type or DataType column")

        if 'APID' not in csv_reader.fieldnames:
            raise NotImplementedError(
                "APID must be one of the columns in the csv file format, other variations are note yet supported")

        return csv_reader

    def gen_flattened_containers(self):
        # FIXME: Recommend changing this method to a @property getter instead.
        """Generates a dict of flattened containers from the csv definition.

        Returns
        -------
        : dict
            A dict of FlattenedContainer namedtuples.
        """

        container_column = [row.Container for row in self._csv_def]
        uniq_container_names = list(dict.fromkeys(container_column))

        flattened_containers = {}
        for container_name in uniq_container_names:
            next_container = [row for row in self._csv_def if row.Container == container_name]
            flatten_container = self.gen_flattened_container(next_container)
            flattened_containers[container_name] = flatten_container

        return flattened_containers

    def gen_flattened_container(self, container) -> FlattenedContainer:
        """Convert the csv definition for a single container type into a FlattenedContainer
        containing the restrictions and entry list for this container type.

        Parameters
        ----------
        container : list of RowTuple
            A list containing all the rows, in order, from the CSV definition
            pertaining to a single container type.

        Returns
        -------
        : FlattenedContainer
            A namedtuple containing an entry list and restrictions.
            FlattenedContainer(
            entry_list=[Parameter, Parameter, ...],
            restrictions={"ParameterName": value, "OtherParamName": value, ...}
            )
        """
        entry_list = self.gen_entry_list(container)
        restrictions = self.gen_restrictions(container)

        return FlattenedContainer(entry_list, restrictions)

    def gen_restrictions(self, container, pkt_apid_header_name='PKT_APID'):
        """ Determines and generates a dict of restrictions for a container type.
        Note: the only restriction currently supported is PKT_APID.

        Parameters
        ----------
        container : dict of RowTuple
            A list containing all the rows, in order, from the CSV definition
            pertaining to a single container type.
        pkt_apid_header_name : str
            The string used in the packet header describing the APID for the CCSDS packet.

        Returns
        -------
        : dict
            A dict containing the restrictions for the container parameter
        """
        last_apid = container[0].APID
        for row in container:
            next_apid = row.APID

            if next_apid != last_apid:
                raise NotImplementedError('The only container restriction currently support is APID and there must be '
                                          'a one to one correlation between Container names and APIDs')
            last_apid = next_apid

        restrictions = [
            Comparison(required_value=last_apid, referenced_parameter=pkt_apid_header_name, use_calibrated_value=False)
        ]

        return restrictions

    def gen_entry_list(self, container: list):
        """Generates a list of Parameters for the given container. Each Parameter corresponds to one
        telemetry item for the container.

        Parameters
        ----------
        container : list of RowTuple
            A list containing all the rows, in order, from the CSV definition
            pertaining to a single container type.

        Returns
        -------
        : list of Parameters
            A list of Parameter objects with each Parameter corresponding to one telemetry
            item from the container input
        """
        pkt_entry_list = []
        for row in container:
            param_type_name = row.ItemName + '_Type'
            param_type = self.get_param_type_from_str(row.DataType, param_type_name)
            param = Parameter(row.ItemName, param_type)
            pkt_entry_list.append(param)

        if self.check_sum_param is not None:
            pkt_entry_list.append(self.check_sum_param)

        return pkt_entry_list

    @staticmethod
    def get_param_type_from_str(dtype, param_type_name, unit=None):
        """Determines the ParameterType to use for a given CSV data type format string.

        Parameters
        ----------
        dtype : str
            A string defining the data encoding of a telemetry item.
            Examples:
            'U8' - unsigned 8-bit integer
            'F16' - 16-bit float
            'C64' - 64 byte character array
        param_type_name : str
            Name to be given to the created ParameterType
        unit : str or None
            Name of the units for the created ParameterType

        Returns
        -------
        : ParameterType
            A ParameterType corresponding to the input variables
        """

        # All data types must be a string starting with all letters and ending with integers ie 'U12' or 'Float8'
        split_i = re.search('[0-9]', dtype).start()
        if split_i is None:
            raise NotImplementedError("According to definition derived types may not specify a bit size. "
                                      "This is not currently supported")

        dtype_size = int(dtype[split_i:])
        dtype_str = dtype[:split_i]

        if dtype_str[0] == 'U':
            encoding = IntegerDataEncoding(dtype_size, 'unsigned')
            paramType = IntegerParameterType(name=param_type_name, encoding=encoding, unit=unit)
        elif dtype_str[0] == 'I':
            encoding = IntegerDataEncoding(dtype_size, 'signed')
            paramType = IntegerParameterType(name=param_type_name, encoding=encoding, unit=unit)
        elif dtype_str[0] == 'D':
            encoding = IntegerDataEncoding(dtype_size, 'unsigned')  # TODO: Should this be converted to discrete values?
            paramType = IntegerParameterType(name=param_type_name, encoding=encoding, unit=unit)
        elif dtype_str[0] == 'F':
            encoding = FloatDataEncoding(dtype_size)
            paramType = FloatParameterType(name=param_type_name, encoding=encoding, unit=unit)
        elif dtype_str[0] == 'C':
            encoding = StringDataEncoding(fixed_length=dtype_size)
            paramType = StringParameterType(name=param_type_name, encoding=encoding, unit=unit)
        else:
            raise NotImplementedError("This dtype not yet supported")

        return paramType

    @property
    def flattened_containers(self):
        """Accesses a flattened, generic representation of non-abstract packet definitions along with their
        aggregated inheritance
        restrictions.

        Returns
        -------
        : dict
            A modified form of the _sequence_container_cache, flattened out to eliminate nested sequence containers
            and with all restriction logic aggregated together for easy comparisons.
        """

        return self._flattened_containers
