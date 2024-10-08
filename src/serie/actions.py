import asyncio
import dataclasses
import logging
import re
from collections.abc import Sequence

from aiochris_oag import (
    Plugin,
    PluginInstance,
    PluginsApi,
    PluginInstanceRequest,
    ApiClient,
    DefaultApi,
    FeedRequest,
)
from serie.clients import Clients
from serie.models import (
    ChrisRunnableRequest,
    RawPacsSeries,
    InvalidRunnable,
)
from serie.resolved_pacs_series import ResolvedPacsSeries, resolve_series

logger = logging.getLogger(__name__)

_HARDCODED_RUNNABLES = [
    ChrisRunnableRequest(runnable_type="plugin", name="pl-dircopy"),
    ChrisRunnableRequest(runnable_type="plugin", name="pl-unstack-folders"),
]
"""
The runnables which are needed to create feeds.
"""

_NOTE_ID_RE = re.compile(r"/api/v1/note(\d+)/")


@dataclasses.dataclass(frozen=True)
class FoundPlugin:
    """
    A plugin which was found in CUBE, and the runnable request which requested it.
    """

    plugin_api: PluginsApi
    plugin: Plugin
    runnable: ChrisRunnableRequest

    async def create_instance(self, previous: PluginInstance) -> PluginInstance:
        """
        Run the plugin with the runnable's parameters on the data from the ``previous`` parameter.
        """
        # WARNING:
        #  - unrecognized parameters are silently ignored.
        #  - unhandled error if parameter value is wrong type.

        return await self.plugin_api.plugins_instances_create(
            self.plugin.id,
            PluginInstanceRequest(
                previous_id=previous.id, additional_properties=self.runnable.params
            ),
        )


@dataclasses.dataclass(frozen=True)
class ClientActions:
    """
    :class:`ClientActions` provides a set of related helper functions which make authorized requests to the CUBE API.
    """

    auth: str | None
    host: str
    clients: Clients

    async def resolve_series(self, data: RawPacsSeries) -> ResolvedPacsSeries:
        return await resolve_series(self._get_client(), data)

    async def create_analysis(
        self,
        series: ResolvedPacsSeries,
        runnables_request: Sequence[ChrisRunnableRequest],
        feed_name_template: str,
    ) -> str:
        """
        Create a feed containing ``data_dir`` and run all of ``runnable_request``.
        Set the name of the created feed using ``feed_name_template``.
        """
        pl_dircopy, pl_unstack_folders, plugins = await self._get_plugins(
            runnables_request
        )
        plugins_api = self._get_plugins_api()
        dircopy_inst = await plugins_api.plugins_instances_create(
            pl_dircopy.id,
            PluginInstanceRequest(additional_properties={"dir": series.folder.path}),
        )
        root_inst = await plugins_api.plugins_instances_create(
            pl_unstack_folders.id, PluginInstanceRequest(previous_id=dircopy_inst.id)
        )
        branches = (plugin.create_instance(root_inst) for plugin in plugins)
        feed_name = _expand_variables(feed_name_template, series)
        set_feed_name = self._set_feed_name(dircopy_inst, feed_name)
        await asyncio.gather(set_feed_name, *branches)
        return dircopy_inst.feed

    async def _get_plugins(
        self, runnables_request: Sequence[ChrisRunnableRequest]
    ) -> tuple[Plugin, Plugin, Sequence[FoundPlugin]]:
        """
        Get the plugins pl-dircopy, pl-unstack-folders, and any other plugins requested.

        :raises InvalidRunnablesError: if any plugins cannot be found in CUBE.
        """
        if any(req.runnable_type != "plugin" for req in runnables_request):
            raise NotImplementedError("Only plugins are supported for now")

        needed_runnables = _HARDCODED_RUNNABLES + list(runnables_request)
        plugin_requests = (
            self.clients.get_plugin(
                self.host, self.auth, runnable.name, runnable.version
            )
            for runnable in needed_runnables
        )
        plugins = await asyncio.gather(*plugin_requests)
        missing_plugins = [
            InvalidRunnable(runnable=runnable, reason="plugin not found")
            for runnable, plugin in zip(needed_runnables, plugins)
            if plugin is None
        ]
        if len(missing_plugins) > 0:
            raise InvalidRunnablesError(missing_plugins)
        pl_dircopy, pl_unstack_folders, *others = plugins  # noqa
        pa = self._get_plugins_api()
        found_plugins = [FoundPlugin(pa, p, r) for p, r in zip(others, runnables_request)]
        return pl_dircopy, pl_unstack_folders, found_plugins

    async def _set_feed_name(self, dircopy_inst: PluginInstance, name: str):
        """
        Set the feed name of a plugin instance.
        """
        feeds_api = self._get_feeds_api()
        await feeds_api.root_update(dircopy_inst.feed_id, FeedRequest(name=name))

    def _get_feeds_api(self) -> DefaultApi:
        return DefaultApi(self._get_client())

    def _get_plugins_api(self) -> PluginsApi:
        return PluginsApi(self._get_client())

    def _get_client(self) -> ApiClient:
        return self.clients.get_api_client(self.host, self.auth)


def _expand_variables(template: str, resolved: ResolvedPacsSeries) -> str:
    """
    Expand the value of variables in ``template`` using field values from ``series``.
    """
    return template.format(**resolved.to_dicom_metadata())


class InvalidRunnablesError(Exception):
    """
    CUBE is missing requested plugins or pipelines.
    """

    def __init__(self, runnables: Sequence[InvalidRunnable]):
        self.runnables = runnables
