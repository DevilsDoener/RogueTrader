/*
 * Search-term highlighting on a chapter page (?q= from a search result): marks
 * the words listed in the #wiki-highlight-terms JSON block inside the article
 * and offers "Markierung entfernen". Progressive enhancement -- without this
 * script the page simply shows no marks. Loaded by chapter.html before
 * wiki-reader.js, so the marks are in place before the reader's own setup.
 */
(function () {
  "use strict";

  var MAX_HITS = 300;

  var article = document.querySelector(".wiki-article");

  /* Run `action`, then hand focus to <main> if the control was activated from
     the keyboard: the control may vanish or the page jump away, and focus
     must not fall back to <body>. (Same helper as in wiki-reader.js.) */
  function withKeyboardFocusToMain(control, action) {
    var keyboard = control.matches(":focus-visible");
    action();
    var main = document.getElementById("main-content");
    if (keyboard && main) {
      main.focus({ preventScroll: true });
    }
  }

  function escapeRegExp(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function readTerms() {
    var script = document.getElementById("wiki-highlight-terms");
    if (!script) {
      return [];
    }
    try {
      var terms = JSON.parse(script.textContent);
      return Array.isArray(terms)
        ? terms.filter(function (term) { return typeof term === "string" && term; })
        : [];
    } catch (error) {
      return [];
    }
  }

  function initHighlight() {
    var terms = readTerms();
    if (!article || !terms.length) {
      return;
    }
    var pattern;
    try {
      // Longest first so "weapons" wins over "weapon"; the lookbehind is a
      // Unicode-aware \b, so a term only matches at the start of a word and
      // the rest of that word is marked with it.
      terms.sort(function (a, b) { return b.length - a.length; });
      pattern = new RegExp(
        "(?<![\\p{L}\\p{N}])(?:" + terms.map(escapeRegExp).join("|") + ")[\\p{L}\\p{N}]*",
        "giu"
      );
    } catch (error) {
      return; // No lookbehind/Unicode property support: skip highlighting.
    }

    var walker = document.createTreeWalker(article, NodeFilter.SHOW_TEXT, {
      acceptNode: function (node) {
        if (!node.nodeValue.trim()) {
          return NodeFilter.FILTER_REJECT;
        }
        var parent = node.parentElement;
        if (!parent || parent.closest("script, style, mark, .wiki-anchor")) {
          return NodeFilter.FILTER_REJECT;
        }
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    var nodes = [];
    while (walker.nextNode()) {
      nodes.push(walker.currentNode);
    }

    var marks = [];
    for (var n = 0; n < nodes.length && marks.length < MAX_HITS; n += 1) {
      var node = nodes[n];
      var text = node.nodeValue;
      pattern.lastIndex = 0;
      var match;
      var last = 0;
      var fragment = null;
      while ((match = pattern.exec(text)) && marks.length < MAX_HITS) {
        fragment = fragment || document.createDocumentFragment();
        if (match.index > last) {
          fragment.appendChild(document.createTextNode(text.slice(last, match.index)));
        }
        var mark = document.createElement("mark");
        mark.className = "wiki-hit";
        mark.textContent = match[0];
        fragment.appendChild(mark);
        marks.push(mark);
        last = match.index + match[0].length;
      }
      if (fragment) {
        if (last < text.length) {
          fragment.appendChild(document.createTextNode(text.slice(last)));
        }
        node.parentNode.replaceChild(fragment, node);
      }
    }
    if (!marks.length) {
      return;
    }

    // The live region goes into the page empty and gets its text a frame
    // later; a status region inserted with its content already in place is
    // not announced by most screen readers.
    var bar = document.createElement("div");
    bar.className = "wiki-hit-bar";
    bar.setAttribute("role", "status");
    var count = document.createElement("span");
    count.className = "wiki-hit-count";
    count.textContent =
      (marks.length >= MAX_HITS ? "Mindestens " : "") +
      marks.length +
      (marks.length === 1 ? " Stelle markiert" : " Stellen markiert");
    var separator = document.createElement("span");
    separator.setAttribute("aria-hidden", "true");
    separator.textContent = " · ";
    var button = document.createElement("button");
    button.type = "button";
    button.textContent = "Markierung entfernen";

    // Above both columns, on the dark shell: inside the flex row it would
    // become a third column, on the parchment it would read as book text.
    var layout = article.closest(".wiki-layout") || article;
    layout.parentNode.insertBefore(bar, layout);
    window.requestAnimationFrame(function () {
      bar.appendChild(count);
      bar.appendChild(separator);
      bar.appendChild(button);
    });

    button.addEventListener("click", function () {
      var parents = new Set();
      marks.forEach(function (mark) {
        var parent = mark.parentNode;
        if (!parent) {
          return;
        }
        parent.replaceChild(document.createTextNode(mark.textContent), mark);
        parents.add(parent);
      });
      parents.forEach(function (parent) {
        parent.normalize();
      });
      marks = [];
      withKeyboardFocusToMain(button, function () {
        bar.remove();
      });
      try {
        var url = new URL(window.location.href);
        url.searchParams.delete("q");
        window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
      } catch (error) {
        /* An old browser keeps ?q= in the address bar; the marks are gone anyway. */
      }
    });
  }

  initHighlight();
})();
