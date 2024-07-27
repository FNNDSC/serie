import dataclasses

import aiochris.models

from serie.dicom_series_metadata import DicomSeriesMetadata, DicomSeriesMetadataName
from serie.models import OxidicomCustomMetadata


@dataclasses.dataclass(frozen=True)
class DicomSeriesFilePair:
    """
    A product type which can provide all the fields listed in :class:`DicomSeriesMetadataName`.
    """

    ocm: OxidicomCustomMetadata
    pacs_file: aiochris.models.PACSFile

    @property
    def series_dir(self) -> str:
        return self.ocm.series_dir

    def to_dict(self) -> DicomSeriesMetadata:
        """
        Create a dict with all the keys from the variants of :class:`DicomSeriesMetadataName`.
        """
        values = {}
        for name in DicomSeriesMetadataName:
            values[name.value] = getattr(self.pacs_file, name.value, None) or getattr(
                self.ocm, name.value
            )
        return values
