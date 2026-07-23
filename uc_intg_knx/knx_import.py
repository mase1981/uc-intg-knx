"""Import KNX entity definitions from one of three sources and normalize them
into a single typed-entity schema.

All three parsers return a list of dicts using the **Home Assistant KNX YAML key
names** (``address``, ``state_address``, ``brightness_address``,
``move_long_address``, ``temperature_address`` …) plus ``type``/``name``/``index``.
``device.py`` maps those keys onto xknx device parameters.

Sources:
- ``parse_yaml``   — HA-style KNX YAML (exact types + grouping).
- ``parse_csv``    — ETS 'Group Addresses' CSV export (flat, one entity per address, typed by DPT).
- ``parse_knxproj``— ETS project file via the xknxproject library (grouped by ETS Functions).
"""

import csv
import io
import re
from typing import Any

TYPE_SWITCH = "switch"
TYPE_LIGHT = "light"
TYPE_COVER = "cover"
TYPE_CLIMATE = "climate"
TYPE_SENSOR = "sensor"
TYPE_BINARY_SENSOR = "binary_sensor"
TYPE_SCENE = "scene"

ENTITY_TYPES = (
    TYPE_SWITCH, TYPE_LIGHT, TYPE_COVER, TYPE_CLIMATE,
    TYPE_SENSOR, TYPE_BINARY_SENSOR, TYPE_SCENE,
)

_ADDRESS_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{1,3}$")
_DPT_DOT_RE = re.compile(r"^(\d{1,3})\.(\d{1,3})$")
_DPT_ETS_RE = re.compile(r"^DPST?-(\d{1,3})(?:-(\d{1,3}))?$", re.IGNORECASE)
_TRAILING_NUM = re.compile(r"(\d{1,2})\s*$")

_STATUS_KW = ("status", "state", "fb", "feedback", "rueckmeld", "rückmeld",
              "ist", "actual", " rm", "rm ", "meldung")
_COVER_KW = ("blind", "cover", "shutter", "roller", "rollo", "jalousie", "shade", "awning")
_TEMP_KW = ("temp", "humid", "lux", "illumi", "co2", "power", "energy",
            "voltage", "current", "wind", "pressure", "brightness lux")


def _parse_dpt(token: str) -> tuple[int | None, int | None]:
    token = (token or "").strip()
    m = _DPT_DOT_RE.match(token)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = _DPT_ETS_RE.match(token)
    if m:
        return int(m.group(1)), int(m.group(2)) if m.group(2) else None
    return None, None


def _value_type(main: int | None, sub: int | None) -> str:
    if main is None:
        return ""
    return f"{main}.{sub:03d}" if sub is not None else f"DPT-{main}"


def _is_status(name: str) -> bool:
    n = (name or "").lower()
    return any(k in n for k in _STATUS_KW)


def _scene_number(name: str) -> int:
    m = _TRAILING_NUM.search(name or "")
    return max(1, min(64, int(m.group(1)))) if m else 1


class _Row:
    __slots__ = ("name", "address", "main", "sub")

    def __init__(self, name, address, main, sub):
        self.name = name
        self.address = address
        self.main = main
        self.sub = sub


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------
def _detect_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:20])
    counts = {d: sample.count(d) for d in (";", "\t", ",")}
    best = max(counts, key=counts.get)
    return best if counts[best] else ";"


def _csv_rows(text: str) -> list[_Row]:
    reader = csv.reader(io.StringIO(text), delimiter=_detect_delimiter(text))
    rows: list[_Row] = []
    seen: set[str] = set()
    for fields in reader:
        fields = [c.strip().strip('"') for c in fields if c is not None]
        if not fields:
            continue
        address = next((f for f in fields if _ADDRESS_RE.match(f)), None)
        if not address or address in seen:
            continue
        dpt = next((f for f in fields if _parse_dpt(f)[0] is not None), "")
        name = ""
        for f in fields:
            if f in (address, dpt) or _ADDRESS_RE.match(f) or _parse_dpt(f)[0] is not None or f.isdigit():
                continue
            if len(f) > len(name):
                name = f
        name = name or address
        main, sub = _parse_dpt(dpt)
        seen.add(address)
        rows.append(_Row(name, address, main, sub))
    return rows


