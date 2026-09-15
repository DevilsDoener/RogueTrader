# Feldkalibrierung vom 14.09.2026

## Sichtbare Änderungen

- Charakterseite 1: 78 vorhandene Textrechtecke an Linienanfänge und -enden angepasst; 44 kurze Fertigkeitszeilen und die erste Talentzeile ergänzt.
- Charakterseite 2: 36 Adv.-Taken-Kreise individuell an der Vorlage ausgerichtet; 23 Gear- und 15 Acquisition-Felder auf je eine vollständige gedruckte Zeile verteilt.
- Schiff: 83 vorhandene Rechtecke korrigiert; 28 runde Waffenmarker mit runder Füllung; fehlende vierte Komponenten-Zeile ergänzt.
- Originalbilder unverändert. Insgesamt 751 Felder, davon 424 Checkboxen.

## Nachweise

Die Source-Pixel-Messungen liegen für Texte in `tests/fixtures/text-line-rectangles.json`, für Checkboxen in `tests/fixtures/checkbox-rectangles.json`. Das SHA-Manifest verankert die Originalbilder und Checkbox-Referenzen.

`python -m sheets.layout --check` bestätigt die Übereinstimmung von Layoutquellen und generierten Daten. Der Vergleich mit `tmp/calibration-before` bestätigt für alle bisherigen Felder unveränderte IDs, Arten und Reihenfolge. Der ergänzende Review fand keine relevanten neuen Fehler und keine wesentlichen Überschneidungen der 46 zusätzlichen Felder.

Abdeckungskarten: `tmp/field-coverage/`. 424 Checkbox-Detailausschnitte: `tests/visual/checkbox-contacts/`. Browserbilder: `tests/visual/`. Die Werkzeuge `tools/render_field_coverage.py` und `tools/render_checkbox_contacts.py` erzeugen die Prüfabbildungen erneut.

## Bekannte getrennte Einschränkung

Einige historische Checkbox-IDs bei Spezialfertigkeiten sind semantisch anderen gedruckten Zeilen zugeordnet. Ihre Rechtecke treffen gedruckte Kästchen, aber die Feldbezeichnung passt nicht immer zur Zeile. Eine verlustfreie Zuordnung vorhandener Werte erfordert eine eigene Migration; siehe `docs/checkbox-row-mapping.md`. Diese Kalibrierung deutet bestehende Werte nicht um.

## Abschlussprüfung

Vollsuite einschließlich Playwright: 400 Tests bestanden (167,84 Sekunden). 126 Warnungen betreffen das lokal nicht angelegte staticfiles-Verzeichnis; der Docker-Build erzeugt die statischen Dateien mit collectstatic. git diff --check ohne Befund.
