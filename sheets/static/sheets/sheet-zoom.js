/* Zoom control for the sheet viewer canvas. Independent of sheet-viewer.js
 * (autosave) -- this only ever touches --sheet-zoom on #sheet-canvas-wrapper
 * and a localStorage preference, and runs on the read-only admin view too.
 */
(function () {
  "use strict";

  const wrapper = document.getElementById("sheet-canvas-wrapper");
  if (!wrapper) {
    return;
  }

  const MIN_ZOOM = 30;
  const MAX_ZOOM = 100;
  const STEP = 10;
  const DEFAULT_ZOOM = 100;
  const STORAGE_KEY = "sheets:viewer:zoom";

  const zoomOutBtn = document.querySelector(".sheet-zoom-out");
  const zoomInBtn = document.querySelector(".sheet-zoom-in");
  const levelEl = document.getElementById("sheet-zoom-level");

  function clamp(value) {
    return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value));
  }

  function loadStoredZoom() {
    let stored;
    try {
      stored = window.localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      return DEFAULT_ZOOM;
    }
    const parsed = parseInt(stored, 10);
    return Number.isNaN(parsed) ? DEFAULT_ZOOM : clamp(parsed);
  }

  function storeZoom(value) {
    try {
      window.localStorage.setItem(STORAGE_KEY, String(value));
    } catch (e) {
      // localStorage unavailable (private mode / disabled) -- zoom still
      // works for this page view, it just won't persist.
    }
  }

  let currentZoom = DEFAULT_ZOOM;

  function applyZoom(value) {
    currentZoom = clamp(value);
    wrapper.style.setProperty("--sheet-zoom", String(currentZoom / 100));
    if (levelEl) levelEl.textContent = currentZoom + "%";
    if (zoomOutBtn) zoomOutBtn.disabled = currentZoom <= MIN_ZOOM;
    if (zoomInBtn) zoomInBtn.disabled = currentZoom >= MAX_ZOOM;
    storeZoom(currentZoom);
  }

  applyZoom(loadStoredZoom());

  if (zoomOutBtn) {
    zoomOutBtn.addEventListener("click", () => applyZoom(currentZoom - STEP));
  }
  if (zoomInBtn) {
    zoomInBtn.addEventListener("click", () => applyZoom(currentZoom + STEP));
  }

  document.addEventListener("keydown", (event) => {
    if (!(event.ctrlKey || event.metaKey)) return;
    if (event.key === "-") {
      event.preventDefault();
      applyZoom(currentZoom - STEP);
    } else if (event.key === "+" || event.key === "=") {
      event.preventDefault();
      applyZoom(currentZoom + STEP);
    } else if (event.key === "0") {
      event.preventDefault();
      applyZoom(DEFAULT_ZOOM);
    }
  });
})();