def _entity_from_single(row: _Row) -> dict | None:
    """Classify one group address into a typed entity (flat CSV mode)."""
    name, addr, main, sub = row.name, row.address, row.main, row.sub
    n = name.lower()
    if main in (17, 18):
        return {"type": TYPE_SCENE, "name": name, "address": addr, "scene_number": _scene_number(name)}
    if main in (7, 8, 9, 12, 13, 14, 6, 16, 10, 11, 29):
        return {"type": TYPE_SENSOR, "name": name, "state_address": addr, "value_type": _value_type(main, sub)}
    if main == 5:
        if _is_status(n) or any(k in n for k in _TEMP_KW):
            return {"type": TYPE_SENSOR, "name": name, "state_address": addr, "value_type": _value_type(main, sub)}
        return {"type": TYPE_LIGHT, "name": name, "brightness_address": addr}
    if main == 3:
        return {"type": TYPE_COVER, "name": name, "move_long_address": addr}
    if main == 1:
        if sub in (7, 8, 9) or any(k in n for k in _COVER_KW):
            return {"type": TYPE_COVER, "name": name, "move_long_address": addr}
        if _is_status(n):
            return {"type": TYPE_BINARY_SENSOR, "name": name, "state_address": addr}
        return {"type": TYPE_SWITCH, "name": name, "address": addr}
    if main is None:
        if any(k in n for k in ("scene", "szene")):
            return {"type": TYPE_SCENE, "name": name, "address": addr, "scene_number": _scene_number(name)}
        if any(k in n for k in _COVER_KW):
            return {"type": TYPE_COVER, "name": name, "move_long_address": addr}
        if any(k in n for k in _TEMP_KW) or _is_status(n):
            return {"type": TYPE_SENSOR, "name": name, "state_address": addr, "value_type": ""}
        return {"type": TYPE_SWITCH, "name": name, "address": addr}
    return {"type": TYPE_SENSOR, "name": name, "state_address": addr, "value_type": _value_type(main, sub)}


def parse_csv(text: str) -> list[dict]:
    text = (text or "").strip()
    if not text:
        return []
    return _finalize(e for e in (_entity_from_single(r) for r in _csv_rows(text)) if e)


# ---------------------------------------------------------------------------
# knxproj (grouped by ETS Functions)
# ---------------------------------------------------------------------------
def _entity_from_group(name: str, rows: list[_Row]) -> dict | None:
    def pick(pred):
        return next((r.address for r in rows if pred(r)), None)

    mains = {r.main for r in rows}
    if mains & {17, 18}:
        addr = pick(lambda r: r.main in (17, 18))
        return {"type": TYPE_SCENE, "name": name, "address": addr, "scene_number": _scene_number(name)}
    if any((r.main == 1 and r.sub in (8, 9)) or r.main == 3 for r in rows) or \
            any(k in name.lower() for k in _COVER_KW):
        return {
            "type": TYPE_COVER, "name": name,
            "move_long_address": pick(lambda r: (r.main == 1 and r.sub in (8, 9)) or r.main == 3),
            "stop_address": pick(lambda r: r.main == 1 and r.sub in (7, 10)),
            "position_address": pick(lambda r: r.main == 5 and not _is_status(r.name)),
            "position_state_address": pick(lambda r: r.main == 5 and _is_status(r.name)),
        }
    if 5 in mains:
        return {
            "type": TYPE_LIGHT, "name": name,
            "address": pick(lambda r: r.main == 1 and not _is_status(r.name)),
            "state_address": pick(lambda r: r.main == 1 and _is_status(r.name)),
            "brightness_address": pick(lambda r: r.main == 5 and not _is_status(r.name)),
            "brightness_state_address": pick(lambda r: r.main == 5 and _is_status(r.name)),
        }
    measure = next((r for r in rows if r.main in (7, 8, 9, 12, 13, 14, 6, 16)), None)
    if measure is not None:
        return {"type": TYPE_SENSOR, "name": name, "state_address": measure.address,
                "value_type": _value_type(measure.main, measure.sub)}
    if 1 in mains:
        writable = pick(lambda r: r.main == 1 and not _is_status(r.name))
        status = pick(lambda r: r.main == 1 and _is_status(r.name))
        if writable:
            return {"type": TYPE_SWITCH, "name": name, "address": writable, "state_address": status}
        if status:
            return {"type": TYPE_BINARY_SENSOR, "name": name, "state_address": status}
    single = next((r for r in rows), None)
    return _entity_from_single(single) if single else None


def parse_knxproj(path: str, password: str | None = None) -> list[dict]:
    from xknxproject import XKNXProj

    project = XKNXProj(path=path, password=password or None).parse()
    ga_index: dict[str, _Row] = {}
    for addr, ga in project["group_addresses"].items():
        main, sub = _parse_dpt(_dpt_str(ga.get("dpt")))
        ga_index[addr] = _Row(ga.get("name", addr), addr, main, sub)

    entities: list[dict] = []
    grouped: set[str] = set()
    for func in project.get("functions", {}).values():
        rows = []
        for ref in func.get("group_addresses", []):
            addr = ref if isinstance(ref, str) else ref.get("address")
            row = ga_index.get(addr)
            if row:
                rows.append(row)
                grouped.add(addr)
        if rows:
            ent = _entity_from_group(func.get("name", rows[0].name), rows)
            if ent:
                entities.append(ent)

    # Ungrouped addresses → one entity each.
    for addr, row in ga_index.items():
        if addr not in grouped:
            ent = _entity_from_single(row)
            if ent:
                entities.append(ent)
    return _finalize(entities)


