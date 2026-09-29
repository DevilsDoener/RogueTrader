# Plan: Wiki-Auspex-Navigation

Spec: `docs/superpowers/specs/2026-09-29-wiki-auspex-navigation.md` — its
section "Globale Randbedingungen" binds every task below. Repo root for all
paths: `Wissensdatenbank/`. Branch: `feature/wiki-auspex-navigation`.

Tasks run in order; each builds on the previous one's interfaces.

## Global Constraints

See the spec, section "Globale Randbedingungen". In short: `--rt-*` tokens
only, parchment only in `.wiki-article`, never touch `sheet-viewer.css`,
desktop-only, progressive enhancement with the `js` class on `<html>` and
`.js-only`, vanilla JS in `static/js/` loaded with `defer`, `localStorage`
in `try/catch`, `textContent` for server strings (snippet HTML excepted),
`LoginRequiredMixin` on new views, no gzip on views echoing `q`, German UI,
no totals in prose docs, never stage `*.onetoc2`, `graphify-out/`,
`AGENTS.md`, `.agents/`, `.codex/`.

Test commands (run from `Wissensdatenbank/`):

- quick: `.venv/Scripts/python.exe -m pytest -q wiki/tests core/tests`
- e2e for the wiki: `.venv/Scripts/python.exe -m pytest -q tests/e2e/test_wiki_navigation.py tests/e2e/test_complete_journey.py tests/e2e/test_responsive_shell.py`

---

### Task 1: Server-side data for navigation and search

Files: `wiki/content.py`, `wiki/search.py`, `wiki/manifest.py`, new tests
in `wiki/tests/test_navigation_data.py`.

1. `WikiSection` gains `parent_titles: Tuple[str, ...] = ()`. In
   `_parse_chapter`'s `convert`, pass the ancestor titles down: children of a
   node get `parent_titles + (node.title,)`, except that an intro node
   (`is_intro`) contributes nothing. Top-level nodes get `()`.
2. `WikiChapter` gains two properties:
   - `numeral`: if `part` matches `^Kapitel\s+([IVXLC]+)$`, the numeral
     (`"Kapitel IV"` → `"IV"`), else `""`.
   - `short_title`: `re.sub(r"^Chapter\s+[0-9IVXLC]+\s*[:\-–]\s*", "", title, flags=re.IGNORECASE)`,
     stripped; falls back to `title` if the result is empty.
     Examples: `"Chapter V: Armoury"` → `"Armoury"`,
     `"Chapter 14 - Adversaries & Aliens"` → `"Adversaries & Aliens"`,
     `"Traits"` → `"Traits"`.
3. `SearchResult` gains `path: Tuple[str, ...] = ()`, filled from
   `getattr(section, "parent_titles", ())`.
4. `SearchIndex.search(query, limit=30)` accepts `limit=None`, meaning no
   cap. `WikiRepository.search(query, limit=30)` passes `limit` through
   unchanged (so `None` works there too).
5. `SearchIndex.highlight_terms(query) -> Tuple[str, ...]`: casefolded query
   tokens plus their `QUERY_ALIASES` entries, **without** prefix expansion,
   deduplicated, sorted, only tokens of length ≥ 2; empty tuple for a query
   shorter than `MIN_QUERY_LENGTH`. `WikiRepository.highlight_terms(query)`
   delegates.
