import asyncio
import dataclasses
from collections.abc import Iterable, Sequence

from aiochris.models import Plugin, Feed, PACSFile, PluginInstance
from aiochris.types import ChrisURL

from serie.clients import get_plugin, get_client
from serie.dicom_series_metadata import DicomSeriesMetadataName
from serie.models import OxidicomCustomMetadata, ChrisRunnableRequest


@dataclasses.dataclass(frozen=True)
class ClientActions:
    """
    :class:`ClientActions` provides a set of related helper functions which make authorized requests to the CUBE API.
    """

    auth: str | None
    url: ChrisURL

    async def create_analysis(
        self,
        oxm_file: OxidicomCustomMetadata,
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
        dircopy_inst = await pl_dircopy.create_instance(dir=oxm_file.series_dir)
        root_inst = await pl_unstack_folders.create_instance(previous=dircopy_inst)
        branches = (
            plugin.create_instance(previous=root_inst, **req.params)
            for plugin, req in zip(plugins, runnables_request)
        )
        set_feed_name = self._set_feed_name(oxm_file, dircopy_inst, feed_name_template)
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

    async def _set_feed_name(
        self, oxm_file: OxidicomCustomMetadata, plinst: PluginInstance, template: str
    ) -> Feed:
        """
        Set the name of the plugin instance's feed using the given template and the related DICOM series.
        """
        feed, dicom = await asyncio.gather(
            plinst.get_feed(), self._get_first_dicom_of(oxm_file)
        )
        name = template.format(**_feed_name_template_variables(oxm_file, dicom))
        return await feed.set(name=name)

    async def _get_first_dicom_of(self, oxm_file: OxidicomCustomMetadata) -> PACSFile:
        """
        Get an arbitrary DICOM file belonging to the series represented by ``oxm_file``.
        """
        chris = await get_client(self.url, self.auth)
        dicom_file = await chris.search_pacsfiles(
            pacs_identifier=oxm_file.pacs_identifier,
            PatientID=oxm_file.patient_id,
            StudyInstanceUID=oxm_file.study_instance_uid,
            SeriesInstanceUID=oxm_file.series_instance_uid,
        ).first()
        if dicom_file is None:
            raise ValueError(
                "DICOM series not found. It is likely the given oxidicom custom file is invalid.",
                oxm_file,
            )
        return dicom_file


def _feed_name_template_variables(oxm_file: OxidicomCustomMetadata, dicom: PACSFile):
    """
    Create a dict of values which can be used in a feed name template.
    """
    values = {}
    for name in DicomSeriesMetadataName:
        values[name.value] = getattr(dicom, name, None) or getattr(oxm_file, name)
    return values
