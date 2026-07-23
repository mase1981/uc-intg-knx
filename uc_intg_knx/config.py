"""Configuration dataclass and manager for the KNX Hub integration."""

from dataclasses import dataclass, field
from typing import Any

from ucapi_framework import BaseConfigManager

from uc_intg_knx.const import CONNECTION_AUTOMATIC, DEFAULT_KNX_PORT


@dataclass
class KnxConfig:
    """Configuration for a single KNX/IP gateway and its exposed entities."""

    identifier: str = ""
    name: str = ""
    connection_type: str = CONNECTION_AUTOMATIC
    host: str = ""
    port: int = DEFAULT_KNX_PORT
    local_ip: str = ""
    route_back: bool = False
    individual_address: str = ""
    entities: list[dict[str, Any]] = field(default_factory=list)


class KnxConfigManager(BaseConfigManager[KnxConfig]):
    """Config manager bound to :class:`KnxConfig`."""
