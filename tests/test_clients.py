import serie.clients as clients
import pytest


@pytest.mark.parametrize(
    "auth, expected",
    [
        (
            "Basic cnVkb2xwaDp0aGVjaGlsZHJlbnNob3NwaXRhbA==",
            ("rudolph", "thechildrenshospital"),
        ),
        (
            "Token 21e16bfab4aae4c42ef185203f0b75ae437369cd",
            "21e16bfab4aae4c42ef185203f0b75ae437369cd",
        ),
    ],
)
def test_parse_auth(auth, expected):
    assert clients._parse_auth(auth) == expected
