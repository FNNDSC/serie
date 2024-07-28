"""
A script for preparing the state of CUBE for test_e2e.py.
"""

import asyncio
import textwrap

import docker
from aiochris import acollect, ChrisAdminClient, ChrisClient
from aiochris.errors import IncorrectLoginError
from asyncer import asyncify

import tests.e2e_config as config
from serie.settings import get_settings


async def _delete_feeds():
    """
    Delete all the feeds for the user.
    """
    chris = await _get_or_create_chris()
    async with chris as c:
        all_feeds = await acollect(c.search_feeds())
        await asyncio.gather(*(feed.delete() for feed in all_feeds))
        assert await c.search_feeds().count() == 0


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


def clear_dicoms_from_cube(ae_title: str):
    """
    Delete all PACSFiles of a PACS from CUBE.
    """
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


async def _get_or_create_chris():
    """
    Get a client for the test user. If the account does not exist, create it.
    """
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
    return client


async def main():
    await asyncio.gather(
        _delete_feeds(),
        _register_plugins(),
        asyncify(clear_dicoms_from_cube)(config.AE_TITLE),
    )


if __name__ == "__main__":
    asyncio.run(main())
