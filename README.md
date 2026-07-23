# KNX Integration for Unfolded Circle Remote 2/3

Control your **KNX** smart‑home installation directly from your Unfolded Circle Remote 2 or Remote 3 through any **KNX/IP gateway** (interface or router). Enter your gateway's IP, import your entities once, and the integration **auto‑builds native entities** — real **lights** (with dimming/colour), **switches**, **covers**, **climate** thermostats, **sensors**, and a **scenes** selector.

![KNX](https://img.shields.io/badge/KNX-Smart%20Home-blue)
[![GitHub Release](https://img.shields.io/github/v/release/mase1981/uc-intg-knx?style=flat-square)](https://github.com/mase1981/uc-intg-knx/releases)
![License](https://img.shields.io/badge/license-MPL--2.0-blue?style=flat-square)
[![GitHub issues](https://img.shields.io/github/issues/mase1981/uc-intg-knx?style=flat-square)](https://github.com/mase1981/uc-intg-knx/issues)
[![Community Forum](https://img.shields.io/badge/community-forum-blue?style=flat-square)](https://unfolded.community/)
[![Buy Me A Coffee](https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=flat-square)](https://buymeacoffee.com/meirmiyara)
[![PayPal](https://img.shields.io/badge/PayPal-donate-blue.svg?style=flat-square)](https://paypal.me/mmiyara)

## Features

A KNX/IP gateway is a bridge to the bus — it doesn't store your device list. That information lives in your **ETS project**, so you import it once (three easy ways, below) and the integration turns it into proper Unfolded Circle entities:

- **💡 Lights** — on/off, dimming, colour and colour‑temperature (as defined in your project).
- **🔌 Switches** — lights, sockets, and any on/off actuator.
- **🪟 Covers** — blinds/shutters with open/close/stop and position/tilt.
- **🌡️ Climate** — KNX room thermostats (current + target temperature, on/off, heat/cool).
- **📊 Sensors** — temperature, humidity, power, energy, contacts/status — typed from the KNX datapoint type (DPT).
- **🎬 Scenes** — all your KNX scenes in one Select entity.
- **⚡ Real‑time** updates via KNX telegram callbacks, and full **reboot/standby** survival.

Built on [xknx](https://github.com/XKNX/xknx) and [xknxproject](https://github.com/XKNX/xknxproject) — the same libraries used by Home Assistant's KNX integration.

---
## ❤️ Support Development ❤️

If you find this integration useful, consider supporting development:

[![GitHub Sponsors](https://img.shields.io/badge/Sponsor-GitHub-pink?style=for-the-badge&logo=github)](https://github.com/sponsors/mase1981)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/meirmiyara)
[![PayPal](https://img.shields.io/badge/PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white)](https://paypal.me/mmiyara)

Your support helps maintain this integration. Thank you! ❤️
---

## Requirements

- A **KNX/IP gateway** (interface or router — e.g. MDT, Weinzierl, Gira, ISE, Siemens) reachable on your network, with **tunneling** enabled.
- Your KNX entity information, in **one** of these forms (see [Configuration](#configuration)): an ETS **CSV** export, a Home Assistant **KNX YAML** block, or your ETS **`.knxproj`** file.
- Unfolded Circle Remote 2 / 3 with firmware supporting custom integrations.

## Installation

### Option 1: Remote Web Interface (Recommended)

1. Download the latest `uc-intg-knx-<version>.tar.gz` from the [**Releases**](https://github.com/mase1981/uc-intg-knx/releases) page.
2. Open your Remote's web interface (`http://your-remote-ip`).
3. Go to **Settings → Integrations → Add Integration → Install Custom** and upload the `.tar.gz`.

### Option 2: Docker (Advanced — required for the `.knxproj` file method)

```bash
docker run -d --name uc-intg-knx --network host \
  -v $(pwd)/config:/config \
  -e UC_INTEGRATION_HTTP_PORT=9090 \
  ghcr.io/mase1981/uc-intg-knx:latest
```

`--network host` is required so the container can reach your KNX/IP gateway. The mounted `./config` folder is also where you drop a `.knxproj` for the file import method.

## Configuration

Setup asks for your **gateway IP** and a **configuration method**. Pick whichever fits you — all three produce the same native entities; they only differ in effort and grouping accuracy.

| Method | What you provide | Grouping | Works on Remote? |
|---|---|---|---|
| **ETS CSV** (paste) | ETS "Export Group Addresses" → paste the text | Flat (one entity per address, typed by DPT) | ✅ |
| **HA KNX YAML** (paste) | A Home Assistant `knx:` YAML block → paste the text | **Exact** (types + grouping) | ✅ |
| **ETS `.knxproj`** (file/URL) | A URL to your `.knxproj`, or its filename in the Docker config folder | **Richest** (ETS Functions) | ⚠️ Docker/URL only |

> Why three? UC's setup only supports text fields (no file upload), so binary `.knxproj` files can't be uploaded on the Remote. Pasting CSV or YAML works everywhere; `.knxproj` is offered for Docker users (mounted file) or anyone who can host it at a URL.

### Method A — ETS CSV (easiest)

1. In **ETS**: **Group Addresses** view → right‑click the top node → **Export Group Addresses…** → **CSV** (3‑level; include the **Datapoint Type** column for best results).
2. Open the `.csv`, copy all, and paste it into the setup field.

CSV is a flat list, so each address becomes its own entity (a dimmable light may appear as a separate switch + dimmer). For fully grouped entities, use YAML or `.knxproj`.

### Method B — Home Assistant KNX YAML (most accurate paste)

If you already run Home Assistant with KNX, paste your existing `knx:` config — the exact same schema is understood, e.g.:

```yaml
knx:
  light:
    - name: "Kitchen"
      address: "1/1/1"
      state_address: "1/1/2"
      brightness_address: "1/1/3"
      brightness_state_address: "1/1/4"
  cover:
    - name: "Living Blind"
      move_long_address: "2/1/1"
      stop_address: "2/1/2"
      position_address: "2/1/3"
      position_state_address: "2/1/4"
  climate:
    - name: "Thermostat"
      temperature_address: "3/1/1"
      target_temperature_address: "3/1/2"
      on_off_address: "3/1/4"
  sensor:
    - name: "Outside Temp"
      state_address: "3/2/1"
      type: "temperature"
  scene:
    - name: "Movie"
      address: "5/1/1"
      scene_number: 5
```

Supported platforms: `light`, `switch`, `cover`, `climate`, `sensor`, `binary_sensor`, `scene`. The `knx:` wrapper is optional.

### Method C — ETS `.knxproj` (richest, Docker/URL)

Provides the best grouping because it reads your ETS **Functions**. Since it's a binary file it can't be pasted on the Remote:

- **Docker:** copy your `project.knxproj` into the mounted `./config` folder and enter its filename.
- **URL:** host the `.knxproj` somewhere reachable (e.g. a raw link) and paste the URL.

Enter the project **password** if it's encrypted. Parsed with the `xknxproject` library.

## Using the Integration

After setup, your entities appear natively on the Remote — add them to pages and Activities like any other:

- **Lights** with power + brightness (and colour where available)
- **Covers** with open/close/stop and a position slider
- **Climate** thermostats with current/target temperature
- **Sensors** on dashboards
- The **Scenes** selector to recall any KNX scene

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Nothing could be imported" | Check the pasted text (CSV needs an address column; YAML needs valid `knx:` platforms). |
| Sensors show odd values | Export the ETS CSV **with the DPT column**, or use YAML/`.knxproj` so types are known. |
| A dimmable light shows as two entities | Expected with CSV (flat). Use YAML or `.knxproj` for grouped entities. |
| `.knxproj` "not found" | On the Remote there's no filesystem — use Docker with a mounted config folder, or provide a URL. |
| Cannot connect | Verify the gateway IP and that it has a free **tunneling** channel on your network. |

## Credits

- **Developer**: Meir Miyara
- **KNX**: Built on [xknx](https://github.com/XKNX/xknx) and [xknxproject](https://github.com/XKNX/xknxproject).
- **Unfolded Circle**: Remote 2/3 integration framework ([ucapi](https://github.com/unfoldedcircle/integration-python-library) / [ucapi-framework](https://github.com/JackJPowell/ucapi-framework)).

## License

Mozilla Public License 2.0 (MPL‑2.0) — see the LICENSE file.

## Support & Community

- **GitHub Issues**: [Report bugs and request features](https://github.com/mase1981/uc-intg-knx/issues)
- **UC Community Forum**: [General discussion and support](https://unfolded.community/)
- **Developer**: [Meir Miyara](https://www.linkedin.com/in/meirmiyara)

---

**Made with ❤️ for the Unfolded Circle Community**

**Thank You**: Meir Miyara
