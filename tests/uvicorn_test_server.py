import asyncio

import uvicorn
import threading


class UvicornTestServer:
    """
    An uvicorn server which runs in a different thread, and can be shut down programmatically.

    See https://github.com/encode/uvicorn/discussions/1103
    """

    def __init__(self, config: uvicorn.Config):
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(daemon=True, target=self._server.run)

    async def start(self):
        self._thread.start()
        await self._wait_for_started()

    async def _wait_for_started(self):
        while not self._server.started:
            await asyncio.sleep(0.1)

    async def stop(self):
        if self._thread.is_alive():
            self._server.should_exit = True
            while self._thread.is_alive():
                await asyncio.sleep(0.1)
