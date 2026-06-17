import contextlib
import importlib
import io
import json
import os
import re
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from traceback import format_exc
from urllib.parse import parse_qs, urlparse

from interrupt_guard import install_deferred_keyboard_interrupt


BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "resources" / "mobotic-logo.png"
SERIAL_LAST4 = ""
DEFAULT_CAN_BITRATE = 125
DEFAULT_NODE_ID = 50
ZERO_ANGLE_DEG = 270.0
ZERO_VISUAL_TOLERANCE_DEG = 1.0
ANGLE_SETTLE_S = 2.0
ANGLE_SAMPLES = 20
ANGLE_TIMEOUT_S = 20.0
ANGLE_READ_ATTEMPTS = 2
SPIN_CHECK_DEG = 90.0
SPIN_CHECK_RPM = 200
SPIN_CHECK_TIMEOUT_S = 3.0
SPIN_FAILURE_ERROR = -1092
MANUAL_SPIN_DEFAULT_RPM = 1000
MANUAL_SPIN_STEP_RPM = 200
MANUAL_SPIN_MIN_RPM = 200
MANUAL_SPIN_MAX_RPM = 5000
ENCODER_COUNTS_PER_REV = 4096.0
ZERO_MOVE_RPM = 1000
ZERO_MOVE_SETTLE_S = 2.0
ZERO_MOVE_TIMEOUT_S = 25.0
ZERO_POSITION_TOLERANCE_COUNTS = 3
POWER_CYCLE_CONFIRM_TIMEOUT_S = 600.0
CONTROLLER_ENCODER_DIGITAL_OUTPUT = False
SSI_READY_STATUS = 9


TASKS = {
    "run_all": "Run all program",
    "load_script_config": "Configuration",
    "load_script": "Load Script",
    "load_config": "Load Config",
    "start_calibration": "Calibration",
    "test_calibration": "TestCalibration",
    "show_current_zero": "Show Current Zero",
    "start_zeroing": "Write Zero",
}


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Steering Calibration</title>
  <style>
    :root {
      --black: #000000;
      --blue: #1ba9e1;
      --white: #ffffff;
      --muted: #9a9a9a;
      --error: #ff6b6b;
      --danger: #d71920;
      --ok: #49d17d;
      --panel: rgba(0, 0, 0, 0.9);
      --shadow: 0 18px 55px rgba(0, 0, 0, 0.46);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      color: var(--white);
      background: var(--black);
      font-family: "DejaVu Sans", "Liberation Sans", sans-serif;
    }

    main {
      width: min(940px, calc(100vw - 16px));
      margin: 0 auto;
      padding: 18px 18px 20px;
      border-radius: 18px;
      border: 2px solid var(--blue);
      background: var(--panel);
      box-shadow: var(--shadow);
    }

    .topbar {
      display: grid;
      grid-template-columns: 180px minmax(0, 1fr) 180px;
      align-items: center;
      gap: 36px;
      margin-bottom: 6px;
    }

    .logo {
      width: 110px;
      height: auto;
      flex: 0 0 auto;
    }

    h1 {
      margin: 0;
      font-size: clamp(34px, 4.3vw, 42px);
      color: var(--muted);
      text-align: left;
    }

    #status {
      margin: 6px 0 0;
      color: var(--blue);
      font-size: 19px;
      font-weight: 800;
    }

    #status.ok {
      color: var(--ok);
    }

    #status.fail {
      color: var(--error);
    }

    .power-controls {
      align-self: end;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }

    .power-toggle {
      min-height: 38px;
      padding: 7px 18px;
      border-radius: 0;
      color: var(--blue);
      font-size: 15px;
    }

    button {
      border: 2px solid var(--blue);
      border-radius: 14px;
      color: var(--white);
      background: var(--black);
      box-shadow: none;
      cursor: pointer;
      font-weight: 800;
      transition: transform 150ms ease, opacity 150ms ease, box-shadow 150ms ease, background 150ms ease;
    }

    button:hover {
      transform: translateY(-2px);
      background: var(--blue);
      box-shadow: 0 18px 32px rgba(27, 169, 225, 0.34);
    }

    .run-all {
      width: 100%;
      min-height: 72px;
      margin-bottom: 12px;
      font-size: 20px;
      color: var(--blue);
    }

    .kill-all {
      min-height: 36px;
      padding: 7px 14px;
      border-color: var(--danger);
      color: var(--white);
      background: #220000;
      font-size: 13px;
    }

    .continue-power {
      display: none;
      width: 100%;
      min-height: 54px;
      margin: 0 0 12px;
      border-color: var(--ok);
      color: var(--black);
      background: var(--ok);
      font-size: 18px;
    }

    .continue-power.visible {
      display: block;
    }

    .continue-power:hover {
      background: var(--ok);
      box-shadow: 0 18px 32px rgba(73, 209, 125, 0.34);
    }

    .kill-all:hover {
      background: var(--danger);
      box-shadow: 0 18px 32px rgba(215, 25, 32, 0.34);
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }

    .grid button {
      min-height: 58px;
      padding: 12px;
      color: var(--muted);
      font-size: 14px;
    }

    .settings {
      display: grid;
      grid-template-columns: minmax(220px, 1fr) max-content max-content max-content;
      align-items: center;
      justify-content: stretch;
      gap: 14px;
      margin: 0 0 14px;
      padding: 12px 62px 10px;
      border: 2px solid var(--blue);
      border-radius: 14px;
    }

    .can-status {
      display: none;
      color: var(--blue);
      font-size: 12px;
      font-weight: 800;
      text-align: center;
      min-height: 18px;
    }

    .node-panel {
      display: grid;
      gap: 8px;
      min-width: 255px;
    }

    .node-panel label {
      justify-content: flex-end;
    }

    .can-controls {
      display: grid;
      grid-template-columns: 116px;
      gap: 8px;
    }

    .can-controls button {
      min-height: 38px;
      padding: 6px 9px;
      border-radius: 12px;
      color: var(--muted);
      font-size: 12px;
    }

    .can-status.ok {
      color: var(--ok);
    }

    .can-status.fail {
      color: var(--error);
    }

    label {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 17px;
      font-weight: 800;
    }

    input {
      width: 108px;
      min-height: 42px;
      padding: 9px 12px;
      border: 2px solid var(--blue);
      border-radius: 12px;
      color: var(--muted);
      background: var(--black);
      font: 16px "DejaVu Sans", "Liberation Sans", sans-serif;
      outline: none;
    }

    input:focus {
      box-shadow: 0 0 0 3px rgba(27, 169, 225, 0.28);
    }

    .manual-spin {
      display: grid;
      grid-template-columns: 42px 72px 42px;
      align-items: center;
      gap: 8px;
    }

    .manual-spin button {
      min-height: 38px;
      padding: 5px;
      color: var(--muted);
      font-size: 16px;
    }

    .spin-arrow {
      width: 42px;
      min-width: 42px;
      font-size: 22px;
      line-height: 1;
      touch-action: none;
      user-select: none;
    }

    .rpm-control {
      display: grid;
      grid-template-rows: 30px 24px 30px;
      gap: 4px;
      align-items: stretch;
    }

    .rpm-control button {
      min-height: 30px;
      padding: 3px;
      font-size: 18px;
      line-height: 1;
    }

    #manual-rpm {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 24px;
      border: 2px solid var(--blue);
      border-radius: 10px;
      color: var(--muted);
      background: var(--black);
      font-size: 11px;
      font-weight: 800;
      white-space: nowrap;
    }

    .view-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 8px;
    }

    .view-head strong {
      font-size: 17px;
      color: var(--muted);
    }

    .view-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      flex-wrap: wrap;
      gap: 8px;
    }

    .view-actions button {
      padding: 8px 14px;
      border-radius: 12px;
      background: var(--black);
      box-shadow: none;
      font-size: 13px;
    }

    .view-actions button.active {
      color: var(--black);
      background: var(--blue);
    }

    .view-actions .kill-all {
      border-color: var(--danger);
      background: #220000;
    }

    .view-actions .kill-all:hover {
      background: var(--danger);
      box-shadow: 0 18px 32px rgba(215, 25, 32, 0.34);
    }

    .view {
      display: none;
    }

    .view.active {
      display: block;
    }

    #status-feed {
      height: min(35vh, 280px);
      min-height: 240px;
      margin: 0;
      padding: 18px;
      overflow: auto;
      white-space: pre-wrap;
      border-radius: 14px;
      border: 2px solid var(--blue);
      color: var(--muted);
      background: var(--black);
      font: 15px/1.55 "DejaVu Sans Mono", "Liberation Mono", monospace;
    }

    #status-feed.fail {
      color: var(--error);
    }

    #log {
      height: min(44vh, 430px);
      min-height: 220px;
      margin: 0;
      padding: 18px;
      overflow: auto;
      white-space: pre-wrap;
      border-radius: 14px;
      border: 2px solid var(--blue);
      color: var(--muted);
      background: var(--black);
      font: 14px/1.45 "DejaVu Sans Mono", "Liberation Mono", monospace;
    }

    @media (max-width: 760px) {
      main {
        margin: 16px auto;
        padding: 18px;
        border-radius: 18px;
      }

      .grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .settings {
        grid-template-columns: 1fr;
        justify-content: stretch;
        padding: 12px;
      }

      .manual-spin {
        justify-content: start;
      }

      input {
        width: 100%;
      }

      .node-panel {
        min-width: 0;
      }

      .node-panel label {
        justify-content: space-between;
      }

      .topbar {
        grid-template-columns: 1fr;
        align-items: start;
        gap: 16px;
      }

      h1 {
        text-align: left;
      }
    }
  </style>
