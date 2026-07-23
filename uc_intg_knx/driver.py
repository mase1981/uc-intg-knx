"""Integration driver for KNX."""

from ucapi_framework import BaseIntegrationDriver

from uc_intg_knx.config import KnxConfig
from uc_intg_knx.device import KnxDevice
from uc_intg_knx.remote import create_remote
from uc_intg_knx.select import create_selects
from uc_intg_knx.sensor import create_sensors


class KnxDriver(BaseIntegrationDriver[KnxDevice, KnxConfig]):
    """Driver that connects to a KNX/IP gateway and auto-builds entities from
    the imported group addresses."""

    def __init__(self) -> None:
        super().__init__(
            device_class=KnxDevice,
            entity_classes=[
                create_remote,
                create_selects,
                create_sensors,
            ],
            driver_id="uc_intg_knx",
        )
