"""KNX cover entity (blinds, shutters, shades).

KNX position convention is 0 = fully open, 100 = fully closed. The UC Remote
uses 0 = closed, 100 = open, so positions are inverted at the boundary.
"""

import logging
from typing import Any

from ucapi import StatusCodes, cover
from ucapi_framework import CoverEntity

from uc_intg_knx.config import KnxConfig
from uc_intg_knx.const import TYPE_COVER
from uc_intg_knx.device import KnxDevice

_LOG = logging.getLogger(__name__)

_DEVICE_CLASSES = {
    "blind": cover.DeviceClasses.BLIND,
    "curtain": cover.DeviceClasses.CURTAIN,
    "garage": cover.DeviceClasses.GARAGE,
    "shade": cover.DeviceClasses.SHADE,
    "door": cover.DeviceClasses.DOOR,
    "gate": cover.DeviceClasses.GATE,
    "window": cover.DeviceClasses.WINDOW,
}


class KnxCover(CoverEntity):
    """Cover backed by KNX group addresses."""

    def __init__(
        self, device_config: KnxConfig, device: KnxDevice, definition: dict, index: int
    ) -> None:
        self._device = device
        self._index = index

        features = [cover.Features.OPEN, cover.Features.CLOSE, cover.Features.STOP]
        if definition.get("position_address") or definition.get(
            "position_state_address"
        ):
            features.append(cover.Features.POSITION)
        if definition.get("angle_address"):
            features.extend(
                [
                    cover.Features.TILT,
                    cover.Features.TILT_STOP,
                    cover.Features.TILT_POSITION,
                ]
            )

        device_class = _DEVICE_CLASSES.get(str(definition.get("device_class", "blind")))
        entity_id = f"cover.{device_config.identifier}.{index}"
        super().__init__(
            entity_id,
            definition.get("name", f"Cover {index}"),
            features,
            {cover.Attributes.STATE: cover.States.UNKNOWN},
            device_class=device_class,
            cmd_handler=self._handle_command,
        )
        self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        if not self._device.available:
            self.update({cover.Attributes.STATE: cover.States.UNAVAILABLE})
            return
        xdev = self._device.xknx_device(self._index)
        if xdev is None:
            self.update({cover.Attributes.STATE: cover.States.UNKNOWN})
            return

        if xdev.is_opening():
            state = cover.States.OPENING
        elif xdev.is_closing():
            state = cover.States.CLOSING
        elif xdev.is_closed():
            state = cover.States.CLOSED
        else:
            state = cover.States.OPEN

        attrs: dict[str, Any] = {cover.Attributes.STATE: state}
        knx_position = xdev.current_position()
        if knx_position is not None:
            attrs[cover.Attributes.POSITION] = 100 - int(knx_position)
        knx_angle = xdev.current_angle()
        if knx_angle is not None:
            attrs[cover.Attributes.TILT_POSITION] = int(knx_angle)
        self.update(attrs)

    async def _handle_command(
        self, entity: Any, cmd_id: str, params: dict[str, Any] | None
    ) -> StatusCodes:
        xdev = self._device.xknx_device(self._index)
        if xdev is None:
            return StatusCodes.SERVER_ERROR
        params = params or {}
        try:
            if cmd_id == cover.Commands.OPEN:
                await xdev.set_up()
            elif cmd_id == cover.Commands.CLOSE:
                await xdev.set_down()
            elif cmd_id == cover.Commands.STOP:
                await xdev.stop()
            elif cmd_id == cover.Commands.POSITION:
                await xdev.set_position(100 - int(params.get("position", 0)))
            elif cmd_id == cover.Commands.TILT:
                await xdev.set_angle(int(params.get("tilt_position", 0)))
            elif cmd_id == cover.Commands.TILT_UP:
                await xdev.set_short_up()
            elif cmd_id == cover.Commands.TILT_DOWN:
                await xdev.set_short_down()
            elif cmd_id == cover.Commands.TILT_STOP:
                await xdev.stop()
            else:
                return StatusCodes.NOT_IMPLEMENTED
            return StatusCodes.OK
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Cover command error: %s", entity.id, err)
            return StatusCodes.SERVER_ERROR


def create_covers(device_config: KnxConfig, device: KnxDevice) -> list[KnxCover]:
    """Build all cover entities defined in the config."""
    return [
        KnxCover(device_config, device, definition, index)
        for index, definition in enumerate(device_config.entities)
        if definition.get("type") == TYPE_COVER
    ]
