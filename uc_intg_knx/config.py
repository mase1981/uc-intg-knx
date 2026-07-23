"""Configuration dataclass and manager for the KNX integration."""

from dataclasses import dataclass, field
from typing import Any

from ucapi_framework import BaseConfigManager

from uc_intg_knx.const import DEFAULT_KNX_PORT


@dataclass
class KnxConfig:
    """Configuration for a single KNX/IP gateway and its imported entities.

    ``entities`` is the classified list of group addresses parsed from the ETS
    group-address export the user pastes during setup. Users never edit it by
    hand.
    """

    identifier: str = ""
    name: str = ""
    host: str = ""
    port: int = DEFAULT_KNX_PORT
    connection_type: str = "tunneling"
    local_ip: str = ""
    entities: list[dict[str, Any]] = field(default_factory=list)


class KnxConfigManager(BaseConfigManager[KnxConfig]):
    """Config manager bound to :class:`KnxConfig`."""
