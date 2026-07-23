"""KNX light entity (on/off, dimming, color, color temperature).

Value-range mapping between the UC Remote and KNX/xknx:
- brightness: 0-255 on both sides (direct).
- hue: 0-360 on both sides; saturation: 0-100 on both sides (direct).
- color_temperature: the UC attribute (0-255) is mapped linearly to the
  configured Kelvin range (``min_kelvin``..``max_kelvin``).
"""

import logging
from typing import Any

from ucapi import StatusCodes, light
from ucapi_framework import LightEntity

from uc_intg_knx.config import KnxConfig
from uc_intg_knx.const import DEFAULT_MAX_KELVIN, DEFAULT_MIN_KELVIN, TYPE_LIGHT
from uc_intg_knx.device import KnxDevice

_LOG = logging.getLogger(__name__)


class KnxLight(LightEntity):
    """Light backed by KNX group addresses."""

    def __init__(
        self, device_config: KnxConfig, device: KnxDevice, definition: dict, index: int
    ) -> None:
        self._device = device
        self._index = index
        self._min_kelvin = int(definition.get("min_kelvin", DEFAULT_MIN_KELVIN))
        self._max_kelvin = int(definition.get("max_kelvin", DEFAULT_MAX_KELVIN))

        features = [light.Features.ON_OFF, light.Features.TOGGLE]
        if definition.get("brightness_address"):
            features.append(light.Features.DIM)
        if (definition.get("hue_address") and definition.get("saturation_address")) or (
            definition.get("color_address")
        ):
            features.append(light.Features.COLOR)
        if definition.get("color_temp_address"):
            features.append(light.Features.COLOR_TEMPERATURE)

        entity_id = f"light.{device_config.identifier}.{index}"
        super().__init__(
            entity_id,
            definition.get("name", f"Light {index}"),
            features,
            {
                light.Attributes.STATE: light.States.UNKNOWN,
                light.Attributes.BRIGHTNESS: 0,
            },
            cmd_handler=self._handle_command,
        )
        self.subscribe_to_device(device)

    def _kelvin_to_uc(self, kelvin: int) -> int:
        span = max(1, self._max_kelvin - self._min_kelvin)
        ratio = (kelvin - self._min_kelvin) / span
        return max(0, min(255, round(ratio * 255)))

    def _uc_to_kelvin(self, value: int) -> int:
        ratio = max(0, min(255, value)) / 255
        return round(self._min_kelvin + ratio * (self._max_kelvin - self._min_kelvin))

    async def sync_state(self) -> None:
        if not self._device.available:
            self.update({light.Attributes.STATE: light.States.UNAVAILABLE})
            return
        xdev = self._device.xknx_device(self._index)
        if xdev is None or xdev.state is None:
            self.update({light.Attributes.STATE: light.States.UNKNOWN})
            return

        attrs: dict[str, Any] = {
            light.Attributes.STATE: light.States.ON
            if xdev.state
            else light.States.OFF
        }
        if xdev.supports_brightness and xdev.current_brightness is not None:
            attrs[light.Attributes.BRIGHTNESS] = xdev.current_brightness
        if xdev.supports_hs_color and xdev.current_hs_color is not None:
            hue, saturation = xdev.current_hs_color
            if hue is not None:
                attrs[light.Attributes.HUE] = round(hue)
            if saturation is not None:
                attrs[light.Attributes.SATURATION] = round(saturation)
        if (
            xdev.supports_color_temperature
            and xdev.current_color_temperature is not None
        ):
            attrs[light.Attributes.COLOR_TEMPERATURE] = self._kelvin_to_uc(
                int(xdev.current_color_temperature)
            )
        self.update(attrs)

    async def _handle_command(
        self, entity: Any, cmd_id: str, params: dict[str, Any] | None
    ) -> StatusCodes:
        xdev = self._device.xknx_device(self._index)
        if xdev is None:
            return StatusCodes.SERVER_ERROR
        params = params or {}
        try:
            if cmd_id == light.Commands.OFF:
                await xdev.set_off()
                return StatusCodes.OK
            if cmd_id == light.Commands.TOGGLE:
                if xdev.state:
                    await xdev.set_off()
                else:
                    await xdev.set_on()
                return StatusCodes.OK
            if cmd_id == light.Commands.ON:
                if "color_temperature" in params and xdev.supports_color_temperature:
                    await xdev.set_color_temperature(
                        self._uc_to_kelvin(int(params["color_temperature"]))
                    )
                if (
                    "hue" in params or "saturation" in params
                ) and xdev.supports_hs_color:
                    hue = float(params.get("hue", 0))
                    saturation = float(params.get("saturation", 100))
                    await xdev.set_hs_color((hue, saturation))
                if "brightness" in params and xdev.supports_brightness:
                    await xdev.set_brightness(int(params["brightness"]))
                elif not params:
                    await xdev.set_on()
                elif "brightness" not in params and not xdev.state:
                    await xdev.set_on()
                return StatusCodes.OK
            return StatusCodes.NOT_IMPLEMENTED
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Light command error: %s", entity.id, err)
            return StatusCodes.SERVER_ERROR


def create_lights(device_config: KnxConfig, device: KnxDevice) -> list[KnxLight]:
    """Build all light entities defined in the config."""
    return [
        KnxLight(device_config, device, definition, index)
        for index, definition in enumerate(device_config.entities)
        if definition.get("type") == TYPE_LIGHT
    ]
