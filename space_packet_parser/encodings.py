"""DataEncoding definitions"""
# Standard
from abc import ABCMeta, abstractmethod
import logging
import struct
from typing import Any, List, Optional, Tuple, Union
# Installed
import lxml.etree as ElementTree
# Local
from space_packet_parser import calibrators, comparisons, packets

logger = logging.getLogger(__name__)


class DataEncoding(comparisons.AttrComparable, metaclass=ABCMeta):
    """Abstract base class for XTCE data encodings"""

    @classmethod
    @abstractmethod
    def from_data_encoding_xml_element(cls, element: ElementTree.Element, ns: dict) -> 'DataEncoding':
        """Abstract classmethod to create a data encoding object from an XML element.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        : DataEncoding
        """
        return NotImplemented

    @staticmethod
    def get_default_calibrator(data_encoding_element: ElementTree.Element,
                               ns: dict) -> Union[calibrators.Calibrator, None]:
        """Gets the default_calibrator for the data encoding element

        Parameters
        ----------
        data_encoding_element : ElementTree.Element
            The data encoding element which should contain the default_calibrator
        ns : dict
            XML namespace dict

        Returns
        -------
        : Union[Calibrator, None]
        """
        for calibrator in [calibrators.SplineCalibrator,
                           calibrators.PolynomialCalibrator,
                           calibrators.MathOperationCalibrator]:
            # Try to find each type of data encoding element. If we find one, we assume it's the only one.
            element = data_encoding_element.find(f"xtce:DefaultCalibrator/xtce:{calibrator.__name__}", ns)
            if element is not None:
                return calibrator.from_calibrator_xml_element(element, ns)
        return None

    @staticmethod
    def get_context_calibrators(
            data_encoding_element: ElementTree.Element, ns: dict) -> Union[List[calibrators.ContextCalibrator], None]:
        """Get the context default_calibrator(s) for the data encoding element

        Parameters
        ----------
        data_encoding_element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        : Union[List[ContextCalibrator], None]
            List of ContextCalibrator objects or None if there are no context calibrators
        """
        if data_encoding_element.find('xtce:ContextCalibratorList', ns):
            context_calibrators_elements = data_encoding_element.findall(
                'xtce:ContextCalibratorList/xtce:ContextCalibrator', ns)
            return [calibrators.ContextCalibrator.from_context_calibrator_xml_element(el, ns)
                    for el in context_calibrators_elements]
        return None

    @staticmethod
    def _get_linear_adjuster(parent_element: ElementTree.Element, ns: dict) -> Union[callable, None]:
        """Examine a parent (e.g. a <xtce:DynamicValue>) element and find a LinearAdjustment if present,
        creating and returning a function that evaluates the adjustment.

        Parameters
        ----------
        parent_element : ElementTree.Element
            Parent element which may contain a LinearAdjustment
        ns : dict
            XML namespace dict

        Returns
        -------
        adjuster : Union[callable, None]
            Function object that adjusts a SizeInBits value by a linear function or None if no adjuster present
        """
        linear_adjustment_element = parent_element.find('xtce:LinearAdjustment', ns)
        if linear_adjustment_element is not None:
            slope = (int(linear_adjustment_element.attrib['slope'])
                     if 'slope' in linear_adjustment_element.attrib else 0)
            intercept = (int(linear_adjustment_element.attrib['intercept'])
                         if 'intercept' in linear_adjustment_element.attrib else 0)

            def adjuster(x: int) -> int:
                """Perform a linear adjustment to a size parameter

                Parameters
                ----------
                x : int
                    Unadjusted size parameter.

                Returns
                -------
                : int
                    Adjusted size parameter
                """
                adjusted = (slope * float(x)) + intercept
                if not adjusted.is_integer():
                    raise ValueError(f"Error when adjusting a value with a LinearAdjustment. Got y=mx + b as "
                                     f"{adjusted}={slope}*{x}+{intercept} returned a float. "
                                     f"Should have been an int.")
                return int(adjusted)

            return adjuster
        return None

    def _calculate_size(self, packet: packets.CCSDSPacket) -> int:
        """Calculate the size of the data item in bits.

        Parameters
        ----------
        packet: CCSDSPacket
            Binary representation of the packet used to get the coming bits and any
            previously parsed data items to infer field lengths.

        Returns
        -------
        : int
            Size of the data item in bits.
        """
        raise NotImplementedError()

    def parse_value(self, packet: packets.CCSDSPacket, **kwargs) -> Tuple[Any, Any]:
        """Parse a value from packet data, possibly using previously parsed data items to inform parsing.

        Parameters
        ----------
        packet: CCSDSPacket
            Binary representation of the packet used to get the coming bits and any
            previously parsed data items to infer field lengths.
        Returns
        -------
        : any
            Raw value
        : any
            Calibrated value
        """
        raise NotImplementedError()


