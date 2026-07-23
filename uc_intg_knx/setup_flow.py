"""Setup flow for the KNX integration.

Two inputs, one screen: the KNX/IP gateway IP address, and the ETS
'Group Addresses' export pasted as text. The integration parses the export and
auto-builds all entities.
"""

import logging
from typing import Any

from ucapi import RequestUserInput
from ucapi_framework import BaseSetupFlow

from uc_intg_knx.config import KnxConfig
from uc_intg_knx.const import DEFAULT_KNX_PORT
from uc_intg_knx.knx_import import items_to_dicts, parse_group_export, summarize

_LOG = logging.getLogger(__name__)


class KnxSetupFlow(BaseSetupFlow[KnxConfig]):
    """Collect the gateway IP and the pasted ETS group-address export."""

    def get_manual_entry_form(self) -> RequestUserInput:
        return RequestUserInput(
            {"en": "KNX Gateway Setup"},
            [
                {
                    "id": "info",
                    "label": {"en": "KNX/IP Gateway"},
                    "field": {
                        "label": {
                            "value": {
                                "en": "Enter your KNX/IP gateway (interface or router) IP "
                                "address, then paste your ETS 'Group Addresses' export "
                                "(CSV) below. The integration builds all entities "
                                "automatically."
                            }
                        }
                    },
                },
                {
                    "id": "name",
                    "label": {"en": "Name"},
                    "field": {"text": {"value": "KNX"}},
                },
                {
                    "id": "host",
                    "label": {"en": "Gateway IP address"},
                    "field": {"text": {"value": ""}},
                },
                {
                    "id": "port",
                    "label": {"en": "Gateway port"},
                    "field": {"number": {"value": DEFAULT_KNX_PORT, "min": 1, "max": 65535}},
                },
                {
                    "id": "import_data",
                    "label": {"en": "ETS Group Address export (paste CSV)"},
                    "field": {"textarea": {"value": ""}},
                },
            ],
        )

    async def query_device(
        self, input_values: dict[str, Any]
    ) -> KnxConfig | RequestUserInput:
        host = input_values.get("host", "").strip()
        if not host:
            raise ValueError("Gateway IP address is required")

        items = parse_group_export(input_values.get("import_data", ""))
        if not items:
            raise ValueError(
                "No group addresses found. Paste the ETS 'Group Addresses' CSV export."
            )

        try:
            port = int(input_values.get("port", DEFAULT_KNX_PORT))
        except (TypeError, ValueError):
            port = DEFAULT_KNX_PORT

        name = input_values.get("name", "").strip() or "KNX"
        identifier = f"knx_{host.replace('.', '_')}"

        _LOG.info(
            "KNX gateway '%s' (%s): imported %d group addresses %s",
            name,
            host,
            len(items),
            summarize(items),
        )

        return KnxConfig(
            identifier=identifier,
            name=name,
            host=host,
            port=port,
            connection_type="tunneling",
            entities=items_to_dicts(items),
        )
