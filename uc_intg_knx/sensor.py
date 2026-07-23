"""KNX sensor and binary-sensor entities (read-only), auto-built from the import."""

import logging

from ucapi import sensor
from ucapi_framework import SensorEntity

from uc_intg_knx.config import KnxConfig
from uc_intg_knx.device import KnxDevice
from uc_intg_knx.knx_import import KIND_BINARY_SENSOR, KIND_SENSOR

_LOG = logging.getLogger(__name__)

_DEVICE_CLASS_BY_MAIN = {
    9: sensor.DeviceClasses.TEMPERATURE,
    12: sensor.DeviceClasses.CUSTOM,
    13: sensor.DeviceClasses.ENERGY,
    14: sensor.DeviceClasses.POWER,
}

_DEVICE_CLASS_BY_VALUE_TYPE = {
    "temperature": sensor.DeviceClasses.TEMPERATURE,
    "humidity": sensor.DeviceClasses.HUMIDITY,
    "power": sensor.DeviceClasses.POWER,
    "active_energy": sensor.DeviceClasses.ENERGY,
    "current": sensor.DeviceClasses.CURRENT,
    "voltage": sensor.DeviceClasses.VOLTAGE,
}


class KnxSensor(SensorEntity):
    """Sensor backed by a KNX group address."""

    def __init__(
        self, device_config: KnxConfig, device: KnxDevice, item: dict, binary: bool
    ) -> None:
        self._device = device
        self._address = item["address"]
        self._binary = binary

        if binary:
            device_class = sensor.DeviceClasses.BINARY
        else:
            device_class = _DEVICE_CLASS_BY_VALUE_TYPE.get(
                str(item.get("value_type", "")),
                _DEVICE_CLASS_BY_MAIN.get(item.get("main"), sensor.DeviceClasses.CUSTOM),
            )

        entity_id = f"sensor.{device_config.identifier}.{item['index']}"
        super().__init__(
            entity_id,
            item.get("name", self._address),
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
        xdev = self._device.sensor_device(self._address)
        if xdev is None:
            self.update({sensor.Attributes.STATE: sensor.States.UNKNOWN})
            return

        if self._binary:
            if xdev.state is None:
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
    """Build a Sensor entity for every sensor / binary-sensor group address."""
    entities: list[KnxSensor] = []
    for item in device_config.entities:
        kind = item.get("kind")
        if kind == KIND_SENSOR:
            entities.append(KnxSensor(device_config, device, item, binary=False))
        elif kind == KIND_BINARY_SENSOR:
            entities.append(KnxSensor(device_config, device, item, binary=True))
    return entities
