# IoT Device Impersonation Detection and Behaviour-Based Security Monitoring System

A beginner-friendly college project that simulates an IoT monitoring system and detects when a device claims to be a registered sensor but sends an unexpected identity or implausible behaviour. The security engine evaluates incoming telemetry, assigns a trust score, and can trigger a local simulated alert (LED/buzzer) while forwarding monitoring data to ThingsBoard.

## Requirements analysis

- **Real-life use case:** monitor a room or restricted area using environmental and motion telemetry, while identifying unauthorized devices that try to pose as registered sensors.
- **Sensors:** DHT11 temperature/humidity and PIR motion provide two sensor types. A third sensor can be added later if needed; two satisfy the stated minimum.
- **Actuator:** simulated LED and/or buzzer response when a device is rejected or its trust becomes low.
- **IoT and cloud path:** simulated ESP32 publishes MQTT telemetry; the Python security engine validates it, then sends accepted telemetry and security status to ThingsBoard.
- **Simulation:** Wokwi (or a simple Python publisher) can represent the ESP32 and sensors. This avoids requiring physical hardware for the demonstration.
- **Difficulty and scope:** use explicit identity checks, understandable behaviour rules, and a small trust-score calculation. No machine learning is needed.

## Proposed architecture

```text
Wokwi ESP32 simulation
  ├─ DHT11: temperature and humidity
  └─ PIR: motion state
       │ MQTT telemetry
       ▼
MQTT broker (local/public broker for development)
       │
       ▼
Python security engine
  ├─ Parse and validate message schema
  ├─ Verify device identity against a registered-device list
  ├─ Check simple behaviour rules (for example, valid ranges and plausible update rate)
  ├─ Update a trust score and record a decision/reason
  ├─ Forward approved telemetry and security status to ThingsBoard
  └─ Pass the decision to a simulated actuator adapter
       │
       ├─ LED response: green, yellow, or red
       └─ Buzzer response: off, brief pulse, or on
```

The MQTT broker is the transport layer; it does not prove that a device is genuine. The security engine should treat the claimed device ID as untrusted input and compare it with configured registrations. A later implementation should use per-device credentials where supported and explain that a copied ID alone is not strong authentication. Keep the demo's identity check and behavioural checks separate so their decisions can be demonstrated independently.

### Initial message and checks (implementation guidance)

A telemetry message can include `device_id`, `temperature`, `humidity`, `motion`, and a timestamp. Identity verification checks whether `device_id` is registered (and, once configured, whether its credentials/client identity match). Behaviour verification applies a few visible rules, such as numeric sensor ranges, expected fields, and an allowed reporting interval. The trust score can start at a configured value, decrease by a fixed amount for each failed check, and recover slowly after valid messages. Define thresholds and actions explicitly in the implementation; this README does not prescribe a production security design.

Use distinct MQTT topics for simulated device input and security-engine output. The local actuator adapter represents LED and buzzer commands in the console; a future simulator bridge can implement the same interface to drive a simulated ESP32. Keep broker credentials and ThingsBoard access tokens in the local `.env` file; never commit real secrets.

## Planned project structure

```text
.
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── config/
│   └── device_registry.json       # editable registered-device profiles
├── docs/
│   ├── architecture.md            # optional detailed diagrams/demo notes
│   └── thingsboard_dashboard_setup.md # exact dashboard layout and setup guide
├── simulator/
│   ├── __init__.py
│   ├── demo_controller.py        # run deterministic local demo scenarios
│   ├── device_simulator/          # Python MQTT simulator (implemented)
│   │   ├── config.py
│   │   ├── sensors.py
│   │   ├── payload.py
│   │   ├── publisher.py
│   │   └── main.py
│   ├── impersonation_simulator/  # safe synthetic MQTT scenarios
│   │   ├── __init__.py
│   │   ├── scenarios.py
│   │   └── main.py
│   └── wokwi/                     # optional Wokwi project files
├── src/
│   └── security_engine/
│       ├── __init__.py
│       ├── device_registry.py     # registry loading, lookup, validation
│       ├── behaviour.py           # profile-based telemetry checks
│       ├── impersonation_detector.py # classification and security events
│       ├── risk_scoring.py        # weighted risk points and levels
│       ├── main.py                # application startup and wiring
│       ├── mqtt_client.py         # MQTT subscribe/publish boundary
│       ├── message_schema.py      # telemetry parsing and basic validation
│       ├── engine.py              # processing pipeline and event log
│       ├── thingsboard.py         # optional ThingsBoard MQTT publisher
│       ├── identity.py            # registered identity checks
│       ├── trust.py               # trust-score updates and thresholds
│       ├── actuator.py            # simulated LED/buzzer response
│       └── thingsboard.py         # cloud telemetry integration
└── tests/
    ├── test_device_simulator.py   # offline simulator checks
    ├── test_device_registry.py    # registry loading/validation checks
    ├── test_behaviour.py         # profile behaviour checks
    ├── test_impersonation_detector.py # detection classifications
    ├── test_risk_scoring.py      # weighted score and level checks
    ├── test_impersonation_simulator.py # safe scenario generator checks
    ├── test_security_engine_integration.py # offline pipeline/log tests
    ├── test_identity.py           # detection checks (future work)
    └── test_trust.py
```

