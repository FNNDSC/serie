import asyncio
import shutil
import textwrap

import docker
import pytest
import pytest_asyncio
import uvicorn
from aiochris import ChrisClient, ChrisAdminClient, acollect
from aiochris.errors import IncorrectLoginError
from aiochris.models import Feed
from asyncer import asyncify
from fastapi import FastAPI

import tests.e2e_config as config
from serie import get_router
from serie.settings import get_settings
from tests.helpers import download_and_send_dicom
from tests.uvicorn_test_server import UvicornTestServer


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e(server: UvicornTestServer, chris: ChrisClient):
    await asyncio.gather(
        asyncify(_configure_hasura)(), _delete_feeds(chris), _register_plugins()
    )
    await _start_test(chris)
    feed = await _poll_for_feed(chris, config.EXPECTED_FEED_NAME)
    plinsts = await acollect(chris.plugin_instances(feed_id=feed.id))
    ran_plugins = set(p.plugin_name for p in plinsts)
    assert ran_plugins == {"pl-dircopy", "pl-unstack-folders", *config.PLUGINS.keys()}


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
    try:
        client = await ChrisClient.from_login(
            url=settings.chris_url,
            username=config.CHRIS_USERNAME,
            password=config.CHRIS_PASSWORD,
        )
    except IncorrectLoginError:
        await ChrisClient.create_user(
            url=settings.chris_url,
            username=config.CHRIS_USERNAME,
            password=config.CHRIS_PASSWORD,
            email=f"{config.CHRIS_USERNAME}@example.org",
        )
        client = await ChrisClient.from_login(
            url=settings.chris_url,
            username=config.CHRIS_USERNAME,
            password=config.CHRIS_PASSWORD,
        )
    async with client as c:
        yield c


async def _start_test(chris: ChrisClient):
    await asyncify(clear_dicoms_from_cube)(config.AE_TITLE)
    assert await chris.search_pacsfiles(pacs_identifier=config.AE_TITLE).count() == 0

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


def clear_dicoms_from_cube(ae_title: str):
    client = docker.from_env()
    cube = client.containers.get(config.CUBE_CONTAINER_ID)
    cube.exec_run(
        [
            "python",
            "manage.py",
            "shell",
            "-c",
            textwrap.dedent(f"""
        from pacsfiles.models import PACS, PACSFile
        try:
            pacs = PACS.objects.get(identifier='{ae_title}')
            for pacs_file in PACSFile.objects.filter(pacs=pacs):
                pacs_file.delete()
        except PACS.DoesNotExist:
            pass
        """),
        ]
    )


def _configure_hasura():
    """
    Copy the hasura metadata YAML files to the path where a shared volume is mounted,
    then run the hasura-cli in a container with the copied YAML files.
    """
    # these paths, and the volume name "hasura-copy" are set in docker-compose.yml
    shutil.copytree("/hasura", "/hasura_copy", dirs_exist_ok=True)
    client = docker.from_env()
    client.containers.run(
        image=config.HASURA_CLI_IMAGE,
        command=["hasura", "metadata", "apply"],
        volumes={"hasura-copy": {"bind": "/config", "mode": "ro"}},
        working_dir="/config",
        network="minichris-local",
        auto_remove=True,
    )


async def _delete_feeds(chris: ChrisClient):
    """
    Delete all the feeds for the user.
    """
    all_feeds = await acollect(chris.search_feeds())
    await asyncio.gather(*(feed.delete() for feed in all_feeds))
    assert await chris.search_feeds().count() == 0


async def _register_plugins():
    """
    Register the plugins we need for this test.
    """
    settings = get_settings()
    admin: ChrisAdminClient = await ChrisAdminClient.from_login(
        url=settings.chris_url,
        username=config.CHRIS_ADMIN_USERNAME,
        password=config.CHRIS_ADMIN_PASSWORD,
    )
    async with admin as a:
        compute_resource = await a.search_compute_resources().first()
        assert compute_resource is not None
        await asyncio.gather(
            *(
                a.register_plugin_from_store(url, [compute_resource.name])
                for url in config.PLUGINS.values()
            )
        )
