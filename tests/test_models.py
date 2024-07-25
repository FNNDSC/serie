import pytest

from serie.models import PacsFile, OxidicomCustomMetadata, OxidicomCustomMetadataField

from examples import read_example


def test_parse_ocm_fname():
    fname = (
        "SERVICES/PACS/org.fnndsc.oxidicom/SERVICES/PACS/EXPECTEDPACS/"
        "1449c1d-anonymized-20090701/MR-Brain_w_o_Contrast-98edede8b2-20130308/"
        "5-SAG_MPRAGE_220_FOV-a27cf06/01HZ7WP273YRHSH33TC3BNDJEB/OxidicomAttemptedPushCount=192"
    )
    pacs_identifier, association_ulid = OxidicomCustomMetadata._parse_ocm_fname(fname)
    assert pacs_identifier == "EXPECTEDPACS"
    assert association_ulid == "01HZ7WP273YRHSH33TC3BNDJEB"

    with pytest.raises(ValueError, match=r'Invalid fname of a "oxidicom custom metadata" file.'):
        OxidicomCustomMetadata._parse_ocm_fname(
            "SERVICES/PACS/MINICHRISORTHANC/1449c1d-anonymized-20090701/"
            "MR-Brain_w_o_Contrast-98edede8b2-20130308/00005-SAG_MPRAGE_220_FOV-a27cf06/"
            "0001-1.3.12.2.1107.5.2.19.45152.2013030808110258929186035.dcm"
        )


def test_pacsfiles_models():
    oxi_file = PacsFile.model_validate_json(read_example("oxidicom_attempted_push_count.json"))
    pac_file = PacsFile.model_validate_json(read_example("pacsfile6.json"))

    assert OxidicomCustomMetadata.from_pacsfile(pac_file) is None

    ocm_file = OxidicomCustomMetadata.from_pacsfile(oxi_file)
    assert ocm_file is not None
    assert ocm_file.series_instance_uid == oxi_file.series_instance_uid
    assert ocm_file.study_instance_uid == ocm_file.study_instance_uid
    assert ocm_file.name == OxidicomCustomMetadataField.attempted_push_count
