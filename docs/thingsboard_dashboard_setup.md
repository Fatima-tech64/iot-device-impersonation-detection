# ThingsBoard Dashboard: IoT Device Security Monitor

This is the project dashboard build specification for the telemetry emitted by `src/security_engine/thingsboard.py`. It is designed for a college demonstration: one device alias, simple cards, four time-series charts, and a recent security-event table. Use a clean light background and avoid animation or decorative widgets.

## Dashboard settings

- **Title:** IoT Device Security Monitor
- **Entity alias:** `Project Cloud Device`, fixed to the ThingsBoard device whose access token is in `THINGSBOARD_ACCESS_TOKEN`.
- **Default time window:** Realtime, last 1 hour.
- **Refresh:** 5 seconds (or the nearest refresh interval offered by the tenant).
- **Data model:** This integration authenticates to one ThingsBoard device. Messages from multiple local `device_id` values therefore appear in that device's telemetry; the `device_id` key shows which simulated ID produced each message.

## Suggested layout

| Row | Widget | Data key(s) | Display |
| --- | --- | --- | --- |
| 1 | Value card | `device_id` | Claimed device ID |
| 1 | Value card | `device_status` | Color-coded decision |
| 1 | Value card | `risk_level` | Color-coded level |
| 1 | Value card | `impersonation_detected` | Green false / red true |
| 2 | Value card | `temperature` | °C, 1 decimal |
| 2 | Value card | `humidity` | %, 1 decimal |
| 2 | Value card | `motion` | Boolean state |
| 2 | Gauge | `risk_score` | 0–100, colored risk bands |
| 2 | Value card | `message_frequency` | Hz, 2 decimals |
| 3 | Time-series chart | `temperature` | °C over time |
| 3 | Time-series chart | `humidity` | % over time |
| 4 | Time-series chart | `risk_score` | Risk score over time |
| 4 | Time-series chart | `message_frequency` | Messages/second over time |
| 5 | Time-series table | `device_status`, `risk_score`, `impersonation_detected`, `security_event`, `security_reasons` | Recent decisions and reasons |

Make the four charts equal width in two rows. Keep the event table full width at the bottom. Set its time window to the last hour, newest data first if the widget offers sorting, and leave pagination enabled.

## Status colors

Use these values consistently in data-key color functions:

- Green `#2E7D32`: `TRUSTED`; `LOW` risk; `impersonation_detected=false`.
- Yellow `#F9A825`: `SUSPICIOUS`, `UNKNOWN_DEVICE`, or `MEDIUM` risk.
- Red `#C62828`: `POSSIBLE_IMPERSONATION`, `HIGH_RISK_IMPERSONATION`, `HIGH` risk, `CRITICAL` risk, or `impersonation_detected=true`.
- For a risk-score gauge, set range 0–100 and thresholds 0–29 green, 30–59 yellow, 60–100 red.

Value Card color function for `device_status` (configure as the Value color function):

```javascript
if (value === 'TRUSTED') return '#2E7D32';
if (value === 'SUSPICIOUS' || value === 'UNKNOWN_DEVICE') return '#F9A825';
if (value === 'POSSIBLE_IMPERSONATION' || value === 'HIGH_RISK_IMPERSONATION') return '#C62828';
return '#616161';
```

For `risk_level`:

```javascript
if (value === 'LOW') return '#2E7D32';
if (value === 'MEDIUM') return '#F9A825';
if (value === 'HIGH' || value === 'CRITICAL') return '#C62828';
return '#616161';
```

For `impersonation_detected`:

```javascript
return value === true ? '#C62828' : '#2E7D32';
```

## Build it in ThingsBoard

1. In ThingsBoard, open **Dashboards → + Add dashboard → Create new dashboard**. Name it **IoT Device Security Monitor** and open it in edit mode.
2. Open **Entity aliases** in the dashboard toolbar and add an alias named **Project Cloud Device**. Choose a fixed/single device and select the project device that owns the access token configured in the local `.env`. Save the alias.
3. Add each status and sensor card using **+ Add widget → Cards → Value card**. Set its datasource to **Entity alias → Project Cloud Device**, add the one key listed in the layout table, set the label and units, then configure the value color function where listed. A `device_id` card shows the latest claiming ID, not the ThingsBoard entity name.
4. Add the risk gauge using **+ Add widget → Analogue gauges → Analogue gauge** (or the tenant's equivalent gauge widget). Bind it to `risk_score`, use a 0–100 range, and apply the green/yellow/red thresholds above. If the gauge bundle is unavailable, use a Value card with the same thresholds/colors.
5. Add four charts using **+ Add widget → Charts → Time series chart**. Bind each to the alias and its single key from the layout. Use the dashboard time window and label axes with °C, %, score, and Hz.
6. Add the events table using **+ Add widget → Tables → Time series table**. Bind it to the same alias, use the last-hour time window, and add the five keys from the layout. Label columns **Decision**, **Risk score**, **Impersonation**, **Event**, and **Reasons**. The `security_event` and `security_reasons` telemetry keys are sent for non-`TRUSTED` events, so those cells will be empty on normal readings.
7. Arrange cards in rows 1–2, charts in rows 3–4, and the table in row 5. Use consistent card sizes and titles; leave chart animations and extra decorative widgets disabled.
8. Click **Save** on the dashboard. Start the local broker, the MQTT security engine, and the simulator(s). Confirm data is arriving under the project device's **Latest telemetry**, then return to the dashboard.

## Key availability

`device_id`, `risk_score`, `risk_level`, `device_status`, `impersonation_detected`, and `message_frequency` are included in every cloud assessment. `temperature`, `humidity`, and `motion` are included for schema-valid telemetry. `security_event` and `security_reasons` are included for non-`TRUSTED` classifications only. Message frequency is in Hz; the first sample uses the profile's expected rate and later samples use the measured timestamp interval.