class StringDataEncoding(DataEncoding):
    """<xtce:StringDataEncoding>"""

    _supported_encodings = ('US-ASCII', 'ISO-8859-1', 'Windows-1252', 'UTF-8', 'UTF-16',
                            'UTF-16LE', 'UTF-16BE', 'UTF-32', 'UTF-32LE', 'UTF-32BE')

    def __init__(  # pylint: disable=too-many-branches
            self,
            *,
            encoding: str = 'UTF-8',
            byte_order: Optional[str] = None,
            fixed_raw_length: Optional[int] = None,
            dynamic_length_reference: Optional[str] = None,
            discrete_lookup_length: Optional[List[comparisons.DiscreteLookup]] = None,
            use_calibrated_value: Optional[bool] = True,
            length_linear_adjuster: Optional[callable] = None,
            termination_character: Optional[str] = None,
            leading_length_size: Optional[int] = None
    ):
        # pylint: disable=pointless-statement
        f"""Constructor
        Only one of termination_character, fixed_length, or leading_length_size should be set. Setting more than one
        is nonsensical.

        Parameters
        ----------
        encoding : str
            One of the XTCE-supported encodings: {self._supported_encodings}
            Describes how to read the characters in the string.
            Default is UTF-8.
        byte_order : Optional[str]
            Description of the byte order, used for multi-byte character encodings where the endianness cannot be
            determined from the encoding specifier. Can be None if encoding is single-byte or UTF-*BE/UTF-*LE.
        termination_character : Optional[str]
            A single hexadecimal character, represented as a string. Must be encoded in the same encoding as the string
            itself. For example, for a utf-8 encoded string, the hex string must be two hex characters (one byte).
            For a UTF-16* encoded string, the hex representation of the termination character must be four characters
            (two bytes).
        fixed_raw_length : Optional[int]
            Fixed length of the raw string, in bits. Comes from a SizeInBits/Fixed/FixedValue element.
        leading_length_size : Optional[int]
            Fixed size in bits of a leading field that contains the length of the subsequent derived string.
        dynamic_length_reference : Optional[str]
            Name of referenced parameter for dynamic raw length, in bits. May be combined with a linear_adjuster.
        use_calibrated_value: Optional[bool]
            Whether to use the calibrated value on the referenced parameter in dynamic_length_reference.
            Default is True.
        discrete_lookup_length : Optional[List[DiscreteLookup]]
            List of DiscreteLookup objects with which to determine raw string length from another parameter.
        length_linear_adjuster : Optional[callable]
            Function that linearly adjusts a size. e.g. if the size reference parameter gives a length in bytes, the
            linear adjuster should multiply by 8 to give the size in bits.
        """
        if encoding not in self._supported_encodings:
            raise ValueError(f"Got encoding={encoding} (uppercased). "
                             f"Encoding must be one of {self._supported_encodings}.")
        self.encoding = encoding
        if encoding not in ['US-ASCII', 'ISO-8859-1', 'Windows-1252', 'UTF-8']:  # for these, byte order doesn't matter
            if byte_order is None:
                if "LE" in encoding:
                    self.byte_order = "leastSignificantByteFirst"
                elif "BE" in encoding:
                    self.byte_order = "mostSignificantByteFirst"
                else:
                    raise ValueError("Byte order must be specified for multi-byte character encodings.")
        else:
            self.byte_order = byte_order
            if self.byte_order and self.byte_order not in ("leastSignificantByteFirst", "mostSignificantByteFirst"):
                raise ValueError("If specified, byte order must be one of `leastSignificantByteFirst`, "
                                 "`mostSignificantByteFirst`.")

        if termination_character and leading_length_size:
            raise ValueError("Got both a termination character and a leading size for a string encoding.")

        # Check to see if we are specifying raw length in more than one way
        buffer_length_specs = sum(
            bool(x) for x in (dynamic_length_reference, discrete_lookup_length, fixed_raw_length)
        )
        if buffer_length_specs != 1:
            raise ValueError("Expected exactly one of dynamic length reference, discrete length lookup, "
                             "or fixed length for specifying the raw length of a string.")

        if length_linear_adjuster and not dynamic_length_reference:
            raise ValueError("Got a length linear adjuster for a string whose length is not specified by a dynamic "
                             "length reference.")

        self.termination_character = termination_character
        if termination_character:
            # Always in hex, per 4.3.2.2.5.5.4 of XTCE spec
            self.termination_character = bytes.fromhex(termination_character)
            # Check that the termination character is a single character in the specified encoding
            # e.g. b'\x58' in utf-8 is "X"
            # b'\x21\00' in utf-16-le is "!"
            # b'\x00\x21' in utf-16-be is "!"
            if len(self.termination_character.decode(encoding)) != 1:
                raise ValueError(f"Termination character {termination_character} appears to be malformed. "
                                 f"Expected a hex string representation of a single character, e.g. '58' for "
                                 f"character 'X' in utf-8 or '5800' for character 'X' in utf-16-le. Note that "
                                 f"variable-width encoding is not yet supported in any encoding.")

        self.fixed_length = fixed_raw_length
        self.leading_length_size = leading_length_size
        self.dynamic_length_reference = dynamic_length_reference
        self.use_calibrated_value = use_calibrated_value
        self.discrete_lookup_length = discrete_lookup_length
        self.length_linear_adjuster = length_linear_adjuster

    def _calculate_size(self, packet: packets.CCSDSPacket) -> int:
        """Calculate the size of the raw string buffer field

        Parameters
        ----------
        packet : packets.CCSDSPacket
            Partially parsed packet for referencing previous data fields.

        Returns
        -------
        : int
            Size, in bits, of the raw string buffer.
        """
        if self.fixed_length:
            buflen_bits = self.fixed_length
        elif self.discrete_lookup_length:
            for discrete_lookup in self.discrete_lookup_length:
                buflen_bits = discrete_lookup.evaluate(packet)
                if buflen_bits:
                    break
            else:
                raise ValueError('List of discrete lookup values being used for determining length of '
                                 f'string {self} found no matches based on {packet}.')
        elif self.dynamic_length_reference:
            if self.use_calibrated_value is True:
                buflen_bits = packet[self.dynamic_length_reference].derived_value
            else:
                buflen_bits = packet[self.dynamic_length_reference].raw_value

            if self.length_linear_adjuster:
                buflen_bits = self.length_linear_adjuster(buflen_bits)
        else:
            raise ValueError("No raw length specifier found when decoding a string.")
        return int(buflen_bits)

    def _get_raw_buffer(self, packet: packets.CCSDSPacket) -> bytes:
        """Get the raw string buffer as bytes. This will include any leading size or termination characters.

        Notes
        -----
        If the buffer size is not an integer number of bytes, the bytestring is padded at the end with zeros.

        Parameters
        ----------
        packet : packets.CCSDSPacket
            Packet parsed so far, for referencing previous values

        Returns
        -------
        : bytes
            The raw string buffer, padded on the RHS to a byte boundary if the raw length specified is not an integer
            number of bytes.
        """
        buflen_bits = self._calculate_size(packet)
        pad_bits = (8 - (buflen_bits % 8)) % 8
        buflen_bytes = (buflen_bits + pad_bits) // 8
        if (buflen_bits + pad_bits) % 8 != 0:
            raise ValueError(f"Error in buffer length math in _get_raw_buffer. "
                             f"buflen_bits={buflen_bits}, pad_bits={pad_bits}, buflen_bytes={buflen_bytes}")
        # read_as_bytes pads on the left because it internally treats bytes as integers,
        # but for strings, we want any padding on the right, so shift the bytestring left by pad_bits
        raw_string_buffer = (
                packet.raw_data.read_as_int(buflen_bits) << pad_bits
        ).to_bytes(buflen_bytes, "big")
        return raw_string_buffer

    def parse_value(self, packet: packets.CCSDSPacket, **kwargs) -> Tuple[bytes, str]:
        """Parse a string value from packet data, possibly using previously parsed data items to inform parsing.

        Parameters
        ----------
        packet: CCSDSPacket
            Binary representation of the packet used to get the coming bits and any
            previously parsed data items to infer field lengths.

        Returns
        -------
        : bytes
            Raw string bytes buffer. This includes any leading size or termination character and may be a non-integer
            number of bytes, padded on the RHS.
        : str
            Parsed string value, as a python string object.
        """
        raw_string_buffer = packets.RawPacketData(self._get_raw_buffer(packet))
        if self.leading_length_size:
            strlen_bits = raw_string_buffer.read_as_int(self.leading_length_size)
            if strlen_bits % 8 != 0:
                raise ValueError(f"String length (in bits) is {strlen_bits}, which is not a multiple of 8. "
                                 "This is an error since strings must be an integer numbers of bytes.")
            parsed_string = raw_string_buffer.read_as_bytes(strlen_bits).decode(self.encoding)
        elif self.termination_character is not None:
            try:
                tchar_byte_index = raw_string_buffer.index(self.termination_character)
            except ValueError as exc:
                raise ValueError(f"Reached the end of the raw string buffer {raw_string_buffer} without finding the "
                                 f"termination character {self.termination_character}") from exc
            parsed_string = raw_string_buffer.read_as_bytes(tchar_byte_index * 8).decode(self.encoding)
        else:
            # Indicates there is no further parsing. The raw string value is the whole string value.
            parsed_string = raw_string_buffer.decode(self.encoding)

        return bytes(raw_string_buffer), parsed_string

    @classmethod
    def from_data_encoding_xml_element(cls, element: ElementTree.Element, ns: dict) -> 'StringDataEncoding':
        """Create a data encoding object from an <xtce:StringDataEncoding> XML element.

        Notes
        -----
        Raw strings in XTCE can be described in two ways:

        1. Using a SizeInBits/Fixed/FixedSize element that specifies the length of the raw string, including any
           termination character or leading size integer. This is sometimes referred to as the "container" or
           "memory allocation" for the string.
        2. Using a Variable element that contains either a DynamicValue or a DiscreteLookup to other parameters
           that specify the length of the raw string, including any termination character or leading size integer.

        Derived strings in XTCE can be specified in two ways:

        1. Via a TerminationCharacter element that contains the hex value of the termination character in the
           specified encoding (e.g. UTF-16BE).
        2. Via a LeadingSize element that specifies the number of bits allocated at the beginning of the raw string
           for an integer that specifies the subsequent length, in bits, of the derived string.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        cls
        """
        init_kwargs = {}  # Build up kwargs for class initialization
        encoding: str = element.get("encoding", "UTF-8")
        init_kwargs["encoding"] = encoding

        if encoding not in ('US-ASCII', 'ISO-8859-1', 'Windows-1252', 'UTF-8'):  # single-byte chars
            if not (encoding.endswith("BE") or encoding.endswith("LE")):
                byte_order = element.get("byteOrder")
                init_kwargs["byte_order"] = byte_order
                if byte_order is None:
                    raise ValueError("For multi-byte character encodings, byte order must be specified "
                                     "either using the byteOrder attribute or via the encoding itself.")

        # Raw string specifiers
        if element.find("xtce:SizeInBits", ns) is not None:
            # This is a fixed length raw string
            size_element = element.find("xtce:SizeInBits", ns)
            fixed_raw_length = int(size_element.find("xtce:Fixed/xtce:FixedValue", ns).text)
            init_kwargs["fixed_raw_length"] = fixed_raw_length
        elif element.find("xtce:Variable", ns) is not None:
            # This is a variable length raw string
            size_element = element.find("xtce:Variable", ns)
            if size_element.find("xtce:DynamicValue", ns) is not None:
                # Raw string length is specified by reference to another parameter
                dynamic_value_element = size_element.find('xtce:DynamicValue', ns)
                referenced_parameter = dynamic_value_element.find('xtce:ParameterInstanceRef', ns).attrib[
                    'parameterRef']
                init_kwargs["dynamic_length_reference"] = referenced_parameter

                if 'useCalibratedValue' in dynamic_value_element.find('xtce:ParameterInstanceRef', ns).attrib:
                    use_calibrated_value = dynamic_value_element.find(
                        'xtce:ParameterInstanceRef', ns).attrib['useCalibratedValue'].lower() == "true"
                    init_kwargs["use_calibrated_value"] = use_calibrated_value

                linear_adjuster = cls._get_linear_adjuster(dynamic_value_element, ns)
                init_kwargs["length_linear_adjuster"] = linear_adjuster
            elif size_element.find("xtce:DiscreteLookupList", ns) is not None:
                # Raw string length is specified by lookup table based on another parameter
                discrete_lookup_list_element = element.find('xtce:Variable/xtce:DiscreteLookupList', ns)
                discrete_lookup_list = [comparisons.DiscreteLookup.from_discrete_lookup_xml_element(el, ns)
                                        for el in discrete_lookup_list_element.findall('xtce:DiscreteLookup', ns)]
                init_kwargs["discrete_lookup_length"] = discrete_lookup_list
            else:
                raise ValueError("Variable element must contain either DynamicValue or DiscreteLookupList.")
        else:
            raise ValueError("StringDataEncoding must contain either a SizeInBits or Variable element.")

        # Derived string specifiers
        if size_element.find("xtce:TerminationChar", ns) is not None:
            termination_character = size_element.find('xtce:TerminationChar', ns).text
            init_kwargs["termination_character"] = termination_character

        if size_element.find("xtce:LeadingSize", ns) is not None:
            leading_length_size = int(size_element.find('xtce:LeadingSize', ns).attrib['sizeInBitsOfSizeTag'])
            init_kwargs["leading_length_size"] = leading_length_size

        return cls(**init_kwargs)


