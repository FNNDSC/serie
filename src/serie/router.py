from contextlib import asynccontextmanager
from typing import Annotated

from aiochris.types import FeedUrl
from fastapi import Response, status, Header, APIRouter

from serie.actions import ClientActions, InvalidRunnablesError
from serie.clients import BadAuthorizationError, Clients
from serie.match import is_match
from serie.models import DicomSeriesPayload, InvalidRunnableResponse
from serie.settings import get_settings


def get_router() -> APIRouter:
    """
    The one and only router of SERIE!

    N.B.: router instances may not be shared across different async event loop instances.
    (This happens if you use a global router object in pytest.)
    """

    clients = Clients()

    @asynccontextmanager
    async def lifespan():
        yield
        clients.clean()

    router = APIRouter(lifespan=lifespan)

    @router.post("/dicom_series/")
    async def dicom_series(
        payload: DicomSeriesPayload,
        authorization: Annotated[str, Header()],
        response: Response,
    ) -> None | InvalidRunnableResponse | FeedUrl:
        """
        Create *ChRIS* plugin instances and/or workflows on DICOM series data when an entire DICOM series is received.
        """
        settings = get_settings()
        actions = ClientActions(
            auth=authorization, url=settings.chris_url, clients=clients
        )
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
        except BadAuthorizationError as _e:
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return None
        except InvalidRunnablesError as e:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return InvalidRunnableResponse(errors=e.runnables)

        response.status_code = status.HTTP_201_CREATED
        return feed.url

    return router
