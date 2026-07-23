"""Setup flow for the KNX Hub integration."""

import json
import logging
from typing import Any

from ucapi import RequestUserInput
from ucapi_framework import BaseSetupFlow

from uc_intg_knx.config import KnxConfig
from uc_intg_knx.const import (
    CONNECTION_TYPES,
    DEFAULT_KNX_PORT,
    ENTITY_TYPES,
    slugify,
)

_LOG = logging.getLogger(__name__)

_EXAMPLE_ENTITIES = (
    '[{"type":"switch","name":"Office Light","address":"1/1/1",'
    '"state_address":"1/1/2"}]'
)


class KnxSetupFlow(BaseSetupFlow[KnxConfig]):
    """Collect gateway connection details and the entity definitions."""

    def get_manual_entry_form(self) -> RequestUserInput:
        return RequestUserInput(
            {"en": "KNX/IP Gateway Setup"},
            [
                {
                    "id": "name",
                    "label": {"en": "Gateway Name"},
                    "field": {"text": {"value": "KNX Hub"}},
                },
                {
                    "id": "connection_type",
                    "label": {"en": "Connection Type"},
                    "field": {
                        "dropdown": {
                            "value": "automatic",
                            "items": [
                                {"id": "automatic", "label": {"en": "Automatic (discover gateway)"}},
                                {"id": "tunneling", "label": {"en": "Tunneling (UDP)"}},
                                {"id": "tunneling_tcp", "label": {"en": "Tunneling (TCP)"}},
                                {"id": "routing", "label": {"en": "Routing (multicast)"}},
                            ],
                        }
                    },
                },
                {
                    "id": "host",
                    "label": {"en": "Gateway IP (blank for automatic/routing)"},
                    "field": {"text": {"value": ""}},
                },
                {
                    "id": "port",
                    "label": {"en": "Gateway Port"},
                    "field": {"number": {"value": DEFAULT_KNX_PORT, "min": 1, "max": 65535}},
                },
                {
                    "id": "local_ip",
                    "label": {"en": "Local IP (optional)"},
                    "field": {"text": {"value": ""}},
                },
                {
                    "id": "route_back",
                    "label": {"en": "Route Back (for NAT/VPN tunnels)"},
                    "field": {
                        "dropdown": {
                            "value": "false",
                            "items": [
                                {"id": "false", "label": {"en": "No"}},
                                {"id": "true", "label": {"en": "Yes"}},
                            ],
                        }
                    },
                },
                {
                    "id": "individual_address",
                    "label": {"en": "Individual Address (routing only, e.g. 1.0.255)"},
                    "field": {"text": {"value": ""}},
                },
                {
                    "id": "entities",
                    "label": {"en": "Entities (JSON array — see the README)"},
                    "field": {"text": {"value": _EXAMPLE_ENTITIES}},
                },
            ],
        )

    async def query_device(
        self, input_values: dict[str, Any]
    ) -> KnxConfig | RequestUserInput:
        connection_type = input_values.get("connection_type", "automatic").strip()
        if connection_type not in CONNECTION_TYPES:
            raise ValueError(f"Invalid connection type: {connection_type}")

        host = input_values.get("host", "").strip()
        if connection_type in ("tunneling", "tunneling_tcp") and not host:
            raise ValueError("Gateway IP is required for tunneling connections")

        entities = self._parse_entities(input_values.get("entities", ""))

        name = input_values.get("name", "").strip() or "KNX Hub"
        identifier = f"knx_{slugify(host or name)}"

        try:
            port = int(input_values.get("port", DEFAULT_KNX_PORT))
        except (TypeError, ValueError):
            port = DEFAULT_KNX_PORT

        config = KnxConfig(
            identifier=identifier,
            name=name,
            connection_type=connection_type,
            host=host,
            port=port,
            local_ip=input_values.get("local_ip", "").strip(),
            route_back=str(input_values.get("route_back", "false")).lower() == "true",
            individual_address=input_values.get("individual_address", "").strip(),
            entities=entities,
        )
        _LOG.info(
            "KNX gateway '%s' configured (%s) with %d entities",
            name,
            connection_type,
            len(entities),
        )
        return config

    def _parse_entities(self, raw: str) -> list[dict[str, Any]]:
        raw = (raw or "").strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as err:
            raise ValueError(f"Entities field is not valid JSON: {err}") from err
        if isinstance(parsed, dict):
            parsed = [parsed]
        if not isinstance(parsed, list):
            raise ValueError("Entities must be a JSON array of objects")

        for i, item in enumerate(parsed):
            if not isinstance(item, dict):
                raise ValueError(f"Entity #{i + 1} is not a JSON object")
            entity_type = item.get("type")
            if entity_type not in ENTITY_TYPES:
                raise ValueError(
                    f"Entity #{i + 1} has invalid type '{entity_type}'. "
                    f"Valid types: {', '.join(ENTITY_TYPES)}"
                )
            if not item.get("name"):
                raise ValueError(f"Entity #{i + 1} ({entity_type}) is missing 'name'")
        return parsed
