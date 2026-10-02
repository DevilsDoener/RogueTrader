/* Expand-on-demand details for the ship history list.
 *
 * Old/new values are only ever fetched (from an authenticated route) once a
 * user explicitly opens a row -- they are never present in the initial page
 * load. The fetched fragment is a small <dl>; only its dt/dd texts are copied
 * into the table (as text, never as markup), and anything else the request
 * returned -- a login page after the session expired, an error page -- is
 * replaced by a short message instead of being injected.
 */
(function () {
  "use strict";

  var ERROR_TEXT = "Die Details konnten nicht geladen werden.";

  function showMessage(cell, text) {
    cell.textContent = text;
  }

  function showDetails(cell, html) {
    var doc = new DOMParser().parseFromString(html, "text/html");
    var items = doc.querySelectorAll("dl > dt, dl > dd");
    if (!items.length) {
      showMessage(cell, ERROR_TEXT);
      return;
    }
    var list = document.createElement("dl");
    items.forEach(function (item) {
      var copy = document.createElement(item.tagName.toLowerCase());
      copy.textContent = item.textContent;
      list.appendChild(copy);
    });
    cell.replaceChildren(list);
  }

  document.querySelectorAll(".ship-history-expand").forEach(function (button) {
    button.addEventListener("click", function () {
      var row = button.closest("tr");
      var detailRow = row.nextElementSibling;
      if (!detailRow) return;
      if (!detailRow.hidden) {
        detailRow.hidden = true;
        return;
      }
      var cell = detailRow.querySelector("td");
      fetch(button.dataset.detailUrl, { credentials: "same-origin" })
        .then(function (response) {
          if (!response.ok || response.redirected) {
            throw new Error("history detail request failed");
          }
          return response.text();
        })
        .then(function (html) {
          showDetails(cell, html);
        })
        .catch(function () {
          showMessage(cell, ERROR_TEXT);
        })
        .then(function () {
          detailRow.hidden = false;
        });
    });
  });
})();
