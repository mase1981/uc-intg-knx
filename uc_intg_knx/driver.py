"""Integration driver for the KNX Hub."""

from ucapi_framework import BaseIntegrationDriver

from uc_intg_knx.button import create_buttons
from uc_intg_knx.climate import create_climates
from uc_intg_knx.config import KnxConfig
from uc_intg_knx.cover import create_covers
from uc_intg_knx.device import KnxDevice
from uc_intg_knx.light import create_lights
from uc_intg_knx.sensor import create_binary_sensors, create_sensors
from uc_intg_knx.switch import create_switches


class KnxDriver(BaseIntegrationDriver[KnxDevice, KnxConfig]):
    """Driver that builds a KNX gateway device and its user-defined entities."""

    def __init__(self) -> None:
        super().__init__(
            device_class=KnxDevice,
            entity_classes=[
                create_switches,
                create_lights,
                create_covers,
                create_climates,
                create_sensors,
                create_binary_sensors,
                create_buttons,
            ],
            driver_id="uc_intg_knx",
        )
