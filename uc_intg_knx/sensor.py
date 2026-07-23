"""KNX sensor and binary-sensor entities (read-only)."""

import logging

from ucapi import sensor
from ucapi_framework import SensorEntity

from uc_intg_knx.config import KnxConfig
from uc_intg_knx.device import KnxDevice
from uc_intg_knx.knx_import import TYPE_BINARY_SENSOR, TYPE_SENSOR

_LOG = logging.getLogger(__name__)

_DEVICE_CLASS_BY_VALUE_TYPE = {
    "temperature": sensor.DeviceClasses.TEMPERATURE,
    "humidity": sensor.DeviceClasses.HUMIDITY,
    "power": sensor.DeviceClasses.POWER,
    "active_energy": sensor.DeviceClasses.ENERGY,
    "current": sensor.DeviceClasses.CURRENT,
    "voltage": sensor.DeviceClasses.VOLTAGE,
}

_DEVICE_CLASS_BY_NAME = {
    "temperature": sensor.DeviceClasses.TEMPERATURE,
    "humidity": sensor.DeviceClasses.HUMIDITY,
    "power": sensor.DeviceClasses.POWER,
    "energy": sensor.DeviceClasses.ENERGY,
    "current": sensor.DeviceClasses.CURRENT,
    "voltage": sensor.DeviceClasses.VOLTAGE,
    "battery": sensor.DeviceClasses.BATTERY,
}


class KnxSensor(SensorEntity):
    def __init__(self, device_config: KnxConfig, device: KnxDevice, item: dict, binary: bool) -> None:
        self._device = device
        self._index = item["index"]
        self._binary = binary

        if binary:
            device_class = sensor.DeviceClasses.BINARY
        else:
            device_class = _DEVICE_CLASS_BY_NAME.get(
                str(item.get("device_class", "")),
                _DEVICE_CLASS_BY_VALUE_TYPE.get(str(item.get("value_type", "")), sensor.DeviceClasses.CUSTOM),
            )

        entity_id = f"sensor.{device_config.identifier}.{self._index}"
        super().__init__(
            entity_id,
            item.get("name", f"Sensor {self._index}"),
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
            if xdev.state is None:
                self.update({sensor.Attributes.STATE: sensor.States.UNKNOWN})
                return
            self.update({
                sensor.Attributes.STATE: sensor.States.ON,
                sensor.Attributes.VALUE: "ON" if xdev.is_on() else "OFF",
            })
            return
        value = xdev.resolve_state()
        if value is None:
            self.update({sensor.Attributes.STATE: sensor.States.UNKNOWN})
            return
        self.update({
            sensor.Attributes.STATE: sensor.States.ON,
            sensor.Attributes.VALUE: str(value),
            sensor.Attributes.UNIT: xdev.unit_of_measurement() or "",
        })


def create_sensors(device_config: KnxConfig, device: KnxDevice) -> list[KnxSensor]:
    return [
        KnxSensor(device_config, device, item, binary=False)
        for item in device_config.entities if item.get("type") == TYPE_SENSOR
    ]


def create_binary_sensors(device_config: KnxConfig, device: KnxDevice) -> list[KnxSensor]:
    return [
        KnxSensor(device_config, device, item, binary=True)
        for item in device_config.entities if item.get("type") == TYPE_BINARY_SENSOR
    ]
