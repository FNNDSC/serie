"""
Integration tests to assert that SERIE correctly does nothing in situations where it should.
"""

import re
import os.path

import asyncio
import pydantic
import pytest
import pytest_asyncio
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

import tests.e2e_config as config
from aiochris_oag import PACSSeriesPatientSex, ApiClient, PacsApi, PACSSeries
from serie import get_router
from serie.dicom_series_metadata import DicomSeriesMetadataName
from serie.models import (
    RawPacsSeries,
    DicomSeriesPayload,
    DicomSeriesMatcher,
    ChrisRunnableRequest,
    InvalidRunnableList, BadRequestResponse,
)
from tests.helpers import download_and_send_dicom, get_configuration

_EXAMPLE_DICOM_URL = "https://zenodo.org/records/13883238/files/DAI000290.dcm?download=1"
_EXAMPLE_DICOM_SERIES_UID = "1.2.276.0.7230010.3.1.3.8323329.8519.1517874337.873097"
_FOLDER_ID_RE = re.compile(r"(?<=/api/v1/filebrowser/)(?P<id>\d+)(?=/)")


@pytest.mark.integration
def test_does_nothing(example_series):
    payload = DicomSeriesPayload(
        hasura_id="8765-4321",
        data=example_series,
        match=[
            DicomSeriesMatcher(
                tag="SeriesDescription",
                regex=r".*(Chest).*",
                case_sensitive=False
            )
        ],
        jobs=[ChrisRunnableRequest(runnable_type="plugin", name="pl-dcm2niix")],
        feed_name_template="I should not be created",
    )
    res = post(payload)
    assert res.status_code == status.HTTP_204_NO_CONTENT
    # assert res.json().get("error", None) == "DICOM series not found"


@pytest.mark.integration
def test_catches_missing_plugins(example_series):
    data = DicomSeriesPayload(
        hasura_id="8765-4321",
        data=example_series,
        match=[
            DicomSeriesMatcher(
                tag=DicomSeriesMetadataName.StudyDescription,
                regex=r".*(Chest).*",
                case_sensitive=False,
            ),
            DicomSeriesMatcher(
                tag=DicomSeriesMetadataName.Modality, regex="CR", case_sensitive=True
            ),
        ],
        jobs=[
            ChrisRunnableRequest(
                runnable_type="plugin", name="pl-i-do-not-exist", version="99"
            )
        ],
        feed_name_template="I should not be created",
    )
    res = post(data)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    error = BadRequestResponse.model_validate_json(res.content)
    assert isinstance(error.data, dict)
    invalid_list = InvalidRunnableList.model_validate(error.data)
    assert invalid_list.errors[0].runnable.name == "pl-i-do-not-exist"
    assert invalid_list.errors[0].runnable.version == "99"


def post(data: pydantic.BaseModel):
    app = FastAPI(title=f"SERIE - test {os.path.basename(__file__)}")
    app.include_router(get_router())
    client = TestClient(app)
    res = client.post(
        "/dicom_series/",
        auth=(config.CHRIS_USERNAME, config.CHRIS_PASSWORD),
        content=data.model_dump_json(by_alias=True),
        headers={"Content-Type": "application/json"},
    )
    return res


@pytest_asyncio.fixture(scope="session")
async def example_series(push_sample_dicom, api_client: ApiClient) -> RawPacsSeries:
    pacs_api = PacsApi(api_client)
    poll_count = 0
    while poll_count < config.MAX_POLL:
        search = await pacs_api.pacs_series_search_list(
            series_instance_uid=_EXAMPLE_DICOM_SERIES_UID
        )
        if len(search.results) > 0:
            return _series_to_raw(search.results[0])
        await asyncio.sleep(1)
        poll_count += 1
    raise pytest.fail(f"Series {_EXAMPLE_DICOM_SERIES_UID} was not pushed to CUBE.")


@pytest_asyncio.fixture(scope="session")
async def api_client() -> ApiClient:
    configuration = get_configuration()
    async with ApiClient(configuration) as api_client:
        yield api_client


@pytest.fixture(scope="session")
def push_sample_dicom():
    download_and_send_dicom(_EXAMPLE_DICOM_URL, config.AE_TITLE)


def _series_to_raw(series: PACSSeries) -> RawPacsSeries:
    data = series.model_dump(by_alias=True)
    del data["folder"]
    del data["pacs_identifier"]
    data["folder_id"] = int(_FOLDER_ID_RE.search(series.folder).group('id'))
    data["pacs_id"] = 99  # fake value does not matter
    data["PatientSex"] = series.patient_sex.to_dict()
    return RawPacsSeries.model_validate(data)
