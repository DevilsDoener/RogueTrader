/*
 * Auspex: the global command palette (Ctrl+K / Meta+K, "/", or a click or
 * keystroke in the topbar search field). Suggests chapters, section titles
 * and full-text hits from `wiki:suggest` as you type; fully keyboard-driven
 * (combobox + listbox).
 *
 * Progressive enhancement: without this script the <dialog> is never opened
 * and the topbar form stays a plain GET search. Server strings are inserted
 * with textContent; the one exception is `snippet_html`, which the server has
 * already escaped (only <mark> survives). localStorage is optional.
 */
(function () {
  "use strict";

  var dialog = document.getElementById("auspex");
  if (!dialog || typeof dialog.showModal !== "function") {
    return;
  }

  var input = dialog.querySelector(".auspex-input");
  var results = dialog.querySelector(".auspex-results");
  var inputRow = dialog.querySelector(".auspex-input-row");
  var allLink = dialog.querySelector(".auspex-all");
  var topbarInput = document.getElementById("topbar-search-input");
  var suggestUrl = dialog.getAttribute("data-suggest-url");
  var searchUrl = dialog.getAttribute("data-search-url");

  var RECENT_LIMIT = 6;
  var MIN_QUERY_LENGTH = 2;
  var DEBOUNCE_MS = 120;

  var MSG_IDLE = "Tippe, um Kapitel, Abschnitte und Regeltexte zu scannen.";
  var MSG_EMPTY = "Keine Vorschläge – Enter sucht im Volltext.";
  var MSG_ERROR = "Auspex gestört – Enter sucht im Volltext.";

  var options = [];
  var activeIndex = -1;
  var debounceTimer = null;
  var controller = null;
  var returnFocus = null;
  var navigating = false;
  var pointerDownOnBackdrop = false;

  // Two live regions beside the listbox (which holds only groups and
  // options): the visible note for the idle/empty/error line, and a
  // screen-reader-only count of the suggestions shown.
  var note = dialog.querySelector(".auspex-note");
  var count = dialog.querySelector(".auspex-count");
  // Storage and URL checks for rt-wiki-recent: static/js/wiki-recent.js.
  var recent = window.RTWikiRecent || null;

  /* ---- helpers --------------------------------------------------------- */

  function currentQuery() {
    return input.value;
  }

  function isLongEnough(query) {
    return query.replace(/\s+/g, "").length >= MIN_QUERY_LENGTH;
  }

  function fullSearchHref(query) {
    return query.trim() ? searchUrl + "?q=" + encodeURIComponent(query) : searchUrl;
  }

  function isTypingTarget(element) {
    if (!element || element === document.body) {
      return false;
    }
    var tag = element.tagName;
    return (
      tag === "INPUT" ||
      tag === "TEXTAREA" ||
      tag === "SELECT" ||
      element.isContentEditable === true
    );
  }

  function numeralOf(numeral) {
    return typeof numeral === "string" && numeral !== "" ? numeral : "§";
  }

  /* ---- rendering ------------------------------------------------------- */

  function setActive(index, reveal) {
    if (activeIndex >= 0 && options[activeIndex]) {
      options[activeIndex].classList.remove("is-active");
      options[activeIndex].setAttribute("aria-selected", "false");
    }
    activeIndex = index;
    var option = options[index];
    if (!option) {
      activeIndex = -1;
      input.removeAttribute("aria-activedescendant");
      return;
    }
    option.classList.add("is-active");
    option.setAttribute("aria-selected", "true");
    input.setAttribute("aria-activedescendant", option.id);
    if (reveal) {
      revealOption(option, index);
    }
  }

  /* Scroll the results list (never the page) so the option is visible; the
     first option brings its group heading along. */
  function revealOption(option, index) {
    if (index === 0) {
      results.scrollTop = 0;
      return;
    }
    var top = option.offsetTop;
    var bottom = top + option.offsetHeight;
    if (top < results.scrollTop) {
      var heading = option.previousElementSibling;
      results.scrollTop =
        heading && heading.classList.contains("auspex-group") ? heading.offsetTop : top;
    } else if (bottom > results.scrollTop + results.clientHeight) {
      results.scrollTop = bottom - results.clientHeight;
    }
  }

  function clearList() {
    results.textContent = "";
    options = [];
    activeIndex = -1;
    input.removeAttribute("aria-activedescendant");
  }

  function finishRender(message) {
    input.setAttribute("aria-expanded", options.length ? "true" : "false");
    note.textContent = "";
    note.classList.remove("is-error");
    count.textContent = message;
  }

  function showNote(text, isError) {
    clearList();
    input.setAttribute("aria-expanded", "false");
    count.textContent = "";
    note.classList.toggle("is-error", !!isError);
    note.textContent = text;
  }

  function makeOption(item) {
    var option = document.createElement("a");
    option.className = "auspex-option";
    option.setAttribute("role", "option");
    option.setAttribute("aria-selected", "false");
    option.setAttribute("tabindex", "-1");
    option.id = "auspex-opt-" + options.length;
    option.setAttribute("href", item.url);

    var title = document.createElement("span");
    title.className = "auspex-option-title";
    title.textContent = item.title;
    option.appendChild(title);

    if (item.path) {
      var path = document.createElement("span");
      path.className = "auspex-option-path";
      path.textContent = item.path;
      option.appendChild(path);
    }

    if (typeof item.snippetHtml === "string" && item.snippetHtml !== "") {
      var snippet = document.createElement("span");
      snippet.className = "auspex-option-snippet";
      snippet.innerHTML = item.snippetHtml; // server-escaped; only <mark> remains
      option.appendChild(snippet);
    }

    options.push(option);
    return option;
  }

  function appendGroup(label, items) {
    if (!items.length) {
      return;
    }
    // ARIA 1.2 listbox > group > option: the group is named by its visible
    // heading, so a screen reader announces "Kapitel", "Abschnitte" ... with
    // the options. The heading stays the first child, which revealOption()
    // relies on to scroll it into view with the group's first option.
    var headingId = "auspex-group-" + results.children.length;
    var group = document.createElement("div");
    group.className = "auspex-optgroup";
    group.setAttribute("role", "group");
    group.setAttribute("aria-labelledby", headingId);
    var heading = document.createElement("div");
    heading.className = "auspex-group";
    heading.id = headingId;
    heading.setAttribute("role", "presentation");
    heading.textContent = label;
    group.appendChild(heading);
    items.forEach(function (item) {
      group.appendChild(makeOption(item));
    });
    results.appendChild(group);
  }

  function trail(numeral, chapter, path) {
    var parts = [numeralOf(numeral)];
    var rest = [];
    if (typeof chapter === "string" && chapter !== "") {
      rest.push(chapter);
    }
    if (Array.isArray(path)) {
      path.forEach(function (part) {
        if (typeof part === "string" && part !== "") {
          rest.push(part);
        }
      });
    }
    if (rest.length) {
      parts.push(rest.join(" › "));
    }
    return parts.join(" · ");
  }

  /* Server-supplied targets: chapter/section pages or the search page only. */
  function validUrl(url) {
    return !!recent && recent.isSafeUrl(url, ["/wiki/", "/search/"]);
  }

  function renderRecent() {
    var entries = recent ? recent.read(RECENT_LIMIT) : [];
    if (!entries.length) {
      showNote(MSG_IDLE, false);
      return;
    }
    clearList();
    appendGroup(
      "Zuletzt gelesen",
      entries.map(function (entry) {
        return {
          title: entry.title,
          path: typeof entry.chapter === "string" ? entry.chapter : "",
          url: entry.url,
        };
      })
    );
    finishRender(options.length + " zuletzt gelesene Abschnitte");
  }

  function renderSuggestions(data) {
    var chapters = (Array.isArray(data.chapters) ? data.chapters : [])
      .filter(function (item) { return item && validUrl(item.url); })
      .map(function (item) {
        var path = numeralOf(item.numeral);
        if (item.short_title && item.short_title !== item.title) {
          path += " · " + item.short_title;
        }
        return { title: String(item.title), path: path, url: item.url };
      });
    var sections = (Array.isArray(data.sections) ? data.sections : [])
      .filter(function (item) { return item && validUrl(item.url); })
      .map(function (item) {
        return {
          title: String(item.title),
          path: trail(item.numeral, item.chapter, item.path),
          url: item.url,
        };
      });
    var hits = (Array.isArray(data.hits) ? data.hits : [])
      .filter(function (item) { return item && validUrl(item.url); })
      .map(function (item) {
        return {
          title: String(item.title),
          path: trail(item.numeral, item.chapter, item.path),
          snippetHtml: item.snippet_html,
          url: item.url,
        };
      });

    if (!chapters.length && !sections.length && !hits.length) {
      showNote(MSG_EMPTY, false);
      return;
    }
    clearList();
    appendGroup("Kapitel", chapters);
    appendGroup("Abschnitte", sections);
    appendGroup("Volltext", hits);
    results.scrollTop = 0;
    finishRender(options.length === 1 ? "1 Vorschlag" : options.length + " Vorschläge");
  }

  /* ---- fetching -------------------------------------------------------- */

  function setScanning(on) {
    inputRow.classList.toggle("is-scanning", on);
    if (on) {
      results.setAttribute("aria-busy", "true");
    } else {
      results.removeAttribute("aria-busy");
    }
  }

  function cancelPending() {
    if (debounceTimer !== null) {
      window.clearTimeout(debounceTimer);
      debounceTimer = null;
    }
    if (controller) {
      controller.abort();
      controller = null;
    }
    setScanning(false);
  }

  function fetchSuggestions(query) {
    debounceTimer = null;
    if (controller) {
      controller.abort();
    }
    var own = typeof AbortController === "function" ? new AbortController() : null;
    controller = own;
    setScanning(true);
    fetch(suggestUrl + "?q=" + encodeURIComponent(query), {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
      signal: own ? own.signal : undefined,
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("HTTP " + response.status);
        }
        return response.json();
      })
      .then(function (data) {
        if (controller !== own || !dialog.open) {
          return;
        }
        controller = null;
        setScanning(false);
        if (!data || data.query !== currentQuery()) {
          return; // The reader has typed on; a newer request is on its way.
        }
        renderSuggestions(data);
      })
      .catch(function (error) {
        if (controller !== own || (error && error.name === "AbortError")) {
          return;
        }
        controller = null;
        setScanning(false);
        if (dialog.open) {
          showNote(MSG_ERROR, true);
        }
      });
  }

  /* React to the current query; `immediate` skips the debounce (on open). */
  function update(immediate) {
    var query = currentQuery();
    if (allLink) {
      allLink.setAttribute("href", fullSearchHref(query));
    }
    if (debounceTimer !== null) {
      window.clearTimeout(debounceTimer);
      debounceTimer = null;
    }
    // Whatever is highlighted belongs to the previous query: Enter now means
    // "search the full text" until the reader picks a fresh suggestion.
    setActive(-1);

    if (!isLongEnough(query)) {
      if (controller) {
        controller.abort();
        controller = null;
      }
      setScanning(false);
      renderRecent();
      return;
    }
    if (immediate) {
      fetchSuggestions(query);
    } else {
      debounceTimer = window.setTimeout(function () {
        fetchSuggestions(query);
      }, DEBOUNCE_MS);
    }
  }

  /* ---- open / close ---------------------------------------------------- */

  /* `caret` (optional): place the caret there instead of selecting the
     text, so a keystroke carried over from the topbar field is not
     overwritten by the next one. */
  function open(initialValue, caret) {
    if (dialog.open) {
      input.focus();
      input.select();
      return;
    }
    var active = document.activeElement;
    returnFocus = active && active !== document.body ? active : null;
    if (typeof initialValue === "string") {
      input.value = initialValue;
    }
    navigating = false;
    dialog.showModal();
    input.focus();
    if (typeof caret === "number") {
      input.setSelectionRange(caret, caret);
    } else {
      input.select();
    }
    update(true);
  }

  function navigate(href) {
    navigating = true;
    if (dialog.open) {
      dialog.close();
    }
    window.location.assign(href);
  }

  dialog.addEventListener("close", function () {
    cancelPending();
    var target = returnFocus;
    returnFocus = null;
    // Focus goes back where the reader was, the topbar field included:
    // focusing that field no longer opens the palette, so nothing loops.
    if (!navigating && target && document.contains(target)) {
      target.focus({ preventScroll: true });
    }
  });

  // Backdrop click: the dialog has no padding, so only a press that starts
  // and ends outside the panel targets the <dialog> itself.
  dialog.addEventListener("pointerdown", function (event) {
    pointerDownOnBackdrop = event.target === dialog;
  });
  dialog.addEventListener("click", function (event) {
    if (event.target === dialog && pointerDownOnBackdrop) {
      dialog.close();
    }
    pointerDownOnBackdrop = false;
  });

  // A page restored from the back/forward cache must not show the palette.
  window.addEventListener("pageshow", function (event) {
    if (event.persisted && dialog.open) {
      navigating = true;
      dialog.close();
    }
    navigating = false;
  });

  /* ---- input & keyboard ------------------------------------------------ */

  input.addEventListener("input", function () {
    update(false);
  });

  input.addEventListener("keydown", function (event) {
    if (event.isComposing) {
      return;
    }
    if (event.key === "Escape" && input.value !== "") {
      // A non-empty search field swallows Esc to clear itself, so the
      // dialog's native `cancel` never comes; the footer promises one press.
      event.preventDefault();
      dialog.close();
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!options.length) {
        return;
      }
      var step = event.key === "ArrowDown" ? 1 : -1;
      var next;
      if (activeIndex < 0) {
        next = step === 1 ? 0 : options.length - 1;
      } else {
        next = (activeIndex + step + options.length) % options.length;
      }
      setActive(next, true);
    } else if (event.key === "Enter") {
      event.preventDefault();
      var option = options[activeIndex];
      if (option) {
        navigate(option.getAttribute("href"));
      } else if (currentQuery().trim()) {
        navigate(fullSearchHref(currentQuery()));
      }
    }
  });

  // Only a real pointer movement takes over from the keyboard: scrolling the
  // list under a resting cursor must not steal the active option.
  var lastPointer = { x: -1, y: -1 };
  results.addEventListener("mousemove", function (event) {
    if (event.clientX === lastPointer.x && event.clientY === lastPointer.y) {
      return;
    }
    lastPointer.x = event.clientX;
    lastPointer.y = event.clientY;
    var option = event.target.closest && event.target.closest(".auspex-option");
    if (option) {
      var index = options.indexOf(option);
      if (index !== -1 && index !== activeIndex) {
        setActive(index, false);
      }
    }
  });

  results.addEventListener("click", function (event) {
    var option = event.target.closest && event.target.closest(".auspex-option");
    if (!option || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) {
      return;
    }
    // Let the link navigate; closing first matters for a same-page #anchor.
    navigating = true;
    dialog.close();
  });

  if (allLink) {
    allLink.addEventListener("click", function (event) {
      if (event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
        navigating = true;
        dialog.close();
      }
    });
  }

  document.addEventListener("keydown", function (event) {
    if (event.defaultPrevented || event.isComposing) {
      return;
    }
    var key = event.key;
    if (
      (key === "k" || key === "K") &&
      (event.ctrlKey || event.metaKey) &&
      !event.altKey &&
      !event.shiftKey
    ) {
      event.preventDefault();
      open();
      return;
    }
    if (
      key === "/" &&
      !event.ctrlKey &&
      !event.metaKey &&
      !event.altKey &&
      !dialog.open &&
      !isTypingTarget(document.activeElement)
    ) {
      event.preventDefault();
      open();
    }
  });

  // The topbar field opens the palette on a click or on the first printable
  // key typed into it -- never on focus alone, so Tab passes through the
  // header without a dialog appearing (WCAG 3.2.1). Enter still submits the
  // plain GET form.
  if (topbarInput) {
    topbarInput.addEventListener("click", function () {
      if (!dialog.open) {
        open(topbarInput.value);
      }
    });
    topbarInput.addEventListener("keydown", function (event) {
      // AltGr (reported as Ctrl+Alt on Windows) types characters like "@".
      var altGraph =
        typeof event.getModifierState === "function" && event.getModifierState("AltGraph");
      if (
        dialog.open ||
        event.isComposing ||
        ((event.ctrlKey || event.metaKey || event.altKey) && !altGraph) ||
        typeof event.key !== "string" ||
        event.key.length !== 1
      ) {
        return;
      }
      event.preventDefault();
      // The keystroke replaces any selected text, as it would in the field.
      var value = topbarInput.value;
      var from = topbarInput.selectionStart;
      var to = topbarInput.selectionEnd;
      if (typeof from !== "number" || typeof to !== "number") {
        from = to = value.length;
      }
      open(value.slice(0, from) + event.key + value.slice(to), from + 1);
    });
  }
})();
