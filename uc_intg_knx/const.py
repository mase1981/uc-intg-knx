"""Constants and shared helpers for the KNX Hub integration."""

DEFAULT_KNX_PORT = 3671
DEFAULT_MULTICAST_GROUP = "224.0.23.12"

CONNECTION_AUTOMATIC = "automatic"
CONNECTION_TUNNELING = "tunneling"
CONNECTION_TUNNELING_TCP = "tunneling_tcp"
CONNECTION_ROUTING = "routing"

CONNECTION_TYPES = [
    CONNECTION_AUTOMATIC,
    CONNECTION_TUNNELING,
    CONNECTION_TUNNELING_TCP,
    CONNECTION_ROUTING,
]

TYPE_SWITCH = "switch"
TYPE_LIGHT = "light"
TYPE_COVER = "cover"
TYPE_CLIMATE = "climate"
TYPE_SENSOR = "sensor"
TYPE_BINARY_SENSOR = "binary_sensor"
TYPE_BUTTON = "button"

ENTITY_TYPES = [
    TYPE_SWITCH,
    TYPE_LIGHT,
    TYPE_COVER,
    TYPE_CLIMATE,
    TYPE_SENSOR,
    TYPE_BINARY_SENSOR,
    TYPE_BUTTON,
]

DEFAULT_MIN_KELVIN = 2700
DEFAULT_MAX_KELVIN = 6500

STATE_ON = "ON"
STATE_OFF = "OFF"
STATE_UNAVAILABLE = "UNAVAILABLE"


def slugify(value: str) -> str:
    """Return a filesystem/entity-id safe slug for a free-text value."""
    out = []
    for ch in value.strip().lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "_", "."):
            out.append("_")
    slug = "".join(out).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "device"
