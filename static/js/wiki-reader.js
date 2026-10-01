/*
 * Chapter page reading aids: scroll-spy on the outline, outline filter,
 * reading progress, search-term highlighting, "Nach oben" and the
 * "Weiterlesen" position for the Bibliothek (rt-wiki-recent, stored through
 * static/js/wiki-recent.js).
 *
 * Progressive enhancement throughout -- without this script the outline is a
 * plain <details> tree, the anchors still jump, and the JS-only controls stay
 * hidden via `.js-only`. Every feature is a no-op when its elements are
 * missing, and every localStorage access is guarded.
 */
(function () {
  "use strict";

  var RECENT_THROTTLE_MS = 2000;
  var MAX_HITS = 300;

  var article = document.querySelector(".wiki-article");
  var sectionNav = document.querySelector(".wiki-section-nav");
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Listeners for "the reader's section changed"; the recent-position writer
  // subscribes here so the spy does not need to know about it.
  var sectionListeners = [];
  var activeSection = null;

  // Folding and token matching: static/js/wiki-recent.js (loaded before this).
  var fold = window.RTWikiText.fold;
  var matchesAll = window.RTWikiText.matchesAll;

  function toArray(list) {
    return Array.prototype.slice.call(list);
  }

  function scrollBehavior() {
    return reduceMotion ? "auto" : "smooth";
  }

  /* Scroll `container` (never the page) so that `element` is visible inside
     it, centring it when it has to move at all. */
  function revealIn(container, element, behavior) {
    if (!container || !element || container.scrollHeight <= container.clientHeight) {
      return;
    }
    var box = container.getBoundingClientRect();
    var rect = element.getBoundingClientRect();
    if (!rect.height) {
      return; // Hidden (e.g. filtered out): nothing to scroll to.
    }
    var margin = 8;
    if (rect.top >= box.top + margin && rect.bottom <= box.bottom - margin) {
      return;
    }
    var target =
      container.scrollTop + (rect.top - box.top) - (container.clientHeight - rect.height) / 2;
    container.scrollTo({ top: Math.max(0, target), behavior: behavior || "auto" });
  }

  /* The heading's own words, without the trailing "#" permalink. */
  function headingTitle(heading) {
    var text = "";
    toArray(heading.childNodes).forEach(function (node) {
      if (node.nodeType === 1 && node.classList.contains("wiki-anchor")) {
        return;
      }
      text += node.textContent;
    });
    return text.replace(/\s+/g, " ").trim();
  }

  /* The reading line sits just below the sticky topbar and chapter bar:
     exactly where an anchor jump puts a section (its scroll-margin-top), plus
     a little slack so a freshly jumped-to section already counts as current. */
  function readingLine() {
    var section = article && article.querySelector("section[id]");
    var margin = section ? parseFloat(window.getComputedStyle(section).scrollMarginTop) : NaN;
    return (margin || 120) + 12;
  }

  /* Run `action`, then hand focus to <main> if the control was activated from
     the keyboard: the control may vanish or the page jump away, and focus
     must not fall back to <body>. */
  function withKeyboardFocusToMain(control, action) {
    var keyboard = control.matches(":focus-visible");
    action();
    var main = document.getElementById("main-content");
    if (keyboard && main) {
      main.focus({ preventScroll: true });
    }
  }

  function sectionHeading(section) {
    var first = section.firstElementChild;
    return first && /^H[2-6]$/.test(first.tagName) ? first : null;
  }

  /* ------------------------------------------------------------------
     Chapter tree in the primary nav: bring the current chapter into view
     ------------------------------------------------------------------ */

  function initChapterTree() {
    var nav = document.querySelector(".primary-nav");
    var current = nav && nav.querySelector('.primary-nav-sub a[aria-current="page"]');
    if (current) {
      revealIn(nav, current);
    }
  }

  /* ------------------------------------------------------------------
     Outline filter
     ------------------------------------------------------------------ */

  var filterActive = false;

  /* `element`'s ancestors matching `selector` (itself included), innermost
     first, up to the section nav. */
  function ancestorsIn(element, selector) {
    var found = [];
    for (
      var node = element.closest(selector);
      node && sectionNav.contains(node);
      node = node.parentElement.closest(selector)
    ) {
      found.push(node);
    }
    return found;
  }

  function initTocFilter() {
    var input = sectionNav && sectionNav.querySelector(".wiki-toc-filter");
    if (!input) {
      return;
    }
    var items = toArray(sectionNav.querySelectorAll("li"));
    var indexLinks = toArray(sectionNav.querySelectorAll(".wiki-toc-index > a"));
    var allDetails = toArray(sectionNav.querySelectorAll("details"));
    var links = toArray(sectionNav.querySelectorAll("a[href^='#']"));
    var linkText = new Map();
    links.forEach(function (link) {
      linkText.set(link, fold(link.textContent));
    });
    var summaryLinks = new Map();
    allDetails.forEach(function (details) {
      summaryLinks.set(details, details.querySelector(":scope > summary a"));
    });
    // The open/closed state from before the reader started typing, restored
    // when the field is cleared again.
    var savedOpen = null;

    var empty = document.createElement("p");
    empty.className = "wiki-toc-empty";
    empty.hidden = true;
    empty.textContent = "Kein Abschnitt passt.";
    sectionNav.appendChild(empty);

    function restore() {
      items.forEach(function (item) {
        item.hidden = false;
      });
      indexLinks.forEach(function (link) {
        link.hidden = false;
      });
      if (savedOpen) {
        savedOpen.forEach(function (open, details) {
          details.open = open;
        });
      }
      savedOpen = null;
      filterActive = false;
      empty.hidden = true;
    }

    function apply() {
      var tokens = fold(input.value).split(/\s+/).filter(Boolean);
      if (!tokens.length) {
        restore();
        return;
      }
      if (!savedOpen) {
        savedOpen = new Map();
        allDetails.forEach(function (details) {
          savedOpen.set(details, details.open);
        });
      }
      filterActive = true;

      // Walk up from every matching link once: each <li> above it stays
      // visible, and each <details> above it opens -- unless the link is
      // that <details>' own summary link, which does not count as a match
      // inside it.
      var matched = new Set();
      var visibleItems = new Set();
      var openDetails = new Set();
      links.forEach(function (link) {
        if (!matchesAll(linkText.get(link), tokens)) {
          return;
        }
        matched.add(link);
        ancestorsIn(link, "li").forEach(function (item) {
          visibleItems.add(item);
        });
        ancestorsIn(link, "details").forEach(function (details) {
          if (summaryLinks.get(details) !== link) {
            openDetails.add(details);
          }
        });
      });

      items.forEach(function (item) {
        item.hidden = !visibleItems.has(item);
      });
      indexLinks.forEach(function (link) {
        link.hidden = !matched.has(link);
      });
      allDetails.forEach(function (details) {
        details.open = openDetails.has(details);
      });
      empty.hidden = matched.size > 0;
    }

    input.addEventListener("input", apply);
    input.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && input.value) {
        event.preventDefault();
        input.value = "";
        apply();
      }
    });
    // A value restored by the browser's form cache on back/forward.
    if (input.value) {
      apply();
    }
  }

  /* ------------------------------------------------------------------
     Scroll-spy
     ------------------------------------------------------------------ */

  function initScrollSpy(line) {
    if (!article) {
      return;
    }
    var entries = [];
    toArray(article.querySelectorAll("section[id]")).forEach(function (section) {
      var heading = sectionHeading(section);
      if (heading) {
        entries.push({ section: section, heading: heading });
      }
    });
    if (!entries.length) {
      return;
    }

    var activeLink = null;
    var spyOpened = new Set();

    function tocLinkFor(section) {
      var node = section;
      while (node && sectionNav) {
        var link = sectionNav.querySelector('a[href="#' + CSS.escape(node.id) + '"]');
        if (link) {
          return link;
        }
        // Deeper than the outline goes: fall back to the nearest listed parent.
        node = node.parentElement && node.parentElement.closest("section[id]");
      }
      return null;
    }

    function ancestorsDetails(link) {
      var list = [];
      var details = link.parentElement && link.parentElement.closest("details");
      while (details && sectionNav.contains(details)) {
        list.push(details);
        details = details.parentElement && details.parentElement.closest("details");
      }
      return list;
    }

    function setActiveLink(link) {
      if (link === activeLink) {
        return;
      }
      if (activeLink) {
        activeLink.classList.remove("is-active");
        activeLink.removeAttribute("aria-current");
      }
      activeLink = link;
      if (!link) {
        return;
      }
      link.classList.add("is-active");
      link.setAttribute("aria-current", "location");

      if (!filterActive) {
        var ancestors = ancestorsDetails(link);
        // Fold away what the spy itself opened for an earlier section, so the
        // outline does not end up fully expanded after one read-through.
        spyOpened.forEach(function (details) {
          if (ancestors.indexOf(details) === -1) {
            details.open = false;
            spyOpened.delete(details);
          }
        });
        ancestors.forEach(function (details) {
          if (!details.open) {
            details.open = true;
            spyOpened.add(details);
          }
        });
      }
      var index = link.closest(".wiki-toc-index");
      if (index) {
        revealIn(index, link);
      }
      revealIn(sectionNav, link);
    }

    if (sectionNav) {
      // A branch the reader toggles by hand is theirs; the spy leaves it be.
      sectionNav.addEventListener("click", function (event) {
        var summary = event.target.closest("summary");
        if (summary && summary.parentElement) {
          spyOpened.delete(summary.parentElement);
        }
      });
    }

    function current() {
      // Headings are in document order, so their tops are monotonic: binary
      // search for the last one at or above the reading line.
      var low = 0;
      var high = entries.length - 1;
      var found = -1;
      while (low <= high) {
        var mid = (low + high) >> 1;
        if (entries[mid].heading.getBoundingClientRect().top <= line) {
          found = mid;
          low = mid + 1;
        } else {
          high = mid - 1;
        }
      }
      // At the very end of the page the last short sections can never reach
      // the line; then the last heading on screen is the one being read.
      var doc = document.documentElement;
      if (window.innerHeight + window.scrollY >= doc.scrollHeight - 2) {
        for (var i = entries.length - 1; i > found; i -= 1) {
          if (entries[i].heading.getBoundingClientRect().top < window.innerHeight) {
            found = i;
            break;
          }
        }
      }
      return found === -1 ? null : entries[found];
    }

    function update() {
      var entry = current();
      var section = entry ? entry.section : null;
      if (section === activeSection) {
        return;
      }
      activeSection = section;
      setActiveLink(section ? tocLinkFor(section) : null);
      sectionListeners.forEach(function (listener) {
        listener(entry);
      });
    }

    // Re-evaluated on every (rAF-throttled) scroll frame by initScrollLoop,
    // not only when a heading crosses a band: a scrollbar drag, Home/End,
    // find-in-page or an instant "Nach oben" jump past many headings at once.
    // The binary search keeps each frame at a handful of layout reads.
    return update;
  }

  /* ------------------------------------------------------------------
     The scroll loop: scroll-spy, reading progress and "Nach oben"
     ------------------------------------------------------------------ */

  function initScrollLoop(spyUpdate, line) {
    var bar = document.querySelector(".wiki-progress-bar");
    var toTop = document.querySelector(".wiki-to-top");
    if (!bar && !toTop && !spyUpdate) {
      return;
    }
    if (toTop) {
      toTop.addEventListener("click", function () {
        withKeyboardFocusToMain(toTop, function () {
          window.scrollTo({ top: 0, behavior: scrollBehavior() });
        });
      });
    }

    function progress() {
      if (!article) {
        return 0;
      }
      // 0 while the article's top is below the reading line, 1 once its end
      // has scrolled into view.
      var rect = article.getBoundingClientRect();
      var start = rect.top + window.scrollY - line;
      var end = rect.bottom + window.scrollY - window.innerHeight;
      if (end <= start) {
        return 1;
      }
      return Math.min(1, Math.max(0, (window.scrollY - start) / (end - start)));
    }

    var scheduled = false;
    function frame() {
      scheduled = false;
      if (bar) {
        bar.style.transform = "scaleX(" + progress().toFixed(4) + ")";
      }
      if (toTop) {
        toTop.hidden = !(window.scrollY > window.innerHeight);
      }
      if (spyUpdate) {
        spyUpdate();
      }
    }
    function schedule() {
      if (!scheduled) {
        scheduled = true;
        window.requestAnimationFrame(frame);
      }
    }
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    schedule();
  }

  /* ------------------------------------------------------------------
     Search-term highlighting (?q= from a search result)
     ------------------------------------------------------------------ */

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

  /* ------------------------------------------------------------------
     Reading position for "Weiterlesen" (read by wiki-library.js)
     ------------------------------------------------------------------ */

  function initRecent() {
    // Storage format, URL checks and the one-per-chapter rule live in
    // static/js/wiki-recent.js (loaded by base.html before this script).
    var recent = window.RTWikiRecent;
    if (!article || !recent) {
      return;
    }
    var chapterTitle = article.getAttribute("data-chapter-title") || "";
    var h1 = article.querySelector("h1");
    var fullTitle = h1 ? h1.textContent.trim() : chapterTitle;
    var path = window.location.pathname;
    var currentEntry = null;
    var lastWrite = 0;
    var pending = null;

    function write() {
      if (pending) {
        window.clearTimeout(pending);
        pending = null;
      }
      lastWrite = Date.now();
      var section = currentEntry ? currentEntry.section : null;
      recent.record({
        title: (currentEntry && headingTitle(currentEntry.heading)) || fullTitle,
        chapter: chapterTitle,
        url: path + (section ? "#" + section.id : ""),
        ts: lastWrite,
      });
    }

    sectionListeners.push(function (entry) {
      currentEntry = entry;
      var wait = RECENT_THROTTLE_MS - (Date.now() - lastWrite);
      if (wait <= 0) {
        write();
      } else if (!pending) {
        // Trailing write, so the last section reached is the one kept.
        pending = window.setTimeout(write, wait);
      }
    });
    window.addEventListener("pagehide", write);
  }

  initChapterTree();
  initRecent();
  initTocFilter();
  initHighlight();
  var line = readingLine();
  var spyUpdate = initScrollSpy(line);
  initScrollLoop(spyUpdate, line);
})();