6. `wiki/manifest.py` gains:

   ```python
   @dataclass(frozen=True)
   class QuickLink:
       label: str
       chapter_slug: str
       section_id: str

   #: Rules the table looks up mid-session. Labels are German; targets are
   #: section anchors (``sec-<id>``) checked against the real corpus by
   #: wiki/tests/test_navigation_data.py.
   QUICK_LINKS: Tuple[QuickLink, ...] = (
       QuickLink("Proben", "playing-the-game", "tests-the-basic-mechanic"),
       QuickLink("Erfolgsgrade", "playing-the-game", "degrees-of-success-and-failure"),
       QuickLink("Kampfaktionen", "playing-the-game", "table-9-4-combat-actions"),
       QuickLink("Trefferzonen", "playing-the-game", "table-9-6-hit-locations"),
       QuickLink("Kritischer Schaden", "playing-the-game", "critical-effect-tables-tables-9-11-to-9-26"),
       QuickLink("Fernkampfwaffen", "armoury", "table-5-4-ranged-weapons"),
       QuickLink("Waffeneigenschaften", "armoury", "weapon-special-qualities"),
       QuickLink("Rüstung", "armoury", "armour"),
       QuickLink("Fertigkeiten", "skills", "skill-descriptions"),
       QuickLink("Talente", "talents", "detailed-talent-descriptions"),
       QuickLink("Gefahren des Warp", "psychic-powers", "table-6-3-perils-of-the-warp"),
       QuickLink("Raumkampf", "starships", "starship-combat"),
   )
   ```

   Keep the module importable without `django.setup()`.
7. `WikiRepository.quick_links()` returns a tuple of
   `(QuickLink, WikiChapter)` pairs for links whose chapter exists and
   whose `section_id` is among that chapter's section ids; others are
   silently dropped (logged once at debug level at most).

Tests (`wiki/tests/test_navigation_data.py`), using the existing fixtures
in `wiki/tests/conftest.py` where they fit and small inline Markdown
repositories otherwise:

- `parent_titles` for a three-level tree, and that the intro contributes
  nothing.
- `numeral` / `short_title` for the three examples above plus a
  front-matter chapter (`numeral == ""`).
- `SearchResult.path` is filled.
- `search(q, limit=None)` returns more than 30 results where the fixture
  has more than 30 matches (or construct one), and the default is still 30.
- `highlight_terms("Waffe")` contains `"waffe"` and `"weapon"`;
  `highlight_terms("x")` is empty.
- Against the real corpus (`settings.BASE_DIR / "content"`, full manifest
  allowlist, load a fresh `WikiRepository` and restore the singleton
  afterwards — follow how `wiki/tests/test_corpus_invariants.py` does it):
  every `QUICK_LINKS` entry resolves, i.e. `len(repository.quick_links()) ==
  len(QUICK_LINKS)`.

Run the quick test command; all green.

---

### Task 2: Suggest endpoint for the Auspex palette

Files: new `wiki/suggest.py`, `wiki/views.py`, `wiki/urls.py`, new tests
`wiki/tests/test_suggest.py`.

1. `wiki/suggest.py` with a pure function
   `suggest(repository, query: str) -> dict` returning a JSON-ready dict:

   ```json
   {
     "query": "<q as given>",
     "chapters": [{"title": "...", "short_title": "...", "numeral": "IV", "url": "/wiki/talents/"}],
     "sections": [{"title": "...", "chapter": "<chapter short_title>", "numeral": "IV", "path": ["..."], "url": "/wiki/<slug>/?q=<q>#sec-<id>"}],
     "hits":     [{"title": "...", "chapter": "...", "numeral": "...", "path": ["..."], "snippet_html": "...<mark>..</mark>..", "url": "..."}],
     "search_url": "/search/?q=<q>"
   }
   ```

   - Query shorter than `MIN_QUERY_LENGTH` (spaces removed): all three lists
     empty, `search_url` still set.
   - `chapters`: up to **4**, chapters where every casefolded query token is a
     substring of the casefolded `title`; book order.
   - `sections`: up to **6**, non-intro sections (all depths) where every
     casefolded query token is a substring of the casefolded section title.
     Rank: title starts with the full casefolded query → 0; some title word
     starts with the first token → 1; otherwise 2; ties by chapter ordinal
     then section ordinal.
   - `hits`: `repository.search(query, limit=12)`, dropping any whose
     `(chapter_slug, section_id)` already appears in `sections`, first **6**
     kept. `snippet_html` is `SearchResult.snippet` as-is.
   - URLs built with `django.urls.reverse` and `urllib.parse.urlencode`
     for `q`.
