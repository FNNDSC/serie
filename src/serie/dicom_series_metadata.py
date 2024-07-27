import enum
from typing import TypedDict


class DicomSeriesMetadataName(enum.Enum):
    """
    DICOM tag or metadata of DICOM file for DICOM files stored in *CUBE*'s database.
    """

    PatientID = "PatientID"
    PatientName = "PatientName"
    PatientBirthDate = "PatientBirthDate"
    PatientSex = "PatientSex"
    StudyDate = "StudyDate"
    AccessionNumber = "AccessionNumber"
    Modality = "Modality"
    ProtocolName = "ProtocolName"
    StudyInstanceUID = "StudyInstanceUID"
    SeriesInstanceUID = "SeriesInstanceUID"
    SeriesDescription = "SeriesDescription"
    pacs_identifier = "pacs_identifier"
    series_dir = "series_dir"


DicomSeriesMetadata = TypedDict(
    "DicomSeriesMetadata",
    {name.value: None | bool | int | float | str for name in DicomSeriesMetadataName},
)
"""
A :class:`dict` with the keys of :class:`DicomSeriesMetadataName`.
"""
