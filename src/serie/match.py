import re
from collections.abc import Sequence

from serie.dicom_series_metadata import DicomSeriesMetadata
from serie.models import DicomSeriesMatcher
from serie.series_file_pair import DicomSeriesFilePair


def is_match(
    series: DicomSeriesFilePair, conditions: Sequence[DicomSeriesMatcher]
) -> bool:
    """
    :return: True if the series matches the conditions
    """
    series_dict = series.to_dict()
    return all(_matches(cond, series_dict) for cond in conditions)


def _matches(condition: DicomSeriesMatcher, series_dict: DicomSeriesMetadata) -> bool:
    if condition.tag.value not in series_dict:
        return False
    value = series_dict[condition.tag.value]
    flag = re.IGNORECASE if condition.case_sensitive else re.NOFLAG
    return condition.regex.fullmatch(value) is not None