2. `WikiSuggestView(LoginRequiredMixin, View)` in `wiki/views.py`: `GET`
   returns `JsonResponse(suggest(get_repository(), request.GET.get("q", "")))`
   with header `Cache-Control: private, max-age=60`. **Not** gzip-wrapped
   (it echoes `q`; add one line to the existing BREACH comment).
3. `wiki/urls.py`: `path("search/suggest/", views.WikiSuggestView.as_view(), name="suggest")`.

Tests (`wiki/tests/test_suggest.py`):

- anonymous request → redirect to login (302);
- short query → empty lists, 200;
- chapter match, section title match ranked starts-with first, full-text
  hit present, hits never duplicate sections, caps (4 / 6 / 6) respected;
- a query containing `<script>` comes back only as JSON data (the response
  `Content-Type` is `application/json`), and a title containing `<b>` is
  returned as a plain string (no HTML added by the server);
- section URL contains `?q=` and `#sec-`.

Run the quick test command; all green.

---

### Task 3: Search results page with facets

Files: `wiki/views.py` (`WikiSearchView`), `wiki/templates/wiki/search_results.html`,
`static/css/portal.css`, tests in `wiki/tests/test_search_view.py`
(extend/adjust).

1. View: `SEARCH_RESULTS_LIMIT = 50`. Compute
   `all_results = repository.search(query, limit=None)` (empty when no
   query). Facets: list of `{"chapter": WikiChapter, "count": n}` for chapters
   with ≥ 1 hit, in book order. `kapitel = request.GET.get("kapitel", "")`;
   if it matches a facet's slug, filter to that chapter and expose
   `active_chapter`; otherwise ignore it. Context adds: `results` (filtered,
   capped at 50), `total_count` (after filter, before cap), `all_count`,
   `facets`, `active_chapter`, `results_capped` (bool), `quick_links`
   (`repository.quick_links()`), and a `chapters_by_slug` lookup or
   equivalent so each result can show the chapter's `numeral` and
   `short_title`. Keep existing context keys (`query`, `query_too_short`,
   `min_query_length`).
2. Template:
   - `h1` "Suche", GET form (input `#wiki-search-input` name `q`, no hidden
     `kapitel`).
   - Layout `.search-layout`: `<aside class="search-facets" aria-label="Nach Kapitel eingrenzen">`
     with a list: "Alle Kapitel" (count `all_count`) linking to `?q=<q>`,
     then each facet linking to `?q=<q>&kapitel=<slug>`, showing
     `numeral · short_title` and the count; the active one carries
     `aria-current="true"`. Only rendered when there are results.
   - Summary: "{{ total_count }} Treffer für „q“" plus " in <short_title>"
     when filtered; when `results_capped`: "– die besten 50 werden angezeigt".
   - `<ol class="wiki-results">`, each `<li class="search-hit-card">`:
     first element the title link (`<a class="search-hit-title" href=".../?q=..#sec-..">title</a>`),
     then `<p class="search-hit-path">` with `numeral · short_title` and each
     `path` entry separated by `›`, then `<p class="search-hit-snippet">`
     snippet `|safe`. When no facet is active, the first card gets class
     `search-hit-card--best` and a small label "Bester Treffer".
   - Empty states keep their current wording; the "keine Treffer" state
     additionally renders the quick-link chips (`.quick-links`, same markup
     as Task 4 will use: `<ul class="quick-links"><li><a class="quick-link" href="...#sec-..">label</a></li></ul>`).
