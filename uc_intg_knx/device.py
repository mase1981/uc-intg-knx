"""KNX/IP gateway device wrapping the xknx client library.

Builds one xknx device per imported entity (mapping the Home Assistant KNX key
names onto xknx parameters) and sends telegrams for scenes.
"""

import asyncio
import logging
from typing import Any

from ucapi_framework import ExternalClientDevice

from uc_intg_knx.config import KnxConfig
from uc_intg_knx.const import STATE_ON, STATE_UNAVAILABLE
from uc_intg_knx.knx_import import (
    TYPE_BINARY_SENSOR,
    TYPE_CLIMATE,
    TYPE_COVER,
    TYPE_LIGHT,
    TYPE_SENSOR,
    TYPE_SWITCH,
)

_LOG = logging.getLogger(__name__)

DEFAULT_MIN_KELVIN = 2700
DEFAULT_MAX_KELVIN = 6500


def _ga(item: dict, *keys: str) -> str | None:
    for key in keys:
        val = item.get(key)
        if val:
            return str(val).strip()
    return None


class KnxDevice(ExternalClientDevice):
    """A single KNX/IP gateway."""

    def __init__(self, device_config: KnxConfig, **kwargs: Any) -> None:
        super().__init__(
            device_config, enable_watchdog=True, watchdog_interval=30,
            reconnect_delay=5, max_reconnect_attempts=0, **kwargs,
        )
        self._device_config = device_config
        self._xknx: Any = None
        self._devices: dict[int, Any] = {}
        self._connect_lock: asyncio.Lock = asyncio.Lock()
        self._state: str = STATE_UNAVAILABLE

    @property
    def identifier(self) -> str:
        return self._device_config.identifier

    @property
    def name(self) -> str:
        return self._device_config.name

    @property
    def address(self) -> str:
        return self._device_config.host

    @property
    def log_id(self) -> str:
        return f"{self.name} ({self.address})"

    @property
    def state(self) -> str:
        return self._state

    @property
    def available(self) -> bool:
        return self.check_client_connected()

    def xknx_device(self, index: int) -> Any:
        return self._devices.get(index)

    # ------------------------------------------------------------------
    def _build_connection_config(self) -> Any:
        from xknx.io import ConnectionConfig, ConnectionType

        cfg = self._device_config
        mapping = {
            "tunneling": ConnectionType.TUNNELING,
            "tunneling_tcp": ConnectionType.TUNNELING_TCP,
            "routing": ConnectionType.ROUTING,
            "automatic": ConnectionType.AUTOMATIC,
        }
        kwargs: dict[str, Any] = {
            "connection_type": mapping.get(cfg.connection_type, ConnectionType.TUNNELING)
        }
        if cfg.host:
            kwargs["gateway_ip"] = cfg.host
            kwargs["gateway_port"] = cfg.port
        if cfg.local_ip:
            kwargs["local_ip"] = cfg.local_ip
        return ConnectionConfig(**kwargs)

    def _build_devices(self) -> None:
        from xknx.devices import (
            BinarySensor, Climate, ClimateMode, Cover, Light, Sensor, Switch,
        )

        self._devices = {}
        for item in self._device_config.entities:
            etype = item.get("type")
            index = item.get("index", 0)
            name = item.get("name", f"knx_{index}")
            device: Any = None
            try:
                if etype == TYPE_SWITCH:
                    device = Switch(
                        self._xknx, name,
                        group_address=_ga(item, "address"),
                        group_address_state=_ga(item, "state_address"),
                        invert=bool(item.get("invert", False)),
                    )
                elif etype == TYPE_LIGHT:
                    device = Light(
                        self._xknx, name,
                        group_address_switch=_ga(item, "address"),
                        group_address_switch_state=_ga(item, "state_address"),
                        group_address_brightness=_ga(item, "brightness_address"),
                        group_address_brightness_state=_ga(item, "brightness_state_address"),
                        group_address_color=_ga(item, "color_address"),
                        group_address_color_state=_ga(item, "color_state_address"),
                        group_address_hue=_ga(item, "hue_address"),
                        group_address_hue_state=_ga(item, "hue_state_address"),
                        group_address_saturation=_ga(item, "saturation_address"),
                        group_address_saturation_state=_ga(item, "saturation_state_address"),
                        group_address_color_temperature=_ga(item, "color_temperature_address"),
                        group_address_color_temperature_state=_ga(item, "color_temperature_state_address"),
                        min_kelvin=int(item.get("min_kelvin", DEFAULT_MIN_KELVIN)),
                        max_kelvin=int(item.get("max_kelvin", DEFAULT_MAX_KELVIN)),
                    )
                elif etype == TYPE_COVER:
                    device = Cover(
                        self._xknx, name,
                        group_address_long=_ga(item, "move_long_address"),
                        group_address_short=_ga(item, "move_short_address"),
                        group_address_stop=_ga(item, "stop_address"),
                        group_address_position=_ga(item, "position_address"),
                        group_address_position_state=_ga(item, "position_state_address"),
                        group_address_angle=_ga(item, "angle_address"),
                        group_address_angle_state=_ga(item, "angle_state_address"),
                        travel_time_down=float(item.get("travelling_time_down", 25)),
                        travel_time_up=float(item.get("travelling_time_up", 25)),
                        invert_updown=bool(item.get("invert_updown", False)),
                        invert_position=bool(item.get("invert_position", False)),
                        invert_angle=bool(item.get("invert_angle", False)),
                    )
                elif etype == TYPE_CLIMATE:
                    mode = None
                    controller = _ga(item, "controller_mode_address")
                    operation = _ga(item, "operation_mode_address")
                    if controller or operation:
                        mode = ClimateMode(
                            self._xknx, f"{name} Mode",
                            group_address_controller_mode=controller,
                            group_address_controller_mode_state=_ga(item, "controller_mode_state_address"),
                            group_address_operation_mode=operation,
                            group_address_operation_mode_state=_ga(item, "operation_mode_state_address"),
                        )
                        self._xknx.devices.async_add(mode)
                    device = Climate(
                        self._xknx, name,
                        group_address_temperature=_ga(item, "temperature_address"),
                        group_address_target_temperature=_ga(item, "target_temperature_address"),
                        group_address_target_temperature_state=_ga(item, "target_temperature_state_address"),
                        group_address_on_off=_ga(item, "on_off_address"),
                        group_address_on_off_state=_ga(item, "on_off_state_address"),
                        min_temp=item.get("min_temp"),
                        max_temp=item.get("max_temp"),
                        temperature_step=float(item.get("temperature_step", 0.5)),
                        mode=mode,
                    )
                elif etype == TYPE_SENSOR:
                    device = Sensor(
                        self._xknx, name,
                        group_address_state=_ga(item, "state_address"),
                        value_type=item.get("value_type") or None,
                    )
                elif etype == TYPE_BINARY_SENSOR:
                    device = BinarySensor(
                        self._xknx, name,
                        group_address_state=_ga(item, "state_address"),
                        invert=bool(item.get("invert", False)),
                    )
            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOG.warning("[%s] Could not build %s '%s': %s", self.log_id, etype, name, err)
                device = None
            if device is not None:
                self._xknx.devices.async_add(device)
            self._devices[index] = device

    # ------------------------------------------------------------------
    async def connect(self) -> bool:
        async with self._connect_lock:
            return await super().connect()

    async def create_client(self) -> Any:
        from xknx import XKNX

        if self._xknx is not None:
            await self._teardown_xknx()
        self._xknx = XKNX(
            connection_config=self._build_connection_config(),
            device_updated_cb=self._on_device_updated,
            connection_state_changed_cb=self._on_connection_state_changed,
            state_updater="init 60",
        )
        self._build_devices()
        return self._xknx

    async def connect_client(self) -> None:
        await self._xknx.start()
        self._state = STATE_ON
        self._loop.create_task(self._initial_sync())

    async def disconnect_client(self) -> None:
        await self._teardown_xknx()
        self._state = STATE_UNAVAILABLE

    async def _teardown_xknx(self) -> None:
        if self._xknx is not None:
            try:
                await self._xknx.stop()
            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOG.debug("[%s] Error stopping xknx: %s", self.log_id, err)
            self._xknx = None
        self._devices = {}

    def check_client_connected(self) -> bool:
        if self._xknx is None:
            return False
        from xknx.core.connection_state import XknxConnectionState

        return self._xknx.connection_manager.state == XknxConnectionState.CONNECTED

    async def disconnect(self) -> None:
        async with self._connect_lock:
            await super().disconnect()
        self._state = STATE_UNAVAILABLE

    # ------------------------------------------------------------------
    def _on_device_updated(self, _device: Any) -> None:
        self.push_update()

    def _on_connection_state_changed(self, state: Any) -> None:
        from xknx.core.connection_state import XknxConnectionState

        self._state = STATE_ON if state == XknxConnectionState.CONNECTED else STATE_UNAVAILABLE
        self.push_update()

    async def _initial_sync(self) -> None:
        try:
            await self._xknx.devices.sync()
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.debug("[%s] Initial state sync failed: %s", self.log_id, err)

    async def send_group_value(self, address: str, value_type: str | None = None, value: Any = None) -> None:
        from xknx.dpt import DPTBase, DPTBinary
        from xknx.telegram import Telegram
        from xknx.telegram.address import GroupAddress
        from xknx.telegram.apci import GroupValueWrite

        if self._xknx is None:
            raise ConnectionError("KNX client not connected")
        if value_type:
            transcoder = DPTBase.parse_transcoder(value_type)
            if transcoder is None:
                raise ValueError(f"Unknown KNX value_type '{value_type}'")
            payload = GroupValueWrite(transcoder.to_knx(value))
        else:
            payload = GroupValueWrite(DPTBinary(0 if value in (0, False, "0", "off", "OFF") else 1))
        await self._xknx.telegrams.put(
            Telegram(destination_address=GroupAddress(address), payload=payload)
        )
