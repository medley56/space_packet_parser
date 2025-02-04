"""Test creating an xarray dataset from CCSDS packets"""
import pytest
pytest.importorskip("xarray")
pytest.importorskip("numpy")
import numpy as np
from space_packet_parser.xarr import create_dataset


def test_create_xarray_dataset(jpss_test_data_dir):
    """Test creating an xarray dataset from JPSS geolocation packets"""
    packet_file = jpss_test_data_dir / "J01_G011_LZ_2021-04-09T00-00-00Z_V01.DAT1"
    definition_file = jpss_test_data_dir / "jpss1_geolocation_xtce_v1.xml"
    ds = create_dataset(packet_file, definition_file)
    assert list(ds.keys()) == [11]
    assert len(ds[11]) == 27
    assert len(ds[11]["VERSION"]) == 7200
    assert ds[11].dtypes == {
        'VERSION': np.dtype('uint8'), 'TYPE': np.dtype('uint8'), 'SEC_HDR_FLG': np.dtype('uint8'),
        'PKT_APID': np.dtype('uint16'), 'SEQ_FLGS': np.dtype('uint8'), 'SRC_SEQ_CTR': np.dtype('uint16'),
        'PKT_LEN': np.dtype('uint16'), 'DOY': np.dtype('uint16'), 'MSEC': np.dtype('uint32'),
        'USEC': np.dtype('uint16'), 'ADAESCID': np.dtype('uint8'), 'ADAET1DAY': np.dtype('uint16'),
        'ADAET1MS': np.dtype('uint32'), 'ADAET1US': np.dtype('uint16'), 'ADGPSPOSX': np.dtype('float32'),
        'ADGPSPOSY': np.dtype('float32'), 'ADGPSPOSZ': np.dtype('float32'), 'ADGPSVELX': np.dtype('float32'),
        'ADGPSVELY': np.dtype('float32'), 'ADGPSVELZ': np.dtype('float32'), 'ADAET2DAY': np.dtype('uint16'),
        'ADAET2MS': np.dtype('uint32'), 'ADAET2US': np.dtype('uint16'), 'ADCFAQ1': np.dtype('float32'),
        'ADCFAQ2': np.dtype('float32'), 'ADCFAQ3': np.dtype('float32'), 'ADCFAQ4': np.dtype('float32')
    }


def test_create_xarray_dataset_multiple_files(jpss_test_data_dir):
    """Testing parsing multiple files of packets"""
    packet_file = jpss_test_data_dir / "J01_G011_LZ_2021-04-09T00-00-00Z_V01.DAT1"
    definition_file = jpss_test_data_dir / "jpss1_geolocation_xtce_v1.xml"
    ds = create_dataset([packet_file, packet_file], definition_file)
    assert list(ds.keys()) == [11]
    assert len(ds[11]) == 27
    assert len(ds[11]["VERSION"]) == 14400


@pytest.mark.filterwarnings("ignore:Number of bits parsed")
def test_create_xarray_dataset_ctim(ctim_test_data_dir, caplog):
    """CTIM data contains many APIDs"""
    packet_file = ctim_test_data_dir / "ccsds_2021_155_14_39_51"
    definition_file = ctim_test_data_dir / "ctim_xtce_v1.xml"
    ds = create_dataset(packet_file, definition_file, root_container_name="CCSDSTelemetryPacket", parse_bad_pkts=False)
    print(ds)


def test_create_xarray_dataset_suda(suda_test_data_dir):
    """SUDA contains a polymorphic packet structure so can't be read into an xarray dataset"""
    packet_file = suda_test_data_dir / "sciData_2022_130_17_41_53.spl"
    definition_file = suda_test_data_dir / "suda_combined_science_definition.xml"
    with pytest.raises(ValueError):  # SUDA has a polymorphic packet structure
        create_dataset(packet_file, definition_file, skip_header_bytes=4)
