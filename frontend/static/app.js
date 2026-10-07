const $ = (selector) => document.querySelector(selector);
const formatNumber = (value, digits = 1) => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : "--";

function setText(selector, value) {
  $(selector).textContent = value ?? "--";
}

function toneClass(value) {
  if (["TRUSTED", "NORMAL", "LOW", "GREEN", "OFF", "RECEIVING", "REACHABLE", "CONFIGURED"].includes(value)) return "tone-green";
  if (["SUSPICIOUS", "UNKNOWN_DEVICE", "MEDIUM", "YELLOW", "WAITING"].includes(value)) return "tone-yellow";
  if (["POSSIBLE_IMPERSONATION", "HIGH_RISK_IMPERSONATION", "HIGH", "CRITICAL", "RED", "ON", "UNAVAILABLE", "INCOMPLETE"].includes(value)) return "tone-red";
  return "tone-muted";
}

function updateTone(element, value) {
  element.classList.remove("tone-green", "tone-yellow", "tone-red", "tone-muted");
  element.classList.add(toneClass(value));
}

function updateCheckStates(checks = {}) {
  document.querySelectorAll("[data-check]").forEach((element) => {
    const value = checks[element.dataset.check];
    element.className = "check-state";
    if (value === true) {
      element.textContent = "VALID";
      element.classList.add("valid");
    } else if (value === false) {
      element.textContent = "ABNORMAL";
      element.classList.add("abnormal");
    } else {
      element.textContent = "NO DATA";
      element.classList.add("unknown");
    }
  });
}

function setService(id, detailId, service) {
  const state = $(`#${id}`);
  setText(`#${detailId}`, service?.detail || "No status data");
  const value = service?.state || "UNKNOWN";
  state.textContent = value;
  state.className = "service-state";
  state.classList.add(["RECEIVING", "REACHABLE"].includes(value) ? "good" : "unknown");
}

function getStatusEvent(data) {
  const looksLikeEvent = (candidate) => candidate
    && typeof candidate.classification === "string"
    && typeof candidate.timestamp === "string"
    && Number.isFinite(Number(candidate.risk_score));
  if (looksLikeEvent(data)) return data;
  if (looksLikeEvent(data?.event)) return data.event;
  // Compatibility with a Flask process that was started before /api/status
  // began returning the raw event. This prevents health and history from
  // appearing live while a wrapped current event is ignored by the UI.
  const oldDevice = data?.device;
  if (!looksLikeEvent(oldDevice)) return null;
  return {
    ...oldDevice,
    telemetry: {
      temperature: oldDevice.temperature,
      humidity: oldDevice.humidity,
      motion: oldDevice.motion,
    },
    behaviour_checks: {
      identity_valid: oldDevice.checks?.Identity,
      temperature_valid: oldDevice.checks?.["Temperature Behaviour"],
      humidity_valid: oldDevice.checks?.["Humidity Behaviour"],
      message_rate_valid: oldDevice.checks?.["Message Frequency"],
      motion_valid: oldDevice.checks?.Motion,
      message_frequency: oldDevice.message_frequency,
    },
    actuator_response: {
      led: { color: oldDevice.led },
      buzzer: { state: oldDevice.buzzer },
    },
  };
}

