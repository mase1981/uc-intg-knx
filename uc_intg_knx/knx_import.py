"""Parse an ETS 'Group Addresses' export (CSV/TSV) and classify each group
address into a Unfolded Circle entity kind.

A KNX/IP gateway cannot advertise its configured functions, so the user pastes
the plain-text group-address export from ETS. Each row gives a name, a group
address and (usually) a datapoint type (DPT). We derive the entity kind from the
DPT main number, falling back to name keywords when no DPT is present.
"""

import csv
import io
import re
from dataclasses import dataclass, field
from typing import Any

# Internal entity kinds
KIND_SENSOR = "sensor"
KIND_BINARY_SENSOR = "binary_sensor"
KIND_SWITCH = "switch"
KIND_DIM = "dim"
KIND_COVER = "cover"
KIND_SCENE = "scene"

_ADDRESS_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{1,3}$")
_ADDRESS_2LVL_RE = re.compile(r"^\d{1,2}/\d{1,4}$")
# DPT formats seen in ETS exports: "9.001", "DPST-9-1", "DPT-9"
_DPT_DOT_RE = re.compile(r"^(\d{1,3})\.(\d{1,3})$")
_DPT_ETS_RE = re.compile(r"^DPST?-(\d{1,3})(?:-(\d{1,3}))?$", re.IGNORECASE)

_STATUS_KEYWORDS = (
    "status", "state", "fb", "feedback", "rueckmeld", "rückmeld",
    "ist", "actual", "current", " rm", "rm ", "meldung",
)
_COVER_KEYWORDS = (
    "blind", "cover", "shutter", "roller", "rollo", "jalousie",
    "shade", "awning", "up/down", "updown", "up-down",
)
_DIM_KEYWORDS = ("dim", "bright", "level", "value", "volume", "helligkeit")
_SCENE_KEYWORDS = ("scene", "szene", "mood")
_TEMP_KEYWORDS = ("temp", "humid", "lux", "illumi", "co2", "power", "energy",
                  "voltage", "current", "wind", "pressure")


@dataclass
class KnxItem:
    """A single classified KNX group address."""

    name: str
    address: str
    dpt: str = ""
    kind: str = KIND_SWITCH
    value_type: str = ""
    main: int | None = None
    sub: int | None = None
    index: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


def _parse_dpt(token: str) -> tuple[int | None, int | None]:
    token = (token or "").strip()
    m = _DPT_DOT_RE.match(token)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = _DPT_ETS_RE.match(token)
    if m:
        return int(m.group(1)), int(m.group(2)) if m.group(2) else None
    return None, None


def _dpt_value_type(main: int | None, sub: int | None) -> str:
    """Return an xknx-parsable value_type string for a measurement DPT."""
    if main is None:
        return ""
    if sub is not None:
        return f"{main}.{sub:03d}"
    return f"DPT-{main}"


def _is_status(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in _STATUS_KEYWORDS)


def _looks_like_address(token: str) -> bool:
    token = token.strip()
    return bool(_ADDRESS_RE.match(token) or _ADDRESS_2LVL_RE.match(token))


def _looks_like_dpt(token: str) -> bool:
    main, _sub = _parse_dpt(token)
    return main is not None


def _detect_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:20])
    counts = {d: sample.count(d) for d in (";", "\t", ",")}
    delimiter = max(counts, key=counts.get)
    return delimiter if counts[delimiter] > 0 else ";"


def _classify(name: str, main: int | None, sub: int | None) -> str:
    n = name.lower()
    if main is None:
        # No DPT — guess purely from the name.
        if any(k in n for k in _SCENE_KEYWORDS):
            return KIND_SCENE
        if any(k in n for k in _COVER_KEYWORDS):
            return KIND_COVER
        if any(k in n for k in _TEMP_KEYWORDS) or _is_status(n):
            return KIND_SENSOR
        return KIND_SWITCH

    if main in (7, 8, 9, 12, 13, 14, 6, 16, 10, 11, 29):
        return KIND_SENSOR
    if main in (17, 18):
        return KIND_SCENE
    if main == 5:
        if any(k in n for k in _DIM_KEYWORDS) and not _is_status(n):
            return KIND_DIM
        return KIND_SENSOR
    if main == 3:
        return KIND_COVER
    if main == 2:
        return KIND_SWITCH
    if main == 1:
        if sub in (7, 8, 9) or any(k in n for k in _COVER_KEYWORDS):
            return KIND_COVER
        if _is_status(n):
            return KIND_BINARY_SENSOR
        return KIND_SWITCH
    if main == 232:
        return KIND_DIM
    # Unknown main → treat measurable-looking names as sensors, else a switch.
    if any(k in n for k in _TEMP_KEYWORDS) or _is_status(n):
        return KIND_SENSOR
    return KIND_SWITCH


def parse_group_export(text: str) -> list[KnxItem]:
    """Parse pasted ETS group-address export text into classified items."""
    text = (text or "").strip()
    if not text:
        return []

    delimiter = _detect_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)

    items: list[KnxItem] = []
    seen: set[str] = set()
    index = 0
    for row in reader:
        fields = [c.strip().strip('"') for c in row if c is not None]
        if not fields:
            continue

        address = next((f for f in fields if _looks_like_address(f)), None)
        if not address or address in seen:
            continue
        # Only accept 3-level addresses for real group objects.
        if not _ADDRESS_RE.match(address):
            continue

        dpt = next((f for f in fields if _looks_like_dpt(f)), "")

        # Name = the best descriptive, non-address, non-dpt, non-numeric field.
        name = ""
        for f in fields:
            if not f or f == address or f == dpt:
                continue
            if _looks_like_address(f) or _looks_like_dpt(f):
                continue
            if f.isdigit():
                continue
            if len(f) > len(name):
                name = f
        if not name:
            name = address

        main, sub = _parse_dpt(dpt)
        kind = _classify(name, main, sub)
        value_type = _dpt_value_type(main, sub) if kind in (
            KIND_SENSOR,
        ) else ""

        seen.add(address)
        items.append(
            KnxItem(
                name=name,
                address=address,
                dpt=dpt,
                kind=kind,
                value_type=value_type,
                main=main,
                sub=sub,
                index=index,
            )
        )
        index += 1

    return items


def items_to_dicts(items: list[KnxItem]) -> list[dict[str, Any]]:
    """Serialize classified items for storage in the device config."""
    return [
        {
            "name": it.name,
            "address": it.address,
            "dpt": it.dpt,
            "kind": it.kind,
            "value_type": it.value_type,
            "main": it.main,
            "sub": it.sub,
            "index": it.index,
        }
        for it in items
    ]


def summarize(items: list[KnxItem]) -> dict[str, int]:
    """Return a count per entity kind (for the setup confirmation message)."""
    counts: dict[str, int] = {}
    for it in items:
        counts[it.kind] = counts.get(it.kind, 0) + 1
    return counts
