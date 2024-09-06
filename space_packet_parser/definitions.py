"""Module for parsing XTCE xml files to specify packet format"""
# Standard
from collections import namedtuple
import csv
import re
import logging
from pathlib import Path
from typing import Tuple, Optional, List, TextIO, Dict
import warnings
# Installed
import lxml.etree as ElementTree

from space_packet_parser.exceptions import ElementNotFoundError, InvalidParameterTypeError
from space_packet_parser import comparisons, encodings, parameters, parseables

logger = logging.getLogger(__name__)


class XtcePacketDefinition:
    """Object representation of the XTCE definition of a CCSDS packet object"""

    _tag_to_type_template = {
        '{{{xtce}}}StringParameterType': parameters.StringParameterType,
        '{{{xtce}}}IntegerParameterType': parameters.IntegerParameterType,
        '{{{xtce}}}FloatParameterType': parameters.FloatParameterType,
        '{{{xtce}}}EnumeratedParameterType': parameters.EnumeratedParameterType,
        '{{{xtce}}}BinaryParameterType': parameters.BinaryParameterType,
        '{{{xtce}}}BooleanParameterType': parameters.BooleanParameterType,
        '{{{xtce}}}AbsoluteTimeParameterType': parameters.AbsoluteTimeParameterType,
        '{{{xtce}}}RelativeTimeParameterType': parameters.RelativeTimeParameterType,
    }

    def __init__(self, xtce_document: TextIO, ns: Optional[dict] = None):
        """Instantiate an object representation of a CCSDS packet definition, according to a format specified in an XTCE
        XML document. The parser iteratively builds sequences of parameters according to the
        SequenceContainers specified in the XML document's ContainerSet element. The notions of container inheritance
        (via BaseContainer) and nested container (by including a SequenceContainer within a SequenceContainer) are
        supported. Exclusion of containers based on topLevelPacket in AncillaryData is not supported, so all
        containers are examined and returned.

        Parameters
        ----------
        xtce_document : TextIO
            Path to XTCE XML document containing packet definition.
        ns : Optional[dict]
            Optional different namespace than the default xtce namespace.
        """
        self._sequence_container_cache = {}  # Lookup for parsed sequence container objects
        self._parameter_cache = {}  # Lookup for parsed parameter objects
        self._parameter_type_cache = {}  # Lookup for parsed parameter type objects
        self.tree = ElementTree.parse(xtce_document)
        self.ns = ns or self.tree.getroot().nsmap
        self.type_tag_to_object = {k.format(**self.ns): v for k, v in
                                   self._tag_to_type_template.items()}

        self._populate_sequence_container_cache()

    def __getitem__(self, item):
        return self._sequence_container_cache[item]

    def _populate_sequence_container_cache(self):
        """Force populating sequence_container_cache by parsing all SequenceContainers"""
        for sequence_container in self.container_set.iterfind('xtce:SequenceContainer', self.ns):
            self._sequence_container_cache[
                sequence_container.attrib['name']
            ] = self.parse_sequence_container_contents(sequence_container)

        # Back-populate the list of inheritors for each container
        for name, sc in self._sequence_container_cache.items():
            if sc.base_container_name:
                self._sequence_container_cache[sc.base_container_name].inheritors.append(name)

    def parse_sequence_container_contents(self,
                                          sequence_container: ElementTree.Element) -> parseables.SequenceContainer:
        """Parses the list of parameters in a SequenceContainer element, recursively parsing nested SequenceContainers
        to build an entry list of parameters that flattens the nested structure to derive a sequential ordering of
        expected parameters for each SequenceContainer. Note that this also stores entry lists for containers that are
        not intended to stand alone.

        Parameters
        ----------
        sequence_container : ElementTree.Element
            The SequenceContainer element to parse.

        Returns
        -------
        : SequenceContainer
            SequenceContainer containing an entry_list of SequenceContainers and Parameters
            in the order expected in a packet.
        """
        entry_list = []  # List to house Parameters for the current SequenceContainer
        try:
            base_container, restriction_criteria = self._get_container_base_container(sequence_container)
            base_sequence_container = self.parse_sequence_container_contents(base_container)
            base_container_name = base_sequence_container.name
        except ElementNotFoundError:
            base_container_name = None
            restriction_criteria = None

        container_contents = sequence_container.find('xtce:EntryList', self.ns).findall('*', self.ns)

        for entry in container_contents:
            if entry.tag == '{{{xtce}}}ParameterRefEntry'.format(**self.ns):  # pylint: disable=consider-using-f-string
                parameter_name = entry.attrib['parameterRef']

                # If we've already parsed this parameter in a different container
                if parameter_name in self._parameter_cache:
                    entry_list.append(self._parameter_cache[parameter_name])
                else:
                    parameter_element = self._find_parameter(parameter_name)
                    parameter_type_name = parameter_element.attrib['parameterTypeRef']

                    # If we've already parsed this parameter type for a different parameter
                    if parameter_type_name in self._parameter_type_cache:
                        parameter_type_object = self._parameter_type_cache[parameter_type_name]
                    else:
                        parameter_type_element = self._find_parameter_type(parameter_type_name)
                        try:
                            parameter_type_class = self.type_tag_to_object[parameter_type_element.tag]
                        except KeyError as e:
                            if (
                                    "ArrayParameterType" in parameter_type_element.tag or
                                    "AggregateParameterType" in parameter_type_element.tag
                            ):
                                raise NotImplementedError(f"Unsupported parameter type {parameter_type_element.tag}. "
                                                          "Supporting this parameter type is in the roadmap but has "
                                                          "not yet been implemented.") from e
                            raise InvalidParameterTypeError(f"Invalid parameter type {parameter_type_element.tag}. "
                                                            "If you believe this is a valid XTCE parameter type, "
                                                            "please open a feature request as a Github issue with a "
                                                            "reference to the XTCE element description for the "
                                                            "parameter type element.") from e
                        parameter_type_object = parameter_type_class.from_parameter_type_xml_element(
                            parameter_type_element, self.ns)
                        self._parameter_type_cache[parameter_type_name] = parameter_type_object  # Add to cache

                    parameter_short_description = parameter_element.attrib['shortDescription'] if (
                        'shortDescription' in parameter_element.attrib
                    ) else None
                    parameter_long_description = parameter_element.find('xtce:LongDescription', self.ns).text if (
                        parameter_element.find('xtce:LongDescription', self.ns) is not None
                    ) else None

                    parameter_object = parameters.Parameter(
                        name=parameter_name,
                        parameter_type=parameter_type_object,
                        short_description=parameter_short_description,
                        long_description=parameter_long_description
                    )
                    entry_list.append(parameter_object)
                    self._parameter_cache[parameter_name] = parameter_object  # Add to cache
            elif entry.tag == '{{{xtce}}}ContainerRefEntry'.format(  # pylint: disable=consider-using-f-string
                    **self.ns):
                nested_container = self._find_container(name=entry.attrib['containerRef'])
                entry_list.append(self.parse_sequence_container_contents(nested_container))

        short_description = sequence_container.attrib['shortDescription'] if (
            'shortDescription' in sequence_container.attrib
        ) else None
        long_description = sequence_container.find('xtce:LongDescription', self.ns).text if (
            sequence_container.find('xtce:LongDescription', self.ns) is not None
        ) else None

        return parseables.SequenceContainer(name=sequence_container.attrib['name'],
                                            entry_list=entry_list,
                                            base_container_name=base_container_name,
                                            restriction_criteria=restriction_criteria,
                                            abstract=self._is_abstract_container(sequence_container),
                                            short_description=short_description,
                                            long_description=long_description)

    @property
    def named_containers(self) -> Dict[str, parseables.SequenceContainer]:
        """Property accessor that returns the dict cache of SequenceContainer objects"""
        return self._sequence_container_cache

    @property
    def named_parameters(self) -> Dict[str, parameters.Parameter]:
        """Property accessor that returns the dict cache of Parameter objects"""
        return self._parameter_cache

    @property
    def named_parameter_types(self) -> Dict[str, parameters.ParameterType]:
        """Property accessor that returns the dict cache of ParameterType objects"""
        return self._parameter_type_cache

    # DEPRECATED! This is only used by CSV-parser code. Remove for 5.0.0 release
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
            {
            "PacketNameA": {
            FlattenedContainer(
            entry_list=[Parameter, Parameter, ...],
            restrictions={"ParameterName": value, "OtherParamName": value, ...}
            )
            },
            "PacketNameB": {
            FlattenedContainer(
            entry_list=[Parameter, Parameter, ...],
            restrictions={"ParameterName": value, "OtherParamName": value, ...}
            )
            }, ...
            }
        """

        def flatten_container(sequence_container: parseables.SequenceContainer):
            """Flattens the representation of a SequenceContainer object into a list of Parameters (in order) and
            an aggregated dictionary of restriction criteria where the keys are Parameter names and the values are the
            required values of those parameters in order to adopt the SequenceContainer's definition.

            Parameters
            ----------
            sequence_container : SequenceContainer
                SequenceContainer object to flatten, recursively.

            Returns
            -------
            : list
                List of Parameters, in order.
            : dict
                Dictionary of required Parameter values in order to use this definition.
            """
            aggregated_entry_list = []
            aggregated_restrictions = []
            for entry in sequence_container.entry_list:
                if isinstance(entry, parseables.SequenceContainer):
                    if entry.restriction_criteria:
                        aggregated_restrictions += entry.restriction_criteria
                    entry_list, restrictions = flatten_container(entry)
                    aggregated_entry_list += entry_list
                    aggregated_restrictions += restrictions
                elif isinstance(entry, parameters.Parameter):
                    aggregated_entry_list.append(entry)
            return aggregated_entry_list, aggregated_restrictions

        warnings.warn("The 'flattened_containers' property is deprecated to allow for dynamic container "
                      "inheritance matching during parsing.", DeprecationWarning)
        return {
            name: parseables.FlattenedContainer(*flatten_container(sc))
            for name, sc in self._sequence_container_cache.items()
            if not sc.abstract
        }

    @property
    def container_set(self) -> ElementTree.Element:
        """Property that returns the <xtce:ContainerSet> element, containing all the sequence container elements."""
        return self.tree.getroot().find('xtce:TelemetryMetaData/xtce:ContainerSet', self.ns)

    @property
    def parameter_type_set(self) -> ElementTree.Element:
        """Property that returns the <xtce:ParameterTypeSet> element, containing all parameter type elements."""
        return self.tree.getroot().find('xtce:TelemetryMetaData/xtce:ParameterTypeSet', self.ns)

    @property
    def parameter_set(self) -> ElementTree.Element:
        """Property that returns the <xtce:ParameterSet> element, containing all parameter elements."""
        return self.tree.getroot().find('xtce:TelemetryMetaData/xtce:ParameterSet', self.ns)

    @staticmethod
    def _is_abstract_container(container_element: ElementTree.Element) -> bool:
        """Determine in a SequenceContainer element is abstract

        Parameters
        ----------
        container_element : ElementTree.Element
            SequenceContainer element to examine

        Returns
        -------
        : bool
            True if SequenceContainer element has the attribute abstract=true. False otherwise.
        """
        if 'abstract' in container_element.attrib:
            return container_element.attrib['abstract'].lower() == 'true'
        return False

    def _find_container(self, name: str) -> ElementTree.Element:
        """Finds an XTCE container <xtce:SequenceContainer> by name.

        Parameters
        ----------
        name : str
            Name of the container to find

        Returns
        -------
        : ElementTree.Element
        """
        containers = self.container_set.findall(f"./xtce:SequenceContainer[@name='{name}']", self.ns)
        assert len(containers) == 1, f"Found {len(containers)} matching container_set with name {name}. " \
                                     f"Container names are expected to exist and be unique."
        return containers[0]

    def _find_parameter(self, name: str) -> ElementTree.Element:
        """Finds an XTCE Parameter in the tree.

        Parameters
        ----------
        name : str
            Name of the parameter to find

        Returns
        -------
        : ElementTree.Element
        """
        params = self.parameter_set.findall(f"./xtce:Parameter[@name='{name}']", self.ns)
        assert len(params) == 1, f"Found {len(params)} matching parameters with name {name}. " \
                                 f"Parameter names are expected to exist and be unique."
        return params[0]

    def _find_parameter_type(self, name: str) -> ElementTree.Element:
        """Finds an XTCE ParameterType in the tree.

        Parameters
        ----------
        name : str
            Name of the parameter type to find

        Returns
        -------
        : ElementTree.Element
        """
        param_types = self.parameter_type_set.findall(f"./*[@name='{name}']", self.ns)
        assert len(param_types) == 1, f"Found {len(param_types)} matching parameter types with name {name}. " \
                                      f"Parameter type names are expected to exist and be unique."
        return param_types[0]

    def _get_container_base_container(
            self,
            container_element: ElementTree.Element) -> Tuple[ElementTree.Element, List[comparisons.MatchCriteria]]:
        """Examines the container_element and returns information about its inheritance.

        Parameters
        ----------
        container_element : ElementTree.Element
            The container element for which to find its base container.

        Returns
        -------
        : ElementTree.Element
            The base container element of the input container_element.
        : list
            The restriction criteria for the inheritance.
        """
        base_container_element = container_element.find('xtce:BaseContainer', self.ns)
        if base_container_element is None:
            raise ElementNotFoundError(
                f"Container element {container_element} does not have a BaseContainer child element.")

        restriction_criteria_element = base_container_element.find('xtce:RestrictionCriteria', self.ns)
        if restriction_criteria_element is not None:
            comparison_list_element = restriction_criteria_element.find('xtce:ComparisonList', self.ns)
            single_comparison_element = restriction_criteria_element.find('xtce:Comparison', self.ns)
            boolean_expression_element = restriction_criteria_element.find('xtce:BooleanExpression', self.ns)
            custom_algorithm_element = restriction_criteria_element.find('xtce:CustomAlgorithm', self.ns)
            if custom_algorithm_element is not None:
                raise NotImplementedError("Detected a CustomAlgorithm in a RestrictionCriteria element. "
                                          "This is not implemented.")

            if comparison_list_element is not None:
                comparison_items = comparison_list_element.findall('xtce:Comparison', self.ns)
                restrictions = [
                    comparisons.Comparison.from_match_criteria_xml_element(comp, self.ns) for comp in comparison_items]
            elif single_comparison_element is not None:
                restrictions = [
                    comparisons.Comparison.from_match_criteria_xml_element(single_comparison_element, self.ns)]
            elif boolean_expression_element is not None:
                restrictions = [
                    comparisons.BooleanExpression.from_match_criteria_xml_element(boolean_expression_element, self.ns)]
            else:
                raise ValueError("Detected a RestrictionCriteria element containing no "
                                 "Comparison, ComparisonList, BooleanExpression or CustomAlgorithm.")
            # TODO: Implement NextContainer support inside RestrictionCriteria. This might make the parser much
            #    more complicated.
        else:
            restrictions = []
        return self._find_container(base_container_element.attrib['containerRef']), restrictions


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
            self.check_sum_param = parameters.Parameter('CHECKSUM', check_sum_type)
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
            comparisons.Comparison(required_value=last_apid,
                                   referenced_parameter=pkt_apid_header_name,
                                   use_calibrated_value=False)
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
            param = parameters.Parameter(row.ItemName, param_type)
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
            encoding = encodings.IntegerDataEncoding(dtype_size, 'unsigned')
            paramType = parameters.IntegerParameterType(name=param_type_name, encoding=encoding, unit=unit)
        elif dtype_str[0] == 'I':
            encoding = encodings.IntegerDataEncoding(dtype_size, 'signed')
            paramType = parameters.IntegerParameterType(name=param_type_name,
                                                        encoding=encoding,
                                                        unit=unit)
        elif dtype_str[0] == 'D':
            # TODO: Should this be converted to discrete values?
            encoding = encodings.IntegerDataEncoding(dtype_size, 'unsigned')
            paramType = parameters.IntegerParameterType(name=param_type_name, encoding=encoding, unit=unit)
        elif dtype_str[0] == 'F':
            encoding = encodings.FloatDataEncoding(dtype_size)
            paramType = parameters.FloatParameterType(name=param_type_name, encoding=encoding, unit=unit)
        elif dtype_str[0] == 'C':
            encoding = encodings.StringDataEncoding(fixed_length=dtype_size)
            paramType = parameters.StringParameterType(name=param_type_name, encoding=encoding, unit=unit)
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