function renderStatus(data, health = null) {
  const event = getStatusEvent(data);
  const system = health || data.system || {};
  const live = system.security_engine?.state === "RECEIVING" || data.is_fresh === true;
  setText("#header-device", event?.device_id || data.configured_device_id || "No device");
  const onlineText = event ? (live ? "CONNECTED / LIVE" : "LATEST EVENT") : "WAITING FOR TELEMETRY";
  setText("#header-system-status", onlineText);
  $(".live-dot").style.background = event ? (live ? "var(--green)" : "var(--yellow)") : "var(--yellow)";

  setService("mqtt-state", "mqtt-detail", system.mqtt_broker);
  if (system.mqtt_broker?.state === "UNAVAILABLE") $("#mqtt-state").classList.replace("unknown", "bad");
  setService("engine-state", "engine-detail", system.security_engine);
  if (system.security_engine?.state === "RECEIVING") $("#engine-state").classList.replace("unknown", "good");
  setService("cloud-state", "cloud-detail", system.thingsboard);

  if (!event) {
    setText("#device-status", "NO DATA");
    setText("#device-id-caption", "Awaiting security event");
    setText("#temperature", "--");
    setText("#humidity", "--");
    setText("#risk-score", "--");
    setText("#risk-level", "Waiting for assessment");
    setText("#classification", "Awaiting event");
    setText("#threat-band", "NO DATA");
    setText("#threat-score", "--");
    setText("#threat-risk-level", "--");
    setText("#led-state", "--");
    setText("#buzzer-state", "--");
    setText("#last-event-time", "Waiting for telemetry");
    $("#reasons").replaceChildren(Object.assign(document.createElement("li"), { textContent: "Security engine events will appear here." }));
    updateCheckStates();
    drawCharts([]);
    return;
  }

  const telemetry = event.telemetry || {};
  const checks = event.behaviour_checks || {};
  const actuator = event.actuator_response || {};
  const led = actuator.led?.color || "--";
  const buzzer = actuator.buzzer?.state || "--";
  const liveLabel = live ? "Live telemetry" : "Latest recorded state";
  setText("#device-status", event.classification || "--");
  updateTone($("#device-status"), event.classification);
  setText("#device-id-caption", `${event.device_id || "Unknown device"} · ${liveLabel}`);
  setText("#temperature", formatNumber(telemetry.temperature));
  setText("#humidity", formatNumber(telemetry.humidity));
  setText("#risk-score", event.risk_score ?? "--");
  setText("#risk-level", event.risk_level || "--");
  updateTone($("#risk-level"), event.risk_level);
  setText("#classification", event.classification || "--");
  updateTone($("#classification"), event.classification);
  setText("#threat-score", event.risk_score ?? "--");
  setText("#threat-risk-level", event.risk_level || "--");
  const score = Number(event.risk_score);
  const band = !Number.isFinite(score) ? ["NO DATA", "neutral"] : score < 30 ? ["NORMAL / LOW RISK", "good"] : score < 60 ? ["SUSPICIOUS / MEDIUM RISK", "warn"] : ["HIGH RISK", "danger"];
  setText("#threat-band", band[0]);
  $("#threat-band").className = `threat-pill ${band[1]}`;

  const reasons = $("#reasons");
  reasons.replaceChildren();
  (event.reasons?.length ? event.reasons : ["No rule-based deviations detected."]).forEach((reason) => {
    const item = document.createElement("li");
    item.textContent = reason;
    reasons.append(item);
  });
  updateCheckStates({
    Identity: checks.identity_valid,
    "Temperature Behaviour": checks.temperature_valid,
    "Humidity Behaviour": checks.humidity_valid,
    "Message Frequency": checks.message_rate_valid,
    Motion: checks.motion_valid,
  });
  setText("#led-state", led);
  updateTone($("#led-state"), led);
  setText("#buzzer-state", buzzer);
  updateTone($("#buzzer-state"), buzzer);
  setText("#last-event-time", event.timestamp ? new Date(event.timestamp).toLocaleString() : "--");
}

function showBackendOffline(error) {
  setText("#header-system-status", "BACKEND OFFLINE");
  $(".live-dot").style.background = "var(--red)";
  setText("#device-status", "BACKEND OFFLINE");
  setText("#temperature", "--");
  setText("#humidity", "--");
  setText("#risk-score", "--");
  setText("#risk-level", "--");
  setText("#classification", "API unavailable");
  setText("#threat-band", "BACKEND OFFLINE");
  setText("#threat-score", "--");
  setText("#threat-risk-level", "--");
  setText("#led-state", "--");
  setText("#buzzer-state", "--");
  setText("#last-event-time", "API unavailable");
  $("#threat-band").className = "threat-pill neutral";
  updateCheckStates();
  drawCharts([]);
  setText("#control-message", `Backend API unavailable: ${error.message}`);
}

