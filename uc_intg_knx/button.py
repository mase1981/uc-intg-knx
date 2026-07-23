"""KNX button entity — writes a value to a group address on press.

Useful for scene triggers, blinds macros, or any one-shot group-address write.
"""

import logging
from typing import Any

from ucapi import StatusCodes, button
from ucapi_framework import ButtonEntity

from uc_intg_knx.config import KnxConfig
from uc_intg_knx.const import TYPE_BUTTON
from uc_intg_knx.device import KnxDevice

_LOG = logging.getLogger(__name__)


class KnxButton(ButtonEntity):
    """Button that writes a configured value to a KNX group address."""

    def __init__(
        self, device_config: KnxConfig, device: KnxDevice, definition: dict, index: int
    ) -> None:
        self._device = device
        self._address = str(definition.get("address", "")).strip()
        self._value_type = definition.get("value_type")
        self._value = definition.get("value", 1)
        entity_id = f"button.{device_config.identifier}.{index}"
        super().__init__(
            entity_id,
            definition.get("name", f"Button {index}"),
            cmd_handler=self._handle_command,
        )

    async def _handle_command(
        self, entity: Any, cmd_id: str, params: dict[str, Any] | None
    ) -> StatusCodes:
        if cmd_id != button.Commands.PUSH:
            return StatusCodes.NOT_IMPLEMENTED
        if not self._address:
            return StatusCodes.SERVER_ERROR
        try:
            await self._device.send_group_value(
                self._address, self._value_type, self._value
            )
            return StatusCodes.OK
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Button command error: %s", entity.id, err)
            return StatusCodes.SERVER_ERROR


def create_buttons(device_config: KnxConfig, device: KnxDevice) -> list[KnxButton]:
    """Build all button entities defined in the config."""
    return [
        KnxButton(device_config, device, definition, index)
        for index, definition in enumerate(device_config.entities)
        if definition.get("type") == TYPE_BUTTON
    ]
