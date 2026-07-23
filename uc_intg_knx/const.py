"""Constants and shared helpers for the KNX integration."""

DEFAULT_KNX_PORT = 3671

STATE_ON = "ON"
STATE_UNAVAILABLE = "UNAVAILABLE"

DIM_STEP = 26  # ~10% of the 0-255 KNX brightness range


def slugify(value: str) -> str:
    """Return an uppercase token safe for use inside a Remote command string."""
    out = []
    for ch in (value or "").strip().upper():
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "_", "."):
            out.append("_")
    slug = "".join(out).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "FUNC"
