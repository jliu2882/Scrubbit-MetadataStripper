"""Privacy risk scoring.

Rules are deliberately simple and transparent:

* HIGH   - can identify a person or place (GPS, serial numbers, owner names,
           XMP/IPTC blocks which routinely hold names and locations).
* MEDIUM - helps fingerprint you or reveals when/how a file was made
           (timestamps, camera model, software, free-text comments).
* LOW    - technical settings (exposure, ISO, color space, ...).
"""

from __future__ import annotations

from metastrip.core.models import Risk

_HIGH_GROUPS = {"GPS", "XMP", "IPTC"}
_LOW_GPS_TAGS = {"GPSVersionID", "GPSMapDatum"}

_HIGH_NAMES = {
    "bodyserialnumber",
    "lensserialnumber",
    "cameraownername",
    "cameraserialnumber",
    "serialnumber",
    "ownername",
    "imageuniqueid",
    "artist",
    "xpauthor",
    "author",
    "creator",
    "photographer",
}

_MEDIUM_NAMES = {
    "datetime",
    "datetimeoriginal",
    "datetimedigitized",
    "subsectime",
    "subsectimeoriginal",
    "subsectimedigitized",
    "offsettime",
    "offsettimeoriginal",
    "offsettimedigitized",
    "make",
    "model",
    "lensmake",
    "lensmodel",
    "software",
    "hostcomputer",
    "usercomment",
    "imagedescription",
    "makernote",
    "copyright",
    "documentname",
    "pagename",
    "xpcomment",
    "xptitle",
    "xpsubject",
    "xpkeywords",
    "title",
    "description",
    "comment",
    "source",
    "creation time",
    "disclaimer",
    "warning",
}

_MEDIUM_GROUPS = {"Thumbnail", "Comment", "Time"}


def score(group: str, name: str) -> Risk:
    """Return the privacy risk of a metadata item."""
    if group == "GPS":
        return Risk.LOW if name in _LOW_GPS_TAGS else Risk.HIGH
    if group in _HIGH_GROUPS:
        return Risk.HIGH
    lowered = name.lower()
    if lowered in _HIGH_NAMES:
        return Risk.HIGH
    if lowered in _MEDIUM_NAMES or group in _MEDIUM_GROUPS:
        return Risk.MEDIUM
    return Risk.LOW
