import pytest

from metastrip.core.models import Risk
from metastrip.core.risk import score


@pytest.mark.parametrize(
    ("group", "name", "expected"),
    [
        ("GPS", "GPSLatitude", Risk.HIGH),
        ("GPS", "GPSVersionID", Risk.LOW),
        ("Exif", "BodySerialNumber", Risk.HIGH),
        ("Image", "Artist", Risk.HIGH),
        ("XMP", "Packet", Risk.HIGH),
        ("IPTC", "Photoshop Block", Risk.HIGH),
        ("Exif", "DateTimeOriginal", Risk.MEDIUM),
        ("Image", "Make", Risk.MEDIUM),
        ("PNG Text", "Software", Risk.MEDIUM),
        ("Thumbnail", "Embedded Image", Risk.MEDIUM),
        ("Comment", "JPEG Comment", Risk.MEDIUM),
        ("Exif", "ISOSpeedRatings", Risk.LOW),
        ("Image", "Orientation", Risk.LOW),
    ],
)
def test_score(group, name, expected):
    assert score(group, name) == expected


def test_risk_parse_and_label():
    assert Risk.parse("high") is Risk.HIGH
    assert Risk.HIGH.label == "High"
    with pytest.raises(ValueError):
        Risk.parse("extreme")
