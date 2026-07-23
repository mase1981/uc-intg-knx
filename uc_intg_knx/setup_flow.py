"""Setup flow for the KNX integration.

Screen 1: gateway IP + configuration method (CSV paste / HA YAML paste /
ETS .knxproj). Screen 2: the method-specific input. The chosen source is
parsed into the normalized entity list and the entities are auto-built.
"""

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from ucapi import RequestUserInput
from ucapi.api_definitions import IntegrationSetupError, SetupError
from ucapi_framework import BaseSetupFlow

from uc_intg_knx.config import KnxConfig
from uc_intg_knx.const import (
    DEFAULT_KNX_PORT,
    SOURCE_CSV,
    SOURCE_KNXPROJ,
    SOURCE_YAML,
)
from uc_intg_knx.knx_import import (
    detect_format,
    parse_csv,
    parse_knxproj,
    parse_yaml,
    summarize,
)

_LOG = logging.getLogger(__name__)


class KnxSetupFlow(BaseSetupFlow[KnxConfig]):
    """Multi-step setup: connection, then the chosen import source."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._method: str = SOURCE_CSV

    # -- Screen 1: connection + method -------------------------------------
    def get_manual_entry_form(self) -> RequestUserInput:
        return RequestUserInput(
            {"en": "KNX Gateway Setup"},
            [
                {
                    "id": "info",
                    "label": {"en": "KNX/IP Gateway"},
                    "field": {"label": {"value": {"en": "Enter your KNX/IP gateway IP address and choose how to import your entities. See the README for details."}}},
                },
                {"id": "name", "label": {"en": "Name"}, "field": {"text": {"value": "KNX"}}},
                {"id": "host", "label": {"en": "Gateway IP address"}, "field": {"text": {"value": ""}}},
                {"id": "port", "label": {"en": "Gateway port"}, "field": {"number": {"value": DEFAULT_KNX_PORT, "min": 1, "max": 65535}}},
                {
                    "id": "method",
                    "label": {"en": "Configuration method"},
                    "field": {"dropdown": {"value": SOURCE_CSV, "items": [
                        {"id": SOURCE_CSV, "label": {"en": "Paste ETS Group Address CSV export"}},
                        {"id": SOURCE_YAML, "label": {"en": "Paste Home Assistant KNX YAML"}},
                        {"id": SOURCE_KNXPROJ, "label": {"en": "ETS project (.knxproj) file/URL (Docker)"}},
                    ]}},
                },
            ],
        )

    async def query_device(self, input_values: dict[str, Any]) -> KnxConfig | RequestUserInput:
        host = input_values.get("host", "").strip()
        if not host:
            raise ValueError("Gateway IP address is required")
        self._method = input_values.get("method", SOURCE_CSV)
        try:
            port = int(input_values.get("port", DEFAULT_KNX_PORT))
        except (TypeError, ValueError):
            port = DEFAULT_KNX_PORT
        name = input_values.get("name", "").strip() or "KNX"

        self._pending_device_config = KnxConfig(
            identifier=f"knx_{host.replace('.', '_')}",
            name=name, host=host, port=port, connection_type="tunneling",
            source=self._method, entities=[],
        )
        return self._build_source_screen(self._method)

    # -- Screen 2: source-specific input -----------------------------------
    def _build_source_screen(self, method: str, error: bool = False) -> RequestUserInput:
        err = [{"id": "err", "label": {"en": ""}, "field": {"label": {"value": {"en": "⚠️ Nothing could be imported. Please check your input and try again."}}}}] if error else []
        if method == SOURCE_KNXPROJ:
            return RequestUserInput({"en": "ETS Project Import"}, err + [
                {"id": "note", "label": {"en": "ETS .knxproj"}, "field": {"label": {"value": {"en": "Provide a URL to your .knxproj, or the filename of a .knxproj placed in the mounted config folder (Docker). A .knxproj cannot be uploaded through the Remote."}}}},
                {"id": "knxproj_source", "label": {"en": "URL or filename"}, "field": {"text": {"value": ""}}},
                {"id": "knxproj_password", "label": {"en": "Project password (if encrypted)"}, "field": {"password": {"value": ""}}},
            ])
        label = "Home Assistant KNX YAML" if method == SOURCE_YAML else "ETS Group Address CSV"
        return RequestUserInput({"en": f"Paste {label}"}, err + [
            {"id": "import_data", "label": {"en": f"Paste your {label}"}, "field": {"textarea": {"value": ""}}},
        ])

    async def handle_additional_configuration_response(self, msg: Any) -> Any:
        iv = msg.input_values
        try:
            entities = await self._parse_source(iv)
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("KNX import failed: %s", err)
            return SetupError(error_type=IntegrationSetupError.OTHER)

        if not entities:
            return self._build_source_screen(self._method, error=True)

        self._pending_device_config.entities = entities
        self._pending_device_config.source = self._method
        _LOG.info("KNX import (%s): %d entities %s", self._method, len(entities), summarize(entities))
        return None

    async def _parse_source(self, iv: dict[str, Any]) -> list[dict]:
        if self._method == SOURCE_KNXPROJ:
            source = iv.get("knxproj_source", "").strip()
            password = iv.get("knxproj_password", "").strip()
            if not source:
                return []
            path = await self._resolve_knxproj(source)
            return await asyncio.to_thread(parse_knxproj, path, password)

        text = iv.get("import_data", "")
        method = self._method
        if method == SOURCE_CSV and detect_format(text) == SOURCE_YAML:
            method = SOURCE_YAML  # user pasted YAML into the CSV box
        return parse_yaml(text) if method == SOURCE_YAML else parse_csv(text)

    async def _resolve_knxproj(self, source: str) -> str:
        if source.lower().startswith(("http://", "https://")):
            import ssl

            import aiohttp
            import certifi

            ssl_ctx = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(source) as resp:
                    resp.raise_for_status()
                    data = await resp.read()
            fd, path = tempfile.mkstemp(suffix=".knxproj")
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            return path

        config_home = os.getenv("UC_CONFIG_HOME") or os.getenv("UC_DATA_HOME") or os.getcwd()
        candidate = Path(source)
        if not candidate.is_absolute():
            candidate = Path(config_home) / source
        if not candidate.exists():
            raise ValueError(
                f"'{source}' not found. Place the .knxproj in the mounted config folder "
                f"({config_home}) — this requires running the integration in Docker — or provide a URL."
            )
        return str(candidate)
