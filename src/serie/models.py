import enum
from typing import Literal, Optional, Self, ClassVar
import re

from pydantic import BaseModel, ConfigDict, NonNegativeInt, PastDatetime, Field


class PacsFile(BaseModel):
    """
    A row from the ``pacsfiles_pacsfile`` table.
    """

    model_config = ConfigDict(frozen=True)

    id: NonNegativeInt
    protocol_name: str = Field(alias="ProtocolName")
    patient_name: str = Field(alias="PatientName")
    patient_sex: Optional[str] = Field(alias="PatientSex")
    accession_number: str = Field(alias="AccessionNumber")
    patient_age: Optional[NonNegativeInt] = Field(alias="PatientAge")
    creation_date: PastDatetime
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

    _FNAME_RE: ClassVar[re.Pattern] = re.compile(
        r"SERVICES/PACS/org.fnndsc.oxidicom/SERVICES/PACS/"
        r"(?P<pacs_identifier>\w+)/.+?/.+?/.+?/(?P<association_ulid>\w+?)/\w+=\d+"
    )

    @classmethod
    def from_pacsfile(cls, pacs_file: PacsFile) -> Optional[Self]:
        """
        Attempt to convert from :class:`PacsFile`.
        """
        name = OxidicomCustomMetadataField.from_str(pacs_file.protocol_name)
        if name is None:
            return None

        pacs_identifier, association_ulid = cls._parse_ocm_fname(pacs_file.fname)

        return cls(
            name=name,
            value=pacs_file.series_description,
            series_instance_uid=pacs_file.series_instance_uid,
            study_instance_uid=pacs_file.study_instance_uid,
            pacs_identifier=pacs_identifier,
            patient_id=pacs_file.patient_id,
            creation_date=pacs_file.creation_date,
            association_ulid=association_ulid
        )

    @classmethod
    def _parse_ocm_fname(cls, fname: str) -> tuple[str, str]:
        """
        Parse a fname of an "oxidicom custom metadata" file.

        :return: pacs_identifier and association_ulid
        """
        match = cls._FNAME_RE.fullmatch(fname)
        if not match:
            raise ValueError('Invalid fname of a "oxidicom custom metadata" file.')
        return match.group("pacs_identifier"), match.group("association_ulid")


class ChrisRunnable(BaseModel):
    """
    A _ChRIS_ plugin.

    (In the near future, ``ChrisRunnable`` can be a plugin or pipeline. Right now,
    only plugins are supported.)
    """

    model_config = ConfigDict(frozen=True)

    runnable_type: Literal["plugin"] = Field(alias="type")
    name: str
    version: Optional[str]


class DicomSeriesPayload(BaseModel):
    """
    The payload sent from Hasura each time a row is inserted into the ``pacsfiles_pacsfile`` table.
    """

    model_config = ConfigDict(frozen=True)

    data: PacsFile
    """The inserted data."""
    jobs: frozenset[ChrisRunnable]
    """Jobs to run on the series data."""
