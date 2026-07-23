"""KNX light entity (on/off, dimming, color, color temperature).

Value mapping: brightness 0-255 both sides; hue 0-360, saturation 0-100 both
sides; UC color_temperature (0-255) is mapped linearly to the Kelvin range.
"""

import logging
from typing import Any

from ucapi import StatusCodes, light
from ucapi_framework import LightEntity

from uc_intg_knx.config import KnxConfig
from uc_intg_knx.device import DEFAULT_MAX_KELVIN, DEFAULT_MIN_KELVIN, KnxDevice
from uc_intg_knx.knx_import import TYPE_LIGHT

_LOG = logging.getLogger(__name__)


class KnxLight(LightEntity):
    def __init__(self, device_config: KnxConfig, device: KnxDevice, item: dict) -> None:
        self._device = device
        self._index = item["index"]
        self._has_switch = bool(item.get("address"))
        self._min_kelvin = int(item.get("min_kelvin", DEFAULT_MIN_KELVIN))
        self._max_kelvin = int(item.get("max_kelvin", DEFAULT_MAX_KELVIN))

        features = [light.Features.ON_OFF, light.Features.TOGGLE]
        if item.get("brightness_address"):
            features.append(light.Features.DIM)
        if (item.get("hue_address") and item.get("saturation_address")) or item.get("color_address"):
            features.append(light.Features.COLOR)
        if item.get("color_temperature_address"):
            features.append(light.Features.COLOR_TEMPERATURE)

        entity_id = f"light.{device_config.identifier}.{self._index}"
        super().__init__(
            entity_id,
            item.get("name", f"Light {self._index}"),
            features,
            {light.Attributes.STATE: light.States.UNKNOWN, light.Attributes.BRIGHTNESS: 0},
            cmd_handler=self._handle_command,
        )
        self.subscribe_to_device(device)

    def _k2uc(self, kelvin: int) -> int:
        span = max(1, self._max_kelvin - self._min_kelvin)
        return max(0, min(255, round((kelvin - self._min_kelvin) / span * 255)))

    def _uc2k(self, value: int) -> int:
        return round(self._min_kelvin + max(0, min(255, value)) / 255 * (self._max_kelvin - self._min_kelvin))

    async def sync_state(self) -> None:
        if not self._device.available:
            self.update({light.Attributes.STATE: light.States.UNAVAILABLE})
            return
        xdev = self._device.xknx_device(self._index)
        if xdev is None:
            self.update({light.Attributes.STATE: light.States.UNKNOWN})
            return
        on = xdev.state
        if on is None and xdev.current_brightness is not None:
            on = xdev.current_brightness > 0
        if on is None:
            self.update({light.Attributes.STATE: light.States.UNKNOWN})
            return
        attrs: dict[str, Any] = {light.Attributes.STATE: light.States.ON if on else light.States.OFF}
        if xdev.supports_brightness and xdev.current_brightness is not None:
            attrs[light.Attributes.BRIGHTNESS] = xdev.current_brightness
        if xdev.supports_hs_color and xdev.current_hs_color is not None:
            hue, sat = xdev.current_hs_color
            if hue is not None:
                attrs[light.Attributes.HUE] = round(hue)
            if sat is not None:
                attrs[light.Attributes.SATURATION] = round(sat)
        if xdev.supports_color_temperature and xdev.current_color_temperature is not None:
            attrs[light.Attributes.COLOR_TEMPERATURE] = self._k2uc(int(xdev.current_color_temperature))
        self.update(attrs)

    async def _handle_command(self, entity: Any, cmd_id: str, params: dict | None = None, *_a: Any) -> StatusCodes:
        xdev = self._device.xknx_device(self._index)
        if xdev is None:
            return StatusCodes.SERVER_ERROR
        params = params or {}
        try:
            if cmd_id == light.Commands.OFF:
                await (xdev.set_off() if self._has_switch else xdev.set_brightness(0))
                return StatusCodes.OK
            if cmd_id == light.Commands.TOGGLE:
                await (xdev.set_off() if xdev.state else xdev.set_on())
                return StatusCodes.OK
            if cmd_id == light.Commands.ON:
                if "color_temperature" in params and xdev.supports_color_temperature:
                    await xdev.set_color_temperature(self._uc2k(int(params["color_temperature"])))
                if ("hue" in params or "saturation" in params) and xdev.supports_hs_color:
                    await xdev.set_hs_color((float(params.get("hue", 0)), float(params.get("saturation", 100))))
                if "brightness" in params and xdev.supports_brightness:
                    await xdev.set_brightness(int(params["brightness"]))
                elif not any(k in params for k in ("brightness", "hue", "saturation", "color_temperature")):
                    await (xdev.set_on() if self._has_switch else xdev.set_brightness(255))
                return StatusCodes.OK
            return StatusCodes.NOT_IMPLEMENTED
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Light command error: %s", entity.id, err)
            return StatusCodes.SERVER_ERROR


def create_lights(device_config: KnxConfig, device: KnxDevice) -> list[KnxLight]:
    return [
        KnxLight(device_config, device, item)
        for item in device_config.entities if item.get("type") == TYPE_LIGHT
    ]
