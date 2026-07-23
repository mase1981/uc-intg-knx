"""KNX climate entity (thermostat)."""

import logging
from typing import Any

from ucapi import StatusCodes, climate
from ucapi_framework import ClimateEntity

from uc_intg_knx.config import KnxConfig
from uc_intg_knx.const import TYPE_CLIMATE
from uc_intg_knx.device import KnxDevice

_LOG = logging.getLogger(__name__)


class KnxClimate(ClimateEntity):
    """Thermostat backed by KNX group addresses."""

    def __init__(
        self, device_config: KnxConfig, device: KnxDevice, definition: dict, index: int
    ) -> None:
        self._device = device
        self._index = index
        self._has_mode = bool(
            definition.get("controller_mode_address")
            or definition.get("controller_mode_state_address")
        )
        self._has_on_off = bool(definition.get("on_off_address"))

        features = []
        if self._has_on_off:
            features.append(climate.Features.ON_OFF)
        if definition.get("temperature_address"):
            features.append(climate.Features.CURRENT_TEMPERATURE)
        if definition.get("target_temperature_address"):
            features.append(climate.Features.TARGET_TEMPERATURE)
        if self._has_mode:
            features.extend([climate.Features.HEAT, climate.Features.COOL])
        elif climate.Features.HEAT not in features:
            features.append(climate.Features.HEAT)

        options = {
            climate.Options.TEMPERATURE_UNIT: "CELSIUS",
            climate.Options.TARGET_TEMPERATURE_STEP: float(
                definition.get("temperature_step", 0.5)
            ),
        }
        if definition.get("min_temp") is not None:
            options[climate.Options.MIN_TEMPERATURE] = float(definition["min_temp"])
        if definition.get("max_temp") is not None:
            options[climate.Options.MAX_TEMPERATURE] = float(definition["max_temp"])

        entity_id = f"climate.{device_config.identifier}.{index}"
        super().__init__(
            entity_id,
            definition.get("name", f"Climate {index}"),
            features,
            {climate.Attributes.STATE: climate.States.UNKNOWN},
            options=options,
            cmd_handler=self._handle_command,
        )
        self.subscribe_to_device(device)

    def _map_state(self, xdev: Any) -> climate.States:
        mode = getattr(xdev, "mode", None)
        if self._has_mode and mode is not None:
            controller = getattr(mode, "controller_mode", None)
            name = getattr(controller, "name", "")
            if name == "HEAT":
                return climate.States.HEAT
            if name == "COOL":
                return climate.States.COOL
            if name == "AUTO":
                return climate.States.AUTO
            if name in ("OFF", "NODEM"):
                return climate.States.OFF
            if name == "FAN_ONLY":
                return climate.States.FAN
        if self._has_on_off:
            return climate.States.HEAT if xdev.is_on else climate.States.OFF
        return climate.States.HEAT

    async def sync_state(self) -> None:
        if not self._device.available:
            self.update({climate.Attributes.STATE: climate.States.UNAVAILABLE})
            return
        xdev = self._device.xknx_device(self._index)
        if xdev is None:
            self.update({climate.Attributes.STATE: climate.States.UNKNOWN})
            return

        attrs: dict[str, Any] = {climate.Attributes.STATE: self._map_state(xdev)}
        current = xdev.temperature.value if xdev.temperature is not None else None
        if current is not None:
            attrs[climate.Attributes.CURRENT_TEMPERATURE] = round(float(current), 1)
        target = (
            xdev.target_temperature.value
            if xdev.target_temperature is not None
            else None
        )
        if target is not None:
            attrs[climate.Attributes.TARGET_TEMPERATURE] = round(float(target), 1)
        self.update(attrs)

    async def _handle_command(
        self, entity: Any, cmd_id: str, params: dict[str, Any] | None
    ) -> StatusCodes:
        xdev = self._device.xknx_device(self._index)
        if xdev is None:
            return StatusCodes.SERVER_ERROR
        params = params or {}
        try:
            if cmd_id == climate.Commands.ON:
                await xdev.turn_on()
            elif cmd_id == climate.Commands.OFF:
                await xdev.turn_off()
            elif cmd_id == climate.Commands.TARGET_TEMPERATURE:
                await xdev.set_target_temperature(float(params.get("temperature", 0)))
            elif cmd_id == climate.Commands.HVAC_MODE:
                return await self._set_hvac_mode(xdev, params.get("hvac_mode", ""))
            else:
                return StatusCodes.NOT_IMPLEMENTED
            return StatusCodes.OK
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Climate command error: %s", entity.id, err)
            return StatusCodes.SERVER_ERROR

    async def _set_hvac_mode(self, xdev: Any, mode: str) -> StatusCodes:
        from xknx.dpt.dpt_20 import HVACControllerMode

        mode = str(mode).upper()
        if mode == "OFF":
            if self._has_on_off:
                await xdev.turn_off()
                return StatusCodes.OK
            if xdev.mode is not None:
                await xdev.mode.set_controller_mode(HVACControllerMode.OFF)
                return StatusCodes.OK
            return StatusCodes.NOT_IMPLEMENTED

        target = {
            "HEAT": HVACControllerMode.HEAT,
            "COOL": HVACControllerMode.COOL,
            "AUTO": HVACControllerMode.AUTO,
            "FAN": HVACControllerMode.FAN_ONLY,
        }.get(mode)
        if target is None or xdev.mode is None:
            return StatusCodes.NOT_IMPLEMENTED
        if self._has_on_off and not xdev.is_on:
            await xdev.turn_on()
        await xdev.mode.set_controller_mode(target)
        return StatusCodes.OK


def create_climates(device_config: KnxConfig, device: KnxDevice) -> list[KnxClimate]:
    """Build all climate entities defined in the config."""
    return [
        KnxClimate(device_config, device, definition, index)
        for index, definition in enumerate(device_config.entities)
        if definition.get("type") == TYPE_CLIMATE
    ]