The Python device simulator is implemented under `simulator/device_simulator/`. The editable device registry is in `config/device_registry.json`, with loading and validation functions in `src/security_engine/device_registry.py`. The registry, behaviour verifier, risk scorer, impersonation detector, and MQTT-connected local security engine are implemented. Wokwi assets and cloud integration remain future work.

## Demonstration scenarios

Run one deterministic, safe scenario from the project root:

```powershell
py -m simulator.demo_controller NORMAL_OPERATION
py -m simulator.demo_controller UNKNOWN_DEVICE
py -m simulator.demo_controller SENSOR_ANOMALY
py -m simulator.demo_controller TRAFFIC_ANOMALY
py -m simulator.demo_controller DEVICE_IMPERSONATION
```

The controller prints the scenario, synthetic behaviour, detection classification, risk score, and rule reasons. It evaluates two timestamped sample messages locally through the project's existing registry and detection engine; it does not require a broker and does not send MQTT or cloud telemetry. The scenario thresholds are set to keep single sensor/traffic anomalies at `SUSPICIOUS` and combined deviations at possible/high-risk impersonation indicators. Risk weights are unchanged. For the MQTT end-to-end demonstration, run `py -m src.security_engine.main` and use the existing device or safe impersonation simulator in another terminal.

## Configuration

1. Copy `.env.example` to `.env` and set broker and ThingsBoard values for your chosen simulation setup.
2. Keep `.env` local; `.gitignore` excludes it.
3. Edit `config/device_registry.json` to add or update registered device profiles. The registry module loads and validates this file; it does not make message-time security decisions.

## Python dependencies

`requirements.txt` contains only the MQTT client and environment-variable loader. ThingsBoard can receive telemetry over MQTT using the same client library; avoid adding a web framework or ML libraries for this project.

## Suggested implementation order

1. Decide the MQTT broker and ThingsBoard instance, then create the Wokwi ESP32 simulation and publish one well-formed telemetry message.
2. Build the message schema parser and MQTT subscriber; print received messages before adding security decisions.
3. Add a small registered-device configuration and identity verification. Demonstrate a registered ID and an unknown/spoofed ID.
4. Add simple behaviour rules, then the transparent trust-score update and clear decision reasons.
5. Add simulated LED/buzzer alerts and ThingsBoard publishing/dashboard widgets for sensor values, trust, and security events.
6. Add focused tests and rehearse normal, impersonation, and abnormal-behaviour demonstrations.


## IoT device simulator (implemented)

The first implementation step is a Python MQTT simulator for one ESP32-style environment sensor. It generates gently varying DHT11 temperature/humidity readings and occasional PIR motion events, then publishes JSON periodically. The default device ID is `IOT-001`, and its topic is `iot/devices/IOT-001/telemetry`.

### Start the simulator

1. Install Python dependencies from the project root:

   ```powershell
   py -m pip install -r requirements.txt
   ```

2. Start an MQTT broker that is reachable from this computer. For a local Mosquitto broker, the default host and port are `localhost:1883`.
3. Copy `.env.example` to `.env` and set `MQTT_HOST`, `MQTT_PORT`, and optional broker credentials. Set `SIM_DEVICE_ID` and `SIM_PUBLISH_INTERVAL` as needed.
4. From the project root, run:

   ```powershell
   py -m simulator.device_simulator.main
   ```

