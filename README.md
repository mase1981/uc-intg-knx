# KNX Hub — Unfolded Circle Integration

Control a [KNX](https://www.knx.org/) smart-home installation from your Unfolded
Circle Remote Two/3 through any KNX/IP gateway (router or interface). The
integration talks native KNXnet/IP using the [xknx](https://xknx.io/) library —
the same engine that powers Home Assistant's KNX component — and exposes your
devices to the Remote as switches, lights, covers, climate, sensors, and scene
buttons.

Because KNX has no concept of auto-discoverable "devices" (functions are defined
by group addresses in your ETS project), you describe the entities you want as a
small JSON list during setup. See [Entity Definitions](#entity-definitions).

## Features

- **Connection types**: Automatic gateway discovery, Tunneling (UDP), Tunneling
  (TCP), and Routing (multicast).
- **Entity types**: `switch`, `light` (on/off, dimming, color, color temperature),
  `cover` (position + tilt), `climate` (thermostat), `sensor`, `binary_sensor`,
  and `button` (scene / group-address trigger).
- **Real-time updates**: State changes on the KNX bus are pushed to the Remote
  instantly via telegram callbacks — no polling lag.
- **Reboot & standby survival**: Configuration and entities are restored
  automatically after a Remote reboot or resume from standby.

## Requirements

- A KNX/IP gateway (interface or router) reachable on your network.
- The group addresses for the functions you want to control (from your ETS
  project or KNX documentation).
- Unfolded Circle Remote Two/3 with firmware supporting custom integrations.

## Installation

### Remote (recommended)

1. Download the latest `uc-intg-knx-*.tar.gz` from the
   [Releases](https://github.com/mase1981/uc-intg-knx/releases) page.
2. In the Remote web configurator, go to **Integrations → Add → Install Custom**
   and upload the archive.
3. Start the setup and follow [Configuration](#configuration).

### Docker

```bash
docker run -d --name uc-intg-knx --network host \
  -v $(pwd)/config:/config \
  -e UC_INTEGRATION_HTTP_PORT=9090 \
  ghcr.io/mase1981/uc-intg-knx:latest
```

`--network host` is required so the container can send/receive KNX multicast and
reach the gateway.

## Configuration

On the setup screen you provide:

| Field | Description |
|-------|-------------|
| **Gateway Name** | A friendly name for this KNX hub. |
| **Connection Type** | `automatic`, `tunneling`, `tunneling_tcp`, or `routing`. |
| **Gateway IP** | The gateway's IP. Required for tunneling; leave blank for automatic/routing. |
| **Gateway Port** | KNXnet/IP port (default `3671`). |
| **Local IP** | Optional — the local interface to bind. Useful with multiple NICs/VPN. |
| **Route Back** | Set to *Yes* only for NAT/VPN tunneling scenarios. |
| **Individual Address** | Routing only — the integration's own bus address (e.g. `1.0.255`). |
| **Entities** | A JSON array describing the entities to expose (below). |

## Entity Definitions

The **Entities** field takes a JSON array. Each element is an object with a
`type`, a `name`, and the group addresses for that function. Group addresses use
the standard 3-level notation (`main/middle/sub`, e.g. `1/2/3`).

`*_state` / `*_state_address` fields are the **status** group addresses the KNX
device sends its current value on. Provide them wherever available so the Remote
reflects real state; without them the integration still sends commands but can't
show live status.

### switch

```json
{ "type": "switch", "name": "Office Lamp", "address": "1/1/1", "state_address": "1/1/2" }
```

| Field | Required | Notes |
|-------|----------|-------|
| `address` | yes | On/off write GA (DPT 1). |
| `state_address` | no | Status GA. |
| `invert` | no | `true` to invert on/off. |

### light

```json
{
  "type": "light", "name": "Kitchen Ceiling",
  "address": "1/2/1", "state_address": "1/2/2",
  "brightness_address": "1/2/3", "brightness_state_address": "1/2/4",
  "color_temp_address": "1/2/5", "color_temp_state_address": "1/2/6",
  "min_kelvin": 2700, "max_kelvin": 6500
}
```

| Field | Notes |
|-------|-------|
| `address` / `state_address` | On/off switch GA (+ status). |
| `brightness_address` / `brightness_state_address` | Dimming (DPT 5, 0–255). Enables dimming. |
| `color_temp_address` / `color_temp_state_address` | Color temperature in Kelvin. |
| `hue_address` / `saturation_address` (+ `*_state_address`) | HS color. |
| `color_address` / `color_state_address` | RGB color (DPT 232.600). |
| `min_kelvin` / `max_kelvin` | Kelvin range for color-temperature mapping (default 2700–6500). |

### cover

```json
{
  "type": "cover", "name": "Living Blinds", "device_class": "blind",
  "updown_address": "2/1/1", "stop_address": "2/1/2", "step_address": "2/1/3",
  "position_address": "2/1/4", "position_state_address": "2/1/5",
  "angle_address": "2/1/6", "angle_state_address": "2/1/7"
}
```

| Field | Notes |
|-------|-------|
| `updown_address` | Long move up/down (DPT 1). |
| `stop_address` | Stop GA. |
| `step_address` | Short step (slat tilt) GA. |
| `position_address` / `position_state_address` | Absolute position (DPT 5, 0–100). |
| `angle_address` / `angle_state_address` | Slat angle/tilt. |
| `device_class` | `blind`, `curtain`, `garage`, `shade`, `door`, `gate`, `window`. |
| `travel_time` | Seconds of travel for position estimation (default 25). |
| `invert_updown` / `invert_position` / `invert_angle` | Optional inversions. |

### climate

```json
{
  "type": "climate", "name": "Living Thermostat",
  "temperature_address": "3/1/1",
  "target_temperature_address": "3/1/2", "target_temperature_state_address": "3/1/3",
  "on_off_address": "3/1/4", "on_off_state_address": "3/1/5",
  "controller_mode_address": "3/1/6", "controller_mode_state_address": "3/1/7",
  "min_temp": 7, "max_temp": 35, "temperature_step": 0.5
}
```

| Field | Notes |
|-------|-------|
| `temperature_address` | Current temperature (read). |
| `target_temperature_address` (+ `*_state_address`) | Setpoint. |
| `on_off_address` (+ `*_state_address`) | On/off control. |
| `controller_mode_address` (+ `*_state_address`) | HVAC controller mode (DPT 20.105) — enables Heat/Cool. |
| `operation_mode_address` (+ `*_state_address`) | Operation mode (comfort/standby/…). |
| `min_temp` / `max_temp` / `temperature_step` | Setpoint limits and step. |

### sensor

```json
{ "type": "sensor", "name": "Living Temp", "state_address": "4/1/1", "value_type": "temperature", "device_class": "temperature" }
```

| Field | Notes |
|-------|-------|
| `state_address` | Status GA to read. |
| `value_type` | xknx DPT name, e.g. `temperature`, `humidity`, `illuminance`, `power`, `percent`, `voltage`, `current`, `energy`. |
| `device_class` | Optional Remote sensor class: `temperature`, `humidity`, `power`, `energy`, `current`, `voltage`, `battery`. |

### binary_sensor

```json
{ "type": "binary_sensor", "name": "Front Door", "state_address": "4/2/1", "invert": false }
```

### button

Writes a value to a group address on press — ideal for scenes or triggers.

```json
{ "type": "button", "name": "Movie Scene", "address": "5/1/1", "value_type": "scene_number", "value": 5 }
```

| Field | Notes |
|-------|-------|
| `address` | GA to write. |
| `value_type` | Optional DPT name. Omit to send a simple on-bit (DPT 1). |
| `value` | Value to send (default `1`). For scenes use `value_type: "scene_number"`. |

### Full example

```json
[
  {"type":"light","name":"Kitchen","address":"1/2/1","state_address":"1/2/2","brightness_address":"1/2/3","brightness_state_address":"1/2/4"},
  {"type":"switch","name":"Fan","address":"1/1/1","state_address":"1/1/2"},
  {"type":"cover","name":"Blinds","updown_address":"2/1/1","stop_address":"2/1/2","position_address":"2/1/4","position_state_address":"2/1/5"},
  {"type":"climate","name":"Thermostat","temperature_address":"3/1/1","target_temperature_address":"3/1/2","target_temperature_state_address":"3/1/3","on_off_address":"3/1/4","on_off_state_address":"3/1/5"},
  {"type":"sensor","name":"Outdoor Temp","state_address":"4/1/1","value_type":"temperature","device_class":"temperature"},
  {"type":"binary_sensor","name":"Front Door","state_address":"4/2/1"},
  {"type":"button","name":"Movie Scene","address":"5/1/1","value_type":"scene_number","value":5}
]
```

## Troubleshooting

- **No state shown** — provide the `*_state_address` group addresses; without them
  the integration can command devices but cannot read their status.
- **Cannot connect (tunneling)** — verify the Gateway IP/port and that the gateway
  has a free tunneling channel. Try `automatic` to confirm discovery works.
- **Routing not working** — ensure `--network host` (Docker) and that multicast
  `224.0.23.12:3671` is allowed on your network.

## Support

If this integration is useful to you, consider supporting development:

- [Buy Me a Coffee](https://buymeacoffee.com/meirmiyara)
- [PayPal](https://paypal.me/mmiyara)

## Acknowledgements

Built on [xknx](https://github.com/XKNX/xknx) and the
[ucapi-framework](https://github.com/JackJPowell/ucapi-framework).

**Author**: Meir Miyara