3. CSS block "Search results": two-column grid (facets ~14rem, results
   1fr), facet list styled like a quiet console list (count as a muted
   badge, active item gold left border like `.primary-nav a[aria-current]`),
   hit cards on `--rt-panel` with `--rt-border`, title in
   `--rt-font-display` gold-bright without underline (underline on hover),
   path line in `--rt-font-mono` small caps muted, best-hit card with
   `--rt-gold-dim` border and a gold eyebrow. Quick-link chips: pill
   buttons on `--rt-panel-raised`, gold text, hover `--rt-gold` border.
   No raw colours.

Tests: facet counts, `kapitel` filter, unknown `kapitel` ignored, cap at 50
with `results_capped`, first link in each `.wiki-results li` points to the
chapter with `?q=` and `#sec-`, path rendered, quick links shown when there
are no hits. Adjust existing assertions in `test_search_view.py` only where
the markup intentionally changed (`ul` → `ol` etc.). Check
`tests/e2e/test_complete_journey.py` still finds `.wiki-results li a`.

Run the quick test command and `tests/e2e/test_complete_journey.py`.

---

### Task 4: Bibliothek (wiki index)

Files: `wiki/views.py` (`WikiIndexView`), `wiki/templates/wiki/index.html`,
`templates/base.html` (head: `js` class), `static/css/portal.css`, new
`static/js/wiki-library.js`, tests `wiki/tests/test_index_view.py`
(extend/adjust), e2e `tests/e2e/test_wiki_navigation.py` (new file).

1. `base.html` `<head>`: first thing after the charset meta, an inline
   `<script>document.documentElement.classList.add("js");</script>`.
   `portal.css` base block: `.js-only { display: none !important; }` and
   `.js .js-only { display: revert !important; }` — use a form that
   actually works for block/flex elements (e.g. `html:not(.js) .js-only { display: none !important; }`
   so elements keep their own display under `.js`).
2. `base.html` gains `{% block extra_scripts %}` usage unchanged; the index
   template loads `{% static 'js/wiki-library.js' %}` with `defer` in
   `extra_scripts`.
3. View context adds `quick_links` (`repository.quick_links()`).
4. Template (`wiki/index.html`):
   - `<header class="library-hero">`: eyebrow `<span class="library-eyebrow">Regelwerk</span>`,
     `<h1>Bibliothek</h1>`, one sentence of intro, and the form
     `<form class="library-search" method="get" action="{% url 'wiki:search' %}" role="search">`
     with `<input id="library-filter" type="search" name="q" placeholder="Kapitel und Abschnitte filtern – Enter sucht im Volltext" autocomplete="off">`
     and a submit button "Volltextsuche".
   - `<section class="library-recent js-only" hidden aria-labelledby="library-recent-heading">`
     with `h2` "Weiterlesen" and an empty `<ul class="library-recent-list">`;
     JS fills it and removes `hidden` only when entries exist.
   - `<section class="library-quick" aria-labelledby="library-quick-heading">`
     with `h2` "Schnellzugriff" and the quick-link chips (markup as in
     Task 3).
   - Parts loop as today (part heading only when > 1 chapter), then
     `<ul class="library-grid">` of
     `<li class="library-card" data-filter-text="<casefolded title + level-1 and level-2 section titles, space-joined>">`:
     `<span class="library-card-numeral" aria-hidden="true">` numeral, or
     the part name for front matter / appendix (class
     `library-card-numeral--word`), `<a class="library-card-title" href="...">short_title</a>`,
     `<p class="library-card-meta">N Abschnitte</p>` (N = number of
     navigable top-level sections; omit when 0), and when there are
     sections `<details class="library-card-contents"><summary>Inhalt</summary><ul>…each navigable top-level section as <li><a href="…#sec-id">title</a></li>…</ul></details>`.
     Build `data-filter-text` in the view or a small template filter —
     not with ad-hoc template string concatenation that could break on
     quotes (autoescape must stay on).
   - Empty filter state: `<p class="library-empty" hidden>Kein Kapitel passt – Enter startet die Volltextsuche.</p>`.
   - Keep the existing `{% empty %}` "Es sind noch keine Kapitel verfügbar."
