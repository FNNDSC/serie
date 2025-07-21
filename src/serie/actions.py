import asyncio
import dataclasses
import logging
import re
from collections.abc import Sequence
from pydantic import TypeAdapter

from aiochris_oag import (
    Plugin,
    PluginInstance,
    PluginsApi,
    PluginInstanceRequest,
    ApiClient,
    DefaultApi,
    FeedRequest,
    Pipeline,
    PipelinesApi,
    Workflow,
    WorkflowRequest
)
from serie.clients import Clients
from serie.models import (
    ChrisRunnableRequest,
    PluginRunnable,
    PipelineRunnable,
    RawPacsSeries,
    InvalidRunnable,
)
from serie.resolved_pacs_series import ResolvedPacsSeries, resolve_series

logger = logging.getLogger(__name__)

_HARDCODED_RUNNABLES = [
    PluginRunnable(runnable_type="plugin", name="pl-dircopy"),
    PluginRunnable(runnable_type="plugin", name="pl-unstack-folders"),
]
"""
The runnables which are needed to create feeds.
"""

_NOTE_ID_RE = re.compile(r"/api/v1/note(\d+)/")

class FoundRunnableBase:
    def get_name(self) -> str:
        raise NotImplementedError


@dataclasses.dataclass(frozen=True)
class FoundPlugin(FoundRunnableBase):
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
class FoundPipeline(FoundRunnableBase):
    """
    A pipeline which was found in CUBE, and the runnable request which requested it.
    """

    pipeline_api: PipelinesApi
    pipeline: Pipeline
    runnable: ChrisRunnableRequest

    async def create_instance(self, previous: PluginInstance) -> Workflow:
        """
        Run the plugin with the runnable's parameters on the data from the ``previous`` parameter.
        """
        # WARNING:
        #  - unrecognized parameters are silently ignored.
        #  - unhandled error if parameter value is wrong type.

        return await self.pipeline_api.pipelines_workflows_create(
            self.pipeline.id,
            WorkflowRequest(
                previous_plugin_inst_id=previous.id
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
        pl_dircopy, pl_unstack_folders, runnables = await self._get_plugins_or_pipelines(
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
        branches = (runnable.create_instance(root_inst) for runnable in runnables)
        feed_name = _expand_variables(feed_name_template, series)
        set_feed_name = self._set_feed_name(dircopy_inst, feed_name)
        await asyncio.gather(set_feed_name, *branches)
        return dircopy_inst.feed

    async def _get_plugins_or_pipelines(
        self, runnables_request: Sequence[ChrisRunnableRequest]
    ) -> tuple[Plugin, Plugin, Sequence[FoundPlugin | FoundPipeline]]:
        """
        Get the plugins pl-dircopy, pl-unstack-folders, and any other plugins/pipelines requested.

        :raises InvalidRunnablesError: if any plugins/pipelines cannot be found in CUBE.
        """
        if any(req.runnable_type not in ("plugin", "pipeline") for req in runnables_request):
            raise NotImplementedError("Only plugins and pipelines are supported")

        needed_runnables = _HARDCODED_RUNNABLES + list(runnables_request)

        p_requests = (
            self.clients.get_plugin(self.host, self.auth, runnable.name, runnable.version)
            if runnable.runnable_type == "plugin"
            else self.clients.get_pipeline(self.host, self.auth, runnable.name)
            for runnable in needed_runnables
        )

        plugins_or_pipelines = await asyncio.gather(*p_requests)

        # Identify missing
        missing_plugins_or_pipelines = [
            InvalidRunnable(runnable=runnable, reason="plugin/pipeline not found")
            for runnable, result in zip(needed_runnables, plugins_or_pipelines)
            if result is None
        ]
        if missing_plugins_or_pipelines:
            raise InvalidRunnablesError(missing_plugins_or_pipelines)

        # First two are always pl-dircopy and pl-unstack-folders
        pl_dircopy, pl_unstack_folders, *others = plugins_or_pipelines
        _, _, *other_runnables = needed_runnables

        found_items = []
        for plugin_or_pipeline, runnable in zip(others, other_runnables):
            if runnable.runnable_type == "plugin":
                api = self._get_plugins_api()
                found_items.append(FoundPlugin(api, plugin_or_pipeline, runnable))
            else:
                api = self._get_pipelines_api()
                found_items.append(FoundPipeline(api, plugin_or_pipeline, runnable))

        return pl_dircopy, pl_unstack_folders, found_items

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

    def _get_pipelines_api(self) -> PipelinesApi:
        return PipelinesApi(self._get_client())

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