def _dpt_str(dpt: Any) -> str:
    if not dpt:
        return ""
    if isinstance(dpt, dict):
        main, sub = dpt.get("main"), dpt.get("sub")
        if main is None:
            return ""
        return f"{main}.{sub:03d}" if sub is not None else f"DPT-{main}"
    return str(dpt)


# ---------------------------------------------------------------------------
# YAML (Home Assistant KNX schema)
# ---------------------------------------------------------------------------
_YAML_ALLOWED = {
    TYPE_SWITCH: ("address", "state_address", "invert", "device_class"),
    TYPE_LIGHT: ("address", "state_address", "brightness_address", "brightness_state_address",
                 "color_address", "color_state_address", "color_temperature_address",
                 "color_temperature_state_address", "hue_address", "hue_state_address",
                 "saturation_address", "saturation_state_address", "min_kelvin", "max_kelvin"),
    TYPE_COVER: ("move_long_address", "move_short_address", "stop_address", "position_address",
                 "position_state_address", "angle_address", "angle_state_address",
                 "travelling_time_down", "travelling_time_up", "invert_updown",
                 "invert_position", "invert_angle", "device_class"),
    TYPE_CLIMATE: ("temperature_address", "target_temperature_address", "target_temperature_state_address",
                   "on_off_address", "on_off_state_address", "controller_mode_address",
                   "controller_mode_state_address", "operation_mode_address", "operation_mode_state_address",
                   "min_temp", "max_temp", "temperature_step"),
    TYPE_SENSOR: ("state_address", "device_class"),
    TYPE_BINARY_SENSOR: ("state_address", "invert", "device_class"),
    TYPE_SCENE: ("address", "scene_number"),
}


def parse_yaml(text: str) -> list[dict]:
    import yaml

    text = (text or "").strip()
    if not text:
        return []
    data = yaml.safe_load(text)
    if isinstance(data, dict) and "knx" in data and isinstance(data["knx"], dict):
        data = data["knx"]
    if not isinstance(data, dict):
        raise ValueError("YAML must be a mapping of platform -> list of entities")

    entities: list[dict] = []
    for platform, defs in data.items():
        if platform not in ENTITY_TYPES or not isinstance(defs, list):
            continue
        allowed = _YAML_ALLOWED[platform]
        for d in defs:
            if not isinstance(d, dict):
                continue
            ent: dict[str, Any] = {"type": platform, "name": str(d.get("name", platform))}
            for key in allowed:
                if d.get(key) not in (None, ""):
                    ent[key] = d[key]
            if platform == TYPE_SENSOR:
                ent["value_type"] = str(d.get("type", "")) or ""
            entities.append(ent)
    return _finalize(entities)


# ---------------------------------------------------------------------------
# Dispatch / helpers
# ---------------------------------------------------------------------------
def detect_format(text: str) -> str:
    """Best-effort auto-detect between 'yaml' and 'csv' for pasted text."""
    try:
        import yaml

        data = yaml.safe_load(text)
        if isinstance(data, dict):
            keys = set(data.get("knx", data)) if isinstance(data.get("knx", data), dict) else set()
            if keys & set(ENTITY_TYPES):
                return "yaml"
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return "csv"


def _finalize(entities) -> list[dict]:
    out = []
    for i, ent in enumerate(entities):
        if not _has_primary(ent):
            continue
        ent = dict(ent)
        ent["index"] = i
        out.append(ent)
    return out


_PRIMARY = {
    TYPE_SWITCH: ("address",),
    TYPE_LIGHT: ("address", "brightness_address"),
    TYPE_COVER: ("move_long_address", "position_address"),
    TYPE_CLIMATE: ("temperature_address", "target_temperature_address"),
    TYPE_SENSOR: ("state_address",),
    TYPE_BINARY_SENSOR: ("state_address",),
    TYPE_SCENE: ("address",),
}


def _has_primary(ent: dict) -> bool:
    keys = _PRIMARY.get(ent.get("type"), ())
    return any(ent.get(k) for k in keys)


def summarize(entities: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for e in entities:
        counts[e["type"]] = counts.get(e["type"], 0) + 1
    return counts