The console prints each published JSON message. Press **Ctrl+C** to stop; the simulator disconnects from MQTT. For another simulator instance, use a distinct `SIM_DEVICE_ID` (for example, `IOT-002`) and a different MQTT client ID is generated automatically.

Run the offline checks from the project root with:

```powershell
py -m unittest tests.test_device_simulator -v
```

The simulator only publishes telemetry. It does not perform identity detection, trust scoring, actuator control, ThingsBoard integration, or dashboard work.






## Behaviour verification (implemented)

`src/security_engine/behaviour.py` provides `BehaviorVerifier`, an offline, rule-based checker. Pass a loaded `DeviceRegistry` to the constructor, then call `verify(telemetry)` for each parsed message. It returns the device ID, five boolean checks, `behaviour_score`, and `status`. The caller should reuse one verifier instance so it can compare each device's timestamp with its previous message.

Scoring is deliberately transparent: identity, temperature range, humidity range, message interval, and motion behaviour are each worth 20 points. A passing check adds 20; a failed or unevaluable check adds 0. Only a score of 100 is `NORMAL`; any lower score is `SUSPICIOUS` (so one failed check yields 80). Unknown devices have no profile for comparison, so identity and all profile-dependent checks fail, yielding 0.

Temperature and humidity ranges include their endpoints. Message intervals are accepted within ±50% of the profile's expected interval; the first valid timestamp establishes a baseline and passes because there is no earlier interval to compare. Timestamps must be ISO 8601 with a timezone. `intermittent` accepts either boolean motion value; `usually_inactive` requires `false` and `frequent` requires `true`. These motion rules evaluate each message against the configured expectation; they are intentionally simple for the college demonstration.

Run the focused checks with:

```powershell
py -m unittest tests.test_behaviour -v
```

## Impersonation detection (implemented)

`src/security_engine/impersonation_detector.py` combines the registered-device lookup with `BehaviorVerifier` results and returns a structured event containing the device ID, classification, risk score, reasons, timestamp, and detailed behaviour checks. Classifications indicate observed risk; they do not prove a device is malicious.

The defaults are intentionally easy to explain:

- `TRUSTED`: registered profile is trusted and all five behaviour checks pass.
- `UNKNOWN_DEVICE`: device ID is absent from the registry. Its risk score comes from the identity weight; sensor factors are not scored without a trusted profile.
- `POSSIBLE_IMPERSONATION`: registered ID has at least one failed check and risk is at least 10.
- `HIGH_RISK_IMPERSONATION`: risk is at least 40 and at least three of the four behavioural checks fail.
- `SUSPICIOUS_BEHAVIOUR`: a registered ID has a failed check, but custom thresholds place the risk below the possible-impersonation threshold.

The detector uses `RiskScorer` for its risk score. See the risk scoring section below for the fixed factor weights and bands. Configure `DetectionThresholds` to adjust classification thresholds, and keep one detector instance while processing messages so its behaviour verifier can track per-device message intervals.

Run the detector tests from the project root:

```powershell
py -m unittest tests.test_impersonation_detector -v
```



## Transparent risk scoring (implemented)

`src/security_engine/risk_scoring.py` converts behaviour-verification results into a risk score from 0 to 100. Each failed check contributes its configured weight; passed checks contribute zero. The default `RiskWeights` are:

| Factor | Default points |
| --- | ---: |
| Unknown or non-trusted identity | 40 |
| Temperature outside profile range | 15 |
| Humidity outside profile range | 15 |
| Abnormal message frequency/timestamp | 20 |
| Unexpected motion behaviour | 10 |

Weights must be non-negative integers that add up to 100. Pass a `RiskWeights` instance to `ImpersonationDetector(..., risk_weights=...)` to change them. For unknown IDs, only identity contributes because no trusted profile exists to evaluate sensor factors.

Risk bands follow the requested boundaries: 0–29 `LOW`, 30–59 `MEDIUM`, 60–79 `HIGH`, and 80–100 `CRITICAL`. The scoring result contains `risk_score`, `risk_level`, numeric `factors`, and explanatory `reasons`; detection events include the same fields. These are transparent rules for a demonstration, not mathematical proof of malicious activity.

