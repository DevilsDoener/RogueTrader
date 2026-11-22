/*
 * Remembers whether the chapter tree under "Wiki" in the primary nav
 * (<details id="primary-nav-chapters">, templates/base.html) is open, so it
 * stays the way the reader left it from one page to the next. Closed is the
 * default. Without storage (or JavaScript) it simply starts closed each time.
 */
(function () {
  "use strict";

  var KEY = "rt-nav-chapters-open";
  var details = document.getElementById("primary-nav-chapters");
  if (!details) {
    return;
  }

  try {
    if (window.localStorage.getItem(KEY) === "1") {
      details.open = true;
    }
  } catch (error) {
    /* storage blocked: stay closed */
  }

  details.addEventListener("toggle", function () {
    try {
      if (details.open) {
        window.localStorage.setItem(KEY, "1");
      } else {
        window.localStorage.removeItem(KEY);
      }
    } catch (error) {
      /* storage blocked: nothing to remember */
    }
  });
})();
