from typing import Optional

import asyncstdlib

from aiochris_oag import Configuration, Plugin, ApiClient, PluginsApi


class Clients:
    """
    Helper functions for getting client objects with LRU caching.

    N.B.: instances cannot be shared across async event loops.

    Warning: graceful shutdown of clients not handled.
    """

    @asyncstdlib.lru_cache(maxsize=64)
    async def get_plugin(
        self, host: str, auth: Optional[str], name: str, version: Optional[str]
    ) -> Optional[Plugin]:
        """
        Get a *ChRIS* plugin.
        """
        api_client = self.get_api_client(host, auth)
        plugins_api = PluginsApi(api_client)
        res = await plugins_api.plugins_search_list(name=name, version=version)
        if res.results is None or len(res.results) == 0:
            return None
        return res.results[0]

    def get_api_client(self, host: str, auth: Optional[str]) -> ApiClient:
        config = Configuration(host=host)
        auth_params = (
            {"header_name": "Authorization", "header_value": auth} if auth else {}
        )
        return ApiClient(config, **auth_params)