</head>
<body>
  <main>
    <div class="topbar">
      <img class="logo" src="/logo.png" alt="MOBOTIC logo">
      <div>
        <h1>Steering Software Control</h1>
        <div id="status">Choose one operation</div>
      </div>
      <div class="power-controls" aria-label="Power supply controls">
        <button id="ps-on" class="power-toggle" type="button">PS: ON</button>
        <button id="ps-off" class="power-toggle" type="button">PS: OFF</button>
      </div>
    </div>

    <div class="settings">
      <div class="settings-spacer" aria-hidden="true"></div>
      <div class="node-panel">
        <label>
          Current Node ID
          <input id="node-id" type="number" min="1" max="127" step="1" inputmode="numeric" value="50">
        </label>
        <div id="can-status" class="can-status">Checking CAN connection...</div>
        <label>
          Desired Zero
          <input id="desired-angle" type="number" min="0" max="360" step="0.1" inputmode="decimal" value="270.0">
        </label>
      </div>
      <div class="can-controls" aria-label="CAN controller controls">
        <button id="can-connect" type="button">Connect CAN</button>
        <button id="drive-enable" type="button">Enable</button>
        <button id="clear-errors" type="button">Clear error</button>
      </div>
      <div class="manual-spin" aria-label="Manual motor spin">
        <button id="spin-left" class="spin-arrow" type="button" title="Hold to spin left">←</button>
        <div class="rpm-control">
          <button id="rpm-plus" type="button" title="Increase RPM">+</button>
          <div id="manual-rpm">1000 RPM</div>
          <button id="rpm-minus" type="button" title="Decrease RPM">-</button>
        </div>
        <button id="spin-right" class="spin-arrow" type="button" title="Hold to spin right">→</button>
      </div>
    </div>

    <button class="run-all" data-task="run_all">Run all program</button>
    <button id="continue-power-cycle" class="continue-power" type="button">
      Continue after power cycle
    </button>

    <div class="grid">
      <button data-task="load_script_config">Configuration</button>
      <button data-task="start_zeroing">Write Zero</button>
      <button data-task="start_calibration">Calibration</button>
      <button data-task="test_calibration">TestCalibration</button>
      <button data-task="show_current_zero">Show Current Zero</button>
    </div>

    <div class="view-head">
      <strong id="view-title">Status</strong>
      <div class="view-actions">
        <button id="status-tab" class="active" type="button">Status</button>
        <button id="debug-tab" type="button">Debug</button>
        <button id="clear-log" type="button">Clear view</button>
        <button id="kill-all" class="kill-all" type="button">Kill All</button>
      </div>
    </div>

    <section id="status-view" class="view active">
      <pre id="status-feed">Ready.</pre>
    </section>

    <section id="debug-view" class="view">
      <pre id="log"></pre>
    </section>
  </main>

  <script>
    const statusEl = document.querySelector("#status");
    const statusFeedEl = document.querySelector("#status-feed");
    const logEl = document.querySelector("#log");
    const nodeIdEl = document.querySelector("#node-id");
    const canStatusEl = document.querySelector("#can-status");
    const canConnectEl = document.querySelector("#can-connect");
    const driveEnableEl = document.querySelector("#drive-enable");
    const clearErrorsEl = document.querySelector("#clear-errors");
    const psOnEl = document.querySelector("#ps-on");
    const psOffEl = document.querySelector("#ps-off");
    const desiredAngleEl = document.querySelector("#desired-angle");
    const killAllEl = document.querySelector("#kill-all");
    const continuePowerCycleEl = document.querySelector("#continue-power-cycle");
    const spinLeftEl = document.querySelector("#spin-left");
    const spinRightEl = document.querySelector("#spin-right");
    const rpmPlusEl = document.querySelector("#rpm-plus");
    const rpmMinusEl = document.querySelector("#rpm-minus");
    const manualRpmEl = document.querySelector("#manual-rpm");
    const statusViewEl = document.querySelector("#status-view");
    const debugViewEl = document.querySelector("#debug-view");
    const statusTabEl = document.querySelector("#status-tab");
    const debugTabEl = document.querySelector("#debug-tab");
    const viewTitleEl = document.querySelector("#view-title");
    const buttons = [...document.querySelectorAll("[data-task]")];
    const manualButtons = [spinLeftEl, spinRightEl, rpmPlusEl, rpmMinusEl];
    const MANUAL_RPM_DEFAULT = 1000;
    const MANUAL_RPM_STEP = 200;
    const MANUAL_RPM_MIN = 200;
    const MANUAL_RPM_MAX = 5000;
    let lastLength = 0;
    let lastStatusText = "";
    let manualRpm = MANUAL_RPM_DEFAULT;
    let heldSpinDirection = 0;
    let manualCommandSeq = 0;
    let canConnected = false;
    let canCheckRunning = true;
    let controllerEnabled = false;
    let canCheckTimer = null;

    function setBusy(isBusy) {
      updateCanControls(isBusy);
    }

    function updateCanControls(isBusy = false) {
      canConnectEl.textContent = canConnected ? "Disconnect CAN" : "Connect CAN";
      driveEnableEl.textContent = controllerEnabled ? "Disable" : "Enable";
    }

    function setCanStatus(text, state) {
      canStatusEl.textContent = text;
      canStatusEl.classList.toggle("ok", state === "ok");
      canStatusEl.classList.toggle("fail", state === "fail");
      statusEl.textContent = text;
      statusEl.classList.toggle("ok", state === "ok");
      statusEl.classList.toggle("fail", state === "fail");
    }

    function updateManualRpm(delta) {
      manualRpm = Math.max(MANUAL_RPM_MIN, Math.min(MANUAL_RPM_MAX, manualRpm + delta));
      manualRpmEl.textContent = `${manualRpm} RPM`;
    }

    function setView(viewName) {
      const debug = viewName === "debug";
      statusViewEl.classList.toggle("active", !debug);
      debugViewEl.classList.toggle("active", debug);
      statusTabEl.classList.toggle("active", !debug);
      debugTabEl.classList.toggle("active", debug);
      viewTitleEl.textContent = debug ? "Debug" : "Status";
    }

    async function startTask(task) {
      if (!canConnected) {
        statusFeedEl.textContent = "CAN node is not connected. Change Current Node ID and wait for the check to pass.";
        statusFeedEl.classList.add("fail");
        setView("status");
        return;
      }
      const params = new URLSearchParams({ task });
      if (nodeIdEl.value.trim()) {
        params.set("node_id", nodeIdEl.value.trim());
      }
      if (desiredAngleEl.value.trim()) {
        params.set("desired_angle", desiredAngleEl.value.trim());
      }
      try {
        const response = await fetch(`/start?${params.toString()}`, { method: "POST" });
        const data = await response.json();
        if (!data.ok) {
          statusFeedEl.textContent = data.error || "Could not start task.";
          statusFeedEl.classList.add("fail");
          setView("status");
        }
      } catch (error) {
        statusFeedEl.textContent = `Server connection problem: ${error}`;
        statusFeedEl.classList.add("fail");
        setView("status");
      }
      await refreshStatus();
    }

    function manualSpin(rpm, seq = ++manualCommandSeq) {
      if (!canConnected && rpm !== 0) {
        statusFeedEl.textContent = "CAN node is not connected. Change Current Node ID and wait for the check to pass.";
        statusFeedEl.classList.add("fail");
        setView("status");
        return Promise.resolve();
      }
      const params = new URLSearchParams({ rpm: String(rpm), seq: String(seq) });
      if (nodeIdEl.value.trim()) {
        params.set("node_id", nodeIdEl.value.trim());
      }
      return fetch(`/manual-spin?${params.toString()}`, { method: "POST" })
        .then((response) => response.json())
        .then((data) => {
          if (!data.ok) {
            statusFeedEl.textContent = data.error || "Could not command motor.";
            statusFeedEl.classList.add("fail");
            setView("status");
          }
          return refreshStatus();
        })
        .catch((error) => {
          statusFeedEl.textContent = `Server connection problem: ${error}`;
          statusFeedEl.classList.add("fail");
          setView("status");
        });
    }

    function startHeldSpin(direction, event) {
      event.preventDefault();
      event.currentTarget.setPointerCapture?.(event.pointerId);
      if (heldSpinDirection !== 0) {
        return;
      }
      heldSpinDirection = direction;
      manualSpin(direction * manualRpm);
    }

    function stopHeldSpin() {
      if (heldSpinDirection === 0) {
        return;
      }
      heldSpinDirection = 0;
      manualSpin(0);
    }

    function sendReleaseBeacon() {
      if (heldSpinDirection === 0) {
        return;
      }
      heldSpinDirection = 0;
      const params = new URLSearchParams({ rpm: "0", seq: String(++manualCommandSeq) });
      if (nodeIdEl.value.trim()) {
        params.set("node_id", nodeIdEl.value.trim());
      }
      if (navigator.sendBeacon) {
        navigator.sendBeacon(`/manual-spin?${params.toString()}`);
      } else {
        fetch(`/manual-spin?${params.toString()}`, { method: "POST", keepalive: true });
      }
    }

    async function refreshStatus() {
      try {
        const response = await fetch("/status");
        const data = await response.json();
        statusFeedEl.classList.toggle("fail", data.has_error === true);
        canConnected = data.can_connection_ok === true;
        canCheckRunning = data.can_check_running === true;
        controllerEnabled = data.controller_enabled === true;
        if (canCheckRunning) {
          setCanStatus("Checking CAN connection...", "");
        } else if (data.can_connection_ok === true) {
          setCanStatus(data.can_connection_message || "CAN connected.", "ok");
        } else {
          const disconnected = (data.can_connection_message || "").startsWith("CAN disconnected");
          setCanStatus(
            data.can_connection_message || "CAN connection failed. Change Current Node ID.",
            disconnected ? "" : "fail",
          );
        }
        setBusy(data.running);
        continuePowerCycleEl.classList.toggle("visible", data.awaiting_power_cycle === true);

        if (data.status_feed !== lastStatusText) {
          statusFeedEl.textContent = data.status_feed || "Ready.";
          statusFeedEl.scrollTop = statusFeedEl.scrollHeight;
          lastStatusText = data.status_feed;
        }

        if (data.log.length !== lastLength) {
          logEl.textContent = data.log;
          logEl.scrollTop = logEl.scrollHeight;
          lastLength = data.log.length;
        }
      } catch (error) {
        statusFeedEl.textContent = "Server connection problem. Open Debug after the server is reachable again.";
        statusFeedEl.classList.add("fail");
      }
    }

    async function checkCanConnection() {
      const params = new URLSearchParams();
      if (nodeIdEl.value.trim()) {
        params.set("node_id", nodeIdEl.value.trim());
      }
      canConnected = false;
      canCheckRunning = true;
      setCanStatus("Checking CAN connection...", "");
      setBusy(true);
      try {
        const response = await fetch(`/check-can?${params.toString()}`, { method: "POST" });
        const data = await response.json();
        canConnected = data.ok === true;
        canCheckRunning = false;
        controllerEnabled = data.controller_enabled === true;
        if (data.ok) {
          setCanStatus(data.message || "CAN connected.", "ok");
          statusFeedEl.classList.remove("fail");
        } else {
          setCanStatus(data.error || "CAN connection failed. Change Current Node ID.", "fail");
          statusFeedEl.textContent = data.error || "CAN connection failed. Change Current Node ID.";
          statusFeedEl.classList.add("fail");
          setView("status");
        }
      } catch (error) {
        canConnected = false;
        canCheckRunning = false;
        setCanStatus(`CAN check failed: ${error}`, "fail");
        statusFeedEl.textContent = `CAN check failed: ${error}`;
        statusFeedEl.classList.add("fail");
        setView("status");
      }
      setBusy(false);
      await refreshStatus();
    }

    async function toggleCanConnection() {
      if (!canConnected) {
        await checkCanConnection();
        return;
      }
      setBusy(true);
      try {
        const response = await fetch("/disconnect-can", { method: "POST" });
        const data = await response.json();
        if (!data.ok) {
          statusFeedEl.textContent = data.error || "Could not disconnect CAN.";
          statusFeedEl.classList.add("fail");
          setView("status");
        } else {
          canConnected = false;
          controllerEnabled = false;
          setCanStatus(data.message || "CAN disconnected.", "");
          statusFeedEl.textContent = data.message || "CAN disconnected.";
          statusFeedEl.classList.remove("fail");
        }
      } catch (error) {
        statusFeedEl.textContent = `Server connection problem: ${error}`;
        statusFeedEl.classList.add("fail");
        setView("status");
      }
      setBusy(false);
      await refreshStatus();
    }

    async function toggleControllerEnabled() {
      if (!canConnected) {
        return;
      }
      const nextEnabled = !controllerEnabled;
      const params = new URLSearchParams({ enabled: nextEnabled ? "1" : "0" });
      if (nodeIdEl.value.trim()) {
        params.set("node_id", nodeIdEl.value.trim());
      }
      setBusy(true);
      try {
        const response = await fetch(`/controller-enable?${params.toString()}`, { method: "POST" });
        const data = await response.json();
        if (!data.ok) {
          statusFeedEl.textContent = data.error || "Could not change controller enable state.";
          statusFeedEl.classList.add("fail");
          setView("status");
        } else {
          controllerEnabled = data.controller_enabled === true;
          statusFeedEl.textContent = data.message || "Controller state changed.";
          statusFeedEl.classList.remove("fail");
        }
      } catch (error) {
        statusFeedEl.textContent = `Server connection problem: ${error}`;
        statusFeedEl.classList.add("fail");
        setView("status");
      }
      setBusy(false);
      await refreshStatus();
    }

    async function clearControllerErrors() {
      if (!canConnected) {
        return;
      }
      const params = new URLSearchParams();
      if (nodeIdEl.value.trim()) {
        params.set("node_id", nodeIdEl.value.trim());
      }
      setBusy(true);
      try {
        const response = await fetch(`/clear-controller-errors?${params.toString()}`, { method: "POST" });
        const data = await response.json();
        if (!data.ok) {
          statusFeedEl.textContent = data.error || "Could not clear controller errors.";
          statusFeedEl.classList.add("fail");
          setView("status");
        } else {
          statusFeedEl.textContent = data.message || "Controller errors cleared.";
          statusFeedEl.classList.remove("fail");
        }
      } catch (error) {
        statusFeedEl.textContent = `Server connection problem: ${error}`;
        statusFeedEl.classList.add("fail");
        setView("status");
      }
      setBusy(false);
      await refreshStatus();
    }

    async function setPowerSupplyOutput(enabled) {
      setBusy(true);
      statusFeedEl.textContent = enabled ? "Turning power supply on..." : "Turning power supply off...";
      statusFeedEl.classList.remove("fail");
      setView("status");
      const params = new URLSearchParams({ enabled: enabled ? "1" : "0" });
      if (nodeIdEl.value.trim()) {
        params.set("node_id", nodeIdEl.value.trim());
      }
      try {
        const response = await fetch(`/power-supply-output?${params.toString()}`, { method: "POST" });
        const data = await response.json();
        if (!data.ok) {
          statusFeedEl.textContent = data.error || "Could not control power supply.";
          statusFeedEl.classList.add("fail");
        } else {
          canConnected = data.can_connection_ok === true;
          controllerEnabled = data.controller_enabled === true;
          statusFeedEl.textContent = data.message || (enabled ? "Power supply on." : "Power supply off.");
          statusFeedEl.classList.remove("fail");
        }
      } catch (error) {
        statusFeedEl.textContent = `Server connection problem: ${error}`;
        statusFeedEl.classList.add("fail");
      }
      setBusy(false);
      await refreshStatus();
    }

    function scheduleCanCheck() {
      canConnected = false;
      controllerEnabled = false;
      setBusy(true);
      setCanStatus("Node ID changed. Checking CAN connection...", "");
      clearTimeout(canCheckTimer);
      canCheckTimer = setTimeout(checkCanConnection, 400);
    }

    buttons.forEach((button) => {
      button.addEventListener("click", () => startTask(button.dataset.task));
    });

    nodeIdEl.addEventListener("change", scheduleCanCheck);
    nodeIdEl.addEventListener("input", scheduleCanCheck);
    canConnectEl.addEventListener("click", toggleCanConnection);
    driveEnableEl.addEventListener("click", toggleControllerEnabled);
    clearErrorsEl.addEventListener("click", clearControllerErrors);
    psOnEl.addEventListener("click", () => setPowerSupplyOutput(true));
    psOffEl.addEventListener("click", () => setPowerSupplyOutput(false));

    rpmPlusEl.addEventListener("click", () => updateManualRpm(MANUAL_RPM_STEP));
    rpmMinusEl.addEventListener("click", () => updateManualRpm(-MANUAL_RPM_STEP));
    spinLeftEl.addEventListener("pointerdown", (event) => startHeldSpin(-1, event));
    spinRightEl.addEventListener("pointerdown", (event) => startHeldSpin(1, event));
    [spinLeftEl, spinRightEl].forEach((button) => {
      button.addEventListener("pointerup", stopHeldSpin);
      button.addEventListener("pointercancel", stopHeldSpin);
      button.addEventListener("pointerleave", stopHeldSpin);
      button.addEventListener("lostpointercapture", stopHeldSpin);
    });
    window.addEventListener("blur", stopHeldSpin);
    window.addEventListener("pagehide", sendReleaseBeacon);

    continuePowerCycleEl.addEventListener("click", async () => {
      try {
        await fetch("/confirm-power-cycle", { method: "POST" });
      } catch (error) {
        statusFeedEl.textContent = `Could not confirm power cycle: ${error}`;
        statusFeedEl.classList.add("fail");
      }
      await refreshStatus();
    });

    killAllEl.addEventListener("click", async () => {
      statusFeedEl.textContent = "Stopping all programs...";
      statusFeedEl.classList.add("fail");
      try {
        await fetch("/kill-all", { method: "POST" });
      } catch (error) {
        statusFeedEl.textContent = `Programs stopped. Server connection closed: ${error}`;
      }
    });

    statusTabEl.addEventListener("click", () => setView("status"));
    debugTabEl.addEventListener("click", () => setView("debug"));

    document.querySelector("#clear-log").addEventListener("click", async () => {
      try {
        await fetch("/clear-log", { method: "POST" });
      } catch (error) {
        statusFeedEl.textContent = `Could not clear debug log: ${error}`;
        statusFeedEl.classList.add("fail");
      }
      logEl.textContent = "";
      statusFeedEl.textContent = "Ready.";
      lastLength = 0;
      lastStatusText = "";
      await refreshStatus();
    });

    checkCanConnection();
    setInterval(refreshStatus, 750);
  </script>
