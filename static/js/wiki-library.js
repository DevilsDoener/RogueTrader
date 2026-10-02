/*
 * Bibliothek (wiki index): live filter over the chapter cards and the
 * "Weiterlesen" row. Progressive enhancement -- without this script the page
 * is a plain list of cards and the search form still works.
 */
(function () {
  "use strict";

  var RECENT_LIMIT = 3;

  // Folding and token matching: static/js/wiki-text.js (loaded before this).
  var fold = window.RTWikiText.fold;
  var matchesAll = window.RTWikiText.matchesAll;

  function initFilter() {
    var input = document.getElementById("library-filter");
    if (!input) {
      return;
    }
    // Only with JS does typing filter; the HTML placeholder promises search only.
    input.setAttribute("placeholder", "Kapitel und Abschnitte filtern – Enter sucht im Volltext");
    var cards = Array.from(document.querySelectorAll(".library-card"));
    var emptyNote = document.querySelector(".library-empty");
    var bands = Array.from(document.querySelectorAll(".library-band"));
    // Whether the reader opened a <details> themselves, so clearing the
    // filter only closes the ones the filter opened.
    var userOpened = new WeakMap();

    cards.forEach(function (card) {
      var details = card.querySelector("details");
      if (!details) {
        return;
      }
      details.addEventListener("toggle", function () {
        if (!details.dataset.filterOpened) {
          userOpened.set(details, details.open);
        }
      });
    });

    function clearMatches(card) {
      card.querySelectorAll("a.is-match").forEach(function (link) {
        link.classList.remove("is-match");
      });
    }

    function apply() {
      var tokens = fold(input.value).split(/\s+/).filter(Boolean);
      var visibleCount = 0;

      cards.forEach(function (card) {
        var haystack = card.getAttribute("data-filter-text") || "";
        var matches = matchesAll(haystack, tokens);
        card.hidden = !matches;
        if (matches) {
          visibleCount += 1;
        }

        var details = card.querySelector("details");
        clearMatches(card);
        if (!details) {
          return;
        }
        var anyLinkMatch = false;
        if (tokens.length && matches) {
          // Level-1 entries and their nested level-2 entries alike; portal.css
          // reveals a level-2 entry only while it carries `is-match`.
          details.querySelectorAll("a").forEach(function (link) {
            if (matchesAll(fold(link.textContent), tokens)) {
              link.classList.add("is-match");
              anyLinkMatch = true;
            }
          });
        }
        if (anyLinkMatch) {
          if (!details.dataset.filterOpened) {
            // Remember the reader's own state now rather than waiting for the
            // asynchronous `toggle` event, which may not have fired yet.
            userOpened.set(details, details.open);
          }
          details.dataset.filterOpened = "1";
          details.open = true;
        } else if (details.dataset.filterOpened) {
          delete details.dataset.filterOpened;
          details.open = userOpened.get(details) === true;
        }
      });

      // A band with no matching card disappears entirely, heading included.
      bands.forEach(function (band) {
        band.hidden = !band.querySelector(".library-card:not([hidden])");
      });

      if (emptyNote) {
        emptyNote.hidden = visibleCount > 0 || tokens.length === 0;
      }
    }

    input.addEventListener("input", apply);
    apply();
  }

  function initRecent() {
    var section = document.querySelector(".library-recent");
    var list = section && section.querySelector(".library-recent-list");
    // Reading and validating rt-wiki-recent: static/js/wiki-recent.js.
    if (!list || !window.RTWikiRecent) {
      return;
    }
    var entries = window.RTWikiRecent.read(RECENT_LIMIT);
    if (!entries.length) {
      return;
    }
    entries.forEach(function (entry) {
      var item = document.createElement("li");
      var link = document.createElement("a");
      link.className = "library-recent-card";
      link.setAttribute("href", entry.url);
      var chapter = document.createElement("span");
      chapter.className = "library-recent-chapter";
      chapter.textContent = typeof entry.chapter === "string" ? entry.chapter : "";
      var title = document.createElement("span");
      title.className = "library-recent-title";
      title.textContent = entry.title;
      link.appendChild(chapter);
      link.appendChild(title);
      item.appendChild(link);
      list.appendChild(item);
    });
    section.hidden = false;
  }

  initFilter();
  initRecent();
})();
