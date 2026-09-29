# Wiki: Auspex-Suche, Bibliothek und Lesenavigation — Design

> Arbeitsdokument vom 2026-09-29 (Branch `feature/wiki-auspex-navigation`).
> Nach dem Merge gilt es wie alle Specs als **historisches Dokument**
> (siehe `AGENTS.md`); verbindlich ist dann der Code.

## Anlass

Der Projektinhaber findet die Wiki-Übersicht („Inhalts-Bibliothek“), die
Suchergebnisseite und die allgemeine Navigation hässlich und umständlich:

- Übersicht: jede Kachel ist eine Wand aus unterstrichenen Links, keine
  Hierarchie, kein Einstieg „wo war ich?“, kein schneller Weg zu den am
  Spieltisch ständig gebrauchten Tabellen.
- Suche: eine flache Liste von Kästen, „Kapitel – Abschnitt“ als Linktext,
  kein Kontext, wo der Abschnitt im Kapitel liegt, kein Eingrenzen.
- Navigation: Kapitelwechsel nur über Zurück/Weiter oder eine zugeklappte
  Liste ganz unten; die linke Hauptnavigation ist fast leer; im langen
  Kapitel weiß man nicht, wo man gerade ist; der `?q=`-Parameter wird zwar
  mitgegeben, aber auf der Zielseite nichts hervorgehoben.

## Leitidee: „Auspex“

Ein Auspex ist im 40k-Universum der Handscanner. Die Suche wird zum
Auspex: ein Befehlsfenster, das überall mit **Strg+K** (oder `/`) aufgeht,
schon beim Tippen Kapitel, Abschnitte und Volltexttreffer zeigt und per
Tastatur bedient wird. Dazu drei Oberflächen im bestehenden
„Brücken-Hybrid“-Stil:

1. **Auspex-Befehlsfenster** (global, alle angemeldeten Seiten).
2. **Bibliothek** (`/wiki/`): Kapitelkacheln mit großer römischer Ziffer,
   Schnellzugriff auf Spieltisch-Tabellen, „Weiterlesen“, Live-Filter.
3. **Suchergebnisse** (`/search/`): Kapitel-Facetten mit Trefferzahlen,
   Pfad-Breadcrumb je Treffer, hervorgehobener bester Treffer.
4. **Lesenavigation** (`/wiki/<slug>/`): Kapitelbaum in der linken
   Hauptnavigation, mitlaufende Gliederung (Scroll-Spy), Gliederungsfilter,
   Lesefortschritt, Treffer-Hervorhebung, „Nach oben“.

## Globale Randbedingungen (verbindlich für jede Aufgabe)

- **Designsystem:** nur `--rt-*`-Tokens aus `static/css/portal.css`, keine
  rohen Farbwerte in Templates/CSS. Pergament (`--rt-parchment*`) nur für
  `.wiki-article`. Neue Regeln kommen in `portal.css` in eigene,
  kommentierte Blöcke. `sheets/static/sheets/sheet-viewer.css` und dessen
  Selektoren werden nicht berührt.
- **Nur Desktop** (≥ 1024 px). Keine responsiven Umbauten an `.app-shell`.
- **Progressive Enhancement:** Jede Seite funktioniert ohne JavaScript:
  Suchformulare bleiben normale GET-Formulare, Gliederung bleibt
  `<details>`, Links bleiben Links. JS-abhängige Bedienelemente (Filterfeld
  der Gliederung, Tastenkürzel-Hinweis, „Weiterlesen“, Fortschrittsbalken)
  sind ohne JS unsichtbar. Dafür setzt `base.html` im `<head>` per
  Inline-Skript die Klasse `js` auf `<html>`; CSS blendet `.js-only` nur
  unter `.js` ein.
- **JavaScript:** Vanilla-JS, keine Fremdbibliotheken, kein Build-Schritt.
  Dateien unter `static/js/`, per `<script defer>` eingebunden. Jeder
  `localStorage`-Zugriff in `try/catch`; die Seite funktioniert ohne.
  Server-Texte werden per `textContent` eingesetzt, nie per `innerHTML` —
  einzige Ausnahme ist das Snippet-HTML, das der Server bereits escaped hat
  (`wiki/search.py: _make_snippet`, nur `<mark>` bleibt stehen).
