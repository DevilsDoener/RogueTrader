/*
 * Minimal, dependency-free navigation drawer toggle for narrow viewports.
 * Below 800px `primary-nav` is a disclosure drawer (see portal.css); above
 * that breakpoint it is always visible and this script is inert (the
 * toggle button is hidden by CSS so it never receives focus).
 */
(function () {
  "use strict";

  var toggle = document.getElementById("nav-toggle");
  var nav = document.getElementById("primary-nav");
  var scrim = document.getElementById("nav-scrim");
  var shell = document.querySelector(".app-shell");

  if (!toggle || !nav || !shell) {
    return;
  }

  function isOpen() {
    return shell.classList.contains("nav-open");
  }

  function setOpen(open) {
    shell.classList.toggle("nav-open", open);
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (scrim) {
      scrim.hidden = !open;
    }
    if (open) {
      var firstLink = nav.querySelector("a");
      if (firstLink) {
        firstLink.focus();
      }
    }
  }

  toggle.addEventListener("click", function () {
    setOpen(!isOpen());
  });

  if (scrim) {
    scrim.addEventListener("click", function () {
      setOpen(false);
    });
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && isOpen()) {
      setOpen(false);
      toggle.focus();
    }
  });

  // Closing the drawer after following a nav link keeps a later
  // back-navigation from reopening it unexpectedly.
  nav.addEventListener("click", function (event) {
    if (event.target.closest("a")) {
      setOpen(false);
    }
  });
})();
