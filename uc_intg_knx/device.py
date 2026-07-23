"""KNX/IP gateway device wrapping the xknx client library."""

import asyncio
import logging
from typing import Any

from ucapi_framework import ExternalClientDevice

from uc_intg_knx.config import KnxConfig
from uc_intg_knx.const import (
    CONNECTION_ROUTING,
    CONNECTION_TUNNELING,
    CONNECTION_TUNNELING_TCP,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    STATE_ON,
    STATE_UNAVAILABLE,
    TYPE_BINARY_SENSOR,
    TYPE_CLIMATE,
    TYPE_COVER,
    TYPE_LIGHT,
    TYPE_SENSOR,
    TYPE_SWITCH,
)

_LOG = logging.getLogger(__name__)


def _ga(definition: dict[str, Any], *keys: str) -> str | None:
    """Return the first non-empty group address for the given keys, else None."""
    for key in keys:
        value = definition.get(key)
        if value:
            return str(value).strip()
    return None


class KnxDevice(ExternalClientDevice):
    """A single KNX/IP gateway exposing user-defined entities via xknx."""

    def __init__(self, device_config: KnxConfig, **kwargs: Any) -> None:
        super().__init__(
            device_config,
            enable_watchdog=True,
            watchdog_interval=30,
            reconnect_delay=5,
            max_reconnect_attempts=0,
            **kwargs,
        )
        self._device_config = device_config
        self._xknx: Any = None
        self._xknx_devices: dict[int, Any] = {}
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
        return self._device_config.host or self._device_config.connection_type

    @property
    def log_id(self) -> str:
        return f"{self.name} ({self.address})"

    @property
    def state(self) -> str:
        return self._state

    @property
    def available(self) -> bool:
        return self.check_client_connected()

    @property
    def xknx(self) -> Any:
        return self._xknx

    def xknx_device(self, index: int) -> Any:
        """Return the xknx device for the entity at the given config index."""
        return self._xknx_devices.get(index)

    # ------------------------------------------------------------------
    # xknx client construction
    # ------------------------------------------------------------------
    def _build_connection_config(self) -> Any:
        from xknx.io import ConnectionConfig, ConnectionType

        cfg = self._device_config
        mapping = {
            CONNECTION_TUNNELING: ConnectionType.TUNNELING,
            CONNECTION_TUNNELING_TCP: ConnectionType.TUNNELING_TCP,
            CONNECTION_ROUTING: ConnectionType.ROUTING,
        }
        connection_type = mapping.get(cfg.connection_type, ConnectionType.AUTOMATIC)

        kwargs: dict[str, Any] = {"connection_type": connection_type}
        if cfg.host:
            kwargs["gateway_ip"] = cfg.host
            kwargs["gateway_port"] = cfg.port
        if cfg.local_ip:
            kwargs["local_ip"] = cfg.local_ip
        if cfg.route_back:
            kwargs["route_back"] = True
        if cfg.individual_address:
            kwargs["individual_address"] = cfg.individual_address
        return ConnectionConfig(**kwargs)

    def _build_xknx_devices(self) -> None:
        from xknx.devices import (
            BinarySensor,
            Climate,
            ClimateMode,
            Cover,
            Light,
            Sensor,
            Switch,
        )

        self._xknx_devices = {}
        for index, definition in enumerate(self._device_config.entities):
            entity_type = definition.get("type")
            name = definition.get("name", f"knx_{index}")
            device: Any = None
            try:
                if entity_type == TYPE_SWITCH:
                    device = Switch(
                        self._xknx,
                        name,
                        group_address=_ga(definition, "address"),
                        group_address_state=_ga(definition, "state_address"),
                        invert=bool(definition.get("invert", False)),
                    )
                elif entity_type == TYPE_LIGHT:
                    device = Light(
                        self._xknx,
                        name,
                        group_address_switch=_ga(definition, "address"),
                        group_address_switch_state=_ga(definition, "state_address"),
                        group_address_brightness=_ga(definition, "brightness_address"),
                        group_address_brightness_state=_ga(
                            definition, "brightness_state_address"
                        ),
                        group_address_color=_ga(definition, "color_address"),
                        group_address_color_state=_ga(definition, "color_state_address"),
                        group_address_hue=_ga(definition, "hue_address"),
                        group_address_hue_state=_ga(definition, "hue_state_address"),
                        group_address_saturation=_ga(definition, "saturation_address"),
                        group_address_saturation_state=_ga(
                            definition, "saturation_state_address"
                        ),
                        group_address_color_temperature=_ga(
                            definition, "color_temp_address"
                        ),
                        group_address_color_temperature_state=_ga(
                            definition, "color_temp_state_address"
                        ),
                        min_kelvin=int(
                            definition.get("min_kelvin", DEFAULT_MIN_KELVIN)
                        ),
                        max_kelvin=int(
                            definition.get("max_kelvin", DEFAULT_MAX_KELVIN)
                        ),
                    )
                elif entity_type == TYPE_COVER:
                    device = Cover(
                        self._xknx,
                        name,
                        group_address_long=_ga(definition, "updown_address"),
                        group_address_short=_ga(definition, "step_address"),
                        group_address_stop=_ga(definition, "stop_address"),
                        group_address_position=_ga(definition, "position_address"),
                        group_address_position_state=_ga(
                            definition, "position_state_address"
                        ),
                        group_address_angle=_ga(definition, "angle_address"),
                        group_address_angle_state=_ga(
                            definition, "angle_state_address"
                        ),
                        travel_time_down=float(definition.get("travel_time", 25)),
                        travel_time_up=float(definition.get("travel_time", 25)),
                        invert_updown=bool(definition.get("invert_updown", False)),
                        invert_position=bool(definition.get("invert_position", False)),
                        invert_angle=bool(definition.get("invert_angle", False)),
                    )
                elif entity_type == TYPE_CLIMATE:
                    mode = None
                    controller_mode = _ga(definition, "controller_mode_address")
                    operation_mode = _ga(definition, "operation_mode_address")
                    if controller_mode or operation_mode:
                        mode = ClimateMode(
                            self._xknx,
                            f"{name} Mode",
                            group_address_controller_mode=controller_mode,
                            group_address_controller_mode_state=_ga(
                                definition, "controller_mode_state_address"
                            ),
                            group_address_operation_mode=operation_mode,
                            group_address_operation_mode_state=_ga(
                                definition, "operation_mode_state_address"
                            ),
                        )
                        self._xknx.devices.async_add(mode)
                    device = Climate(
                        self._xknx,
                        name,
                        group_address_temperature=_ga(definition, "temperature_address"),
                        group_address_target_temperature=_ga(
                            definition, "target_temperature_address"
                        ),
                        group_address_target_temperature_state=_ga(
                            definition, "target_temperature_state_address"
                        ),
                        group_address_on_off=_ga(definition, "on_off_address"),
                        group_address_on_off_state=_ga(
                            definition, "on_off_state_address"
                        ),
                        min_temp=definition.get("min_temp"),
                        max_temp=definition.get("max_temp"),
                        temperature_step=float(definition.get("temperature_step", 0.5)),
                        mode=mode,
                    )
                elif entity_type == TYPE_SENSOR:
                    device = Sensor(
                        self._xknx,
                        name,
                        group_address_state=_ga(definition, "state_address", "address"),
                        value_type=definition.get("value_type", "temperature"),
                    )
                elif entity_type == TYPE_BINARY_SENSOR:
                    device = BinarySensor(
                        self._xknx,
                        name,
                        group_address_state=_ga(definition, "state_address", "address"),
                        invert=bool(definition.get("invert", False)),
                    )
            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOG.error(
                    "[%s] Failed to build xknx device for '%s' (%s): %s",
                    self.log_id,
                    name,
                    entity_type,
                    err,
                )
                device = None

            if device is not None:
                self._xknx.devices.async_add(device)
            self._xknx_devices[index] = device

    # ------------------------------------------------------------------
    # ExternalClientDevice abstract methods
    # ------------------------------------------------------------------
    async def create_client(self) -> Any:
        async with self._connect_lock:
            from xknx import XKNX

            if self._xknx is not None:
                await self._teardown_xknx()

            self._xknx = XKNX(
                connection_config=self._build_connection_config(),
                device_updated_cb=self._on_device_updated,
                connection_state_changed_cb=self._on_connection_state_changed,
                state_updater="init 60",
            )
            self._build_xknx_devices()
            return self._xknx

    async def connect_client(self) -> None:
        await self._xknx.start()
        self._state = STATE_ON
        self._loop.create_task(self._initial_sync())

    async def disconnect_client(self) -> None:
        async with self._connect_lock:
            await self._teardown_xknx()
        self._state = STATE_UNAVAILABLE

    async def _teardown_xknx(self) -> None:
        if self._xknx is not None:
            try:
                await self._xknx.stop()
            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOG.debug("[%s] Error stopping xknx: %s", self.log_id, err)
            self._xknx = None
        self._xknx_devices = {}

    def check_client_connected(self) -> bool:
        if self._xknx is None:
            return False
        from xknx.core.connection_state import XknxConnectionState

        return (
            self._xknx.connection_manager.state == XknxConnectionState.CONNECTED
        )

    # ------------------------------------------------------------------
    # xknx callbacks (synchronous in xknx 3.x)
    # ------------------------------------------------------------------
    def _on_device_updated(self, _device: Any) -> None:
        self.push_update()

    def _on_connection_state_changed(self, state: Any) -> None:
        from xknx.core.connection_state import XknxConnectionState

        if state == XknxConnectionState.CONNECTED:
            self._state = STATE_ON
        else:
            self._state = STATE_UNAVAILABLE
        self.push_update()

    async def _initial_sync(self) -> None:
        try:
            await self._xknx.devices.sync()
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.debug("[%s] Initial state sync failed: %s", self.log_id, err)

    # ------------------------------------------------------------------
    # Raw telegram sending (used by button entities)
    # ------------------------------------------------------------------
    async def send_group_value(
        self,
        address: str,
        value_type: str | None = None,
        value: Any = None,
    ) -> None:
        """Write a value to an arbitrary group address."""
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
            bit = 0 if value in (0, False, "0", "off", "OFF") else 1
            payload = GroupValueWrite(DPTBinary(bit))

        telegram = Telegram(
            destination_address=GroupAddress(address),
            payload=payload,
        )
        await self._xknx.telegrams.put(telegram)

    async def disconnect(self) -> None:
        await super().disconnect()
        self._state = STATE_UNAVAILABLE
