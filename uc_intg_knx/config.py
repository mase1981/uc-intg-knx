"""Configuration dataclass and manager for the KNX integration."""

from dataclasses import dataclass, field
from typing import Any

from ucapi_framework import BaseConfigManager

from uc_intg_knx.const import DEFAULT_KNX_PORT, SOURCE_CSV


@dataclass
class KnxConfig:
    """Configuration for a single KNX/IP gateway and its imported entities.

    ``entities`` is the normalized, typed entity list produced by whichever
    import source the user chose during setup (CSV / YAML / knxproj). Users
    never edit it by hand.
    """

    identifier: str = ""
    name: str = ""
    host: str = ""
    port: int = DEFAULT_KNX_PORT
    connection_type: str = "tunneling"
    local_ip: str = ""
    source: str = SOURCE_CSV
    entities: list[dict[str, Any]] = field(default_factory=list)


class KnxConfigManager(BaseConfigManager[KnxConfig]):
    """Config manager bound to :class:`KnxConfig`."""