function renderEvents(events) {
  const body = $("#events-body");
  body.replaceChildren();
  setText("#event-count", `${events.length} event${events.length === 1 ? "" : "s"}`);
  if (!events.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 5;
    cell.className = "empty-state";
    cell.textContent = "No events recorded yet. Start the security engine and a simulator.";
    row.append(cell);
    body.append(row);
    return;
  }
  events.slice(0, 30).forEach((event) => {
    const row = document.createElement("tr");
    const values = [
      event.timestamp ? new Date(event.timestamp).toLocaleString() : "--",
      event.device_id || "--",
      event.classification || "--",
      event.risk_score ?? "--",
      event.risk_level || "--",
    ];
    values.forEach((value, index) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      if (index === 2) {
        cell.classList.add("classification", toneClass(String(value)));
      }
      row.append(cell);
    });
    body.append(row);
  });
}

function chartBounds(values, minimumSpan, absoluteMin = null, absoluteMax = null) {
  if (!values.length) return { min: 0, max: 1 };
  const low = Math.min(...values);
  const high = Math.max(...values);
  const center = (low + high) / 2;
  const span = Math.max(high - low, minimumSpan);
  const padding = Math.max((high - low) * 0.2, minimumSpan * 0.15);
  return {
    min: Math.max(absoluteMin ?? -Infinity, center - span / 2 - padding),
    max: Math.min(absoluteMax ?? Infinity, center + span / 2 + padding),
  };
}

function drawChart(canvasId, points, color, minimumSpan, absoluteMin = null, absoluteMax = null) {
  const canvas = $(`#${canvasId}`);
  const context = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * ratio));
  canvas.height = Math.max(1, Math.floor(rect.height * ratio));
  context.scale(ratio, ratio);
  const width = rect.width;
  const height = rect.height;
  const pad = { left: 31, right: 8, top: 10, bottom: 19 };
  const chartWidth = width - pad.left - pad.right;
  const chartHeight = height - pad.top - pad.bottom;
  context.font = "10px Segoe UI, sans-serif";
  context.strokeStyle = "#25364e";
  context.fillStyle = "#7f91a8";
  context.lineWidth = 1;
  const bounds = chartBounds(points.map((point) => point.value), minimumSpan, absoluteMin, absoluteMax);
  const minValue = bounds.min;
  const maxValue = bounds.max;
  for (let line = 0; line < 4; line += 1) {
    const y = pad.top + (chartHeight * line) / 3;
    context.beginPath();
    context.moveTo(pad.left, y);
    context.lineTo(width - pad.right, y);
    context.stroke();
    const label = (maxValue - ((maxValue - minValue) * line) / 3).toFixed(0);
    context.fillText(label, 2, y + 3);
  }
  const usable = points.filter((point) => Number.isFinite(point.value));
  if (!usable.length) {
    context.fillStyle = "#73859d";
    context.textAlign = "center";
    context.fillText("Waiting for telemetry...", width / 2, height / 2);
    context.textAlign = "left";
    return;
  }
  const values = usable.slice(-30);
  const range = Math.max(1, maxValue - minValue);
  const times = values.map((point) => Date.parse(point.timestamp)).filter(Number.isFinite);
  const firstTime = times.length ? Math.min(...times) : 0;
  const lastTime = times.length ? Math.max(...times) : 0;
  const timeRange = lastTime - firstTime;
  const xForPoint = (point, index) => {
    const time = Date.parse(point.timestamp);
    if (Number.isFinite(time) && timeRange > 0) {
      return pad.left + ((time - firstTime) / timeRange) * chartWidth;
    }
    return pad.left + (values.length === 1 ? chartWidth / 2 : (index * chartWidth) / (values.length - 1));
  };
  if (times.length) {
    const startLabel = new Date(firstTime).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    const endLabel = new Date(lastTime).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    context.fillStyle = "#7f91a8";
    context.fillText(startLabel, pad.left, height - 3);
    context.textAlign = "right";
    context.fillText(endLabel, width - pad.right, height - 3);
    context.textAlign = "left";
  }
  context.strokeStyle = color;
  context.lineWidth = 2;
  context.beginPath();
  values.forEach((point, index) => {
    const x = xForPoint(point, index);
    const y = pad.top + chartHeight - ((point.value - minValue) / range) * chartHeight;
    if (index === 0) context.moveTo(x, y); else context.lineTo(x, y);
  });
  context.stroke();
  values.forEach((point, index) => {
    const x = xForPoint(point, index);
    const y = pad.top + chartHeight - ((point.value - minValue) / range) * chartHeight;
    context.beginPath();
    context.fillStyle = color;
    context.arc(x, y, 2.5, 0, Math.PI * 2);
    context.fill();
  });
}