</body>
</html>
"""


class AppState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.log = ""
        self.status = "Choose one operation"
        self.quality = "Calibration quality: no result yet."
        self.quality_ok: bool | None = None
        self._quality_fields: dict[str, str] = {}
        self.status_lines: list[str] = ["Ready."]
        self.has_error = False
        self.running = False
        self.worker: threading.Thread | None = None
        self.awaiting_power_cycle = False
        self.latest_manual_seq = 0
        self.manual_requests_in_flight = 0
        self.can_check_running = False
        self.can_connection_ok: bool | None = None
        self.can_connection_node: int | None = None
        self.can_connection_message = "CAN has not been checked yet."
        self.manual_can = None
        self.manual_mic = None
        self.controller_enabled = False
        self._power_cycle_event = threading.Event()

    def append_log(self, text: str) -> None:
        if not text:
            return
        with self.lock:
            self.log += text

    def reset_quality(self) -> None:
        with self.lock:
            self.quality = "Calibration quality: running..."
            self.quality_ok = None
            self._quality_fields = {}

    def append_status(self, text: str, is_error: bool = False) -> None:
        clean = text.strip()
        if not clean:
            return
        with self.lock:
            timestamp = time.strftime("%H:%M:%S")
            self.status_lines.append(f"{timestamp}  {clean}")
            self.status_lines = self.status_lines[-12:]
            if is_error:
                self.has_error = True

    def clear_log(self) -> None:
        with self.lock:
            self.log = ""
            self.status_lines = ["Ready."]
            self.has_error = False

    def observe_log_line(self, line: str) -> None:
        stripped = line.strip()
        if not stripped:
            return

        if (
            stripped.startswith("[INFO]")
            or stripped.startswith("[ERROR]")
            or stripped.startswith("[WARN]")
            or stripped.startswith("[STATUS]")
            or stripped.startswith("[RESULT]")
            or stripped.startswith("===")
            or "completed" in stripped.lower()
        ):
            self.append_status(
                stripped,
                is_error=stripped.startswith("[ERROR]") or "failed" in stripped.lower(),
            )

        match = re.search(r"quality_status=(PASS|FAIL)", stripped)
        if match:
            self._update_quality_field("status", match.group(1))
            return

        match = re.search(
            r"max_abs_analog_residual=([+-]?\d+(?:\.\d+)?) LSB .*final cap ([+-]?\d+(?:\.\d+)?)",
            stripped,
        )
        if match:
            self._update_quality_field(
                "residual",
                f"{float(match.group(1)):.4f} LSB / cap {float(match.group(2)):.4f}",
            )
            return

        match = re.search(
            r"nonius_phase_margin=([+-]?\d+(?:\.\d+)?)% .*max ([+-]?\d+(?:\.\d+)?)%",
            stripped,
        )
        if match:
            self._update_quality_field(
                "phase_margin",
                f"{float(match.group(1)):.2f}% / max {float(match.group(2)):.2f}%",
            )
            return

        match = re.search(
            r"upper_phase_clearance=([+-]?\d+(?:\.\d+)?)% lower_phase_clearance=([+-]?\d+(?:\.\d+)?)%",
            stripped,
        )
        if match:
            self._update_quality_field(
                "phase_clearance",
                f"upper {float(match.group(1)):.2f}%, lower {float(match.group(2)):.2f}%",
            )
            return

        match = re.search(
            r"upper_phase_margin=([+-]?\d+(?:\.\d+)?)% lower_phase_margin=([+-]?\d+(?:\.\d+)?)%",
            stripped,
        )
        if match:
            self._update_quality_field(
                "phase_clearance",
                f"upper {float(match.group(1)):.2f}%, lower {float(match.group(2)):.2f}%",
            )
            return

        if "quality_gate_reason=" in stripped:
            self._update_quality_field("reason", stripped.split("quality_gate_reason=", 1)[1])
            return

        match = re.search(r"\[RESULT\] (?:full calibration|test calibration) ok=(True|False)", stripped)
        if match:
            self._update_quality_field(
                "overall",
                "PASS" if match.group(1) == "True" else "FAIL",
            )

    def _update_quality_field(self, key: str, value: str) -> None:
        with self.lock:
            self._quality_fields[key] = value
            status = self._quality_fields.get("overall") or self._quality_fields.get("status")
            if status == "PASS":
                self.quality_ok = True
            elif status == "FAIL":
                self.quality_ok = False

            parts = []
            if status:
                parts.append(f"Calibration quality: {status}")
            else:
                parts.append("Calibration quality: running...")
            if "residual" in self._quality_fields:
                parts.append(f"Residual: {self._quality_fields['residual']}")
            if "phase_margin" in self._quality_fields:
                parts.append(f"Phase margin: {self._quality_fields['phase_margin']}")
            if "phase_clearance" in self._quality_fields:
                parts.append(f"Phase clearance: {self._quality_fields['phase_clearance']}")
            if "reason" in self._quality_fields:
                parts.append(f"Reason: {self._quality_fields['reason']}")
            self.quality = "\n".join(parts)

    def mark_quality_failed_if_pending(self, reason: str) -> None:
        with self.lock:
            if self.quality_ok is None and self.quality == "Calibration quality: running...":
                self.quality_ok = False
                self.quality = f"Calibration quality: FAIL\nReason: {reason}"

    def snapshot(self) -> dict[str, object]:
        with self.lock:
            return {
                "log": self.log,
                "status": self.status,
                "quality": self.quality,
                "quality_ok": self.quality_ok,
                "status_feed": "\n".join(self.status_lines),
                "has_error": self.has_error,
                "running": self.running,
                "awaiting_power_cycle": self.awaiting_power_cycle,
                "can_check_running": self.can_check_running,
                "can_connection_ok": self.can_connection_ok,
                "can_connection_node": self.can_connection_node,
                "can_connection_message": self.can_connection_message,
                "controller_enabled": self.controller_enabled,
            }

    def request_power_cycle_confirmation(self, timeout_s: float) -> bool:
        self._power_cycle_event.clear()
        with self.lock:
            self.awaiting_power_cycle = True
            self.status = "Waiting for power-cycle confirmation."
            timestamp = time.strftime("%H:%M:%S")
            self.status_lines.append(
                f"{timestamp}  Waiting for supply power cycle. Press Continue after power is back on."
            )
            self.status_lines = self.status_lines[-12:]
        confirmed = self._power_cycle_event.wait(timeout_s)
        with self.lock:
            self.awaiting_power_cycle = False
        return confirmed

    def confirm_power_cycle(self) -> bool:
        with self.lock:
            if not self.awaiting_power_cycle:
                return False
        self.append_status("Power cycle confirmed. Continuing verification.")
        self._power_cycle_event.set()
        return True

    def start_task(
        self,
        task_id: str,
        desired_node_id: int | None = None,
        desired_angle: float | None = None,
    ) -> tuple[bool, str]:
        if task_id not in TASKS:
            return False, f"Unknown task: {task_id}"

        node = node_or_default(desired_node_id, DEFAULT_NODE_ID)
        with self.lock:
            if self.running:
                return False, "Another operation is already running."
            if self.manual_requests_in_flight > 0:
                return False, "A controller command is still finishing."
            ready, message = self._can_ready_for_node_locked(desired_node_id)
            if not ready:
                return False, message
            self.running = True
            self.status = f"Running: {TASKS[task_id]}"
            self.log += f"\n=== {TASKS[task_id]} started ===\n"
            self.status_lines.append(f"{time.strftime('%H:%M:%S')}  Started: {TASKS[task_id]}")
            self.status_lines = self.status_lines[-12:]
            self.has_error = False
            self.awaiting_power_cycle = False
            self._power_cycle_event.clear()
        if task_id in {"start_calibration", "test_calibration", "run_all"}:
            self.reset_quality()

        self.worker = threading.Thread(
            target=self._run_task,
            args=(task_id, desired_node_id, desired_angle),
            daemon=True,
        )
        self.worker.start()
        return True, ""

    def begin_manual_command(self, seq: int, node: int, rpm: int) -> tuple[bool, str]:
        with self.lock:
            if self.running:
                return False, "Another operation is already running."
            ready, message = self._can_ready_for_node_locked(node)
            if not ready and rpm != 0:
                return False, message
            if seq < self.latest_manual_seq:
                return False, ""
            self.latest_manual_seq = seq
            self.manual_requests_in_flight += 1
            return True, ""

    def is_latest_manual_command(self, seq: int) -> bool:
        with self.lock:
            return seq == self.latest_manual_seq

    def finish_manual_command(self) -> None:
        with self.lock:
            self.manual_requests_in_flight = max(0, self.manual_requests_in_flight - 1)

    def begin_can_check(self, node: int) -> tuple[bool, str]:
        can_to_close = None
        with self.lock:
            if self.running or self.manual_requests_in_flight > 0:
                return False, "Cannot check CAN while another operation is running."
            can_to_close = self._detach_manual_controller_locked(
                message=f"Checking CAN node {node}..."
            )
            self.can_check_running = True
            self.can_connection_ok = None
            self.can_connection_node = node
            self.can_connection_message = f"Checking CAN node {node}..."
            self.has_error = False
        if can_to_close is not None:
            try:
                can_to_close.close_can()
            except Exception:
                pass
        return True, ""

    def finish_can_check(self, node: int, ok: bool, message: str) -> None:
        with self.lock:
            self.can_check_running = False
            self.can_connection_ok = ok
            self.can_connection_node = node
            self.can_connection_message = message
            if not ok:
                self.controller_enabled = False
            if not ok:
                self.has_error = True

    def set_manual_controller(self, node: int, can, mic, enabled: bool = False) -> None:
        with self.lock:
            self.manual_can = can
            self.manual_mic = mic
            self.controller_enabled = enabled
            self.can_connection_ok = True
            self.can_connection_node = node
            self.can_connection_message = f"CAN connected to node {node}."

    def get_manual_controller(self, node: int):
        with self.lock:
            if (
                self.can_connection_ok is True
                and self.can_connection_node == node
                and self.manual_mic is not None
            ):
                return self.manual_can, self.manual_mic
        return None, None

    def _detach_manual_controller_locked(self, message: str | None = None):
        can = self.manual_can
        self.manual_can = None
        self.manual_mic = None
        self.controller_enabled = False
        self.can_connection_ok = False
        if message is not None:
            self.can_connection_message = message
        return can

    def close_manual_controller(self) -> None:
        with self.lock:
            can = self._detach_manual_controller_locked(message="CAN disconnected.")
        if can is not None:
            try:
                can.close_can()
            except Exception:
                pass

    def disconnect_can(self) -> tuple[bool, str]:
        with self.lock:
            if self.running:
                return False, "Cannot disconnect CAN while another operation is running."
            if self.manual_requests_in_flight > 0:
                return False, "A controller command is still finishing."
            node = self.can_connection_node
            can = self._detach_manual_controller_locked(
                message=f"CAN disconnected from node {node}." if node is not None else "CAN disconnected."
            )
            message = self.can_connection_message
        if can is not None:
            try:
                can.close_can()
            except Exception:
                pass
        return True, message

    def begin_power_supply_output(self, node: int, enabled: bool) -> tuple[bool, str, object | None]:
        label = "ON" if enabled else "OFF"
        with self.lock:
            if self.running:
                return False, "Cannot control power supply while another operation is running.", None
            if self.manual_requests_in_flight > 0:
                return False, "A controller command is still finishing.", None
            can = self._detach_manual_controller_locked(
                message=f"Turning power supply {label} for node {node}..."
            )
            self.running = True
            self.status = f"Turning power supply {label}."
            self.log += f"\n=== Power Supply {label} started ===\n"
            self.status_lines.append(f"{time.strftime('%H:%M:%S')}  Turning power supply {label}.")
            self.status_lines = self.status_lines[-12:]
            self.has_error = False
            return True, "", can

    def finish_power_supply_output(self, enabled: bool, ok: bool, message: str) -> None:
        label = "ON" if enabled else "OFF"
        with self.lock:
            self.running = False
            self.status = "Ready." if ok else f"Power supply {label} failed."
            if not ok:
                self.has_error = True
        self.append_log(
            f"\n=== Power Supply {label} finished ===\n"
            if ok
            else f"\n=== Power Supply {label} failed ===\n"
        )
        self.append_status(message, is_error=not ok)

    def begin_controller_command(self, node: int) -> tuple[bool, str]:
        with self.lock:
            if self.running:
                return False, "Another operation is already running."
            if self.manual_requests_in_flight > 0:
                return False, "A controller command is still finishing."
            ready, message = self._can_ready_for_node_locked(node)
            if not ready:
                return False, message
            self.manual_requests_in_flight += 1
            return True, ""

    def set_controller_enabled(self, node: int, enabled: bool) -> None:
        with self.lock:
            if self.can_connection_node == node:
                self.controller_enabled = enabled

    def _can_ready_for_node_locked(self, desired_node_id: int | None) -> tuple[bool, str]:
        node = node_or_default(desired_node_id, DEFAULT_NODE_ID)
        if self.can_check_running:
            return False, "CAN connection check is still running."
        if (
            self.can_connection_ok is not True
            or self.can_connection_node != node
            or self.manual_mic is None
        ):
            return False, "CAN node is not connected. Change Current Node ID and wait for the check to pass."
        return True, ""

    def _run_task(
        self,
        task_id: str,
        desired_node_id: int | None,
        desired_angle: float | None,
    ) -> None:
        label = TASKS[task_id]
        writer = QueueWriter(self)
        started_at = time.monotonic()
        try:
            with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                result = run_task(task_id, desired_node_id, desired_angle)
            elapsed = time.monotonic() - started_at
            success = is_success(result)
            if success:
                self.append_log(f"\n=== {label} finished in {elapsed:.1f}s ===\n")
                self.append_status(f"Finished: {label}")
            else:
                self.append_log(
                    f"\n=== {label} finished with result {result!r} in {elapsed:.1f}s ===\n"
                )
                self.append_status(f"Error: {label} finished with result {result!r}", is_error=True)
                if task_id in {"start_calibration", "test_calibration", "run_all"}:
                    self.mark_quality_failed_if_pending("calibration stopped before final quality report")
            with self.lock:
                self.status = "Ready." if success else "Finished with errors."
        except Exception:
            self.append_log(format_exc())
            self.append_log(f"\n=== {label} failed ===\n")
            self.append_status(f"Error: {label} failed. Open Debug for details.", is_error=True)
            if task_id in {"start_calibration", "test_calibration", "run_all"}:
                self.mark_quality_failed_if_pending("calibration failed before final quality report")
            with self.lock:
                self.status = "Failed. See log."
        finally:
            with self.lock:
                self.running = False
            if task_id in {"start_calibration", "test_calibration", "run_all", "start_zeroing"}:
                node = node_or_default(desired_node_id, DEFAULT_NODE_ID)
                try:
                    reconnect_gui_can(node)
                except Exception:
                    self.append_log(format_exc())
                    self.append_status(
                        f"CAN reconnect failed after {label}. Press Connect CAN.",
                        is_error=True,
                    )


class QueueWriter(io.TextIOBase):
    def __init__(self, state: AppState) -> None:
        self.state = state
        self._line_buffer = ""

    def write(self, text: str) -> int:
        self.state.append_log(text)
        self._line_buffer += text
        while "\n" in self._line_buffer:
            line, self._line_buffer = self._line_buffer.split("\n", 1)
            self.state.observe_log_line(line)
        return len(text)

    def flush(self) -> None:
        if self._line_buffer:
            self.state.observe_log_line(self._line_buffer)
            self._line_buffer = ""
        pass


def is_success(result) -> bool:
    if result is None:
        return True
    if isinstance(result, bool):
        return result
    if isinstance(result, int):
        return result == 0
    return bool(result)


def node_or_default(desired_node_id: int | None, default_node_id: int) -> int:
    return desired_node_id if desired_node_id is not None else default_node_id


def angle_or_default(desired_angle: float | None) -> float:
    return desired_angle if desired_angle is not None else ZERO_ANGLE_DEG


def angle_error_deg(measured_angle: float, desired_angle: float) -> float:
    return abs((float(measured_angle) - float(desired_angle) + 180.0) % 360.0 - 180.0)


def run_task(task_id: str, desired_node_id: int | None = None, desired_angle: float | None = None):
    if task_id == "run_all":
        return run_all(desired_node_id=desired_node_id, desired_angle=desired_angle)

    if task_id == "load_script":
        import FlashSteeringScript

        return FlashSteeringScript.main(desired_node_id=desired_node_id)

    if task_id == "load_script_config":
        return run_load_script_config(desired_node_id=desired_node_id)

    if task_id == "load_config":
        return run_load_config(node=node_or_default(desired_node_id, DEFAULT_NODE_ID))

    if task_id == "start_calibration":
        import FullCalibration

        print(
            "[INFO] Starting calibration without post-calibration zero write. "
            "Use Write Zero before Calibration when the physical zero must be saved."
        )
        calibration_ok = FullCalibration.main(
            serial_last4=SERIAL_LAST4,
            can_bitrate=DEFAULT_CAN_BITRATE,
            node=node_or_default(desired_node_id, DEFAULT_NODE_ID),
        )
        return calibration_ok

    if task_id == "test_calibration":
        import TestCalibration

        result = TestCalibration.main(
            serial_last4=SERIAL_LAST4,
            can_bitrate=DEFAULT_CAN_BITRATE,
            node=node_or_default(desired_node_id, DEFAULT_NODE_ID),
        )
        if not is_success(result):
            return result

        wait_for_power_cycle_after_test_calibration(STATE.request_power_cycle_confirmation)
        return result

    if task_id == "show_current_zero":
        return run_show_current_zero(
            node=node_or_default(desired_node_id, DEFAULT_NODE_ID),
            desired_angle=angle_or_default(desired_angle),
        )

    if task_id == "start_zeroing":
        return run_zeroing(
            node=node_or_default(desired_node_id, DEFAULT_NODE_ID),
            desired_angle=angle_or_default(desired_angle),
        )

    raise ValueError(f"Unknown task: {task_id}")


def run_manual_spin(node: int, rpm: int, seq: int) -> bool:
    can, mic = STATE.get_manual_controller(node)
    close_after_command = False
    if mic is None:
        can, mic = open_controller(node)
        close_after_command = True
    try:
        if not STATE.is_latest_manual_command(seq):
            print(f"[INFO] Ignored stale manual motor command: {rpm} RPM.")
            return True
        mic.enabled(True)
        if not close_after_command:
            STATE.set_controller_enabled(node, True)
        mic.set_velocity_mode()
        mic.set_RPM(rpm)
        if rpm == 0:
            print(f"[STATUS] Manual motor stop sent to node {node}.")
        else:
            print(f"[STATUS] Manual steering spin sent to node {node}: {rpm} RPM.")
        return True
    finally:
        if close_after_command:
            try:
                can.close_can()
            except Exception:
                pass


def check_can_connection(node: int) -> tuple[bool, str]:
    try:
        can, mic = open_controller(node, enable=False)
    except Exception as exc:
        return False, f"CAN connection failed for node {node}. Change Current Node ID. ({exc})"
    STATE.set_manual_controller(node, can, mic, enabled=False)
    return True, f"CAN connected to node {node}."


def reconnect_gui_can(node: int) -> tuple[bool, str]:
    with STATE.lock:
        can = STATE._detach_manual_controller_locked(message=f"Reconnecting CAN node {node}...")
    if can is not None:
        try:
            can.close_can()
        except Exception:
            pass
    connected, message = check_can_connection(node)
    STATE.append_status(message, is_error=not connected)
    return connected, message


def run_controller_enable(node: int, enabled: bool) -> tuple[bool, str]:
    _can, mic = STATE.get_manual_controller(node)
    if mic is None:
        return False, "CAN node is not connected. Press Connect CAN first."
    mic.enabled(enabled)
    STATE.set_controller_enabled(node, enabled)
    message = f"Controller node {node} {'enabled' if enabled else 'disabled'}."
    print(f"[STATUS] {message}")
    return True, message


def run_controller_clear_errors(node: int) -> tuple[bool, str]:
    _can, mic = STATE.get_manual_controller(node)
    if mic is None:
        return False, "CAN node is not connected. Press Connect CAN first."
    mic.clear_errors()
    message = f"Controller errors cleared on node {node}."
    print(f"[STATUS] {message}")
    return True, message


def run_power_supply_output(node: int, enabled: bool) -> tuple[bool, str]:
    import drivers.driver_owon as driver_owon

    driver_owon = importlib.reload(driver_owon)

    print(f"[STATUS] Turning OWON power supply output {'ON' if enabled else 'OFF'}.")
    driver_owon.set_owon_spe6053_output(
        enabled=enabled,
        voltage_v=24.0,
        current_a=5.0,
        required=True,
    )
    if not enabled:
        return True, "Power supply output is OFF. CAN is disconnected until PS: ON."

    connected, message = check_can_connection(node)
    if not connected:
        return False, f"Power supply output is ON, but {message}"
    return True, f"Power supply output is ON and CAN connected to node {node}."


def automatic_power_cycle_for_zero(_timeout_s: float) -> bool:
    can_to_close = None
    with STATE.lock:
        can_to_close = STATE._detach_manual_controller_locked(
            message="Power-cycling supply for Write Zero verification..."
        )
    if can_to_close is not None:
        try:
            can_to_close.close_can()
        except Exception:
            pass

    import drivers.driver_owon as driver_owon

    driver_owon = importlib.reload(driver_owon)
    print("[STATUS] Automatically power-cycling OWON supply for Write Zero verification.")
    STATE.append_status("Automatically power-cycling OWON supply for Write Zero verification.")
    ok = bool(
        driver_owon.power_cycle_owon_spe6053(
            off_seconds=3.0,
            voltage_v=24.0,
            current_a=5.0,
        )
    )
    if ok:
        STATE.append_status("OWON power cycle completed. Continuing zero verification.")
    else:
        STATE.append_status("OWON power cycle failed during Write Zero.", is_error=True)
    return ok


def wait_for_power_cycle_after_test_calibration(power_cycle_wait_fn) -> None:
    print(
        "[STATUS] TestCalibration finished. Power-cycle the supply now, "
        "then press Continue after power cycle."
    )
    if power_cycle_wait_fn is None:
        raise RuntimeError("Power-cycle confirmation is not available in this run mode.")
    if not power_cycle_wait_fn(POWER_CYCLE_CONFIRM_TIMEOUT_S):
        raise RuntimeError(
            "Timed out waiting for power-cycle confirmation after TestCalibration."
        )
    print("[INFO] Power-cycle confirmed after TestCalibration.")


def run_all(desired_node_id: int | None = None, desired_angle: float | None = None) -> bool:
    if not run_load_script_config(desired_node_id=desired_node_id):
        return False

    print("[INFO] Run All: saving physical zero before calibration.")
    run_zeroing(
        node=node_or_default(desired_node_id, DEFAULT_NODE_ID),
        desired_angle=angle_or_default(desired_angle),
    )

    import FullCalibration

    calibration_ok = FullCalibration.main(
        serial_last4=SERIAL_LAST4,
        can_bitrate=DEFAULT_CAN_BITRATE,
        node=node_or_default(desired_node_id, DEFAULT_NODE_ID),
    )
    if not is_success(calibration_ok):
        return False

    print("[INFO] Run All completed after configuration, pre-calibration zero write, and calibration.")
    return True


def open_controller(node: int = DEFAULT_NODE_ID, enable: bool = True):
    from drivers.driver_can import DriverCan
    import drivers.driver_miControlF35 as driver_miControlF35

    driver_miControlF35 = importlib.reload(driver_miControlF35)
    MicontrolF35_CAN = driver_miControlF35.MicontrolF35_CAN

    can = DriverCan(can_bitrate=DEFAULT_CAN_BITRATE)
    mic = MicontrolF35_CAN(can=can.can_network, node=node)
    if not mic.added_node:
        can.close_can()
        raise RuntimeError(f"Could not add CAN node {node}.")
    if enable:
        mic.enabled(True)
    return can, mic


def acquire_controller(node: int = DEFAULT_NODE_ID, enable: bool = True):
    can, mic = STATE.get_manual_controller(node)
    if mic is not None:
        if enable:
            mic.enabled(True)
            STATE.set_controller_enabled(node, True)
        return can, mic, False

    can, mic = open_controller(node, enable=enable)
    return can, mic, True


def release_controller(can, owned: bool) -> None:
    if not owned:
        return
    try:
        can.close_can()
    except Exception:
        pass


def run_load_script_config(desired_node_id: int | None = None) -> bool:
    import FlashSteeringScript

    print("[INFO] Loading steering script...")
    FlashSteeringScript.main(desired_node_id=desired_node_id)
    print("[INFO] Steering script loaded. Loading MU config...")
    node = node_or_default(desired_node_id, DEFAULT_NODE_ID)
    if not run_load_config(node=node):
        return False
    print("[INFO] Script and MU config loaded. Checking that controller error -1092 is absent...")
    return run_ssi_configuration_check(node=node)


def run_load_config(node: int = DEFAULT_NODE_ID) -> bool:
    import FlashConfigZero

    FlashConfigZero = importlib.reload(FlashConfigZero)
    from FlashConfigZero import MU_Handle, mu, write_just_conf

    can, mic, owned = acquire_controller(node)

    try:
        handle = MU_Handle()
        ok = write_just_conf(mu, handle, mic, SERIAL_LAST4)
        if not ok:
            raise RuntimeError("MU config load failed.")
        return True
    finally:
        release_controller(can, owned)


def run_ssi_configuration_check(node: int = DEFAULT_NODE_ID) -> bool:
    can, mic, owned = acquire_controller(node)
    try:
        if not mic.get_extended_ssi():
            print("[RESULT] ssi_configuration_check ok=False forbidden_error=-1092")
            return False
        print("[RESULT] ssi_configuration_check ok=True error=0")
        return True
    finally:
        try:
            mic.enabled(False)
            STATE.set_controller_enabled(node, False)
        except Exception:
            pass
        release_controller(can, owned)


def run_spin_check_90(node: int = DEFAULT_NODE_ID) -> bool:
    can, mic, owned = acquire_controller(node)
    try:
        ok = spin_to_angle_and_verify(
            mic,
            angle_deg=SPIN_CHECK_DEG,
            rpm=SPIN_CHECK_RPM,
            timeout_s=SPIN_CHECK_TIMEOUT_S,
        )
        if ok:
            print(f"[RESULT] spin_check_{SPIN_CHECK_DEG:.0f}_deg ok=True")
            return True

        print(f"[ERROR] Spin check failed; writing controller error {SPIN_FAILURE_ERROR}.")
        mic.set_error(SPIN_FAILURE_ERROR)
        print(f"[RESULT] spin_check_{SPIN_CHECK_DEG:.0f}_deg ok=False error={SPIN_FAILURE_ERROR}")
        return False
    finally:
        try:
            mic.enabled(False)
            STATE.set_controller_enabled(node, False)
        except Exception:
            pass
        release_controller(can, owned)


def run_show_current_zero(
    node: int = DEFAULT_NODE_ID,
    desired_angle: float = ZERO_ANGLE_DEG,
) -> bool:
    can, mic, owned = acquire_controller(node)
    try:
        print("[INFO] Show Current Zero flow version: controller-reference-v2")
        print(
            "[STATUS] Showing current zero using the controller's current steering-position "
            "reference; no restart or encoder reconfiguration."
        )
        steering_pos = move_controller_to_zero(
            mic,
            context="show current zero",
            require_ssi_ready=False,
        )
        visual_angle = read_camera_angle_deg("show current zero")
        visual_error = angle_error_deg(visual_angle, desired_angle)
        print(
            "[RESULT] Show current zero -> "
            f"controller_position={steering_pos} "
            f"target_position=0 "
            f"tolerance_counts={ZERO_POSITION_TOLERANCE_COUNTS} "
            f"visual_angle={visual_angle:.2f} "
            f"target_angle={desired_angle:.2f} "
            f"visual_error={visual_error:.2f} "
            f"visual_tolerance={ZERO_VISUAL_TOLERANCE_DEG:.2f}"
        )
        ok = (
            steering_pos is not None
            and abs(steering_pos) <= ZERO_POSITION_TOLERANCE_COUNTS
            and visual_error <= ZERO_VISUAL_TOLERANCE_DEG
        )
        return ok
    finally:
        try:
            mic.enabled(False)
            STATE.set_controller_enabled(node, False)
        except Exception:
            pass
        release_controller(can, owned)


def prepare_controller_ssi_encoder(mic, context: str) -> tuple[int | None, int | None, int | None, bool]:
    preferred = CONTROLLER_ENCODER_DIGITAL_OUTPUT
    candidates = (preferred, not preferred)
    last_status = None
    last_direct_pos = None
    last_steering_pos = None
    last_mux = preferred

    mic.clear_errors()
    mic.clear_errors()

    for mux in candidates:
        last_mux = mux
        if mic.SSI_encoder(False):
            print("[INFO] SSI encoder disabled before mux selection.")
        else:
            print("[WARN] SSI encoder disable did not report success before mux selection.")
        time.sleep(0.25)
        mic.set_digital_output(mux)
        print(
            f"[INFO] Controller encoder mux selected before {context}: "
            f"digital_output={mux}"
        )
        time.sleep(0.25)
        mic.clear_errors()
        mic.clear_errors()
        if mic.SSI_encoder(True):
            print("[INFO] SSI encoder enabled before zero move.")
        else:
            print("[WARN] SSI encoder enable did not report success before zero move.")

        deadline = time.monotonic() + 4.0
        while True:
            last_status = mic.get_ssi_encoder_status()
            last_direct_pos = mic.get_ssi_direct_position()
            last_steering_pos = mic.get_steering_pos()
            print(
                "[INFO] Controller SSI state before zero move: "
                f"mux={mux} status={last_status} "
                f"direct_position={last_direct_pos} steering_position={last_steering_pos}"
            )
            if last_status == SSI_READY_STATUS:
                return last_status, last_direct_pos, last_steering_pos, mux
            if time.monotonic() >= deadline:
                break
            time.sleep(0.5)

        print(
            "[WARN] SSI encoder did not reach ready status "
            f"{SSI_READY_STATUS} with digital_output={mux}; trying next mux state."
        )

    raise RuntimeError(
        "Controller SSI encoder is not ready for motion: "
        f"last mux={last_mux} status={last_status} "
        f"direct_position={last_direct_pos} steering_position={last_steering_pos}."
    )


def move_controller_to_zero(
    mic,
    context: str = "zero check",
    require_ssi_ready: bool = True,
) -> int | None:
    initial_pos = mic.get_steering_pos()
    print(f"[INFO] Controller steering position before {context}: {initial_pos}")

    if require_ssi_ready:
        _ssi_status, _ssi_direct_pos, start_pos, _mux = prepare_controller_ssi_encoder(mic, context)
    else:
        mic.clear_errors()
        start_pos = initial_pos
        if start_pos is None:
            raise RuntimeError(
                f"Could not read controller steering position before {context}."
            )
        print(
            f"[INFO] Using existing controller steering reference for {context}: "
            f"position={start_pos}; SSI readiness check skipped."
        )

    if start_pos is not None and abs(start_pos) <= ZERO_POSITION_TOLERANCE_COUNTS:
        print(
            "[INFO] Controller is already at steering position 0; "
            f"position={start_pos} counts within tolerance "
            f"+/-{ZERO_POSITION_TOLERANCE_COUNTS}; "
            "no physical move needed."
        )
        return start_pos

    print("[STATUS] Commanding controller steering position 0.")

    mic.set_device_mode_position()
    mic.set_RPM(ZERO_MOVE_RPM)
    mic.set_steering_RPM(ZERO_MOVE_RPM)
    mic.enabled(True)
    try:
        mic.set_steering_pos(0)
    except Exception as exc:
        print(f"[WARN] Absolute zero move command failed: {exc}")
        if start_pos is None:
            raise
        print(f"[STATUS] Trying relative zero move by {-int(start_pos)} counts.")
        try:
            mic.set_steering_relative(-int(start_pos))
        except Exception as rel_exc:
            raise RuntimeError(
                "Controller refused both absolute and relative zero move commands. "
                f"Initial move error: {exc}; relative move error: {rel_exc}"
            ) from rel_exc

    deadline = time.monotonic() + ZERO_MOVE_TIMEOUT_S
    steering_pos = start_pos
    velocity = None
    while time.monotonic() < deadline:
        time.sleep(0.25)
        steering_pos = mic.get_steering_pos()
        velocity = mic.get_velocity()
        if (
            steering_pos is not None
            and abs(steering_pos) <= ZERO_POSITION_TOLERANCE_COUNTS
            and (velocity is None or abs(velocity) <= 1)
        ):
            break

    time.sleep(ZERO_MOVE_SETTLE_S)
    steering_pos = mic.get_steering_pos()
    velocity = mic.get_velocity()
    print(
        f"[INFO] Controller steering position after {context}: "
        f"{steering_pos} velocity={velocity}"
    )
    if steering_pos is not None and abs(steering_pos) > ZERO_POSITION_TOLERANCE_COUNTS:
        error_code = mic.get_error_code()
        raise RuntimeError(
            "Controller did not reach steering position 0: "
            f"position={steering_pos} velocity={velocity} error={error_code}."
        )
    if steering_pos is None:
        error_code = mic.get_error_code()
        raise RuntimeError(
            "Controller steering position could not be read after zero move: "
            f"velocity={velocity} error={error_code}."
        )
    return steering_pos


def spin_to_angle_and_verify(mic, angle_deg: float, rpm: int, timeout_s: float) -> bool:
    target_counts = int(round(angle_deg * ENCODER_COUNTS_PER_REV / 360.0))
    start_pos = mic.get_actual_position()
    print(
        f"[INFO] Commanding relative {angle_deg:.0f} deg spin "
        f"({target_counts} counts) at {rpm} RPM; start_pos={start_pos}"
    )

    mic.clear_errors()
    mic.set_device_mode_position()
    mic.set_RPM(rpm)
    mic.enabled(True)
    mic.set_steering_relative(target_counts)

    deadline = time.monotonic() + timeout_s
    last_pos = start_pos
    last_velocity = None
    while time.monotonic() < deadline:
        time.sleep(0.2)
        last_pos = mic.get_actual_position()
        last_velocity = mic.get_velocity()
        moved = (
            start_pos is not None
            and last_pos is not None
            and abs(last_pos - start_pos) >= 10
        )
        spinning = last_velocity is not None and abs(last_velocity) > 0
        if moved or spinning:
            print(
                f"[INFO] Spin verified: pos={last_pos} "
                f"delta={None if start_pos is None or last_pos is None else last_pos - start_pos} "
                f"velocity={last_velocity}"
            )
            return True

    print(
        f"[ERROR] No spin detected after {timeout_s:.1f}s: "
        f"start_pos={start_pos} last_pos={last_pos} velocity={last_velocity}"
    )
    return False


def read_camera_angle_deg(context: str) -> float:
    from drivers.driver_cam_st import AngleDetection

    for attempt in range(1, ANGLE_READ_ATTEMPTS + 1):
        print(f"[STATUS] Waiting {ANGLE_SETTLE_S:.1f}s for camera angle to stabilize.")
        time.sleep(ANGLE_SETTLE_S)
        print(
            f"[STATUS] Reading camera angle for {context} "
            f"({ANGLE_SAMPLES} samples, timeout {ANGLE_TIMEOUT_S:.0f}s, "
            f"attempt {attempt}/{ANGLE_READ_ATTEMPTS})."
        )
        angle = AngleDetection(debug=False, return_after=ANGLE_SAMPLES, timeout_s=ANGLE_TIMEOUT_S)
        if angle is not None:
            print(f"[INFO] Camera angle for {context}: {float(angle):.2f} deg")
            return float(angle)
        if attempt < ANGLE_READ_ATTEMPTS:
            print("[WARN] Camera angle was not detected; retrying once.")

    raise RuntimeError(
        f"Could not measure steering angle during {context}. "
        "Check that the webcam is connected, accessible, not already in use, "
        "and that the marker is visible. If needed, set ST_CAMERA_ID to the correct camera index."
    )


def run_zeroing(
    node: int = DEFAULT_NODE_ID,
    desired_angle: float = ZERO_ANGLE_DEG,
) -> None:
    import FlashConfigZero

    FlashConfigZero = importlib.reload(FlashConfigZero)
    from FlashConfigZero import write_des_zero_process

    zero_saved = write_des_zero_process(
        serial_last4=SERIAL_LAST4,
        node=node,
        desired_angle=desired_angle,
        can_bitrate=DEFAULT_CAN_BITRATE,
        read_angle_fn=lambda: read_camera_angle_deg("zeroing"),
        prepare_controller_fn=prepare_controller_ssi_encoder,
        power_cycle_wait_fn=automatic_power_cycle_for_zero,
        preserve_current_encoder_config=True,
    )
    if not zero_saved:
        raise RuntimeError("Zeroing parameters were not saved to both encoders.")


STATE = AppState()


def kill_all_programs() -> None:
    STATE.append_status("Kill All Programs pressed. Stopping GUI process.", is_error=True)

    def force_exit() -> None:
        time.sleep(0.2)
        os._exit(0)

    threading.Thread(target=force_exit, daemon=True).start()


def parse_optional_node_id(raw_value: str) -> int | None:
    if not raw_value.strip():
        return None
    node_id = int(raw_value)
    if not 1 <= node_id <= 127:
        raise ValueError("Desired NodeID must be between 1 and 127.")
    return node_id


def parse_optional_angle(raw_value: str) -> float | None:
    if not raw_value.strip():
        return None
    return float(raw_value)


def parse_manual_rpm(raw_value: str) -> int:
    rpm = int(raw_value)
    if rpm == 0:
        return rpm
    if not MANUAL_SPIN_MIN_RPM <= abs(rpm) <= MANUAL_SPIN_MAX_RPM:
        raise ValueError(
            f"Manual RPM must be 0 or between +/-{MANUAL_SPIN_MIN_RPM} "
            f"and +/-{MANUAL_SPIN_MAX_RPM}."
        )
    return rpm


def parse_manual_seq(raw_value: str) -> int:
    seq = int(raw_value)
    if seq < 0:
        raise ValueError("Manual command sequence must be positive.")
    return seq


def parse_enabled(raw_value: str) -> bool:
    if raw_value in {"1", "true", "True", "on"}:
        return True
    if raw_value in {"0", "false", "False", "off"}:
        return False
    raise ValueError("Enabled value must be 1 or 0.")


class CalibrationRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(HTML)
            return
        if parsed.path == "/logo.png":
            self._send_file(LOGO_PATH, "image/png")
            return
        if parsed.path == "/status":
            self._send_json(STATE.snapshot())
            return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/clear-log":
            STATE.clear_log()
            self._send_json({"ok": True})
            return

        if parsed.path == "/kill-all":
            kill_all_programs()
            self._send_json({"ok": True})
            return

        if parsed.path == "/confirm-power-cycle":
            ok = STATE.confirm_power_cycle()
            self._send_json({"ok": ok})
            return

        if parsed.path == "/disconnect-can":
            ok, message = STATE.disconnect_can()
            STATE.append_status(message, is_error=not ok)
            self._send_json({"ok": ok, "message": message, "error": "" if ok else message})
            return

        if parsed.path == "/check-can":
            query = parse_qs(parsed.query)
            try:
                desired_node_id = parse_optional_node_id(query.get("node_id", [""])[0])
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)})
                return

            node = node_or_default(desired_node_id, DEFAULT_NODE_ID)
            ok, error = STATE.begin_can_check(node)
            if not ok:
                self._send_json({"ok": False, "error": error})
                return

            writer = QueueWriter(STATE)
            try:
                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    connected, message = check_can_connection(node)
                STATE.finish_can_check(node, connected, message)
                STATE.append_status(message, is_error=not connected)
                self._send_json(
                    {
                        "ok": connected,
                        "message": message if connected else "",
                        "error": "" if connected else message,
                        "controller_enabled": False,
                    }
                )
            except Exception as exc:
                message = f"CAN connection failed for node {node}. Change Current Node ID. ({exc})"
                STATE.append_log(format_exc())
                STATE.finish_can_check(node, False, message)
                STATE.append_status(message, is_error=True)
                self._send_json({"ok": False, "error": message})
            return

        if parsed.path == "/controller-enable":
            query = parse_qs(parsed.query)
            try:
                desired_node_id = parse_optional_node_id(query.get("node_id", [""])[0])
                enabled = parse_enabled(query.get("enabled", [""])[0])
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)})
                return

            node = node_or_default(desired_node_id, DEFAULT_NODE_ID)
            ok, error = STATE.begin_controller_command(node)
            if not ok:
                self._send_json({"ok": False, "error": error})
                return

            writer = QueueWriter(STATE)
            try:
                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    ok, message = run_controller_enable(node=node, enabled=enabled)
                STATE.append_status(message, is_error=not ok)
                self._send_json(
                    {
                        "ok": ok,
                        "message": message if ok else "",
                        "error": "" if ok else message,
                        "controller_enabled": enabled if ok else STATE.snapshot()["controller_enabled"],
                    }
                )
            except Exception as exc:
                STATE.append_log(format_exc())
                message = f"Controller {'enable' if enabled else 'disable'} failed on node {node}. ({exc})"
                STATE.append_status(message, is_error=True)
                self._send_json({"ok": False, "error": message})
            finally:
                STATE.finish_manual_command()
            return

        if parsed.path == "/clear-controller-errors":
            query = parse_qs(parsed.query)
            try:
                desired_node_id = parse_optional_node_id(query.get("node_id", [""])[0])
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)})
                return

            node = node_or_default(desired_node_id, DEFAULT_NODE_ID)
            ok, error = STATE.begin_controller_command(node)
            if not ok:
                self._send_json({"ok": False, "error": error})
                return

            writer = QueueWriter(STATE)
            try:
                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    ok, message = run_controller_clear_errors(node=node)
                STATE.append_status(message, is_error=not ok)
                self._send_json(
                    {
                        "ok": ok,
                        "message": message if ok else "",
                        "error": "" if ok else message,
                    }
                )
            except Exception as exc:
                STATE.append_log(format_exc())
                message = f"Clear error failed on node {node}. ({exc})"
                STATE.append_status(message, is_error=True)
                self._send_json({"ok": False, "error": message})
            finally:
                STATE.finish_manual_command()
            return

        if parsed.path == "/power-supply-output":
            query = parse_qs(parsed.query)
            try:
                desired_node_id = parse_optional_node_id(query.get("node_id", [""])[0])
                enabled = parse_enabled(query.get("enabled", [""])[0])
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)})
                return

            node = node_or_default(desired_node_id, DEFAULT_NODE_ID)
            ok, error, can_to_close = STATE.begin_power_supply_output(node, enabled)
            if not ok:
                self._send_json({"ok": False, "error": error})
                return

            if can_to_close is not None:
                try:
                    can_to_close.close_can()
                except Exception:
                    pass

            writer = QueueWriter(STATE)
            try:
                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    ok, message = run_power_supply_output(node, enabled)
                STATE.finish_power_supply_output(enabled, ok, message)
                self._send_json(
                    {
                        "ok": ok,
                        "message": message if ok else "",
                        "error": "" if ok else message,
                        "can_connection_ok": ok and enabled,
                        "controller_enabled": False,
                    }
                )
            except Exception as exc:
                STATE.append_log(format_exc())
                message = f"Power supply {'ON' if enabled else 'OFF'} failed. ({exc})"
                STATE.finish_power_supply_output(enabled, False, message)
                self._send_json({"ok": False, "error": message})
            return

        if parsed.path == "/manual-spin":
            query = parse_qs(parsed.query)
            try:
                desired_node_id = parse_optional_node_id(query.get("node_id", [""])[0])
                rpm = parse_manual_rpm(query.get("rpm", [""])[0])
                seq = parse_manual_seq(query.get("seq", ["0"])[0])
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)})
                return

            node = node_or_default(desired_node_id, DEFAULT_NODE_ID)
            ok, error = STATE.begin_manual_command(seq, node, rpm)
            if not ok:
                self._send_json({"ok": not error, "error": error})
                return

            STATE.append_log("\n=== Manual Motor Spin started ===\n")
            STATE.append_status(
                "Manual motor stop requested." if rpm == 0 else f"Manual motor requested: {rpm} RPM"
            )

            writer = QueueWriter(STATE)
            try:
                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    run_manual_spin(node=node, rpm=rpm, seq=seq)
                STATE.append_log("\n=== Manual Motor Spin finished ===\n")
                STATE.append_status(
                    "Manual motor stopped." if rpm == 0 else f"Manual motor command: {rpm} RPM"
                )
                self._send_json({"ok": True})
            except Exception as exc:
                STATE.append_log(format_exc())
                STATE.append_log("\n=== Manual Motor Spin failed ===\n")
                STATE.append_status(
                    "Error: Manual motor command failed. Open Debug for details.",
                    is_error=True,
                )
                self._send_json({"ok": False, "error": str(exc)})
            finally:
                STATE.finish_manual_command()
            return

        if parsed.path != "/start":
            self.send_error(404)
            return

        query = parse_qs(parsed.query)
        task_id = query.get("task", [""])[0]
        try:
            desired_node_id = parse_optional_node_id(query.get("node_id", [""])[0])
            desired_angle = parse_optional_angle(query.get("desired_angle", [""])[0])
        except ValueError as exc:
            self._send_json({"ok": False, "error": str(exc)})
            return

        ok, error = STATE.start_task(task_id, desired_node_id, desired_angle)
        self._send_json({"ok": ok, "error": error})

    def log_message(self, format: str, *args) -> None:
        pass

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), CalibrationRequestHandler)
    host, port = server.server_address
    url = f"http://{host}:{port}/"
    print(f"Calibration GUI running at {url}")
    print("Press Ctrl+C three times quickly in this terminal to stop it.")

    def open_browser() -> None:
        try:
            webbrowser.open(url)
        except Exception as exc:
            print(f"[WARN] Could not open browser automatically: {exc}")

    threading.Thread(target=open_browser, daemon=True).start()
    restore_sigint = install_deferred_keyboard_interrupt(
        label="Calibration GUI",
        on_interrupt=lambda signum, frame: threading.Thread(
            target=server.shutdown,
            daemon=True,
        ).start(),
    )
    try:
        server.serve_forever()
    finally:
        restore_sigint()
        server.server_close()


if __name__ == "__main__":
    main()