5. `static/js/wiki-library.js` (IIFE, strict mode):
   - Live filter on `#library-filter` `input` events: casefold the value,
     split on whitespace; a card matches when every token is in its
     `data-filter-text`. Non-matching cards get `hidden`; part headings
     whose cards are all hidden get `hidden`; matching cards whose section
     links match open their `<details>` and mark matching links with class
     `is-match`; clearing the filter restores everything (details closed
     again unless the user opened them). Toggle `.library-empty`.
   - "Weiterlesen": read `localStorage["rt-wiki-recent"]` (JSON array of
     `{title, chapter, url, ts}`, newest first; ignore malformed), render
     the first 3 as `<li><a class="library-recent-card" href=url><span class="library-recent-chapter">chapter</span><span class="library-recent-title">title</span></a></li>`
     via `textContent`, and unhide the section. Only accept `url` values
     that start with `/wiki/`.
6. CSS block "Bibliothek": hero with generous spacing and display font;
   search field large (min-height ~3.25rem) on `--rt-bg-elevated` with
   `--rt-border-strong`, gold focus ring via `--rt-focus`; grid
   `repeat(auto-fill, minmax(17rem, 1fr))`; cards on `--rt-panel`, border
   `--rt-border`, hover lift (border `--rt-gold-dim`, subtle translateY(-2px)
   with `--rt-transition`); numeral large (≈2.6rem) display font in
   `--rt-gold` with the word variant smaller uppercase mono; title
   `--rt-text` display font, no underline, gold-bright on hover; contents
   list without underlines, two columns when wide, `is-match` in
   `--rt-gold-bright` with a `mark`-like background via existing tokens;
   recent cards as a horizontal row of three.
7. Tests: `test_index_view.py` — adjust intentionally changed assertions
   (h1, card markup), add: quick links rendered, numerals rendered,
   `data-filter-text` present and autoescaped. E2E
   `tests/e2e/test_wiki_navigation.py` (reuse `login_via_browser`,
   `owner` fixtures from `tests/e2e/conftest.py`; load the real corpus like
   `test_complete_journey.py` does, restoring the repository afterwards):
   typing "talent" into `#library-filter` hides a non-matching card
   (e.g. "Starships") and keeps "Talents" visible; clearing restores;
   pressing Enter navigates to `/search/?q=…`; with a seeded
   `rt-wiki-recent` entry the "Weiterlesen" section is visible.

Run the quick test command and the wiki e2e command.

---

### Task 5: Reading navigation (chapter tree, scroll-spy, progress, highlight)

Files: new `wiki/context_processors.py`, `config/settings.py`
(register it), `templates/base.html`, `wiki/views.py`
(`WikiChapterView`), `wiki/templates/wiki/chapter.html`,
`wiki/templates/wiki/_chapter_nav.html`, `static/css/portal.css`, new
`static/js/wiki-reader.js`, tests `wiki/tests/test_chapter_navigation.py`
(adjust), new `wiki/tests/test_context_processor.py`, e2e additions in
`tests/e2e/test_wiki_navigation.py`.

1. Context processor `wiki_navigation(request)` → `{"wiki_nav_chapters": chapters}`
   when `request.resolver_match` exists and its `app_name == "wiki"`,
   else `{"wiki_nav_chapters": ()}`. If the repository is not initialised
   (`RuntimeError`), return `()`. Register as the last entry in
   `TEMPLATES[0]["OPTIONS"]["context_processors"]`.
