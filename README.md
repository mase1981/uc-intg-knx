# KNX Integration for Unfolded Circle Remote 2/3

Control your **KNX** smart-home installation directly from your Unfolded Circle Remote 2 or Remote 3 through any **KNX/IP gateway** (interface or router). Enter your gateway's IP address, paste your ETS group-address export, and the integration **auto-builds all your entities** — a Remote for switches/lights/blinds, Selects for scenes, and Sensors for feedback.

![KNX](https://img.shields.io/badge/KNX-Smart%20Home-blue)
[![GitHub Release](https://img.shields.io/github/v/release/mase1981/uc-intg-knx?style=flat-square)](https://github.com/mase1981/uc-intg-knx/releases)
![License](https://img.shields.io/badge/license-MPL--2.0-blue?style=flat-square)
[![GitHub issues](https://img.shields.io/github/issues/mase1981/uc-intg-knx?style=flat-square)](https://github.com/mase1981/uc-intg-knx/issues)
[![Community Forum](https://img.shields.io/badge/community-forum-blue?style=flat-square)](https://unfolded.community/)
[![Buy Me A Coffee](https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=flat-square)](https://buymeacoffee.com/meirmiyara)
[![PayPal](https://img.shields.io/badge/PayPal-donate-blue.svg?style=flat-square)](https://paypal.me/mmiyara)

## Features

Because a KNX/IP gateway is a bridge to the bus and does not store your device list, the integration reads that information from the **ETS group-address export** you paste during setup. From it, it automatically creates the right Unfolded Circle entities:

- **🎛️ Remote** — every switch, dimmable light, and blind/shutter becomes a command on a single Remote entity, with generated on-screen pages. Use it directly or drop the commands into your Activities.
- **🎬 Scene Select** — all your KNX scenes in one Select entity; pick a scene to recall it.
- **🌡️ Sensors** — temperatures, humidity, power, status/feedback, contacts and more, each typed automatically from its KNX datapoint type (DPT).
- **⚡ Real-time updates** — status changes on the KNX bus are pushed to the Remote instantly via telegram callbacks, no polling lag.
- **🔌 Zero maintenance** — configuration and entities survive Remote reboots and standby automatically.

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
- Your **ETS project's group addresses**, exported as CSV (below). No ETS software is needed on the Remote — you only export once.
- Unfolded Circle Remote 2 / 3 with firmware supporting custom integrations.

## Installation

### Option 1: Remote Web Interface (Recommended)

1. Download the latest `uc-intg-knx-<version>.tar.gz` from the [**Releases**](https://github.com/mase1981/uc-intg-knx/releases) page.
2. Open your Remote's web interface (`http://your-remote-ip`).
3. Go to **Settings → Integrations → Add Integration → Install Custom** and upload the `.tar.gz`.

### Option 2: Docker (Advanced)

```bash
docker run -d --name uc-intg-knx --network host \
  -v $(pwd)/config:/config \
  -e UC_INTEGRATION_HTTP_PORT=9090 \
  ghcr.io/mase1981/uc-intg-knx:latest
```

`--network host` is required so the container can reach your KNX/IP gateway.

## Configuration

Setup is a **single screen** with two things to fill in:

| Field | What to enter |
|-------|---------------|
| **Gateway IP address** | The IP of your KNX/IP gateway (e.g. `192.168.1.10`). |
| **ETS Group Address export** | Paste your ETS group-address CSV (see below). |

That's it — press **Complete** and the integration connects and builds your entities.

### How to export your group addresses from ETS

1. In **ETS**, open your project and go to the **Group Addresses** view.
2. Right-click the top **Group Addresses** node → **Export Group Addresses…**
3. Choose **CSV** as the format. For best results, keep the **3-level** address style and include the **Datapoint Type (DPT)** column (this lets the integration type your sensors correctly).
4. Open the exported `.csv` in a text editor, **select all**, copy, and **paste it** into the *ETS Group Address export* field during setup.

> **Tip:** The integration is tolerant of ETS's CSV/TSV variations and DPT formats (`1.001`, `DPST-1-1`, `DPT-9`). If the export has no DPT column, entities are still created using name heuristics — but including the DPT column gives the most accurate results.

### What gets created

| KNX datapoint (DPT) | Becomes |
|---------------------|---------|
| Switching (1.001), controls | A command on the **Remote** (On / Off / Toggle) |
| Dimming value (5.x) | Remote brightness commands (Off / 25 / 50 / 75 / 100 %) |
| Up/Down, blinds (1.008, 3.x) | Remote **Open / Close / Stop** commands |
| Status / feedback (1.001 named "…status") | A **binary Sensor** |
| Measurements (9.x, 12–14, 7.x…) | A **Sensor**, typed and with units |
| Scene (17.x / 18.x) | An option in the **Scenes** Select |

Controls are aggregated into **one Remote** entity (so a dimmable light appears as its set of commands rather than a separate Light entity). Each command is labeled from your ETS names, so `Kitchen Light Switch` → `KITCHEN_LIGHT_SWITCH_ON` / `_OFF` / `_TOGGLE`.

## Using the Integration

- **Remote entity** — add it to an Activity or open it directly. Its on-screen pages and command list are generated from your import; use the commands (e.g. `LIVING_BLIND_UPDOWN_OPEN`) in Activity sequences and macros.
- **Scenes Select** — expose it on a page or Activity to recall any KNX scene.
- **Sensors** — surface temperatures, humidity, power and contact/status feedback on your dashboards.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "No group addresses found" | Make sure you pasted the **CSV** export (with the group `Address` column), not an empty selection. |
| Sensors show odd values | Re-export from ETS **with the DPT column** so the integration can decode each value correctly. |
| Cannot connect | Verify the gateway IP and that it has a free **tunneling** channel; the Remote/host must be on the same network. |
| A control didn't appear | Only switching/dimming/blind datapoints become controls. Read-only measurement addresses become Sensors instead. |

## Credits

- **Developer**: Meir Miyara
- **KNX / xknx**: Built on the [xknx](https://github.com/XKNX/xknx) library (the same engine used by Home Assistant's KNX integration).
- **Unfolded Circle**: Remote 2/3 integration framework ([ucapi](https://github.com/unfoldedcircle/integration-python-library) / [ucapi-framework](https://github.com/JackJPowell/ucapi-framework)).

## License

This project is licensed under the Mozilla Public License 2.0 (MPL-2.0) — see the LICENSE file for details.

## Support & Community

- **GitHub Issues**: [Report bugs and request features](https://github.com/mase1981/uc-intg-knx/issues)
- **UC Community Forum**: [General discussion and support](https://unfolded.community/)
- **Developer**: [Meir Miyara](https://www.linkedin.com/in/meirmiyara)

---

**Made with ❤️ for the Unfolded Circle Community**

**Thank You**: Meir Miyara
