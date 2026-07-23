"""KNX sensor and binary-sensor entities (read-only)."""

import logging

from ucapi import sensor
from ucapi_framework import SensorEntity

from uc_intg_knx.config import KnxConfig
from uc_intg_knx.const import TYPE_BINARY_SENSOR, TYPE_SENSOR
from uc_intg_knx.device import KnxDevice

_LOG = logging.getLogger(__name__)

_DEVICE_CLASSES = {
    "temperature": sensor.DeviceClasses.TEMPERATURE,
    "humidity": sensor.DeviceClasses.HUMIDITY,
    "power": sensor.DeviceClasses.POWER,
    "energy": sensor.DeviceClasses.ENERGY,
    "current": sensor.DeviceClasses.CURRENT,
    "voltage": sensor.DeviceClasses.VOLTAGE,
    "battery": sensor.DeviceClasses.BATTERY,
}


class KnxSensor(SensorEntity):
    """Sensor backed by a KNX group address."""

    def __init__(
        self,
        device_config: KnxConfig,
        device: KnxDevice,
        definition: dict,
        index: int,
        binary: bool = False,
    ) -> None:
        self._device = device
        self._index = index
        self._binary = binary

        if binary:
            device_class = sensor.DeviceClasses.BINARY
        else:
            device_class = _DEVICE_CLASSES.get(
                str(definition.get("device_class", "")), sensor.DeviceClasses.CUSTOM
            )

        prefix = "sensor"
        entity_id = f"{prefix}.{device_config.identifier}.{index}"
        super().__init__(
            entity_id,
            definition.get("name", f"Sensor {index}"),
            [],
            {
                sensor.Attributes.STATE: sensor.States.UNKNOWN,
                sensor.Attributes.VALUE: "",
                sensor.Attributes.UNIT: "",
            },
            device_class=device_class,
        )
        self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        if not self._device.available:
            self.update({sensor.Attributes.STATE: sensor.States.UNAVAILABLE})
            return
        xdev = self._device.xknx_device(self._index)
        if xdev is None:
            self.update({sensor.Attributes.STATE: sensor.States.UNKNOWN})
            return

        if self._binary:
            state = xdev.state
            if state is None:
                self.update({sensor.Attributes.STATE: sensor.States.UNKNOWN})
                return
            self.update(
                {
                    sensor.Attributes.STATE: sensor.States.ON,
                    sensor.Attributes.VALUE: "ON" if xdev.is_on() else "OFF",
                }
            )
            return

        value = xdev.resolve_state()
        if value is None:
            self.update({sensor.Attributes.STATE: sensor.States.UNKNOWN})
            return
        self.update(
            {
                sensor.Attributes.STATE: sensor.States.ON,
                sensor.Attributes.VALUE: str(value),
                sensor.Attributes.UNIT: xdev.unit_of_measurement() or "",
            }
        )


def create_sensors(device_config: KnxConfig, device: KnxDevice) -> list[KnxSensor]:
    """Build all value-sensor entities defined in the config."""
    return [
        KnxSensor(device_config, device, definition, index, binary=False)
        for index, definition in enumerate(device_config.entities)
        if definition.get("type") == TYPE_SENSOR
    ]


def create_binary_sensors(
    device_config: KnxConfig, device: KnxDevice
) -> list[KnxSensor]:
    """Build all binary-sensor entities defined in the config."""
    return [
        KnxSensor(device_config, device, definition, index, binary=True)
        for index, definition in enumerate(device_config.entities)
        if definition.get("type") == TYPE_BINARY_SENSOR
    ]
