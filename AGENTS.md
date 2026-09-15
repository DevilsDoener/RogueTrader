# AGENTS.md — verbindlicher Einstiegspunkt

Dieses Dokument ist der Einstieg für jede Arbeit in diesem Repository.
Es ist bewusst kurz: es legt die Rangfolge der Dokumente, die Zuständigkeiten
und die Testpflichten fest und verweist für alles Fachliche auf die
jeweiligen Fachdokumente.

## Dokumentenrangfolge

Bei Widersprüchen gilt von oben nach unten:

1. Direkte Anweisungen des Projektinhabers in der laufenden Sitzung.
2. Dieses `AGENTS.md`.
3. Die aktiven Fachdokumente unter „Zuständigkeiten“.
4. Der tatsächliche Code, die Schemas und die Tests.
5. Alles Übrige (Specs, Pläne, Brainstorms, datierte Prüfberichte) — **nicht
   verbindlich**, nur Historie.

Historische Dokumente erklären, *warum* etwas so geworden ist. Sie sind kein
Auftrag und keine gültige Beschreibung des Ist-Zustands. Sie tragen einen
Hinweis am Dateianfang. Dazu gehören:

- `docs/superpowers/specs/` und `docs/superpowers/plans/`
- `.superpowers/brainstorm/`
- datierte Prüf- und Kalibrierberichte in `docs/` (`*-2026-*.md`)
- `docs/archive/`
- `00-FORTSCHRITT.md` — betrifft ausschließlich die Regelwerk-Wissensbasis
  unter `content/`, nicht die Anwendung.

## Zuständigkeiten

| Thema | Verbindliches Dokument |
|---|---|
| Architektur, Designsystem, Berechtigungen, Projektgrenzen | `.claude/skills/project-conventions/SKILL.md` |
| Feld-/Overlay-Konventionen der Bögen | `docs/charakterbogen-feld-anforderungen.md` |
| Layoutquellen, Bereiche, Vorlagen, Darstellungsmetadaten | `docs/sheet-layout.md` |
| Kalibrierung, Fixtures, Manifest | `docs/sheet-calibration.md` |
| Synchronisierte Charakterwerte | `docs/characteristic-sync.md` |
| Berechnete Bewegungsfelder | `docs/movement-calculation.md` |
| Offene Zuordnung der Fertigkeitskästchen | `docs/checkbox-row-mapping.md` |
| Betrieb, Deployment, Backup, Kontowiederherstellung | `docs/operations.md` |
| Einrichtung, Abnahmeliste, Projektüberblick | `README.md` |
| Regelwerk-Wissensbasis (`content/`) | `00-FORTSCHRITT.md` |

## Grundregeln

- **Keine Feld-IDs ändern.** Sie sind persistente Datenschlüssel. Verschieben
  und Umgestalten ja, Umbenennen nur mit gesonderter Datenmigration.
- **Layout nur an der Quelle ändern:** `sheets/layouts/*.json` bearbeiten, dann
  `.venv/Scripts/python.exe -m sheets.layout` ausführen. Direkt geänderte
  `sheets/data/*.json` werden beim nächsten Generieren überschrieben.
- **Berechtigungsgrenzen sind die folgenreichste Fehlerklasse.** Änderungen an
  `services.py`, `permissions.py` oder View-Mixins unter `accounts/` und
  `sheets/` halten die in `project-conventions` beschriebenen Grenzen exakt ein.
- **`.env` wird nicht von Agenten bearbeitet** (ein `PreToolUse`-Hook verweigert
  das). `.env.example` ist die dokumentierte Vorlage.
- **Keine festen Gesamtzahlen in aktive Dokumente schreiben.** Feld- und
  Checkbox-Zahlen stehen in den Schemas, im Kalibrier-Manifest und in den Tests;
  nur datierte Prüfberichte halten ihre historischen Zahlen fest.
- **Fremde Dateien nicht anfassen und nicht einchecken:** `Notizbuch öffnen.onetoc2`
  (OneNote) und `graphify-out/`.

## Tests

Während der Arbeit schnell prüfen — nur die betroffene App:

```bash
.venv/Scripts/python.exe -m pytest -q sheets/tests
```

Vor Build, Push und Abschluss immer die vollständige Suite, einschließlich
Browser- und Sichtprüfungen:

```bash
.venv/Scripts/python.exe -m pytest -q
```

Bei Layoutänderungen zusätzlich:

```bash
.venv/Scripts/python.exe -m sheets.layout --check
```

Ein `PostToolUse`-Hook startet nach jeder Python-Änderung unter `accounts/`,
`core/`, `sheets/` oder `wiki/` automatisch die Tests der betroffenen App.
Migrationen, `.venv/`, `tmp/` und `graphify-out/` lösen ihn nicht aus.

Behauptungen wie „fertig“, „grün“ oder „behoben“ erst nach einem tatsächlich
gelaufenen Kommando mit sichtbarer Ausgabe.
