import os.path

from fastapi import FastAPI

from serie.global_client import (
    pl_dircopy as get_pl_dircopy,
    client_oncelock as get_client,
)
from serie.models import DicomSeriesPayload

app = FastAPI()


@app.post("/dicom_series/")
async def dicom_series(payload: DicomSeriesPayload) -> str:
    if dicom.protocol_name != "OxidicomAttemptedPushCount":
        return "SKIPPED"

    client = await get_client()
    a_series_file = await client.search_pacsfiles(
        SeriesInstanceUID=dicom.series_instance_uid
    ).first()
    series_dir = os.path.dirname(a_series_file)

    pl_dircopy = await get_pl_dircopy()
    plinst = await pl_dircopy.create_instance(dir=series_dir)
    feed = await plinst.get_feed()
    await feed.set(name=f'Auto-event for "{os.path.basename(dicom.fname)}"')

    await plinst.attach_pipeline(...)
    return "OK"
