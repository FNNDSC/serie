import asyncio
import asyncio
import dataclasses
from collections.abc import Iterable, Sequence
from typing import Optional

import aiochris.models
from aiochris.models import Plugin, Feed, PluginInstance
from aiochris.types import ChrisURL

from serie.clients import get_plugin, get_client
from serie.models import (
    OxidicomCustomMetadata,
    ChrisRunnableRequest,
    PacsFile,
)
from serie.series_file_pair import DicomSeriesFilePair


@dataclasses.dataclass(frozen=True)
class ClientActions:
    """
    :class:`ClientActions` provides a set of related helper functions which make authorized requests to the CUBE API.
    """

    auth: str | None
    url: ChrisURL

    async def resolve_series(self, data: PacsFile) -> Optional[DicomSeriesFilePair]:
        """
        Check whether the given PACSFile is a "OxidicomAttemptedPushCount=*" file
        (which signifies that the reception of a DICOM series is complete). If so,
        get one of the DICOM instances of the series from *CUBE*.
        """
        if (ocm := OxidicomCustomMetadata.from_pacsfile(data)) is None:
            return None
        if (pacs_file := await self._get_first_dicom_of(ocm)) is None:
            return None
        return DicomSeriesFilePair(ocm, pacs_file)

    async def create_analysis(
        self,
        series: DicomSeriesFilePair,
        runnables_request: Iterable[ChrisRunnableRequest],
        feed_name_template: str,
    ) -> Feed:
        """
        Create a feed containing ``data_dir`` and run all of ``runnable_request``.
        Set the name of the created feed using ``feed_name_template``.
        """
        if any(req.runnable_type != "plugin" for req in runnables_request):
            raise NotImplementedError("Only plugins are supported for now")

        pl_dircopy, pl_unstack_folders, plugins = await self._get_plugins(
            runnables_request
        )
        dircopy_inst = await pl_dircopy.create_instance(dir=series.series_dir)
        root_inst = await pl_unstack_folders.create_instance(previous=dircopy_inst)
        branches = (
            plugin.create_instance(previous=root_inst, **req.params)
            for plugin, req in zip(plugins, runnables_request)
        )
        feed_name = _expand_variables(feed_name_template, series)
        set_feed_name = self._set_feed_name(dircopy_inst, feed_name)
        feed, *_ = await asyncio.gather(set_feed_name, *branches)
        return feed

    async def _get_plugins(
        self, runnables_request: Iterable[ChrisRunnableRequest]
    ) -> tuple[Plugin, Plugin, Sequence[Plugin]]:
        """
        Get the plugins pl-dircopy, pl-unstack-folders, and any other plugins requested.
        """
        plugin_specs = (
            ("pl-dircopy", None),
            ("pl-unstack-folders", None),
            *((r.name, r.version) for r in runnables_request),
        )
        plugin_requests = (
            get_plugin(self.url, self.auth, name, version)
            for name, version in plugin_specs
        )
        pl_dircopy, pl_unstack_folders, *others = await asyncio.gather(*plugin_requests)  # noqa
        return pl_dircopy, pl_unstack_folders, others

    async def _get_first_dicom_of(
        self, oxm_file: OxidicomCustomMetadata
    ) -> Optional[aiochris.models.PACSFile]:
        """
        Get an arbitrary DICOM file belonging to the series represented by ``oxm_file``.
        """
        chris = await get_client(self.url, self.auth)
        return await chris.search_pacsfiles(
            pacs_identifier=oxm_file.pacs_identifier,
            PatientID=oxm_file.patient_id,
            StudyInstanceUID=oxm_file.study_instance_uid,
            SeriesInstanceUID=oxm_file.series_instance_uid,
        ).first()

    @staticmethod
    async def _set_feed_name(dircopy_inst: PluginInstance, name: str) -> Feed:
        """
        Get the feed of the given plugin instance, and set its feed name.
        """
        feed = await dircopy_inst.get_feed()
        await feed.set(name=name)
        return feed


def _expand_variables(template: str, series: DicomSeriesFilePair) -> str:
    """
    Expand the value of variables in ``template`` using field values from ``series``.
    """
    return template.format(**series.to_dict())
