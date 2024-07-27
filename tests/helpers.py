import os
from pathlib import Path

import pydicom
import pynetdicom
import pytest
import requests

import tests.e2e_config as config


def download_and_send_dicom(url: str, ae_title: str):
    _send_dicom(_get_sample_dicom(url), ae_title)


def _get_sample_dicom(url: str) -> Path:
    tmp_dicom = Path(__file__).parent.parent / ".test_data" / _basename(url)
    if tmp_dicom.exists():
        return tmp_dicom
    tmp_dicom.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with tmp_dicom.open("wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return tmp_dicom


def _send_dicom(dicom_file: str | os.PathLike, ae_title: str):
    """
    See https://pydicom.github.io/pynetdicom/stable/examples/storage.html#storage-scu
    """
    ds = pydicom.dcmread(dicom_file)
    ae = pynetdicom.AE(ae_title=ae_title)
    ae.add_requested_context(ds.file_meta.MediaStorageSOPClassUID)
    assoc = ae.associate(
        config.OXIDICOM_HOST, config.OXIDICOM_PORT, ae_title=config.OXIDICOM_AET
    )
    if not assoc.is_established:
        raise pytest.fail("Could not establish association with oxidicom")
    status = assoc.send_c_store(ds)
    if not status:
        raise pytest.fail(
            "Failed to send data to oxidicom: "
            "connection timed out, was aborted or received invalid response"
        )
    assoc.release()


def _basename(s: str) -> str:
    split = s.rsplit("/", maxsplit=1)
    return s if len(split) == 1 else split[1]