- **Berechtigungen:** jede neue View verlangt Anmeldung
  (`LoginRequiredMixin`). Nichts, was `q` spiegelt, wird gzip-komprimiert
  (BREACH-Begründung in `wiki/views.py`).
- **Barrierefreiheit:** Befehlsfenster als `<dialog>` mit
  Combobox/Listbox-Muster (`role="combobox"`, `aria-expanded`,
  `aria-controls`, `aria-activedescendant`, `role="option"`); sichtbarer
  Fokus; `prefers-reduced-motion` wird von der bestehenden globalen Regel
  abgedeckt.
- **Sprache der Oberfläche:** Deutsch. Buchinhalte bleiben Englisch.
- **Keine festen Gesamtzahlen in Prosa-Dokumente** (`AGENTS.md`).
- **Tests:** schnell `.venv/Scripts/python.exe -m pytest -q wiki/tests`
  bzw. die betroffenen Dateien; neue Browserfunktionen bekommen
  Playwright-Tests unter `tests/e2e/` nach dem Muster von
  `tests/e2e/conftest.py`. Bestehende Tests, die absichtlich geändertes
  Markup prüfen, werden angepasst — nicht gelöscht, und nie so, dass sie
  nichts mehr prüfen. Commits nur mit eigenen Dateien; nie
  `*.onetoc2`, `graphify-out/`, `AGENTS.md`, `.agents/`, `.codex/` stagen.

## Datenmodell-Ergänzungen (Server)

- `WikiSection.parent_titles: Tuple[str, ...]` — Titel der Vorfahren im
  Kapitel (ohne Intro-Abschnitt, ohne das Kapitel selbst), von außen nach
  innen. Gesetzt in `wiki/content.py` beim Aufbau des Baums.
- `WikiChapter.numeral` — römische Ziffer aus dem Manifest-`part`
  („Kapitel IV“ → „IV“), sonst `""`.
- `WikiChapter.short_title` — Titel ohne führendes „Chapter IV:“ /
  „Chapter 14 -“ (Regex `^Chapter\s+[0-9IVXLC]+\s*[:\-–]\s*`, ignoriert
  Groß/Klein); fällt auf `title` zurück.
- `SearchResult.path: Tuple[str, ...]` — `parent_titles` des Treffers.
- `SearchIndex.search(query, limit=None)` liefert alle Treffer;
  `limit` bleibt für bestehende Aufrufer erhalten.
- `SearchIndex.highlight_terms(query)` — die casefolded Suchbegriffe samt
  Alias-Übersetzungen (ohne Präfix-Erweiterung), sortiert, für die
  Hervorhebung auf der Kapitelseite.
- `wiki/manifest.py: QUICK_LINKS` — kuratierte Schnellzugriffe
  (deutsches Label, Kapitel-Slug, Abschnitts-ID). Nicht auflösbare Einträge
  werden beim Rendern ausgelassen und per Test mit dem echten Korpus
  abgesichert.

## Oberflächen im Detail

### Auspex-Befehlsfenster

- Öffnen: Strg+K / Cmd+K überall; `/` wenn der Fokus nicht in einem
  Eingabefeld, einer Textarea, einem Select oder `contenteditable` liegt;
  Klick oder Fokus in das Suchfeld der Topbar (dessen bisheriger Text wird
  übernommen). Schließen: Esc, Klick auf den Hintergrund.
- Die Topbar behält ihr GET-Formular (ohne JS unverändert). Mit JS zeigt es
  rechts im Feld den Hinweis `Strg K`.
- Leerer Suchbegriff: Liste „Zuletzt gelesen“ (aus `localStorage`) und eine
  Zeile mit Tastenhinweisen.
- Beim Tippen (ab 2 Zeichen, 120 ms entprellt, laufende Anfrage per
  `AbortController` verworfen) Abfrage an `GET /search/suggest/?q=` und
  Anzeige in drei Gruppen: **Kapitel**, **Abschnitte** (Titeltreffer),
  **Volltext** (Snippet mit `<mark>`). Jede Zeile zeigt den Pfad
  (Kapitel › Vorfahren).
- ↑/↓ bewegt die Auswahl (umlaufend), Enter öffnet die Auswahl, Enter ohne
  Auswahl öffnet die volle Ergebnisseite; Fußzeile mit Link „Alle Treffer
  anzeigen“.

