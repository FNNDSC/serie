import pytest
import os.path

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from serie import router
from serie.models import (
    PacsFile,
    DicomSeriesPayload,
    DicomSeriesMatcher,
    ChrisRunnableRequest,
)

import tests.e2e_config as config
from tests.examples import read_example

app = FastAPI(title=f"SERIE - test {os.path.basename(__file__)}")
app.include_router(router)
client = TestClient(app)


@pytest.mark.e2e
def test_does_nothing_when_received_other_dicoms(example_body, auth):
    res = client.post(
        "/dicom_series/",
        auth=auth,
        content=example_body.model_dump_json(by_alias=True),
        headers={"Content-Type": "application/json"},
    )
    res.raise_for_status()
    assert res.status_code == status.HTTP_204_NO_CONTENT


@pytest.fixture
def example_body(example_dicom: PacsFile) -> DicomSeriesPayload:
    return DicomSeriesPayload(
        hasura_id="1234-5678",
        data=example_dicom,
        match=[
            DicomSeriesMatcher(
                tag="SeriesDescription",
                regex=r".*(chest).*",
            )
        ],
        jobs=[ChrisRunnableRequest(runnable_type="plugin", name="pl-dcm2niix")],
        feed_name_template="I should not be created",
    )


@pytest.fixture
def example_dicom() -> PacsFile:
    data = read_example("pacsfile6.json")
    return PacsFile.model_validate_json(data)


@pytest.fixture
def auth() -> tuple[str, str]:
    return config.CHRIS_USERNAME, config.CHRIS_PASSWORD


@pytest.mark.skip
@pytest.mark.e2e
def test_does_nothing_when_dicom_not_matched():
    pass
