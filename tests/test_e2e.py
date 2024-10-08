"""
End-to-end test where SERIE is called on by Hasura.
"""

import asyncio

import pytest
import pytest_asyncio
import uvicorn
from asyncer import asyncify
from fastapi import FastAPI

import tests.e2e_config as config
from aiochris_oag import ApiClient, Feed, PacsApi, PluginsApi, PlugininstancesApi, DefaultApi, SearchApi, \
    GenericDefaultPipingParameterValue
from serie import get_router
from tests.helpers import download_and_send_dicom, get_configuration
from tests.uvicorn_test_server import UvicornTestServer


@pytest.mark.integration
@pytest.mark.asyncio
async def test_e2e(server: UvicornTestServer, api_client: ApiClient):
    await _send_and_wait_for_dicom(api_client)
    feed = await _poll_for_feed(api_client, config.EXPECTED_FEED_NAME)
    plugins_api = PluginsApi(api_client)
    plinsts_api = PlugininstancesApi(api_client)
    plinsts = await plugins_api.plugins_instances_search_list(feed_id=str(feed.id))
    ran_plugin_names = set(p.plugin_name for p in plinsts.results)
    assert ran_plugin_names == {
        "pl-dircopy",
        "pl-unstack-folders",
        *config.PLUGINS.keys(),
    }
    plinst = next(p for p in plinsts.results if p.plugin_name == "pl-dcm2niix")
    params = await plugins_api.plugins_instances_parameters_list(id=plinst.id)
    assert params.count == 1
    assert params.results[0].param_name == "z"
    assert params.results[0].value.to_dict() == "y"


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


async def _poll_for_feed(api_client: ApiClient, name_exact: str) -> Feed:
    feeds_api = SearchApi(api_client)
    poll_count = 0
    while poll_count < config.MAX_POLL:
        feeds = await feeds_api.search_list(name_exact=name_exact)
        if len(feeds.results) >= 1:
            return feeds.results[0]
        poll_count += 1
        await asyncio.sleep(1)
    raise pytest.fail("Expected feed was not created.")


async def _send_and_wait_for_dicom(api_client: ApiClient):
    pacs_api = PacsApi(api_client)
    assert (
        await pacs_api.pacs_series_search_list(limit=0, pacs_identifier=config.AE_TITLE)
    ).count == 0, f"CUBE contains DICOMs from {config.AE_TITLE} at start of test."

    await asyncify(download_and_send_dicom)(
        config.EXAMPLE_DOWNLOAD_URL, config.AE_TITLE
    )

    elapsed = 0
    while (await pacs_api.pacs_files_list(limit=0)).count == 0:
        await asyncio.sleep(0.25)
        elapsed += 0.25
        if elapsed > 5:
            raise pytest.fail(
                f"DICOM sent from AET={config.AE_TITLE} to oxidicom did not appear in the CUBE at {api_client.configuration.host}."
            )


@pytest_asyncio.fixture
async def api_client() -> ApiClient:
    configuration = get_configuration()
    async with ApiClient(configuration) as api_client:
        yield api_client
