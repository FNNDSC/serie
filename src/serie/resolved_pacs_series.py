import asyncio
from typing import Optional

from pydantic import BaseModel

from aiochris_oag import PACSSeries, FileBrowserFolder, FilebrowserApi, ApiClient, PacsApi
from serie.dicom_series_metadata import DicomSeriesMetadata
from serie.models import RawPacsSeries


class ResolvedPacsSeries(BaseModel):
    series: PACSSeries
    folder: FileBrowserFolder

    def to_dicom_metadata(self) -> DicomSeriesMetadata:
        return DicomSeriesMetadata(
            PatientID=self.series.patient_id,
            PatientName=self.series.patient_name,
            PatientBirthDate=self.series.patient_birth_date,
            PatientSex=self.series.patient_sex,
            StudyDate=self.series.study_date,
            AccessionNumber=self.series.accession_number,
            Modality=self.series.modality,
            ProtocolName=self.series.protocol_name,
            StudyInstanceUID=self.series.study_instance_uid,
            StudyDescription=self.series.study_description,
            SeriesInstanceUID=self.series.series_instance_uid,
            SeriesDescription=self.series.series_description,
            pacs_identifier=self.series.pacs_identifier,
            series_dir=self.folder.path,
        )


async def resolve_series(
    api_client: ApiClient, data: RawPacsSeries
) -> Optional[ResolvedPacsSeries]:
    pacs_api = PacsApi(api_client)
    folder_api = FilebrowserApi(api_client)
    series, folder = await asyncio.gather(
        pacs_api.pacs_series_retrieve(data.id),
        folder_api.filebrowser_retrieve(data.folder_id),
    )
    return ResolvedPacsSeries(series=series, folder=folder)
