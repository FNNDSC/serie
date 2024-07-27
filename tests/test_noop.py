import datetime
import os.path

import pydantic
import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

import tests.e2e_config as config
from serie import router
from serie.models import (
    PacsFile,
    DicomSeriesPayload,
    DicomSeriesMatcher,
    ChrisRunnableRequest,
)
from tests.examples import read_example
from tests.helpers import download_and_send_dicom

app = FastAPI(title=f"SERIE - test {os.path.basename(__file__)}")
app.include_router(router)
client = TestClient(app)

_EXAMPLE_DICOM_URL = "https://cube-for-testing-chrisui.apps.shift.nerc.mghpcc.org/api/v1/files/570/0156-1.3.12.2.1107.5.2.19.45152.2013030808105683775785575.dcm"
_AE_TITLE = "SERIETESTOTHER"

@pytest.mark.e2e
@pytest.mark.parametrize(
    "explanation, data",
    (
        (
            'Should do nothing when receiving a DICOM that is not "OxidicomAttemptedPushCount=*"',
            DicomSeriesPayload(
                hasura_id="1234-5678",
                data=PacsFile.model_validate_json(read_example("pacsfile6.json")),
                match=[
                    DicomSeriesMatcher(
                        tag="SeriesDescription",
                        regex=r".*(chest).*",
                    )
                ],
                jobs=[ChrisRunnableRequest(runnable_type="plugin", name="pl-dcm2niix")],
                feed_name_template="I should not be created",
            ),
        ),
        (
            "Should do nothing when receiving a series that does not match the specified matcher",
            DicomSeriesPayload(
                hasura_id="8765-4321",
                data=PacsFile(
                    id=500,
                    ProtocolName="SAG MPRAGE 220 FOV",
                    PatientName="anonymized",
                    PatientSex="M",
                    AccessionNumber="98edede8b2",
                    PatientAge=1095.72,
                    creation_date=datetime.datetime(2023, 1, 20),
                    pacs_id=2,
                    PatientBirthDate=datetime.datetime(2009, 7, 1),
                    PatientID="1449c1d",
                    StudyDate=datetime.datetime(2013, 3, 8),
                    Modality="MR",
                    fname=f"SERVICES/PACS/org.fnndsc.oxidicom/SERVICES/PACS/{_AE_TITLE}/1449c1d-anonymized-20090701/MR-Brain_w_o_Contrast-98edede8b2-20130308/00005-SAG_MPRAGE_220_FOV-a27cf06/01J3V1NANC16JHR3XA8S43CCZY/OxidicomAttemptedPushCount=192",
                    StudyDescription="MR-Brain w/o Contrast",
                    SeriesDescription="SAG MPRAGE 220 FOV",
                    SeriesInstanceUID="1.3.12.2.1107.5.2.19.45152.2013030808061520200285270.0.0.0",
                    StudyInstanceUID="1.2.840.113845.11.1000000001785349915.20130308061609.6346698",
                ),
                match=[
                    DicomSeriesMatcher(
                        tag="SeriesDescription",
                        regex=r".*(chest).*",
                    )
                ],
                jobs=[ChrisRunnableRequest(runnable_type="plugin", name="pl-dcm2niix")],
                feed_name_template="I should not be created",
            ),
        ),
    ),
)
def test_does_nothing(explanation, data):
    assert post(data).status_code == status.HTTP_204_NO_CONTENT, explanation


def post(data: pydantic.BaseModel):
    res = client.post(
        "/dicom_series/",
        auth=(config.CHRIS_USERNAME, config.CHRIS_PASSWORD),
        content=data.model_dump_json(by_alias=True),
        headers={"Content-Type": "application/json"},
    )
    res.raise_for_status()
    return res


@pytest.fixture(scope="session", autouse=True)
def push_sample_dicom():
    download_and_send_dicom(_EXAMPLE_DICOM_URL, _AE_TITLE)
