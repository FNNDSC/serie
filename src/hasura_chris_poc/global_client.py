from aiochris import ChrisClient
from aiochris.models import Plugin

__CHRIS = None
__PL_DIRCOPY = None


async def client_oncelock() -> ChrisClient:
    global __CHRIS
    if __CHRIS is None:
        __CHRIS = await ChrisClient.from_login(
            url="http://chris:8000/api/v1/",
            username="automation-cool",
            password="automation1234",
        )
    return __CHRIS


async def pl_dircopy() -> Plugin:
    global __PL_DIRCOPY
    if __PL_DIRCOPY is None:
        client = await client_oncelock()
        __PL_DIRCOPY = await client.search_plugins(name_exact="pl-dircopy").first()
    return __PL_DIRCOPY
