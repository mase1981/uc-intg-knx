"""KNX switch entity."""

import logging
from typing import Any

from ucapi import StatusCodes, switch
from ucapi_framework import SwitchEntity

from uc_intg_knx.config import KnxConfig
from uc_intg_knx.device import KnxDevice
from uc_intg_knx.knx_import import TYPE_SWITCH

_LOG = logging.getLogger(__name__)


class KnxSwitch(SwitchEntity):
    def __init__(self, device_config: KnxConfig, device: KnxDevice, item: dict) -> None:
        self._device = device
        self._index = item["index"]
        entity_id = f"switch.{device_config.identifier}.{self._index}"
        super().__init__(
            entity_id,
            item.get("name", f"Switch {self._index}"),
            [switch.Features.ON_OFF, switch.Features.TOGGLE],
            {switch.Attributes.STATE: switch.States.UNKNOWN},
            cmd_handler=self._handle_command,
        )
        self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        if not self._device.available:
            self.update({switch.Attributes.STATE: switch.States.UNAVAILABLE})
            return
        xdev = self._device.xknx_device(self._index)
        state = xdev.state if xdev else None
        if state is None:
            self.update({switch.Attributes.STATE: switch.States.UNKNOWN})
            return
        self.update({switch.Attributes.STATE: switch.States.ON if state else switch.States.OFF})

    async def _handle_command(self, entity: Any, cmd_id: str, params: dict | None = None, *_a: Any) -> StatusCodes:
        xdev = self._device.xknx_device(self._index)
        if xdev is None:
            return StatusCodes.SERVER_ERROR
        try:
            if cmd_id == switch.Commands.ON:
                await xdev.set_on()
            elif cmd_id == switch.Commands.OFF:
                await xdev.set_off()
            elif cmd_id == switch.Commands.TOGGLE:
                await (xdev.set_off() if xdev.state else xdev.set_on())
            else:
                return StatusCodes.NOT_IMPLEMENTED
            return StatusCodes.OK
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Switch command error: %s", entity.id, err)
            return StatusCodes.SERVER_ERROR


def create_switches(device_config: KnxConfig, device: KnxDevice) -> list[KnxSwitch]:
    return [
        KnxSwitch(device_config, device, item)
        for item in device_config.entities if item.get("type") == TYPE_SWITCH
    ]