Run scoring tests with:

```powershell
py -m unittest tests.test_risk_scoring -v
```

## Safe impersonation simulator (implemented)

`simulator/impersonation_simulator/` publishes demonstration telemetry using the same JSON fields and MQTT topic pattern as the normal simulator. Its MQTT client ID is separate, allowing both simulators to run concurrently while publishing the same claimed `device_id` and topic. It does not scan, exploit, steal credentials, or attempt unauthorized access; it only sends predefined synthetic sensor messages to the configured broker.

Start it from the project root:

```powershell
py -m simulator.impersonation_simulator.main --scenario IMPERSONATION --device-id IOT-001
```

Every console line is labeled `[SAFE SIMULATION][SCENARIO=...]`. Scenarios are `NORMAL`, `ABNORMAL_SENSOR`, `ABNORMAL_FREQUENCY`, `IMPERSONATION`, and `CUSTOM`. The default scenario is `IMPERSONATION`. `NORMAL` and `ABNORMAL_SENSOR` use `SIM_PUBLISH_INTERVAL`; rapid scenarios publish every 0.5 seconds. For `CUSTOM`, supply `--temperature`, `--humidity`, `--motion true|false`, and/or `--interval`.

The claimed ID defaults to `IMPSIM_CLAIMED_DEVICE_ID`, then `SIM_DEVICE_ID`, then `IOT-001`. Broker settings come from the existing MQTT configuration. For example, run the normal simulator and this simulator together with the same device ID to compare legitimate and simulated impersonating telemetry in the local detection engine.

Offline scenario tests:

```powershell
py -m unittest tests.test_impersonation_simulator -v
```




## MQTT-connected security engine (implemented)

The security engine subscribes to `iot/devices/+/telemetry` by default. Each received message is decoded and schema-checked before the existing registry, behaviour verifier, detector, and weighted risk scorer run. It prints a readable event and appends the same event as one JSON object per line to `logs/security_events.jsonl`. Set `MQTT_SUBSCRIBE_TOPIC`, `DEVICE_REGISTRY_PATH`, or `SECURITY_EVENT_LOG` in `.env` to change these paths/settings.

Start the security engine from the project root, with the MQTT broker running:

```powershell
py -m src.security_engine.main
```

Run the normal and safe scenario simulators in separate terminals to send telemetry. The subscriber uses `iot/devices/+/telemetry`, subscribes again after reconnecting, and reports disconnects. Invalid JSON, missing fields, invalid sensor types/ranges, and malformed timestamps are recorded as `SUSPICIOUS` validation events with a `CRITICAL` validation risk; message handling continues. These schema-validation events are marked separately from behaviour assessments.

The pipeline integration tests run without a broker:

```powershell
py -m unittest tests.test_security_engine_integration -v
```

## Optional ThingsBoard Cloud MQTT integration

