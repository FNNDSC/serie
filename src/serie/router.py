from typing import Annotated, Union

from fastapi import Response, status, Header, APIRouter

from aiochris_oag.exceptions import UnauthorizedException, NotFoundException
from serie.actions import ClientActions, InvalidRunnablesError
from serie.clients import Clients
from serie.match import is_match
from serie.models import DicomSeriesPayload, InvalidRunnableList, CreatedFeed, BadRequestResponse
from serie.settings import get_settings


def get_router() -> APIRouter:
    """
    The one and only router of SERIE!

    N.B.: router instances may not be shared across different async event loop instances.
    (This happens if you use a global router object in pytest.)
    """

    clients = Clients()
    router = APIRouter()

    @router.post(
        "/dicom_series/",
        description=(
            "A web hook which should be called when a row is inserted into "
            "CUBE database's pacsfiles_pacsseries table."
        ),
        responses={
            status.HTTP_201_CREATED: {
                "description": "Feed created",
                "model": CreatedFeed,
            },
            status.HTTP_204_NO_CONTENT: {
                "description": "DICOM series did not match"
            },
            status.HTTP_400_BAD_REQUEST: {
                "model": BadRequestResponse
            },
            status.HTTP_401_UNAUTHORIZED: {
                "model": None
            }
        },
        status_code=status.HTTP_201_CREATED
    )
    async def dicom_series(
        payload: DicomSeriesPayload,
        authorization: Annotated[str, Header()],
        response: Response,
    ):
        """
        Create *ChRIS* plugin instances and/or workflows on DICOM series data when an entire DICOM series is received.
        On success, returns the URL of the created feed.
        """
        settings = get_settings()
        actions = ClientActions(
            auth=authorization, host=settings.get_host(), clients=clients
        )
        try:
            resolved = await actions.resolve_series(payload.data)
        except UnauthorizedException as e:
            response.status_code = e.status
            return None
        except NotFoundException as e:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return BadRequestResponse(error="DICOM series not found", data=payload.data)

        if not is_match(resolved.series, payload.match):
            response.status_code = status.HTTP_204_NO_CONTENT
            return None

        try:
            feed_url = await actions.create_analysis(
                resolved, payload.jobs, payload.feed_name_template
            )
        except InvalidRunnablesError as e:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return BadRequestResponse(
                error="Invalid runnables",
                data=InvalidRunnableList(errors=e.runnables)
            )

        response.status_code = status.HTTP_201_CREATED
        return CreatedFeed(feed=feed_url)

    return router
