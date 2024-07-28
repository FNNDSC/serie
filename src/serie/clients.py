import base64
from typing import Optional

import aiochris.errors
import asyncstdlib
from aiochris import ChrisClient
from aiochris.errors import IncorrectLoginError
from aiochris.models import Plugin
from aiochris.types import ChrisURL


class Clients:
    """
    Helper functions for getting client objects with LRU caching.

    N.B.: instances cannot be shared across async event loops.
    """

    @asyncstdlib.lru_cache(maxsize=64)
    async def get_plugin(
        self, url: ChrisURL, auth: Optional[str], name: str, version: Optional[str]
    ) -> Optional[Plugin]:
        """
        Get a *ChRIS* plugin.

        :param url: *CUBE* url
        :param auth: authorization header value
        :param name: plugin name
        :param version: plugin version
        :raises BadAuthorizationError: if authorization header value is invalid or unauthorized.
        """
        client: ChrisClient = await self.get_client(url, auth)
        if version is None:
            search = client.search_plugins(name=name)
        else:
            search = client.search_plugins(name=name, version=version)
        try:
            return await search.first()
        except aiochris.errors.UnauthorizedError as e:
            raise BadAuthorizationError(
                "401 response status when searching for plugins. Did the authorization token expire?"
            )

    @asyncstdlib.lru_cache(maxsize=8)
    async def get_client(self, url: ChrisURL, auth: Optional[str]) -> ChrisClient:
        """
        Get a client object.

        :raises BadAuthorizationError: if authorization header value is invalid or unauthorized.
        """
        parsed_auth = _parse_auth(auth)
        if isinstance(parsed_auth, str):
            return await ChrisClient.from_token(url=url, token=parsed_auth)
        username, password = parsed_auth
        try:
            return await ChrisClient.from_login(
                url=url,
                username=parsed_auth[0],
                password=parsed_auth[1],
            )
        except IncorrectLoginError as e:
            raise BadAuthorizationError(e.args)

    def clean(self):
        """
        Empty the cache.
        """
        self.get_client.cache_clear()
        self.get_plugin.cache_clear()


def _parse_auth(auth: Optional[str]) -> tuple[str, str] | str:
    """
    If the given value is basic HTTP authentication, decode the username and password.
    """
    if not auth:
        raise BadAuthorizationError("No authorization")
    split = auth.split()
    if len(split) != 2:
        raise BadAuthorizationError("Missing space character")
    auth_type, value = split
    match auth_type.lower():
        case "basic":
            return _parse_basic_auth_value(value)
        case "token":
            return value
        case _:
            raise BadAuthorizationError(f"Unknown authorization {auth_type}")


def _parse_basic_auth_value(value: str) -> tuple[str, str]:
    decoded = base64.b64decode(value).decode(encoding="utf-8")
    split = decoded.split(":", maxsplit=1)
    if len(split) != 2:
        raise BadAuthorizationError(f"No password given for HTTP basic auth")
    return split[0], split[1]


class BadAuthorizationError(Exception):
    """
    HTTP authorization header value could not be parsed.
    """
    pass
