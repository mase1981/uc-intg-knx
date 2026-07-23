"""KNX Remote entity — one control surface auto-built from the imported controls.

All switch / dimmable / cover group addresses are aggregated into a single
Remote entity whose simple commands and UI pages are generated from the import,
following the Bond/Govee pattern.
"""

import logging
from typing import Any

from ucapi import StatusCodes, remote
from ucapi.ui import Size, UiPage, create_ui_text
from ucapi_framework import RemoteEntity

from uc_intg_knx.config import KnxConfig
from uc_intg_knx.const import slugify
from uc_intg_knx.device import KnxDevice
from uc_intg_knx.knx_import import KIND_COVER, KIND_DIM, KIND_SWITCH

_LOG = logging.getLogger(__name__)

_MAX_PAGES = 40

# Sentinel value_type used inside the command map for a tracked toggle.
_TOGGLE = "__toggle__"


def _commands_for(item: dict, slug: str) -> tuple[list[tuple[str, str]], dict]:
    """Return (buttons, command_map) for a single control item.

    buttons: list of (label, command) to place on the item's UI page.
    command_map: command -> (address, value_type, value).
    """
    address = item["address"]
    kind = item["kind"]
    sub = item.get("sub")
    name_l = item.get("name", "").lower()
    buttons: list[tuple[str, str]] = []
    cmd_map: dict[str, tuple] = {}

    def add(label: str, action: str, value_type, value):
        command = f"{slug}_{action}"
        buttons.append((label, command))
        cmd_map[command] = (address, value_type, value)

    if kind == KIND_SWITCH:
        add("On", "ON", None, 1)
        add("Off", "OFF", None, 0)
        add("Toggle", "TOGGLE", _TOGGLE, None)
    elif kind == KIND_DIM:
        add("Off", "OFF", "percent", 0)
        add("25%", "25", "percent", 25)
        add("50%", "50", "percent", 50)
        add("75%", "75", "percent", 75)
        add("100%", "100", "percent", 100)
    elif kind == KIND_COVER:
        if sub in (7, 10) or "stop" in name_l:
            add("Stop", "STOP", None, 1)
        else:
            add("Open", "OPEN", None, 0)
            add("Close", "CLOSE", None, 1)
    return buttons, cmd_map


class KnxRemote(RemoteEntity):
    """Aggregated Remote entity for all KNX controls."""

    def __init__(
        self, device_config: KnxConfig, device: KnxDevice, controls: list[dict]
    ) -> None:
        self._device = device
        self._command_map: dict[str, tuple] = {}
        self._switch_addresses: list[str] = []

        simple_commands: list[str] = []
        ui_pages: list[UiPage] = []
        used_slugs: set[str] = set()

        for item in controls:
            slug = slugify(item.get("name", item["address"]))
            base = slug
            n = 2
            while slug in used_slugs:
                slug = f"{base}_{n}"
                n += 1
            used_slugs.add(slug)

            buttons, cmd_map = _commands_for(item, slug)
            if not buttons:
                continue
            self._command_map.update(cmd_map)
            simple_commands.extend(cmd for _label, cmd in buttons)
            if item["kind"] == KIND_SWITCH:
                self._switch_addresses.append(item["address"])

            if len(ui_pages) < _MAX_PAGES:
                ui_pages.append(self._build_page(item.get("name", slug), buttons))

        entity_id = f"remote.{device_config.identifier}"
        super().__init__(
            entity_id,
            f"{device_config.name} Controls",
            [remote.Features.ON_OFF, remote.Features.TOGGLE, remote.Features.SEND_CMD],
            {remote.Attributes.STATE: remote.States.UNKNOWN},
            simple_commands=simple_commands,
            ui_pages=ui_pages,
            cmd_handler=self._handle_command,
        )
        self.subscribe_to_device(device)

    @staticmethod
    def _build_page(title: str, buttons: list[tuple[str, str]]) -> UiPage:
        page = UiPage(title[:20] or "Control", title, grid=Size(4, 6), items=[])
        row = 0
        for label, command in buttons[:6]:
            page.add(create_ui_text(label, 0, row, size=Size(4, 1), cmd=command))
            row += 1
        return page

    async def sync_state(self) -> None:
        if not self._device.available:
            self.update({remote.Attributes.STATE: remote.States.UNAVAILABLE})
            return
        self.update({remote.Attributes.STATE: remote.States.ON})

    async def _handle_command(
        self, entity: Any, cmd_id: str, params: dict[str, Any] | None = None, *_a: Any
    ) -> StatusCodes:
        try:
            if cmd_id == remote.Commands.ON:
                return await self._all_switches(True)
            if cmd_id == remote.Commands.OFF:
                return await self._all_switches(False)
            if cmd_id == remote.Commands.SEND_CMD:
                command = (params or {}).get("command", "")
                return await self._run_command(command)
            if cmd_id == remote.Commands.SEND_CMD_SEQUENCE:
                for command in (params or {}).get("sequence", []):
                    await self._run_command(command)
                return StatusCodes.OK
            return StatusCodes.NOT_IMPLEMENTED
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Remote command error: %s", entity.id, err)
            return StatusCodes.SERVER_ERROR

    async def _run_command(self, command: str) -> StatusCodes:
        entry = self._command_map.get(command)
        if entry is None:
            return StatusCodes.NOT_IMPLEMENTED
        address, value_type, value = entry
        if value_type == _TOGGLE:
            await self._device.switch_toggle(address)
        else:
            await self._device.send_group_value(address, value_type, value)
        return StatusCodes.OK

    async def _all_switches(self, on: bool) -> StatusCodes:
        for address in self._switch_addresses:
            await self._device.send_group_value(address, None, 1 if on else 0)
        return StatusCodes.OK


def create_remote(device_config: KnxConfig, device: KnxDevice) -> list[KnxRemote]:
    """Build the single Remote entity if any controls were imported."""
    controls = [
        item
        for item in device_config.entities
        if item.get("kind") in (KIND_SWITCH, KIND_DIM, KIND_COVER)
    ]
    if not controls:
        return []
    return [KnxRemote(device_config, device, controls)]