### Bibliothek (`/wiki/`)

- Kopf: Eyebrow „Regelwerk“, `h1` „Bibliothek“, ein großes Feld
  „Kapitel und Abschnitte filtern – Enter sucht im Volltext“. Das Feld ist
  ein GET-Formular auf `wiki:search`; mit JS filtert es beim Tippen die
  Kacheln live.
- „Weiterlesen“ (nur JS, nur wenn Einträge vorhanden): die letzten drei
  gelesenen Stellen als Karten.
- „Schnellzugriff“: Chips aus `QUICK_LINKS`.
- Kapitelraster nach Teilen gruppiert (Überschrift nur bei Teilen mit
  mehreren Dateien, wie bisher). Kachel: große römische Ziffer
  (Display-Schrift, Gold) bzw. Teilname für Vorspann/Anhang, Kurztitel als
  Link, Metazeile „N Abschnitte“, darunter `<details>` „Inhalt“ mit allen
  navigierbaren Hauptabschnitten als ruhige, nicht unterstrichene Liste.
- Filter: vergleicht mit Kapiteltitel und Abschnittstiteln (Ebene 1 und 2);
  passende Kacheln bleiben, ihr „Inhalt“ klappt auf und passende Abschnitte
  werden markiert; sonst Leerzustand „Kein Kapitel passt – Enter startet
  die Volltextsuche“.

### Suchergebnisse (`/search/`)

- Zwei Spalten: links Facette „Kapitel“ mit „Alle Kapitel (N)“ und je
  Kapitel mit Treffern „Titel (n)“ in Buchreihenfolge; rechts die Treffer.
  `?kapitel=<slug>` grenzt ein; unbekannter Slug wird ignoriert.
- Zusammenfassung „N Treffer für „q““ (+ „in <Kapitel>“). Angezeigt
  werden höchstens die besten 50; wenn es mehr gibt, steht das dabei.
- Trefferkarte: Pfadzeile (Ziffer · Kurztitel › Vorfahren), Titel als
  Link (weiterhin erster Link im `li` von `.wiki-results`), Snippet. Ohne
  Facette ist der erste Treffer als „Bester Treffer“ hervorgehoben.
- Leerzustände bleiben inhaltlich gleich; bei „keine Treffer“ zusätzlich die
  Schnellzugriff-Chips.

### Lesenavigation (`/wiki/<slug>/`)

- **Hauptnavigation:** Auf allen Wiki-Seiten (App `wiki`) klappt unter
  „Wiki“ die Kapitelliste auf (Ziffer + Kurztitel, aktuelles Kapitel mit
  `aria-current="page"`). Geliefert von einem Context-Processor. Die
  bisherige zugeklappte Liste „Alle Kapitel“ am Seitenende entfällt.
- **Gliederung:** Filterfeld „Abschnitt filtern…“ (nur JS) oben in
  `.wiki-section-nav`; Scroll-Spy markiert den aktuellen Abschnitt
  (`aria-current="location"`, Klasse `is-active`), öffnet dessen
  `<details>`-Vorfahren und hält ihn in der Gliederung sichtbar, ohne die
  Seite zu scrollen.
- **Lesefortschritt:** dünner Goldbalken an der Unterkante der klebenden
  Kapitelleiste.
- **Treffer-Hervorhebung:** Kommt man mit `?q=`, liefert der Server
  `highlight_terms` per `json_script`; JS markiert Wörter im Artikel, die mit
  einem dieser Begriffe beginnen (höchstens 300 Markierungen, `<mark
  class="wiki-hit">`), und zeigt eine kleine Leiste „n Stellen markiert ·
  Markierung entfernen“.
- **Nach oben:** schwebender Knopf nach einer Bildschirmhöhe Scrollen.
- **Zuletzt gelesen:** beim Verlassen der Seite (`pagehide`) und beim
  Wechsel des aktiven Abschnitts gedrosselt wird `{title, chapter, url,
  ts}` gespeichert (Schlüssel `rt-wiki-recent`, höchstens 8 Einträge, je
  Kapitel nur der neueste).

## Nicht im Umfang

Mobile Layouts, serverseitige Nutzerhistorie, Änderungen an den Bögen, am
Dashboard-Suchformular (`#dashboard-search-input` bleibt unverändert) oder
am Ranking der Volltextsuche.