function drawCharts(events) {
  const points = events.map((event) => ({
    timestamp: event.timestamp,
    temperature: typeof event.telemetry?.temperature === "number" ? event.telemetry.temperature : null,
    humidity: typeof event.telemetry?.humidity === "number" ? event.telemetry.humidity : null,
    risk: typeof event.risk_score === "number" ? event.risk_score : null,
  }));
  const temperatures = points.filter((point) => point.temperature !== null).map((point) => point.temperature);
  const humidities = points.filter((point) => point.humidity !== null).map((point) => point.humidity);
  const risks = points.filter((point) => point.risk !== null).map((point) => point.risk);
  const latest = (array) => array.length ? array[array.length - 1] : null;
  setText("#chart-temp-value", latest(temperatures) === null ? "--" : `${formatNumber(latest(temperatures))} °C`);
  setText("#chart-humidity-value", latest(humidities) === null ? "--" : `${formatNumber(latest(humidities))}%`);
  setText("#chart-risk-value", latest(risks) === null ? "--" : `${formatNumber(latest(risks), 0)} / 100`);
  drawChart("temperature-chart", points.filter((point) => point.temperature !== null).map((point) => ({ timestamp: point.timestamp, value: point.temperature })), "#63a7f8", 5);
  drawChart("humidity-chart", points.filter((point) => point.humidity !== null).map((point) => ({ timestamp: point.timestamp, value: point.humidity })), "#48c6c2", 10, 0, 100);
  drawChart("risk-chart", points.filter((point) => point.risk !== null).map((point) => ({ timestamp: point.timestamp, value: point.risk })), "#e5ad50", 100, 0, 100);
}

async function refreshDashboard() {
  try {
    const [statusResponse, eventsResponse, healthResponse] = await Promise.all([
      fetch("/api/status", { cache: "no-store" }),
      fetch("/api/events?limit=30", { cache: "no-store" }),
      fetch("/api/health", { cache: "no-store" }).catch(() => null),
    ]);
    if (!statusResponse.ok || !eventsResponse.ok) throw new Error("Dashboard API or event log is unavailable");
    const status = await statusResponse.json();
    const { events } = await eventsResponse.json();
    const health = healthResponse?.ok ? await healthResponse.json() : null;
    renderStatus(status, health);
    renderEvents(events);
    drawCharts([...events].reverse());
  } catch (error) {
    showBackendOffline(error);
  }
}

async function runScenario(name) {
  const message = $("#control-message");
  message.textContent = `Starting ${name.replaceAll("_", " ")} using the existing simulator…`;
  document.querySelectorAll(".scenario-button, #stop-simulator").forEach((button) => { button.disabled = true; });
  try {
    const response = await fetch(`/api/scenarios/${encodeURIComponent(name)}`, { method: "POST" });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not start scenario");
    message.textContent = `${name.replaceAll("_", " ")} started (PID ${result.pid}). Detection results will appear when the running security engine writes events.`;
  } catch (error) {
    message.textContent = error.message;
  } finally {
    document.querySelectorAll(".scenario-button, #stop-simulator").forEach((button) => { button.disabled = false; });
  }
}

document.querySelectorAll("[data-scenario]").forEach((button) => {
  button.addEventListener("click", () => runScenario(button.dataset.scenario));
});
$("#stop-simulator").addEventListener("click", async () => {
  const response = await fetch("/api/scenarios/stop", { method: "POST" });
  const result = await response.json();
  setText("#control-message", result.stopped ? "Dashboard-launched simulator stopped." : "Could not stop simulator.");
});
window.addEventListener("resize", () => refreshDashboard());
refreshDashboard();
window.setInterval(refreshDashboard, 2000);
