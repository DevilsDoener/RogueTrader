/* Pan/zoom viewer controls, field autosave, and conflict resolution for the
 * character sheet viewer. This file is loaded on both the owner's editable
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
  const userId = root.dataset.userId || "anonymous";
  const sheetId = root.dataset.sheetId || "unknown";
  const fieldUrlTemplate = root.dataset.fieldUrlTemplate || "";

  const viewport = root.querySelector(".sheet-viewport");
  const canvasWrapper = root.querySelector(".sheet-canvas-wrapper");
  const pages = Array.from(root.querySelectorAll(".sheet-page"));
  const pageTabs = Array.from(root.querySelectorAll(".sheet-page-tab"));
  const statusEl = document.getElementById("sheet-save-status");

  const ZOOM_MIN = 0.5;
  const ZOOM_MAX = 3;
  const storageKeyPrefix = "sheets:viewer:" + userId + ":" + sheetId + ":";

  const state = {
    pageIndex: 0,
    zoom: 1,
    panX: 0,
    panY: 0,
  };

  function clampZoom(zoom) {
    return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, zoom));
  }

  function loadStoredState() {
    const storedPage = parseInt(localStorage.getItem(storageKeyPrefix + "page"), 10);
    const storedZoom = parseFloat(localStorage.getItem(storageKeyPrefix + "zoom"));
    if (!Number.isNaN(storedPage) && storedPage >= 0 && storedPage < pages.length) {
      state.pageIndex = storedPage;
    }
    if (!Number.isNaN(storedZoom)) {
      state.zoom = clampZoom(storedZoom);
    }
  }

  function persistState() {
    try {
      localStorage.setItem(storageKeyPrefix + "page", String(state.pageIndex));
      localStorage.setItem(storageKeyPrefix + "zoom", String(state.zoom));
    } catch (err) {
      // localStorage may be unavailable (private browsing, quota); the
      // viewer still works, it just won't remember page/zoom next visit.
    }
  }

  function applyTransform() {
    if (!canvasWrapper) return;
    canvasWrapper.style.transform =
      "translate(" + state.panX + "px, " + state.panY + "px) scale(" + state.zoom + ")";
  }

  function showPage(index) {
    pages.forEach((page, i) => {
      if (i === index) {
        page.removeAttribute("hidden");
      } else {
        page.setAttribute("hidden", "");
      }
    });
    pageTabs.forEach((tab, i) => {
      const active = i === index;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-current", active ? "true" : "false");
    });
    state.pageIndex = index;
    persistState();
  }

  pageTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const index = parseInt(tab.dataset.pageIndex, 10);
      if (!Number.isNaN(index)) {
        showPage(index);
      }
    });
  });

  function setZoom(zoom) {
    state.zoom = clampZoom(zoom);
    applyTransform();
    persistState();
  }

  const zoomInBtn = document.getElementById("zoom-in");
  const zoomOutBtn = document.getElementById("zoom-out");
  const fitWidthBtn = document.getElementById("fit-width");
  const fitPageBtn = document.getElementById("fit-page");

  if (zoomInBtn) zoomInBtn.addEventListener("click", () => setZoom(state.zoom + 0.1));
  if (zoomOutBtn) zoomOutBtn.addEventListener("click", () => setZoom(state.zoom - 0.1));

  function currentCanvas() {
    const page = pages[state.pageIndex];
    return page ? page.querySelector(".sheet-canvas") : null;
  }

  function resetPan() {
    state.panX = 0;
    state.panY = 0;
  }

  function fitWidth() {
    if (!viewport) return;
    const canvas = currentCanvas();
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const naturalWidth = rect.width / state.zoom;
    if (naturalWidth <= 0) return;
    resetPan();
    setZoom(viewport.clientWidth / naturalWidth);
  }

  function fitPage() {
    if (!viewport) return;
    const canvas = currentCanvas();
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const naturalWidth = rect.width / state.zoom;
    const naturalHeight = rect.height / state.zoom;
    if (naturalWidth <= 0 || naturalHeight <= 0) return;
    resetPan();
    setZoom(
      Math.min(viewport.clientWidth / naturalWidth, viewport.clientHeight / naturalHeight)
    );
  }

  if (fitWidthBtn) fitWidthBtn.addEventListener("click", fitWidth);
  if (fitPageBtn) fitPageBtn.addEventListener("click", fitPage);

  if (viewport) {
    // Wheel/pinch zoom. Trackpad pinch gestures are reported by browsers as
    // wheel events with ctrlKey set; a plain scroll wheel is left alone so
    // the viewport can still be scrolled by whatever contains it.
    viewport.addEventListener(
      "wheel",
      (event) => {
        if (!event.ctrlKey && !event.metaKey) return;
        event.preventDefault();
        setZoom(state.zoom - event.deltaY * 0.01);
      },
      { passive: false }
    );

    // Pointer-drag panning.
    let dragging = false;
    let lastX = 0;
    let lastY = 0;

    viewport.addEventListener("pointerdown", (event) => {
      if (event.target.closest(".sheet-input")) return;
      dragging = true;
      lastX = event.clientX;
      lastY = event.clientY;
      viewport.classList.add("dragging");
    });
    window.addEventListener("pointermove", (event) => {
      if (!dragging) return;
      state.panX += event.clientX - lastX;
      state.panY += event.clientY - lastY;
      lastX = event.clientX;
      lastY = event.clientY;
      applyTransform();
    });
    window.addEventListener("pointerup", () => {
      if (!dragging) return;
      dragging = false;
      viewport.classList.remove("dragging");
      persistState();
    });
  }

  loadStoredState();
  showPage(state.pageIndex);
  applyTransform();

  function updateHasValue(input) {
    if (input.type === "checkbox") return;
    input.classList.toggle("has-value", input.value.trim() !== "");
  }

  root.querySelectorAll(".sheet-text").forEach(updateHasValue);

  if (readOnly) {
    // Admin view: geometry/pan/zoom above still works for reading, but no
    // autosave wiring is attached below, so no field request is ever made.
    return;
  }

  // ---- Autosave / conflict handling ----

  function getCsrfToken() {
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : "";
  }

  function fieldUrl(fieldId) {
    return fieldUrlTemplate.replace("__FIELD_ID__", encodeURIComponent(fieldId));
  }

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
  }

  // Per-field monotonic request token: each save captures the token in
  // flight at send time, and a response is only applied if it's still the
  // most recent token issued for that field -- otherwise a newer local
  // edit is already in flight and this (older) response is dropped so it
  // cannot clobber it.
  const fieldTokens = new Map();
  const debounceTimers = new Map();

  function nextToken(fieldId) {
    const token = (fieldTokens.get(fieldId) || 0) + 1;
    fieldTokens.set(fieldId, token);
    return token;
  }

  function closeConflictPanel(input) {
    const wrapper = input.closest(".sheet-field");
    const panel = wrapper && wrapper.querySelector(".sheet-conflict-panel");
    if (panel) panel.remove();
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
        updateHasValue(input);
      }
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
    wrapper.appendChild(panel);
  }

  function readValue(input) {
    return input.type === "checkbox" ? input.checked : input.value;
  }

  function saveField(input) {
    const fieldId = input.dataset.fieldId;
    const value = readValue(input);
    const baseVersion = parseInt(input.dataset.version, 10) || 0;
    const token = nextToken(fieldId);

    setStatus("Speichert…");

    fetch(fieldUrl(fieldId), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify({ value: value, base_version: baseVersion }),
      credentials: "same-origin",
    })
      .then((response) => response.json().then((data) => ({ status: response.status, data: data })))
      .then((result) => {
        if (fieldTokens.get(fieldId) !== token) {
          // A newer save for this field has since been issued; this
          // response is stale and must not touch the field's state.
          return;
        }
        if (result.status === 200) {
          input.dataset.version = String(result.data.version);
          closeConflictPanel(input);
          setStatus("Gespeichert");
        } else if (result.status === 409) {
          setStatus("Fehler");
          showConflictPanel(input, result.data);
        } else {
          setStatus("Fehler");
        }
      })
      .catch(() => {
        if (fieldTokens.get(fieldId) !== token) return;
        setStatus("Fehler");
      });
  }

  function scheduleSave(input) {
    const fieldId = input.dataset.fieldId;
    const existing = debounceTimers.get(fieldId);
    if (existing) clearTimeout(existing);
    const timer = setTimeout(() => {
      debounceTimers.delete(fieldId);
      saveField(input);
    }, 600);
    debounceTimers.set(fieldId, timer);
  }

  function flushPendingSave(input) {
    const fieldId = input.dataset.fieldId;
    const existing = debounceTimers.get(fieldId);
    if (existing) {
      clearTimeout(existing);
      debounceTimers.delete(fieldId);
      saveField(input);
    }
  }

  root.querySelectorAll(".sheet-input").forEach((input) => {
    if (input.dataset.kind === "checkbox") {
      input.addEventListener("change", () => saveField(input));
    } else {
      input.addEventListener("input", () => {
        updateHasValue(input);
        scheduleSave(input);
      });
      input.addEventListener("blur", () => flushPendingSave(input));
    }
  });
})();