2. `base.html`: inside the Wiki `<li>` of `.primary-nav`, when
   `wiki_nav_chapters`, render
   `<ul class="primary-nav-sub" aria-label="Kapitel">` with one
   `<li><a href="…" {% if chapter.slug == c.slug %}aria-current="page"{% endif %}><span class="primary-nav-numeral" aria-hidden="true">{{ c.numeral }}</span><span>{{ c.short_title }}</span></a></li>`
   per chapter (numeral span empty for unnumbered chapters). The top-level
   "Wiki" link keeps `aria-current="page"` only on the index/search pages
   (not on chapter pages, where the sub-item carries it), so there is
   exactly one `aria-current="page"` in the nav. Sub-items: smaller
   (min-height 2rem), indented, numeral in mono muted fixed width
   (~2.4rem), active item gold.
3. `chapter.html`: remove the bottom `<details class="wiki-chapter-list">`
   (the chapter tree replaces it) and its CSS. Add at the top of
   `.wiki-section-nav`, before the TOC, a
   `<input type="search" class="wiki-toc-filter js-only" placeholder="Abschnitt filtern…" aria-label="Abschnitte filtern" autocomplete="off">`.
   Add `<button type="button" class="wiki-to-top js-only" hidden aria-label="Nach oben">↑</button>`
   at the end of the content. Load `{% static 'js/wiki-reader.js' %}`
   with `defer` in `extra_scripts`, and when `highlight_terms` is non-empty
   `{{ highlight_terms|json_script:"wiki-highlight-terms" }}`.
4. `_chapter_nav.html`: in the sticky variant only, add
   `<div class="wiki-progress js-only" aria-hidden="true"><span class="wiki-progress-bar"></span></div>`
   as the last child.
5. View: `highlight_terms = repository.highlight_terms(request.GET.get("q", ""))`
   into the context as a list.
