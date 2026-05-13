# Easee Charge MAX — Home Assistant Integration

A [Home Assistant](https://www.home-assistant.io/) custom integration for the [Easee Charge MAX](https://easee.com/en/products/ev-chargers/charge-max/) EV charger.

Provides full local control and monitoring through the [Easee Cloud REST API](https://developer.easee.com/docs/integrations) — no additional hardware or broker required.

> **API source**: command logic and payload shapes are ported from the open-source [evcc](https://github.com/evcc-io/evcc) Go implementation (`charger/easee/`).

---

## Features

| Entity | Platform | Description |
|---|---|---|
| **Start Charging** | `button` | Send `start_charging` command |
| **Stop Charging** | `button` | Send `stop_charging` command |
| **Pause Charging** | `button` | Send `pause_charging` command |
| **Resume Charging** | `button` | Send `resume_charging` command |
| **Charger Enabled** | `switch` | Enable / disable the charger hardware |
| **Smart Charging** | `switch` | Smart charging mode (LED turns blue) |
| **Charging Current** | `number` | Real-time current limit 6–32 A (slider); auto-capped at hardware max |
| **Max Charger Current (Hardware Limit)** | `number` | Persistent hardware max stored on the charger |
| **Phase Mode** | `select` | `1-phase` (≤ 7.4 kW) or `Auto (3-phase)` (≤ 22 kW) |
| **Charger Status** | `sensor` | Op-mode: Disconnected / Awaiting Start / Charging / Completed / … |
| **Charging Power** | `sensor` | Active power (W) |
| **Session Energy** | `sensor` | Energy delivered this session (kWh) |
| **Lifetime Energy** | `sensor` | Total lifetime energy (kWh) |
| **Current L1 / L2 / L3** | `sensor` × 3 | Per-phase current (A) |
| **Circuit Current P1 / P2 / P3** | `sensor` × 3 | Dynamic circuit allocation per phase (A) |
| **Voltage** | `sensor` | Supply voltage (V) |
| **Cable Rating** | `sensor` | Detected cable max current (A) |
| **Dynamic Charger Current** | `sensor` | Currently applied dynamic limit (A) |
| **Reason for No Current** | `sensor` | Numeric reason code when not charging |
| **Online** | `sensor` | Whether the charger is reachable from cloud |

### Phase switching

When a TN-grid single-charger circuit is detected (same logic as evcc `determineCircuit()`), phase switching uses **circuit-level** `dynamicCircuitCurrentP1/P2/P3` — the correct approach for shared-circuit installations. Otherwise the charger-level `phaseMode` setting is used.

---

## Requirements

- Home Assistant **2024.1** or newer
- Python **3.11+** (bundled with HA)
- An [Easee](https://easee.com/) account with at least one Charge MAX charger
- Internet access from HA (Easee Cloud API)

---

## Installation

### Option A — HACS (recommended)

1. Open HACS → **Integrations** → ⋮ → **Custom repositories**
2. Add `https://github.com/RafyK/ha-easee-charge-max`, category **Integration**
3. Search for **Easee Charge MAX** and click **Download**
4. Restart Home Assistant

### Option B — Manual

1. Download or clone this repository
2. Copy the `custom_components/easee_charge_max/` folder into your HA config directory:
   ```
   <config>/custom_components/easee_charge_max/
   ```
3. Restart Home Assistant

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Easee Charge MAX**
3. Enter your Easee account **email** and **password**
4. Leave **Charger ID** blank for auto-detection (works if you have one charger on the account), or enter the charger serial number (visible in the Easee app)
5. If multiple chargers are found a picker is shown

---

## How it works

### Authentication

`POST https://api.easee.com/api/accounts/login` returns a short-lived JWT and a refresh token. The client automatically refreshes 60 s before expiry and falls back to full re-login if refresh fails — identical to evcc `identity.go`.

### Commands

```
POST /api/chargers/{id}/commands/start_charging
POST /api/chargers/{id}/commands/stop_charging
POST /api/chargers/{id}/commands/pause_charging
POST /api/chargers/{id}/commands/resume_charging
```

The API returns HTTP `200` (already applied) or `202` (async, charger will apply shortly). Both are treated as success.

### Setting current

```
POST /api/chargers/{id}/settings
{ "dynamicChargerCurrent": 16.0 }   ← real-time, resets on reboot
{ "maxChargerCurrent": 20 }          ← persistent hardware limit
```

The **Charging Current** slider is automatically capped at `maxChargerCurrent`, matching evcc's `MaxCurrent()` clamping logic.

### Setting phase mode

```
POST /api/chargers/{id}/settings
{ "phaseMode": 1 }   ← 1-phase
{ "phaseMode": 2 }   ← auto / 3-phase

# Or for TN-grid single-charger circuits:
POST /api/sites/{siteId}/circuits/{circuitId}/settings
{ "dynamicCircuitCurrentP1": 32, "dynamicCircuitCurrentP2": 0, "dynamicCircuitCurrentP3": 0 }  ← 1-phase
{ "dynamicCircuitCurrentP1": 32, "dynamicCircuitCurrentP2": 32, "dynamicCircuitCurrentP3": 32 } ← 3-phase
```

### Polling

State (`/chargers/{id}/state`) and config (`/chargers/{id}/config`) are polled every **30 seconds**. For real-time push updates a SignalR WebSocket connection would be needed (as evcc implements); that is not included here.

---

## Automation examples

### Limit charging to 8 A on high electricity price

```yaml
automation:
  - alias: "Easee: reduce current on expensive tariff"
    trigger:
      - platform: state
        entity_id: sensor.electricity_price
        to: "high"
    action:
      - service: number.set_value
        target:
          entity_id: number.easee_charging_current
        data:
          value: 8
```

### Start charging when solar exceeds 3 kW

```yaml
automation:
  - alias: "Easee: start on solar surplus"
    trigger:
      - platform: numeric_state
        entity_id: sensor.solar_power
        above: 3000
        for: "00:02:00"
    action:
      - service: button.press
        target:
          entity_id: button.easee_start_charging
```

### Switch to 1-phase at night

```yaml
automation:
  - alias: "Easee: 1-phase overnight"
    trigger:
      - platform: time
        at: "23:00:00"
    action:
      - service: select.select_option
        target:
          entity_id: select.easee_phase_mode
        data:
          option: "1-phase"
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "Invalid auth" at setup | Check email/password in the Easee app |
| Cannot connect | HA needs outbound HTTPS to `api.easee.com` |
| Charger not found | Enter the serial number manually (visible in Easee app → charger settings) |
| Commands have no effect | The charger may be offline (`sensor.easee_online = false`). Check Easee app. |
| Phase switching does nothing | Verify your installation supports phase switching; some grids do not |
| State is stale by up to 30 s | Expected — REST polling interval. Restart HA after a long outage to force immediate re-poll |

---

## License

MIT — see [LICENSE](LICENSE)