The ThingsBoard publisher is a separate client in `src/security_engine/thingsboard.py`. It sends data to the standard device telemetry topic `v1/devices/me/telemetry`. It uses its own MQTT host, port, TLS setting, and device token; the existing local broker and `MQTT_SUBSCRIBE_TOPIC` remain unchanged. The device access token is the MQTT username and no password is set. ThingsBoard documents both this topic and access-token authentication in its [MQTT telemetry API](https://thingsboard.io/docs/paas/reference/mqtt-api/telemetry/) and [connection guide](https://thingsboard.io/docs/paas/reference/mqtt-api/getting-connected/).

### Configure ThingsBoard credentials

1. In your ThingsBoard Cloud tenant, open **Entities → Devices → Add device** and create one device for the project’s cloud feed. The single configured access token maps all events sent by this integration to that ThingsBoard device; the `device_id` telemetry key retains the simulated device ID for filtering/inspection.
2. Open the device and choose **Manage credentials** (or **Copy access token**) to copy the token ThingsBoard generated for that device. This project does not create credentials.
3. Use the MQTT host shown by your tenant’s **Check connectivity** dialog. Cloud tenants may use a region-specific host. For TLS, use port `8883` and keep `THINGSBOARD_USE_TLS=true`; the client validates the server certificate with the operating system trust store. Plain MQTT uses port `1883` and `THINGSBOARD_USE_TLS=false`.
4. Copy `.env.example` to `.env`; leave the existing `MQTT_HOST`, `MQTT_PORT`, and `MQTT_SUBSCRIBE_TOPIC` configured for the local simulator/security-engine broker. Separately set:

   ```dotenv
   THINGSBOARD_ENABLED=true
   THINGSBOARD_HOST=your-tenant-host-from-ThingsBoard
   THINGSBOARD_PORT=8883
   THINGSBOARD_ACCESS_TOKEN=paste-the-token-copied-from-your-device
   THINGSBOARD_USE_TLS=true
   THINGSBOARD_TELEMETRY_TOPIC=v1/devices/me/telemetry
   THINGSBOARD_QOS=1
   THINGSBOARD_KEEPALIVE=60
   ```

   Replace the host and token placeholders locally. Keep `.env` private; it is excluded from Git. Do not put the token in source code, simulator payloads, or screenshots.
5. Start the local MQTT broker, then run `py -m src.security_engine.main`. Cloud publishing is disabled unless `THINGSBOARD_ENABLED=true`. If ThingsBoard is disconnected, local detection, actuator response, console output, and JSONL logging continue. Up to 1,000 telemetry messages are queued in memory and sent after reconnection; if that queue fills, the event remains in the local log and a warning is printed.

### Telemetry keys and dashboard widgets

Each valid security assessment publishes these telemetry keys:

| Telemetry key | Meaning | Suggested dashboard widget |
| --- | --- | --- |
| `device_id` | Claimed simulator identity | Latest value card or table column |
| `temperature` | DHT11 temperature in °C | Time-series chart or gauge |
| `humidity` | DHT11 relative humidity in % | Time-series chart or gauge |
| `motion` | PIR state (`true`/`false`) | Boolean indicator or state card |
| `risk_score` | Weighted score from 0–100 | Gauge with 0–29, 30–59, 60–79, 80–100 bands |
| `risk_level` | `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL` | Latest value card |
| `device_status` | Security classification | Latest value card or time-series table |
| `impersonation_detected` | Boolean for possible/high-risk impersonation classifications | Alarm/boolean indicator |
| `message_frequency` | Messages per second (Hz); first reading uses the registered expected rate | Time-series chart or latest value card |
| `security_event` | Classification string for non-`TRUSTED` events | Latest value or table column |
| `security_reasons` | Semicolon-separated reasons for non-`TRUSTED` events | Latest value or table column |

To build the dashboard, open **Dashboards → Add new dashboard**, add an entity alias for the project device created above, then add widgets from **Latest values** and **Time series**. Configure the widget data keys using the names in the table. Put temperature and humidity together in a line chart, use a gauge for risk score, and use indicators/cards for motion, risk level, device status, and impersonation detection. Add `security_event` and `security_reasons` to a latest-values card or time-series table to review the latest alert. ThingsBoard stores the published key-value pairs as telemetry and makes them available to dashboards; see its [telemetry reference](https://thingsboard.io/docs/paas/reference/mqtt-api/telemetry/).


## Simulated actuator response (implemented)

`src/security_engine/actuator.py` defines a hardware-independent `Actuator` interface and the default `SimulatedActuator`. The security engine first produces its classification, then passes that decision to the actuator adapter. The adapter prints the LED/buzzer command and returns an `actuator_response` object that is included in the console event and local JSONL log.

| Decision | LED | Buzzer |
| --- | --- | --- |
| `TRUSTED` | Green | Off |
| `SUSPICIOUS` | Yellow | Off |
| `UNKNOWN_DEVICE` | Yellow | Off |
| `POSSIBLE_IMPERSONATION` | Red | Pulse for 500 ms |
| `HIGH_RISK_IMPERSONATION` | Red | On |

This is a console simulation with no GPIO or hardware-specific dependency. A later ESP32 simulator adapter can implement the same `respond(classification)` interface.

## Project dashboard setup

The dashboard is named **IoT Device Security Monitor**. The complete layout, widget settings, color functions, chart keys, and event-table columns are in [docs/thingsboard_dashboard_setup.md](docs/thingsboard_dashboard_setup.md). ThingsBoard dashboards are built from configured widgets and entity aliases; use the following exact setup summary:

The setup document is a tenant-independent manual blueprint, not an exported/importable ThingsBoard dashboard JSON. The dashboard must be created and bound to the device entity inside your ThingsBoard tenant.

1. In ThingsBoard, choose **Dashboards → + Add dashboard → Create new dashboard**, name it **IoT Device Security Monitor**, and enter edit mode.
2. Create a fixed entity alias named **Project Cloud Device** for the ThingsBoard device whose access token is configured in `.env`.
3. Add Value Cards for `device_id`, `device_status`, `risk_level`, `impersonation_detected`, `temperature`, `humidity`, `motion`, and `message_frequency`. Bind each to the alias and same-named telemetry key. Configure `device_status` and `risk_level` with the color functions in the setup document: green for trusted/low, yellow for suspicious/unknown/medium, red for possible/high-risk/high/critical. Color the boolean impersonation indicator green when false and red when true.
4. Add a risk-score gauge bound to `risk_score`, range 0–100, with green 0–29, yellow 30–59, and red 60–100.
5. Add separate **Charts → Time series chart** widgets for `temperature`, `humidity`, `risk_score`, and `message_frequency`, using a realtime/last-hour window.
6. Add **Tables → Time series table** with `device_status`, `risk_score`, `impersonation_detected`, `security_event`, and `security_reasons`, last-hour window, newest-first sorting if available, and pagination enabled.
7. Arrange status cards at the top, sensor/risk cards beneath, four charts in two rows, and the security-event table full width at the bottom. Use a simple light background and save.

ThingsBoard supports dashboard aliases, time-series charts, and time-series tables; see its [dashboard setup guide](https://thingsboard.io/docs/user-guide/dashboards/), [Value Card configuration](https://thingsboard.io/docs/reference/widgets/cards/value-card/), and [Time Series Table guide](https://thingsboard.io/docs/paas/reference/widgets/tables/timeseries-table/). The user still needs to create the dashboard inside their own ThingsBoard tenant and select their device entity; no tenant session or credentials are available in this workspace.

## Local web demonstration frontend

The separate Flask frontend in `frontend/` reads actual security events from `SECURITY_EVENT_LOG` (default `logs/security_events.jsonl`) and does not recreate security decisions. Its charts and event table are built from those logged engine events. Simulation buttons launch the existing simulator modules as subprocesses; starting a new button scenario stops the previous simulator process started by this page. Stop a simulator launched in another terminal before starting the same simulator here to avoid duplicate MQTT publishers.

The API provides `GET /api/status`, `GET /api/events`, `GET /api/health`, `POST /api/scenarios/<scenario>`, and `POST /api/scenarios/stop`. `/api/status` returns the latest logged security event unchanged, with the engine's original `telemetry`, `behaviour_checks`, and `actuator_response` fields; event age does not suppress it. `/api/events` returns at most 30 actual JSONL events, newest first, and `/api/health` separately provides local service observations. Both event routes use the same JSONL loader. The page polls every two seconds. The header distinguishes live events, waiting for telemetry, and an unreachable API. MQTT status is a local TCP reachability check, and engine status means a recent event was written. The existing ThingsBoard publisher does not expose live connection state to this local API, so the frontend reports the cloud integration as disabled, configured, or incomplete instead of claiming it is connected.

Install the frontend-only dependencies from the project root:

```powershell
py -m pip install -r frontend/requirements.txt
```

Run the existing local MQTT broker and security engine as usual. In a separate terminal, start the frontend:

```powershell
py -m frontend.app
```

Open **http://127.0.0.1:5000**. The frontend is bound to loopback for local demonstration use. It reads the real telemetry/security fields in the event log, displays valid/abnormal behaviour checks, the classification, score, reasons, and simulated LED/buzzer response, and plots recent temperature, humidity, and risk samples. Events with missing telemetry fields (such as rejected payloads) appear in the event table but do not fabricate sensor readings for the charts.

Use the **Normal Operation**, **Simulate Impersonation**, **Sensor Anomaly**, or **Traffic Anomaly** buttons to invoke the existing device or safe impersonation simulator. Start the normal simulator, wait for trusted events, launch impersonation and observe the event/risk/actuator updates, then stop the impersonation process and start normal operation again for recovery. The dashboard refreshes from the engine log every two seconds. See `frontend/requirements.txt` for the isolated Flask dependency list.