6. `static/js/wiki-reader.js` (IIFE, strict mode), each feature a small
   function, all no-ops when their elements are missing:
   - **Scroll-spy:** `IntersectionObserver` on the heading of every
     `.wiki-article section[id]` (rootMargin top offset =
     topbar + sticky-nav height, e.g. `"-120px 0px -65% 0px"`); the active
     section is the last one whose heading has passed the top offset. Its TOC
     link (`.wiki-section-nav a[href="#<id>"]`) gets `is-active` and
     `aria-current="location"`, the previous loses them; all ancestor
     `<details>` get `open`; the nav container scrolls the link into view by
     adjusting `nav.scrollTop` only (never `scrollIntoView` on the page).
   - **TOC filter:** on `input`, casefold; hide `li` whose link text does
     not match and that contain no matching descendant; open `details` that
     contain matches; clearing restores the initial `open` state.
   - **Progress:** on scroll (rAF-throttled) set the bar's
     `transform: scaleX(p)` where p = article progress 0..1.
   - **Highlight:** read `#wiki-highlight-terms` JSON; walk text nodes in
     `.wiki-article` (skip `script`, `style`, `mark`, headings' `.wiki-anchor`),
     wrap words that start with a term (case-insensitive, at a word start)
     in `<mark class="wiki-hit">`, max 300. If any: insert a small bar
     `<div class="wiki-hit-bar" role="status">n Stellen markiert · <button type="button">Markierung entfernen</button></div>`
     above the article; the button unwraps all marks and removes the bar and
     removes `q` from the URL via `history.replaceState` (keep the hash).
   - **Nach oben:** unhide after `scrollY > innerHeight`; click scrolls to
     top (smooth unless reduced motion).
   - **Recent:** write `{title: <active section title or chapter title>, chapter: <chapter short title from a data-attribute>, url: pathname + (active section ? "#sec-id" : ""), ts: Date.now()}`
     to `localStorage["rt-wiki-recent"]` on `pagehide` and, throttled to
     once per 2 s, on active-section change; keep ≤ 8 entries, one per
     chapter path (replace older). The chapter short title comes from
     `data-chapter-title` on `.wiki-article` (add it in the template).
7. CSS block "Reading navigation": sub-nav, TOC filter input (compact,
   `--rt-bg-elevated`), `is-active` TOC link (gold-bright, gold left
   border), progress bar (2px, `--rt-gold`, `transform-origin: left`,
   positioned at the bottom edge of the sticky nav), `.wiki-hit`
   (parchment-appropriate highlight using existing tokens — reuse the
   existing `mark` rule's look inside `.wiki-article`), hit bar, to-top
   button (round, `--rt-panel-raised`, gold border, fixed bottom-right).
8. Tests: context processor (wiki page → chapters, dashboard → `()`);
   chapter page renders `.primary-nav-sub` with exactly one
   `aria-current="page"` in `.primary-nav`, and no `.wiki-chapter-list`;
   `highlight_terms` JSON present with `?q=Waffe` (contains `"weapon"`) and
   absent without `q`. Adjust `test_chapter_navigation.py` assertions about
   the removed bottom list. E2E: on `/wiki/playing-the-game/`, scrolling to
   `#sec-the-attack` marks its TOC link `aria-current="location"`;
   typing "hit" in `.wiki-toc-filter` leaves "Table 9-6: Hit Locations"
   visible and hides "Healing"; `/wiki/armoury/?q=Waffe` shows at least one
   `mark.wiki-hit` and the hit bar, and "Markierung entfernen" removes them.
   Also run `tests/e2e/test_responsive_shell.py` (it asserts the shell).

Run the quick test command and the wiki e2e command.

---

### Task 6: Auspex command palette

Files: `templates/base.html`, new `static/js/auspex.js`,
`static/css/portal.css`, e2e `tests/e2e/test_wiki_navigation.py`
(additions), a template test in `core/tests/` or `wiki/tests/`.

1. `base.html` (authenticated shell only):
   - Topbar form: wrap the input in `<span class="topbar-search-field">`
     and add `<kbd class="topbar-search-kbd js-only" aria-hidden="true">Strg K</kbd>`
     inside it. Input id stays `topbar-search-input`; form stays a GET form
     to `wiki:search`.
   - Before `</body>`'s `extra_scripts`, render:

     ```html
     <dialog class="auspex" id="auspex" aria-label="Auspex-Suche"
             data-suggest-url="{% url 'wiki:suggest' %}"
             data-search-url="{% url 'wiki:search' %}">
       <div class="auspex-panel">
         <div class="auspex-input-row">
           <span class="auspex-glyph" aria-hidden="true">&#9737;</span>
           <input class="auspex-input" type="search" role="combobox"
                  aria-expanded="false" aria-controls="auspex-results"
                  aria-autocomplete="list" autocomplete="off"
                  placeholder="Regelwerk scannen&hellip;">
           <kbd class="auspex-esc">Esc</kbd>
         </div>
         <div class="auspex-results" id="auspex-results" role="listbox" aria-label="Vorschläge"></div>
         <div class="auspex-footer">
           <span><kbd>&uarr;</kbd><kbd>&darr;</kbd> auswählen</span>
           <span><kbd>&crarr;</kbd> öffnen</span>
           <span><kbd>Esc</kbd> schließen</span>
           <a class="auspex-all" href="{% url 'wiki:search' %}">Alle Treffer anzeigen &rarr;</a>
         </div>
       </div>
     </dialog>
     <script defer src="{% static 'js/auspex.js' %}"></script>
     ```
2. `static/js/auspex.js` (IIFE, strict mode):
   - Open via Ctrl+K / Meta+K (preventDefault), via `/` when
     `document.activeElement` is not an input/textarea/select/
     contenteditable, and via `focus`/`click` on `#topbar-search-input`
     (move its current value into the palette input, then blur it). Open =
     `dialog.showModal()`, focus the input, select its text, render.
     Close via Esc (native `cancel`), backdrop click (click target is the
     dialog element itself), and after navigation.
   - Empty/short query: group "Zuletzt gelesen" from
     `localStorage["rt-wiki-recent"]` (same format and `/wiki/` URL check as
     Task 4; up to 6), else a muted line "Tippe, um Kapitel, Abschnitte und
     Regeltexte zu scannen."
   - Query ≥ 2 chars (spaces removed): debounce 120 ms, abort the previous
     request with `AbortController`, `fetch(suggestUrl + "?q=" + encodeURIComponent(q), {credentials: "same-origin", headers: {Accept: "application/json"}})`;
     ignore responses whose `query` no longer equals the current input.
     Render groups in order Kapitel / Abschnitte / Volltext; a group heading
     is `<div class="auspex-group" role="presentation">`; each option is
     `<a class="auspex-option" role="option" id="auspex-opt-N" href=url>`
     containing `<span class="auspex-option-title">`,
     `<span class="auspex-option-path">` (numeral · chapter › path…), and for
     hits `<span class="auspex-option-snippet">` set via `innerHTML` from
     `snippet_html` (the only innerHTML use). All other strings via
     `textContent`. No results: "Keine Vorschläge – Enter sucht im
     Volltext."
   - Keyboard: ArrowDown/ArrowUp move the active option (wrap around),
     setting `aria-selected="true"` on it, `aria-activedescendant` on the
     input and scrolling it into view within the results; Enter opens the
     active option's `href`, or without an active option navigates to
     `searchUrl + "?q=" + encodeURIComponent(q)`; mouse hover sets active.
     `aria-expanded` reflects whether options are shown. Keep the
     `.auspex-all` link's href in sync with the query.
   - Fetch errors: show "Auspex gestört – Enter sucht im Volltext." and
     keep Enter working.
3. CSS block "Auspex": `dialog.auspex` centred near the top (margin-top
   ~12vh), width min(40rem, 90vw), no default border/padding;
   `::backdrop` darkened using a token-based colour (e.g.
   `color-mix(in srgb, var(--rt-bg) 70%, transparent)` plus
   `backdrop-filter: blur(2px)`); panel on `--rt-bg-elevated` with
   `--rt-border-strong` and a thin gold top rule; big input (1.15rem, no
   border, display font); a subtle scanning line animation on the input row
   while a request is in flight (class `is-scanning`, disabled under
   reduced motion by the global rule); results max-height ~60vh scrolling;
   group headings mono uppercase muted; options with title/path/snippet,
   active option `--rt-panel-raised` with gold left border; footer mono
   small muted with styled `kbd` (reuse one `kbd` style for topbar hint,
   palette and footer). Topbar kbd hint positioned inside the input's
   right edge.
4. Tests: a Django template test that an authenticated dashboard response
   contains `id="auspex"` and `data-suggest-url="/search/suggest/"`, and
   an anonymous login page does not. E2E: on the dashboard, Ctrl+K opens
   the dialog (`#auspex[open]`); typing "hit locations" shows an option
   whose title contains "Hit Locations"; ArrowDown + Enter navigates to a
   `/wiki/playing-the-game/` URL; `/` opens it from the wiki index when the
   filter field is not focused; Esc closes it; clicking the topbar search
   input opens it; with a seeded `rt-wiki-recent` entry the empty palette
   lists it. Make sure `tests/e2e/test_complete_journey.py` still passes
   (it types into `#dashboard-search-input`, which must not open the
   palette).

Run the quick test command, the wiki e2e command, and finally the full
suite `.venv/Scripts/python.exe -m pytest -q`.

---

### Task 7: Documentation

Files: `README.md` (wiki section), `docs/` only if an active document
describes the wiki UI.

Describe briefly, in German, in the README's wiki section: the Auspex
palette (Strg+K, `/`), the Bibliothek (filter, Schnellzugriff with the
pointer that the list lives in `wiki/manifest.py: QUICK_LINKS`,
Weiterlesen stored only in the browser), the search facets, and the reading
navigation. No totals. Update `AGENTS.md`'s responsibility table **only if**
it is unstaged-clean — it currently carries an owner edit, so instead leave
`AGENTS.md` untouched and mention `QUICK_LINKS` in the README.
