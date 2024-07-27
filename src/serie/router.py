from typing import Optional, Annotated

from aiochris.types import FeedUrl
from fastapi import Response, status, Header, APIRouter

from serie.clients import BadAuthorizationError
from serie.match import is_match
from serie.models import DicomSeriesPayload, OxidicomCustomMetadata
from serie.settings import get_settings
from serie.actions import ClientActions

router = APIRouter()
"""The one and only router of SERIE!"""


@router.post("/dicom_series/")
async def dicom_series(
    payload: DicomSeriesPayload,
    authorization: Annotated[str, Header()],
    response: Response,
) -> Optional[FeedUrl]:
    """
    Create *ChRIS* plugin instances and/or workflows on DICOM series data when an entire DICOM series is received.
    """
    settings = get_settings()
    actions = ClientActions(auth=authorization, url=settings.chris_url)
    if (series := await actions.resolve_series(payload.data)) is None:
        response.status_code = status.HTTP_204_NO_CONTENT
        return None
    if not is_match(series, payload.match):
        response.status_code = status.HTTP_204_NO_CONTENT
        return None

    try:
        feed = await actions.create_analysis(
            series, payload.jobs, payload.feed_name_template
        )
    except BadAuthorizationError as e:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return None
    response.status_code = status.HTTP_201_CREATED
    return feed.url