class NumericDataEncoding(DataEncoding, metaclass=ABCMeta):
    """Abstract class that is inherited by IntegerDataEncoding and FloatDataEncoding"""

    def __init__(self,
                 size_in_bits: int,
                 encoding: str,
                 *,
                 byte_order: str = "mostSignificantByteFirst",
                 default_calibrator: Optional[calibrators.Calibrator] = None,
                 context_calibrators: Optional[List[calibrators.ContextCalibrator]] = None):
        """Constructor

        Parameters
        ----------
        size_in_bits : int
            Size of the integer
        encoding : str
            String indicating the type of encoding for the integer. FSW seems to use primarily 'signed' and 'unsigned',
            though 'signed' is not actually a valid specifier according to XTCE. 'twosCompliment' [sic] should be used
            instead, though we support the unofficial 'signed' specifier here.
            For supported specifiers, see XTCE spec 4.3.2.2.5.6.2
        byte_order : str
            Description of the byte order. Default is 'mostSignficantByteFirst' (big-endian).
        default_calibrator : Optional[Calibrator]
            Optional Calibrator object, containing information on how to transform the integer-encoded data, e.g. via
            a polynomial conversion or spline interpolation.
        context_calibrators : Optional[List[ContextCalibrator]]
            List of ContextCalibrator objects, containing match criteria and corresponding calibrators to use in
            various scenarios, based on other parameters.
        """
        self.size_in_bits = size_in_bits
        self.encoding = encoding
        self.byte_order = byte_order
        self.default_calibrator = default_calibrator
        self.context_calibrators = context_calibrators

    def _calculate_size(self, packet: packets.CCSDSPacket) -> int:
        return self.size_in_bits

    @abstractmethod
    def _get_raw_value(self, packet: packets.CCSDSPacket) -> Union[int, float]:
        """Read the raw value from the packet data

        Parameters
        ----------
        packet: CCSDSPacket
            Binary representation of the packet used to get the coming bits and any
            previously parsed data items to infer field lengths.

        Returns
        -------
        : int
            Raw value
        """
        raise NotImplementedError()

    @staticmethod
    def _twos_complement(val: int, bit_width: int) -> int:
        """Take the twos complement of val
        Used when parsing ints and some floats
        """
        if (val & (1 << (bit_width - 1))) != 0:  # if sign bit is set e.g., 8bit: 128-255
            return val - (1 << bit_width)  # compute negative value
        return val

    def parse_value(self,
                    packet: packets.CCSDSPacket,
                    **kwargs) -> Tuple[Union[int, float], Union[int, float]]:
        """Parse a value from packet data, possibly using previously parsed data items to inform parsing.

        Parameters
        ----------
        packet: CCSDSPacket
            Binary representation of the packet used to get the coming bits and any
            previously parsed data items to infer field lengths.
        Returns
        -------
        : any
            Parsed value
        : any
            Calibrated value
        """
        parsed_value = self._get_raw_value(packet)
        # Attempt to calibrate
        calibrated_value = parsed_value  # Provides a fall through in case we have no calibrators
        if self.context_calibrators:
            for calibrator in self.context_calibrators:
                match_criteria = calibrator.match_criteria
                if all(criterion.evaluate(packet, parsed_value) for criterion in match_criteria):
                    # If the parsed data so far satisfy all the match criteria
                    calibrated_value = calibrator.calibrate(parsed_value)
                    return parsed_value, calibrated_value
        if self.default_calibrator:  # If no context calibrators or if none apply and there is a default
            calibrated_value = self.default_calibrator.calibrate(parsed_value)
        # Ultimate fallthrough
        return parsed_value, calibrated_value


