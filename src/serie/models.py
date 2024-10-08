import re
from collections.abc import Sequence
from typing import Literal, Optional, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    NonNegativeInt,
    NonNegativeFloat,
    PastDatetime,
    Field,
    HttpUrl
)

from aiochris_oag import PatientSexEnum
from serie.dicom_series_metadata import DicomSeriesMetadataName


class RawPacsSeries(BaseModel):
    """
    A row from the `pacsfiles_pacsseries` table.
    """

    model_config = ConfigDict(frozen=True)

    id: NonNegativeInt
    creation_date: PastDatetime = Field()
    patient_id: str = Field(alias="PatientID")
    patient_name: str = Field(alias="PatientName")
    patient_birth_date: Optional[PastDatetime] = Field(alias="PatientBirthDate")
    patient_age: Optional[NonNegativeFloat] = Field(alias="PatientAge")
    patient_sex: Optional[PatientSexEnum] = Field(alias="PatientSex")
    study_date: PastDatetime = Field(alias="StudyDate")
    accession_number: str = Field(alias="AccessionNumber")
    modality: str = Field(alias="Modality")
    protocol_name: str = Field(alias="ProtocolName")
    study_instance_uid: str = Field(alias="StudyInstanceUID")
    study_description: str = Field(alias="StudyDescription")
    series_instance_uid: str = Field(alias="SeriesInstanceUID")
    series_description: str = Field(alias="SeriesDescription")
    folder_id: NonNegativeInt
    pacs_id: NonNegativeInt


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

    data: RawPacsSeries = Field(title="The inserted DICOM file metadata")
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


class CreatedFeed(BaseModel):
    feed: HttpUrl = Field(title="URL of created field", examples=["https://example.com/api/v1/100/"])



class InvalidRunnable(BaseModel):
    """
    Invalid requested plugins or pipelines.
    """

    runnable: ChrisRunnableRequest = Field(title="The requested plugin or pipeline.")
    reason: str = Field(
        title="Reason why the runnable is invalid.",
        examples=[
            "not found",
            "`something` is not a valid parameter",
            "`stuff` is not a valid argument for parameter `something`",
        ],
    )


class InvalidRunnableList(BaseModel):
    """
    List of invalid requested plugins or pipelines.
    """
    errors: list[InvalidRunnable] = Field(
        title="List of invalid requested plugins or pipelines."
    )


class BadRequestResponse(BaseModel):
    error: str = Field(title="Error message", examples=['error message'])
    data: Any = Field(examples=[{'id': 5}])
