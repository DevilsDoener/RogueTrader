/* Field previews, autosave and conflict resolution for the sheet viewer.
 * This file is loaded on both the owner's editable
 * view and the portal admin's read-only view; the `data-read-only`
 * attribute on #sheet-viewer-root gates all of the autosave wiring so the
 * admin view never issues a single field request.
 *
 * Nothing here ever logs a field value -- only field ids and generic status
 * strings are written to the DOM/console.
 */
(function () {
  "use strict";

  const root = document.getElementById("sheet-viewer-root");
  if (!root) {
    return;
  }

  const readOnly = root.dataset.readOnly === "true";
  const fieldUrlTemplate = root.dataset.fieldUrlTemplate || "";

  const statusEl = document.getElementById("sheet-save-status");
  const conflictPanels = new Map();

  const textMeasure = document.createElement("canvas").getContext("2d");
  function fitShipText(input) {
    if (!input.closest('[data-page-id="ship-page"]')) return;
    input.style.fontSize = "";
    if (!input.value) return;
    const style = getComputedStyle(input);
    const available = input.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
    if (available <= 0) return;
    textMeasure.font = style.font;
    const needed = textMeasure.measureText(input.value).width;
    if (needed > available) {
      input.style.fontSize = (parseFloat(style.fontSize) * (available - 1) / needed) + "px";
    }
  }
  function fitShipFields() {
    root.querySelectorAll('[data-page-id="ship-page"] .sheet-text').forEach(fitShipText);
  }
  // Font size depends on the unscaled canvas width, including its initial fit.
  const shipCanvas = root.querySelector('[data-page-id="ship-page"] .sheet-canvas');
  if (shipCanvas && typeof ResizeObserver === "function") {
    new ResizeObserver(fitShipFields).observe(shipCanvas);
  }
  if (document.fonts) document.fonts.ready.then(fitShipFields);
  window.addEventListener("resize", fitShipFields);

  // Movement factors and the characteristic counterpart map come from the
  // server (sheets/movement.py, sheets/characteristics.py) as JSON next to
  // the sheet, so the instant preview below can never drift from the rules
  // the server enforces. Pages without them (the ship sheet) skip the previews.
  const rulesEl = document.getElementById("sheet-client-rules");
  let rules = {};
  if (rulesEl) {
    try {
      rules = JSON.parse(rulesEl.textContent) || {};
    } catch (error) {
      // Without the rules only the instant previews are lost; the server
      // still computes and returns every derived value.
      rules = {};
    }
  }
  const movementRules = rules.movement || null;
  const movementDigits = movementRules
    ? new RegExp("^\\d{1," + movementRules.max_digits + "}$")
    : null;
  const characteristicCounterparts = rules.counterparts || {};

  function updateMovement(input) {
    if (!movementRules || input.dataset.fieldId !== movementRules.source) return;
    const valid = movementDigits.test(input.value);
    for (const [id, factor] of Object.entries(movementRules.factors)) {
      const target = root.querySelector('[data-field-id="' + id + '"]');
      if (!target) continue;
      target.value = valid ? String(Number(input.value) * factor) : "";
      refreshField(target);
    }
  }
  function characteristicCounterpart(input) {
    const counterpartId = characteristicCounterparts[input.dataset.fieldId || ""];
    if (!counterpartId) return null;
    return root.querySelector('[data-field-id="' + counterpartId + '"]');
  }
  function updateCharacteristic(input) {
    const target = characteristicCounterpart(input);
    if (!target) return;
    if (input.type === "checkbox") {
      target.checked = input.checked;
    } else {
      target.value = input.value;
      refreshField(target);
    }
  }
  // Brings a text field's presentation in line with its current value: the
  // "has-value" class, the ship font fit and (for Half Move) the derived
  // movement fields, which are refreshed in turn.
  function refreshField(input) {
    if (input.type === "checkbox") return;
    input.classList.toggle("has-value", input.value.trim() !== "");
    fitShipText(input);
    updateMovement(input);
  }

  root.querySelectorAll(".sheet-text").forEach(refreshField);

  if (readOnly) {
    // Admin view: no autosave wiring is attached below, so no field request
    // is ever made.
    return;
  }

  // ---- Autosave / conflict handling ----

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : "";
  }

  function fieldUrl(fieldId) {
    return fieldUrlTemplate.replace("__FIELD_ID__", encodeURIComponent(fieldId));
  }

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
  }

  // Saves are serialized per field: while a request for a field is in
  // flight, further edits only mark the field as "queued" and the newest
  // value is sent once the response (and with it the new version) is in. Two
  // requests for one field never race, so a user can never conflict with
  // their own previous save.
  const inFlight = new Set();
  const queued = new Set();
  // fieldId -> {timer, input}: edits waiting for the 600 ms debounce.
  const pendingSaves = new Map();

  function closeConflictPanel(input) {
    const entry = conflictPanels.get(input);
    if (!entry) return;
    window.removeEventListener("resize", entry.reposition);
    window.removeEventListener("scroll", entry.reposition, true);
    entry.panel.remove();
    conflictPanels.delete(input);
  }

  function positionConflictPanel(input, panel) {
    const viewportPadding = 8;
    const anchorGap = 4;
    const anchor = input.getBoundingClientRect();
    const panelRect = panel.getBoundingClientRect();
    const maxLeft = Math.max(viewportPadding, window.innerWidth - panelRect.width - viewportPadding);
    const maxTop = Math.max(viewportPadding, window.innerHeight - panelRect.height - viewportPadding);

    let left = anchor.left;
    if (left + panelRect.width > window.innerWidth - viewportPadding) {
      left = anchor.right - panelRect.width;
    }
    left = Math.min(Math.max(left, viewportPadding), maxLeft);

    const below = anchor.bottom + anchorGap;
    const above = anchor.top - panelRect.height - anchorGap;
    let top;
    if (below + panelRect.height <= window.innerHeight - viewportPadding) {
      top = below;
    } else if (above >= viewportPadding) {
      top = above;
    } else {
      top = Math.min(Math.max(below, viewportPadding), maxTop);
    }

    panel.style.left = Math.round(left) + "px";
    panel.style.top = Math.round(top) + "px";
  }

  function showConflictPanel(input, conflict) {
    closeConflictPanel(input);
    const wrapper = input.closest(".sheet-field");
    if (!wrapper) return;

    const panel = document.createElement("div");
    panel.className = "sheet-conflict-panel";
    panel.setAttribute("role", "alertdialog");

    const message = document.createElement("p");
    message.className = "sheet-conflict-message";
    message.textContent = "Dieses Feld wurde zwischenzeitlich anderswo geändert.";
    panel.appendChild(message);

    const takeCurrentBtn = document.createElement("button");
    takeCurrentBtn.type = "button";
    takeCurrentBtn.className = "sheet-conflict-take-current";
    takeCurrentBtn.textContent = "Aktuellen Wert übernehmen";
    takeCurrentBtn.addEventListener("click", () => {
      if (input.type === "checkbox") {
        input.checked = Boolean(conflict.current_value);
      } else {
        input.value = conflict.current_value == null ? "" : String(conflict.current_value);
        refreshField(input);
      }
      updateCharacteristic(input);
      input.dataset.version = String(conflict.current_version);
      closeConflictPanel(input);
      setStatus("Gespeichert");
    });

    const retryMineBtn = document.createElement("button");
    retryMineBtn.type = "button";
    retryMineBtn.className = "sheet-conflict-retry-mine";
    retryMineBtn.textContent = "Meinen Wert erneut speichern";
    retryMineBtn.addEventListener("click", () => {
      input.dataset.version = String(conflict.current_version);
      closeConflictPanel(input);
      saveField(input);
    });

    panel.appendChild(takeCurrentBtn);
    panel.appendChild(retryMineBtn);
    panel.style.visibility = "hidden";
    document.body.appendChild(panel);

    const reposition = () => positionConflictPanel(input, panel);
    conflictPanels.set(input, { panel: panel, reposition: reposition });
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
    reposition();
    panel.style.visibility = "visible";
  }

  function readValue(input) {
    return input.type === "checkbox" ? input.checked : input.value;
  }

  function applyDerivedFields(input, value, calculated) {
    for (const [id, derived] of Object.entries(calculated || {})) {
      const target = root.querySelector('[data-field-id="' + id + '"]');
      if (!target) continue;
      target.dataset.version = String(derived.version);
      // A newer unsaved input must retain its live preview.
      if (readValue(input) === value) {
        if (target.type === "checkbox") {
          target.checked = Boolean(derived.value);
        } else {
          target.value = derived.value;
          refreshField(target);
        }
      }
    }
  }

  function saveField(input, options) {
    const fieldId = input.dataset.fieldId;
    if (inFlight.has(fieldId)) {
      queued.add(fieldId);
      return;
    }
    const value = readValue(input);
    const baseVersion = parseInt(input.dataset.version, 10) || 0;
    inFlight.add(fieldId);

    setStatus("Speichert…");

    fetch(fieldUrl(fieldId), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify({ value: value, base_version: baseVersion }),
      credentials: "same-origin",
      keepalive: Boolean(options && options.keepalive),
    })
      .then((response) =>
        response.json().then(
          (data) => ({ status: response.status, data: data }),
          () => ({ status: response.status, data: null })
        )
      )
      .catch(() => ({ status: 0, data: null }))
      .then((result) => {
        inFlight.delete(fieldId);
        const resave = queued.delete(fieldId);
        if (result.status === 200 && result.data) {
          input.dataset.version = String(result.data.version);
          applyDerivedFields(input, value, result.data.calculated_fields);
          closeConflictPanel(input);
          setStatus("Gespeichert");
        } else if (result.status === 409 && result.data) {
          // The newest value is shown in the conflict panel; do not
          // overwrite the other change behind the user's back.
          setStatus("Fehler");
          showConflictPanel(input, result.data);
          return;
        } else {
          setStatus("Fehler");
        }
        if (resave) saveField(input);
      });
  }

  function scheduleSave(input) {
    const fieldId = input.dataset.fieldId;
    const existing = pendingSaves.get(fieldId);
    if (existing) clearTimeout(existing.timer);
    const timer = setTimeout(() => {
      pendingSaves.delete(fieldId);
      saveField(input);
    }, 600);
    pendingSaves.set(fieldId, { timer: timer, input: input });
  }

  function flushPendingSave(input, options) {
    const fieldId = input.dataset.fieldId;
    const existing = pendingSaves.get(fieldId);
    if (existing) {
      clearTimeout(existing.timer);
      pendingSaves.delete(fieldId);
      saveField(input, options);
    }
  }

  // Closing or hiding the tab within the debounce window must not drop the
  // last keystrokes: send them now, with keepalive so the request survives
  // the page being unloaded.
  function flushAllPendingSaves() {
    for (const entry of Array.from(pendingSaves.values())) {
      flushPendingSave(entry.input, { keepalive: true });
    }
  }
  window.addEventListener("pagehide", flushAllPendingSaves);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flushAllPendingSaves();
  });

  root.querySelectorAll(".sheet-input").forEach((input) => {
    if (input.readOnly) return;
    if (input.dataset.kind === "checkbox") {
      input.addEventListener("change", () => {
        updateCharacteristic(input);
        saveField(input);
      });
    } else {
      input.addEventListener("input", () => {
        refreshField(input);
        updateCharacteristic(input);
        scheduleSave(input);
      });
      input.addEventListener("blur", () => flushPendingSave(input));
    }
  });
})();
