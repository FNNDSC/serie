import asyncio
import textwrap

import docker
import pytest
import pytest_asyncio
import uvicorn
from aiochris import ChrisClient
from aiochris.errors import IncorrectLoginError
from asyncer import asyncify
from fastapi import FastAPI

import tests.e2e_config as config
from serie import router
from serie.settings import get_settings
from tests.helpers import download_and_send_dicom
from tests.uvicorn_test_server import UvicornTestServer


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e(server: UvicornTestServer, chris: ChrisClient):
    await _start_test(chris)


@pytest_asyncio.fixture
async def server() -> UvicornTestServer:
    app = FastAPI(title="SERIE TEST")
    app.include_router(router)
    uvicorn_config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=config.SERIE_PORT,
        # N.B. uvicorn wants to create its own async event loop.
        # The default option causes some conflict with the outer loop.
        # A workaround is to set loop="asyncio". This will surely
        # break in the future!
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
