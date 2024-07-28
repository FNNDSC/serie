"""
End-to-end test where SERIE is called on by Hasura.
"""

import asyncio

import pytest
import pytest_asyncio
import uvicorn
from aiochris import ChrisClient, acollect
from aiochris.models import Feed
from asyncer import asyncify
from fastapi import FastAPI

import tests.e2e_config as config
from serie import get_router
from serie.settings import get_settings
from tests.helpers import download_and_send_dicom
from tests.uvicorn_test_server import UvicornTestServer


@pytest.mark.integration
@pytest.mark.asyncio
async def test_e2e(server: UvicornTestServer, chris: ChrisClient):
    await _send_and_wait_for_dicom(chris)
    feed = await _poll_for_feed(chris, config.EXPECTED_FEED_NAME)
    plinsts = await acollect(chris.plugin_instances(feed_id=feed.id))
    ran_plugins = set(p.plugin_name for p in plinsts)
    assert ran_plugins == {"pl-dircopy", "pl-unstack-folders", *config.PLUGINS.keys()}
    plinst = next(filter(lambda p: p.plugin_name == "pl-dcm2niix", plinsts))
    params = await acollect(plinst.get_parameters())
    assert len(params) == 1
    assert params[0].param_name == "z"
    assert params[0].value == "y"


@pytest_asyncio.fixture
async def server() -> UvicornTestServer:
    app = FastAPI(title="SERIE TEST")
    app.include_router(get_router())
    uvicorn_config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=config.SERIE_PORT,
        # N.B. uvicorn wants to create its own async event loop.
        # The default option causes some conflict with the outer loop.
        # A workaround is to set loop="asyncio".
        # This is surely to break even more in the future.
        loop="asyncio",
    )
    server = UvicornTestServer(uvicorn_config)
    await server.start()
    try:
        yield server
    except Exception:
        raise
    finally:
        await server.stop()


async def _poll_for_feed(chris: ChrisClient, name: str) -> Feed:
    poll_count = 0
    while (feed := await chris.search_feeds(name=name).first()) is None:
        poll_count += 1
        if poll_count >= config.MAX_POLL:
            raise pytest.fail("Expected feed was not created.")
        await asyncio.sleep(1)
    return feed


@pytest_asyncio.fixture
async def chris() -> ChrisClient:
    settings = get_settings()
    client = await ChrisClient.from_login(
        url=settings.chris_url,
        username=config.CHRIS_USERNAME,
        password=config.CHRIS_PASSWORD,
    )
    async with client as c:
        yield c


async def _send_and_wait_for_dicom(chris: ChrisClient):
    assert (
        await chris.search_pacsfiles(pacs_identifier=config.AE_TITLE).count() == 0
    ), f"CUBE contains DICOMs from {config.AE_TITLE} at start of test."

    await asyncify(download_and_send_dicom)(
        config.EXAMPLE_DOWNLOAD_URL, config.AE_TITLE
    )

    elapsed = 0
    while await chris.search_pacsfiles(pacs_identifier=config.AE_TITLE).count() == 0:
        await asyncio.sleep(0.25)
        elapsed += 0.25
        if elapsed > 5:
            raise pytest.fail(
                f"DICOM sent from AET={config.AE_TITLE} to oxidicom did not appear in the CUBE at {chris.url}."
            )
