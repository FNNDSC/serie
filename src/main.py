from typing import Optional, Annotated

from aiochris.types import FeedUrl
from fastapi import FastAPI, Response, status, Header

from serie import (
    DicomSeriesPayload,
    get_settings,
    BadAuthorizationError,
    ClientActions,
    __version__,
)
from serie.models import OxidicomCustomMetadata

app = FastAPI(
    title="Specific Endpoints for Research Integration Events",
    contact={
        "name": "FNNDSC",
        "url": "https://chrisproject.org",
        "email": "Newborn_FNNDSCdev-dl@childrens.harvard.edu",
    },
    version=__version__,
)


@app.post("/dicom_series/")
async def dicom_series(
    payload: DicomSeriesPayload,
    authorization: Annotated[str, Header()],
    response: Response,
) -> Optional[FeedUrl]:
    """
    Create *ChRIS* plugin instances and/or workflows on DICOM series data when an entire DICOM series is received.
    """
    if (oxm_file := OxidicomCustomMetadata.from_pacsfile(payload.data)) is None:
        response.status_code = status.HTTP_204_NO_CONTENT
        return None

    settings = get_settings()
    actions = ClientActions(auth=authorization, url=settings.chris_url)
    try:
        feed = await actions.create_analysis(
            oxm_file, payload.jobs, payload.feed_name_template
        )
    except BadAuthorizationError as e:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return None
    return feed.url
