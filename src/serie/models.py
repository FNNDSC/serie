import enum
from collections.abc import Sequence
from typing import Literal, Optional, Self, ClassVar
import re

from pydantic import (
    BaseModel,
    ConfigDict,
    NonNegativeInt,
    NonNegativeFloat,
    PastDatetime,
    Field,
)

from serie.dicom_series_metadata import DicomSeriesMetadataName


class PacsFile(BaseModel):
    """
    A row from the `pacsfiles_pacsfile` table.
    """

    model_config = ConfigDict(frozen=True)

    id: NonNegativeInt
    protocol_name: str = Field(alias="ProtocolName")
    patient_name: str = Field(alias="PatientName")
    patient_sex: Optional[str] = Field(alias="PatientSex")
    accession_number: str = Field(alias="AccessionNumber")
    patient_age: Optional[NonNegativeFloat] = Field(alias="PatientAge")
    creation_date: PastDatetime = Field()
    pacs_id: NonNegativeInt
    patient_birth_date: Optional[PastDatetime] = Field(alias="PatientBirthDate")
    patient_id: str = Field(alias="PatientID")
    study_date: PastDatetime = Field(alias="StudyDate")
    modality: str = Field(alias="Modality")
    fname: str
    study_description: str = Field(alias="StudyDescription")
    series_description: str = Field(alias="SeriesDescription")
    series_instance_uid: str = Field(alias="SeriesInstanceUID")
    study_instance_uid: str = Field(alias="StudyInstanceUID")


@enum.unique
class OxidicomCustomMetadataField(enum.StrEnum):
    """
    Field name of oxidicom custom metadata.
    """

    number_of_series_related_instances = "NumberOfSeriesRelatedInstances"
    attempted_push_count = "OxidicomAttemptedPushCount"

    @classmethod
    def from_str(cls, s: str) -> Optional[Self]:
        """
        :return: a :class:`OxidicomCustomMetadataField` for the given value.
        """
        return next(filter(lambda x: x.value == s, cls), None)


class OxidicomCustomMetadata(BaseModel):
    """
    A special row in the `pacsfiles_pacsfile` table described here:

    https://github.com/FNNDSC/oxidicom/blob/v2.0.0/CUSTOM_SPEC.md
    """

    model_config = ConfigDict(frozen=True)
    name: OxidicomCustomMetadataField
    value: int
    series_instance_uid: str
    study_instance_uid: str
    pacs_identifier: str
    patient_id: str
    creation_date: PastDatetime
    association_ulid: str
    series_dir: str
    """Folder path where the series' DICOM files can be found."""

    _FNAME_RE: ClassVar[re.Pattern] = re.compile(
        r"SERVICES/PACS/org.fnndsc.oxidicom/SERVICES/PACS/"
        r"(?P<pacs_identifier>\w+)/(?P<series_dir_rel>.+?/.+?/.+?)/(?P<association_ulid>\w+?)/\w+=\d+"
    )

    @classmethod
    def from_pacsfile(cls, pacs_file: PacsFile) -> Optional[Self]:
        """
        Attempt to convert from :class:`PacsFile`.
        """
        name = OxidicomCustomMetadataField.from_str(pacs_file.protocol_name)
        if name is None:
            return None

        pacs_identifier, series_dir, association_ulid = cls._parse_ocm_fname(
            pacs_file.fname
        )

        return cls(
            name=name,
            value=pacs_file.series_description,
            series_instance_uid=pacs_file.series_instance_uid,
            study_instance_uid=pacs_file.study_instance_uid,
            pacs_identifier=pacs_identifier,
            patient_id=pacs_file.patient_id,
            creation_date=pacs_file.creation_date,
            association_ulid=association_ulid,
            series_dir=series_dir,
        )

    @classmethod
    def _parse_ocm_fname(cls, fname: str) -> tuple[str, str, str]:
        """
        Parse a fname of an "oxidicom custom metadata" file.

        :return: pacs_identifier and association_ulid
        """
        match = cls._FNAME_RE.fullmatch(fname)
        if not match:
            raise ValueError('Invalid fname of a "oxidicom custom metadata" file.')
        pacs_identifier = match.group("pacs_identifier")
        series_dir = f'SERVICES/PACS/{pacs_identifier}/{match.group("series_dir_rel")}'
        return pacs_identifier, series_dir, match.group("association_ulid")


class ChrisRunnableRequest(BaseModel):
    """
    Identifying details of a _ChRIS_ plugin.

    (Only plugins supported for now. Support for pipelines is a potential future feature.)
    """

    model_config = ConfigDict(frozen=True)

    runnable_type: Literal["plugin"] = Field(
        alias="type", title="Type of runnable", default="plugin"
    )
    name: str = Field(title="Plugin name", examples=["pl-dylld", "pl-dcm2niix"])
    version: Optional[str] = Field(
        title="Plugin version", examples=["1.2.3"], default=None
    )
    params: dict[str, int | float | bool | str] = Field(
        title="Plugin parameters", default_factory=dict
    )


class DicomSeriesMatcher(BaseModel):
    """
    A regular expression to be applied to a DICOM series metadata field.
    """

    tag: DicomSeriesMetadataName = Field(title="Tag of field to match")
    regex: re.Pattern = Field(
        title="Regular expression matching the value", examples=[r".*(Chest CT).*"]
    )
    case_sensitive: bool = Field(
        default=False, title="Perform case-sensitive regular expression matching."
    )


class DicomSeriesPayload(BaseModel):
    """
    The payload sent from Hasura each time a row is inserted into the ``pacsfiles_pacsfile`` table.
    """

    model_config = ConfigDict(frozen=True)

    hasura_id: str = Field(title="ID of event from Hasura")

    data: PacsFile = Field(title="The inserted DICOM file metadata")
    match: Sequence[DicomSeriesMatcher] = Field(
        title="Which DICOM series to include. Conditions are joined by AND."
    )
    jobs: Sequence[ChrisRunnableRequest] = Field(
        title="Plugins or pipelines to run on the series data"
    )
    feed_name_template: str = Field(
        title="Template for how to create the feed name",
        description=(
            "Uses the [Python string formatting](https://docs.python.org/3/library/string.html#formatstrings) syntax. "
            f"Available variables include: {','.join(n.value for n in DicomSeriesMetadataName)}"
            "\nKeep in mind that there is a 200-character limit on feed names."
        ),
        examples=[
            r'SERIE analysis: MRN="{PatientID}" description="{SeriesDescription}"'
        ],
    )