class IntegerDataEncoding(NumericDataEncoding):
    """<xtce:IntegerDataEncoding>"""

    def _get_raw_value(self, packet: packets.CCSDSPacket) -> int:
        # Extract the bits from the data in big-endian order from the packet
        val = packet.raw_data.read_as_int(self.size_in_bits)
        if self.byte_order == 'leastSignificantByteFirst':
            # Convert little-endian (LSB first) int to bigendian. Just reverses the order of the bytes.
            val = int.from_bytes(
                val.to_bytes(
                    length=(self.size_in_bits + 7) // 8,
                    byteorder="little"
                ),
                byteorder="big"
            )
        if self.encoding == 'unsigned':
            return val
        # It is a signed integer, and we need to take into account the first bit
        return self._twos_complement(val, self.size_in_bits)

    @classmethod
    def from_data_encoding_xml_element(cls, element: ElementTree.Element, ns: dict) -> 'IntegerDataEncoding':
        """Create a data encoding object from an <xtce:IntegerDataEncoding> XML element.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        : cls
        """
        size_in_bits = int(element.attrib['sizeInBits'])
        encoding = element.attrib['encoding'] if 'encoding' in element.attrib else "unsigned"
        byte_order = element.get("byteOrder", "mostSignificantByteFirst")
        calibrator = cls.get_default_calibrator(element, ns)
        context_calibrators = cls.get_context_calibrators(element, ns)
        return cls(size_in_bits=size_in_bits, encoding=encoding, byte_order=byte_order,
                   default_calibrator=calibrator, context_calibrators=context_calibrators)


