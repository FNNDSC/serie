import os
from pathlib import Path

import pydicom
import pynetdicom
import pytest
import pytest_asyncio
import requests
import docker
import textwrap
from aiochris import ChrisClient
from aiochris.errors import IncorrectLoginError
from asyncer import asyncify

import tests.e2e_config as config


@pytest.mark.skipif(
    os.environ.get("SERIE_PYTEST_E2E", "").lower() != "y",
    reason="Run with `env SERIE_PYTEST_E2E=y pytest` to enable end-to-end test.",
)
@pytest.mark.asyncio
async def test_e2e(chris: ChrisClient):
    await _start_test(chris)


@pytest_asyncio.fixture
async def chris() -> ChrisClient:
    try:
        client = await ChrisClient.from_login(
            url=config.CUBE_URL,
            username=config.CHRIS_USERNAME,
            password=config.CHRIS_PASSWORD,
        )
    except IncorrectLoginError:
        await ChrisClient.create_user(
            url=config.CUBE_URL,
            username=config.CHRIS_USERNAME,
            password=config.CHRIS_PASSWORD,
            email=f"{config.CHRIS_USERNAME}@example.org",
        )
        client = await ChrisClient.from_login(
            url=config.CUBE_URL,
            username=config.CHRIS_USERNAME,
            password=config.CHRIS_PASSWORD,
        )
    async with client as c:
        yield c


async def _start_test(chris: ChrisClient):
    await asyncify(clear_dicoms_from_cube)()
    assert await chris.search_pacsfiles(pacs_identifier=config.AE_TITLE).count() == 0
    await asyncify(send_sample_dicom)()
    assert await chris.search_pacsfiles(pacs_identifier=config.AE_TITLE).count() > 0


def clear_dicoms_from_cube():
    client = docker.from_env()
    cube = client.containers.get(config.CUBE_CONTAINER_ID)
    cube.exec_run(
        [
            "python",
            "manage.py",
            "shell",
            "-c",
            textwrap.dedent(f"""
        from pacsfiles.models import PACS, PACSFile
        try:
            pacs = PACS.objects.get(identifier='{config.AE_TITLE}')
            for pacs_file in PACSFile.objects.filter(pacs=pacs):
                pacs_file.delete()
        except PACS.DoesNotExist:
            pass
        """),
        ]
    )


def send_sample_dicom():
    """
    See https://pydicom.github.io/pynetdicom/stable/examples/storage.html#storage-scu
    """
    # from pynetdicom import debug_logger
    # debug_logger()

    ds = pydicom.dcmread(get_sample_dicom())
    ae = pynetdicom.AE(ae_title="SERIETEST")
    ae.add_requested_context(ds.file_meta.MediaStorageSOPClassUID)
    assoc = ae.associate(
        config.OXIDICOM_ADDRESS, config.OXIDICOM_PORT, ae_title=config.OXIDICOM_AET
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


def get_sample_dicom() -> Path:
    tmp_dicom = Path(__file__).parent.parent / ".test_data" / "chest_ct.dcm"
    if tmp_dicom.exists():
        return tmp_dicom
    tmp_dicom.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(config.DOWNLOAD_URL, stream=True) as r:
        r.raise_for_status()
        with tmp_dicom.open("wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return tmp_dicom
