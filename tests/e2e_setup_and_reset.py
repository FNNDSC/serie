"""
A script for preparing the state of CUBE for test_e2e.py.
"""

import asyncio
import textwrap
from contextlib import asynccontextmanager
from typing import AsyncContextManager

import docker
from asyncer import asyncify

import tests.e2e_config as e2e_config
from aiochris_oag import (
    ChrisAdminApi,
    Configuration,
    ApiClient,
    PluginAdminRequest,
    DefaultApi,
    UsersApi,
    UserRequest,
)
from aiochris_oag.exceptions import UnauthorizedException
from serie.settings import get_settings


async def _delete_feeds():
    """
    Delete all the feeds for the user.
    """
    async with api_client_context() as api_client:
        feeds_api = DefaultApi(api_client)
        all_feeds = await feeds_api.root_list(limit=1000)
        feed_ids = (feed.id for feed in all_feeds.results)
        await asyncio.gather(*map(feeds_api.root_destroy, feed_ids))
        after = await feeds_api.root_list(limit=0)
        assert after.count == 0


async def _register_plugins():
    """
    Register the plugins we need for this test.
    """
    async with api_client_context() as api_client:
        admin_api = ChrisAdminApi(api_client)
        compute_resources = await admin_api.chris_admin_api_v1_computeresources_list()
        compute_resource = compute_resources.results[0]
        requests = (
            PluginAdminRequest(
                plugin_store_url=url, compute_names=compute_resource.name
            )
            for url in e2e_config.PLUGINS.values()
        )
        await asyncio.gather(*map(admin_api.chris_admin_api_v1_create, requests))


@asynccontextmanager
async def api_client_context() -> AsyncContextManager[ApiClient]:
    settings = get_settings()
    config = Configuration(
        host=settings.get_host(),
        username=e2e_config.CHRIS_ADMIN_USERNAME,
        password=e2e_config.CHRIS_ADMIN_PASSWORD,
    )
    async with ApiClient(config, "Accept", "application/json") as api_client:
        yield api_client


def clear_dicoms_from_cube(ae_title: str):
    """
    Delete all PACSFiles of a PACS from CUBE.
    """
    client = docker.from_env()
    cube = client.containers.get(e2e_config.CUBE_CONTAINER_ID)
    cube.exec_run(
        [
            "python",
            "manage.py",
            "shell",
            "-c",
            textwrap.dedent(f"""
        from pacsfiles.models import PACS, PACSSeries
        try:
            pacs = PACS.objects.get(identifier='{ae_title}')
            for series in PACSSeries.objects.filter(pacs=pacs):
                series.delete()
        except PACS.DoesNotExist:
            pass
        """),
        ]
    )


async def _create_user_if_needed():
    """
    Get a client for the test user. If the account does not exist, create it.
    """
    settings = get_settings()
    config = Configuration(
        host=settings.get_host(),
        username=e2e_config.CHRIS_USERNAME,
        password=e2e_config.CHRIS_PASSWORD,
    )

    try:
        async with ApiClient(config) as api_client:
            users_api = UsersApi(api_client)
            await users_api.users_list()
    except UnauthorizedException:
        anon = Configuration(host=settings.get_host())
        async with ApiClient(anon) as anon_api:
            await UsersApi(anon_api).users_create(
                UserRequest(
                    email=f"{e2e_config.CHRIS_USERNAME}@example.org",
                    username=e2e_config.CHRIS_USERNAME,
                    password=e2e_config.CHRIS_PASSWORD,
                )
            )
    return api_client


async def main():
    await asyncio.gather(
        _delete_feeds(),
        _register_plugins(),
        _create_user_if_needed(),
        asyncify(clear_dicoms_from_cube)(e2e_config.AE_TITLE),
    )


if __name__ == "__main__":
    asyncio.run(main())