class FloatDataEncoding(NumericDataEncoding):
    """<xtce:FloatDataEncoding>"""
    _supported_encodings = ['IEEE-754', 'MIL-1750A']

    def __init__(
            self,
            size_in_bits: int,
            *,
            encoding: str = 'IEEE-754',
            byte_order: str = 'mostSignificantByteFirst',
            default_calibrator: Optional[calibrators.Calibrator] = None,
            context_calibrators: Optional[List[calibrators.ContextCalibrator]] = None
    ):
        """Constructor

        Parameters
        ----------
        size_in_bits : int
            Size of the encoded value, in bits.
        encoding : str
            Encoding method of the float data. Must be either 'IEEE-754' or 'MIL-1750A'. Defaults to IEEE-754.
        byte_order : str
            Description of the byte order. Default is 'mostSignificantByteFirst' (big endian).
        default_calibrator : Optional[Calibrator]
            Optional Calibrator object, containing information on how to transform the data, e.g. via
            a polynomial conversion or spline interpolation.
        context_calibrators : Optional[List[ContextCalibrator]]
            List of ContextCalibrator objects, containing match criteria and corresponding calibrators to use in
            various scenarios, based on other parameters.
        """
        if encoding not in self._supported_encodings:
            raise ValueError(f"Invalid encoding type {encoding} for float data. "
                             f"Must be one of {self._supported_encodings}.")
        if encoding == 'MIL-1750A' and size_in_bits != 32:
            raise ValueError("MIL-1750A encoded floats must be 32 bits, per the MIL-1750A spec. See "
                             "https://www.xgc-tek.com/manuals/mil-std-1750a/c191.html#AEN324")
        if encoding == 'IEEE-754' and size_in_bits not in (16, 32, 64):
            raise ValueError(f"Invalid size_in_bits value for IEEE-754 FloatDataEncoding, {size_in_bits}. "
                             "Must be 16, 32, or 64.")
        super().__init__(size_in_bits=size_in_bits, encoding=encoding, byte_order=byte_order,
                         default_calibrator=default_calibrator, context_calibrators=context_calibrators)
        if self.encoding == "MIL-1750A":
            def _mil_parse_func(mil_bytes: bytes):
                """Parsing function for MIL-1750A floats"""
                # MIL 1750A floats are always 32 bit
                # See: https://www.xgc-tek.com/manuals/mil-std-1750a/c191.html#AEN324
                #
                #  MSB                                         LSB MSB          LSB
                # ------------------------------------------------------------------
                # | S|                   Mantissa                 |    Exponent    |
                # ------------------------------------------------------------------
                #   0  1                                        23 24            31
                if self.byte_order == "leastSignificantByteFirst":
                    bytes_as_int = int.from_bytes(mil_bytes, byteorder='little')
                else:
                    bytes_as_int = int.from_bytes(mil_bytes, byteorder='big')
                exponent = bytes_as_int & 0xFF  # last 8 bits
                mantissa = (bytes_as_int >> 8) & 0xFFFFFF  # bits 0 through 23 (24 bits)
                # We include the sign bit with the mantissa because we can just take the twos complement
                # of it directly and use it in the final calculation for the value

                # Both mantissa and exponent are stored as twos complement with no bias
                exponent = self._twos_complement(exponent, 8)
                mantissa = self._twos_complement(mantissa, 24)

                # Calculate float value using native Python floats, which are more precise
                return mantissa * (2.0 ** (exponent - (24 - 1)))

            # Set up the parsing function just once, so we can use it repeatedly with _get_raw_value
            self.parse_func = _mil_parse_func
        else:
            if self.byte_order == "leastSignificantByteFirst":
                self._struct_format = "<"
            else:
                # Big-endian is the default
                self._struct_format = ">"

            if self.size_in_bits == 16:
                self._struct_format += "e"
            elif self.size_in_bits == 32:
                self._struct_format += "f"
            elif self.size_in_bits == 64:
                self._struct_format += "d"

            def ieee_parse_func(data: bytes):
                """Parsing function for IEEE floats"""
                # The packet data we got back is always extracted in big-endian order
                # but the struct format code contains the endianness of the float data
                return struct.unpack(self._struct_format, data)[0]
            # Set up the parsing function just once, so we can use it repeatedly with _get_raw_value
            self.parse_func: callable = ieee_parse_func

    def _get_raw_value(self, packet):
        """Read the data in as bytes and return a float representation."""
        data = packet.raw_data.read_as_bytes(self.size_in_bits)
        # The parsing function is fully set during initialization to save time during parsing
        return self.parse_func(data)

    @classmethod
    def from_data_encoding_xml_element(cls, element: ElementTree.Element, ns: dict) -> 'FloatDataEncoding':
        """Create a data encoding object from an <xtce:FloatDataEncoding> XML element.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        : cls
        """
        size_in_bits = int(element.attrib['sizeInBits'])
        encoding = element.get("encoding", "IEEE-754")
        byte_order = element.get("byteOrder", "mostSignificantByteFirst")
        default_calibrator = cls.get_default_calibrator(element, ns)
        context_calibrators = cls.get_context_calibrators(element, ns)
        return cls(size_in_bits=size_in_bits, encoding=encoding, byte_order=byte_order,
                   default_calibrator=default_calibrator, context_calibrators=context_calibrators)


