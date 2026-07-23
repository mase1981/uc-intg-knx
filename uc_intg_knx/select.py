"""KNX scene Select entity — one Select listing every imported scene."""

import logging
import re
from typing import Any

from ucapi import StatusCodes, select
from ucapi_framework import SelectEntity

from uc_intg_knx.config import KnxConfig
from uc_intg_knx.device import KnxDevice
from uc_intg_knx.knx_import import KIND_SCENE

_LOG = logging.getLogger(__name__)

_TRAILING_NUMBER = re.compile(r"(\d{1,2})\s*$")


class KnxScenes(SelectEntity):
    """A single Select whose options are the imported scenes."""

    def __init__(
        self, device_config: KnxConfig, device: KnxDevice, scenes: list[dict]
    ) -> None:
        self._device = device
        self._current = ""
        self._scenes: dict[str, tuple[str, int]] = {}
        options: list[str] = []
        used: set[str] = set()
        for item in scenes:
            name = item.get("name", item["address"])
            label = name
            n = 2
            while label in used:
                label = f"{name} ({n})"
                n += 1
            used.add(label)
            match = _TRAILING_NUMBER.search(name)
            number = int(match.group(1)) if match else 1
            self._scenes[label] = (item["address"], max(1, min(64, number)))
            options.append(label)

        entity_id = f"select.{device_config.identifier}.scenes"
        super().__init__(
            entity_id,
            f"{device_config.name} Scenes",
            {
                select.Attributes.STATE: select.States.UNKNOWN,
                select.Attributes.OPTIONS: options,
                select.Attributes.CURRENT_OPTION: "",
            },
            cmd_handler=self._handle_command,
        )
        self._options = options
        self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        if not self._device.available:
            self.update({select.Attributes.STATE: select.States.UNAVAILABLE})
            return
        self.update(
            {
                select.Attributes.STATE: select.States.ON,
                select.Attributes.OPTIONS: self._options,
                select.Attributes.CURRENT_OPTION: self._current,
            }
        )

    async def _activate(self, label: str) -> StatusCodes:
        entry = self._scenes.get(label)
        if entry is None:
            return StatusCodes.NOT_IMPLEMENTED
        address, number = entry
        await self._device.send_group_value(address, "scene_number", number)
        self._current = label
        self.update({select.Attributes.CURRENT_OPTION: label})
        return StatusCodes.OK

    async def _handle_command(
        self, entity: Any, cmd_id: str, params: dict[str, Any] | None = None, *_a: Any
    ) -> StatusCodes:
        try:
            if cmd_id == select.Commands.SELECT_OPTION:
                return await self._activate((params or {}).get("option", ""))
            if not self._options:
                return StatusCodes.NOT_IMPLEMENTED
            idx = self._options.index(self._current) if self._current in self._options else -1
            if cmd_id == select.Commands.SELECT_NEXT:
                return await self._activate(self._options[(idx + 1) % len(self._options)])
            if cmd_id == select.Commands.SELECT_PREVIOUS:
                return await self._activate(self._options[(idx - 1) % len(self._options)])
            if cmd_id == select.Commands.SELECT_FIRST:
                return await self._activate(self._options[0])
            if cmd_id == select.Commands.SELECT_LAST:
                return await self._activate(self._options[-1])
            return StatusCodes.NOT_IMPLEMENTED
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Scene select error: %s", entity.id, err)
            return StatusCodes.SERVER_ERROR


def create_selects(device_config: KnxConfig, device: KnxDevice) -> list[KnxScenes]:
    """Build the scenes Select entity if any scenes were imported."""
    scenes = [
        item for item in device_config.entities if item.get("kind") == KIND_SCENE
    ]
    if not scenes:
        return []
    return [KnxScenes(device_config, device, scenes)]
