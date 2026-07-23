"""KNX cover entity (blinds, shutters). KNX position 0=open/100=closed is
inverted vs the UC convention (0=closed/100=open)."""

import logging
from typing import Any

from ucapi import StatusCodes, cover
from ucapi_framework import CoverEntity

from uc_intg_knx.config import KnxConfig
from uc_intg_knx.device import KnxDevice
from uc_intg_knx.knx_import import TYPE_COVER

_LOG = logging.getLogger(__name__)

_DEVICE_CLASSES = {
    "blind": cover.DeviceClasses.BLIND, "curtain": cover.DeviceClasses.CURTAIN,
    "garage": cover.DeviceClasses.GARAGE, "shade": cover.DeviceClasses.SHADE,
    "door": cover.DeviceClasses.DOOR, "gate": cover.DeviceClasses.GATE,
    "window": cover.DeviceClasses.WINDOW,
}


class KnxCover(CoverEntity):
    def __init__(self, device_config: KnxConfig, device: KnxDevice, item: dict) -> None:
        self._device = device
        self._index = item["index"]

        features = [cover.Features.OPEN, cover.Features.CLOSE, cover.Features.STOP]
        if item.get("position_address") or item.get("position_state_address"):
            features.append(cover.Features.POSITION)
        if item.get("angle_address"):
            features += [cover.Features.TILT, cover.Features.TILT_STOP, cover.Features.TILT_POSITION]

        entity_id = f"cover.{device_config.identifier}.{self._index}"
        super().__init__(
            entity_id,
            item.get("name", f"Cover {self._index}"),
            features,
            {cover.Attributes.STATE: cover.States.UNKNOWN},
            device_class=_DEVICE_CLASSES.get(str(item.get("device_class", "blind"))),
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
        pos = xdev.current_position()
        if pos is not None:
            attrs[cover.Attributes.POSITION] = 100 - int(pos)
        angle = xdev.current_angle()
        if angle is not None:
            attrs[cover.Attributes.TILT_POSITION] = int(angle)
        self.update(attrs)

    async def _handle_command(self, entity: Any, cmd_id: str, params: dict | None = None, *_a: Any) -> StatusCodes:
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
    return [
        KnxCover(device_config, device, item)
        for item in device_config.entities if item.get("type") == TYPE_COVER
    ]
