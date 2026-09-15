/* Scaling controller for the sheet viewer canvas. Independent of
 * sheet-viewer.js (autosave); runs on the read-only admin view too.
 *
 * It owns ONE scale factor per page that combines two things:
 *   - fit: shrink the natural-pixel canvas to the available column width
 *   - zoom: the user's 30-100% preference on top of that fit
 * scale = (availableWidth / naturalWidth) * (zoom / 100)
 *
 * That single `transform: scale(scale)` on .sheet-canvas moves the background
 * image and every field (text + checkbox) as one unit, so nothing can drift
 * relative to the artwork on zoom or at any width. Because a transform does not
 * change the layout box, we also pin .sheet-page to the on-screen (scaled) size
 * so document flow, height and vertical scroll stay correct. The transform is
 * on .sheet-canvas, never on #sheet-canvas-wrapper (which stays transform:none).
 */
(function () {
  "use strict";

  const wrapper = document.getElementById("sheet-canvas-wrapper");
  if (!wrapper) {
    return;
  }
  const root = document.getElementById("sheet-viewer-root");

  const MIN_ZOOM = 30;
  const MAX_ZOOM = 100;
  const STEP = 10;
  const DEFAULT_ZOOM = 100;
  const STORAGE_KEY = "sheets:viewer:zoom";

  const zoomOutBtn = document.querySelector(".sheet-zoom-out");
  const zoomInBtn = document.querySelector(".sheet-zoom-in");
  const levelEl = document.getElementById("sheet-zoom-level");

  const pages = Array.prototype.map
    .call(document.querySelectorAll(".sheet-page"), function (page) {
      const canvas = page.querySelector(".sheet-canvas");
      if (!canvas) return null;
      const nw = parseFloat(canvas.dataset.naturalWidth);
      const nh = parseFloat(canvas.dataset.naturalHeight);
      if (!(nw > 0) || !(nh > 0)) return null;
      return { page: page, canvas: canvas, naturalWidth: nw, naturalHeight: nh };
    })
    .filter(Boolean);

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
  let lastAvailable = 0;

  // Pin every page/canvas to the current fit*zoom scale. Reads only the
  // wrapper's own inline width (independent of the fixed-size page children),
  // so writing the child sizes below can never feed back into the measurement.
  // Returns true once it has actually scaled (needs a positive width); the
  // .is-scaled class is only switched on then, so a viewer that first lays out
  // at zero width (hidden pane, display:none ancestor) stays in the fluid
  // fallback until a real width arrives via load/resize -- never a broken
  // half-scaled state.
  function layout() {
    const available = wrapper.clientWidth;
    if (!available || !pages.length) return false;
    for (let i = 0; i < pages.length; i++) {
      const p = pages[i];
      const fit = available / p.naturalWidth;
      const scale = fit * (currentZoom / 100);
      p.canvas.style.width = p.naturalWidth + "px";
      p.canvas.style.height = p.naturalHeight + "px";
      p.canvas.style.setProperty("--sheet-scale", String(scale));
      p.page.style.width = p.naturalWidth * scale + "px";
      p.page.style.height = p.naturalHeight * scale + "px";
    }
    if (root) root.classList.add("is-scaled");
    lastAvailable = available;
    return true;
  }

  function applyZoom(value) {
    currentZoom = clamp(value);
    if (levelEl) levelEl.textContent = currentZoom + "%";
    if (zoomOutBtn) zoomOutBtn.disabled = currentZoom <= MIN_ZOOM;
    if (zoomInBtn) zoomInBtn.disabled = currentZoom >= MAX_ZOOM;
    storeZoom(currentZoom);
    layout();
  }

  currentZoom = loadStoredZoom();
  applyZoom(currentZoom);

  // If the first layout ran at zero width (hidden pane / not yet displayed),
  // try again once the page has fully loaded and had a chance to size.
  if (!lastAvailable) {
    window.addEventListener("load", layout);
  }

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

  // Re-fit when the column width changes. Runs synchronously (ResizeObserver is
  // already throttled to at most once per frame) so a measurement taken right
  // after a resize sees the new scale -- no one-frame lag. Guard on the measured
  // width so that writing page heights (which changes the wrapper's content
  // height, not its width) can never re-trigger and loop.
  function onResize() {
    if (wrapper.clientWidth === lastAvailable) return;
    layout(); // layout() re-reads the width and updates lastAvailable
  }

  // window 'resize' fires synchronously while the browser processes a viewport
  // change, so the re-fit is done before anything measures the canvas again.
  // ResizeObserver additionally catches column-width changes that are not
  // window resizes (devtools dock, container reflow). Both paths are guarded
  // and idempotent, so handling an event twice is harmless.
  window.addEventListener("resize", onResize);
  if (typeof window.ResizeObserver === "function") {
    const observer = new window.ResizeObserver(onResize);
    observer.observe(wrapper);
  }
})();