class BinaryDataEncoding(DataEncoding):
    """<xtce:BinaryDataEncoding>"""

    def __init__(self,
                 *,
                 fixed_size_in_bits: Optional[int] = None,
                 size_reference_parameter: Optional[str] = None,
                 use_calibrated_value: bool = True,
                 size_discrete_lookup_list: Optional[List[comparisons.DiscreteLookup]] = None,
                 linear_adjuster: Optional[callable] = None):
        """Constructor

        Parameters
        ----------
        fixed_size_in_bits : Optional[int]
            Fixed size for the binary field, in bits.
        size_reference_parameter : Optional[str]
            Name of a parameter to reference for the binary field length, in bits. Note that space often specifies these
            fields in byte length, not bit length. This should be taken care of by a LinearAdjuster element that simply
            instructs the value to be multiplied by 8 but that hasn't historically been implemented unfortunately.
        use_calibrated_value: bool, Optional
            Default True. If False, the size_reference_parameter is examined for its raw value.
        size_discrete_lookup_list: Optional[List[DiscreteLookup]]
            List of DiscreteLookup objects by which to determine the length of the binary data field. This suffers from
            the same bit/byte conversion problem as size_reference_parameter.
        linear_adjuster : Optional[callable]
            Function that linearly adjusts a size. e.g. if the size reference parameter gives a length in bytes, the
            linear adjuster should multiply by 8 to give the size in bits.
        """
        self.fixed_size_in_bits = fixed_size_in_bits
        self.size_reference_parameter = size_reference_parameter
        self.use_calibrated_value = use_calibrated_value
        self.size_discrete_lookup_list = size_discrete_lookup_list
        self.linear_adjuster = linear_adjuster

    def _calculate_size(self, packet: packets.CCSDSPacket) -> int:
        """Determine the number of bits in the binary field.

        Returns
        -------
        : Union[str, None]
            Format string in the bitstring format. e.g. bin:1024
        """
        if self.fixed_size_in_bits is not None:
            len_bits = self.fixed_size_in_bits
        elif self.size_reference_parameter is not None:
            field_length_reference = self.size_reference_parameter
            if self.use_calibrated_value:
                len_bits = packet[field_length_reference].derived_value
            else:
                len_bits = packet[field_length_reference].raw_value
        elif self.size_discrete_lookup_list is not None:
            for discrete_lookup in self.size_discrete_lookup_list:
                len_bits = discrete_lookup.evaluate(packet)
                if len_bits is not None:
                    break
            else:
                raise ValueError('List of discrete lookup values being used for determining length of '
                                 f'string {self} found no matches based on {packet}.')
        else:
            raise ValueError("Unable to parse BinaryDataEncoding. "
                             "No fixed size, dynamic size, or dynamic lookup size were provided.")

        if self.linear_adjuster is not None:
            len_bits = self.linear_adjuster(len_bits)
        return len_bits

    def parse_value(self, packet: packets.CCSDSPacket, **kwargs):
        """Parse a value from packet data, possibly using previously parsed data items to inform parsing.

        Parameters
        ----------
        packet: CCSDSPacket
            Binary representation of the packet used to get the coming bits and any
            previously parsed data items to infer field lengths.

        Returns
        -------
        : any
            Parsed value
        : any
            Calibrated value
        """
        nbits = self._calculate_size(packet)
        parsed_value = packet.raw_data.read_as_bytes(nbits)
        return parsed_value, None

    @classmethod
    def from_data_encoding_xml_element(cls, element: ElementTree.Element, ns: dict) -> 'BinaryDataEncoding':
        """Create a data encoding object from an <xtce:BinaryDataEncoding> XML element.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        : BinaryDataEncoding
        """
        fixed_value_element = element.find('xtce:SizeInBits/xtce:FixedValue', ns)
        if fixed_value_element is not None:
            fixed_size_in_bits = int(fixed_value_element.text)
            return cls(fixed_size_in_bits=fixed_size_in_bits)

        dynamic_value_element = element.find('xtce:SizeInBits/xtce:DynamicValue', ns)
        if dynamic_value_element is not None:
            param_inst_ref = dynamic_value_element.find('xtce:ParameterInstanceRef', ns)
            referenced_parameter = param_inst_ref.attrib['parameterRef']
            use_calibrated_value = True
            if 'useCalibratedValue' in param_inst_ref.attrib:
                use_calibrated_value = param_inst_ref.attrib['useCalibratedValue'].lower() == "true"
            linear_adjuster = cls._get_linear_adjuster(dynamic_value_element, ns)
            return cls(size_reference_parameter=referenced_parameter,
                       use_calibrated_value=use_calibrated_value, linear_adjuster=linear_adjuster)

        discrete_lookup_list_element = element.find('xtce:SizeInBits/xtce:DiscreteLookupList', ns)
        if discrete_lookup_list_element is not None:
            discrete_lookup_list = [comparisons.DiscreteLookup.from_discrete_lookup_xml_element(el, ns)
                                    for el in discrete_lookup_list_element.findall('xtce:DiscreteLookup', ns)]
            return cls(size_discrete_lookup_list=discrete_lookup_list)

        raise ValueError("Tried parsing a binary parameter length using Fixed, Dynamic, and DiscreteLookupList "
                         "but failed. See 3.4.5 of the XTCE Green Book CCSDS 660.1-G-2.")
