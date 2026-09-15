# Erneute Layoutprüfung

Ergebnis: keine vollständige Freigabe. Der laufende Build stimmt per SHA-256 auf allen drei Layoutdateien mit dem geprüften Arbeitsstand überein.

## Bestätigte offene Fehler auf Charakterseite 1

1. Fertigkeitszuordnung: Evaluate liegt auf der freien Drive-Zeile; Forbidden Lore beginnt auf Evaluate. Rechts liegt Performer custom 2 auf Pilot; Pilot und Psyniscience sind entsprechend versetzt. Weitere Verschiebungen betreffen Scholastic Lore. Die sichtbaren Kästchenpositionen allein erkennen den Bedeutungsfehler nicht.
2. Fehlende bedienbare Zeilen: Drive custom 1, Scholastic Lore custom 3 und Speak Language custom 3 benötigen je fünf Controls. Insgesamt fehlen 15 Controls.
3. Für fünf bestehende Performer-custom-2-IDs gibt es keine dritte gedruckte Performer-Zeile. Sie dürfen nicht ohne Behandlung vorhandener Werte gelöscht oder umgedeutet werden.

Die vollständige Zielzuordnung im früheren Analyseartefakt enthält 250 unveränderte, 60 zu verschiebende und 15 neue Skill-Controls; fünf Alt-Controls benötigen getrennte Behandlung. Dies ist keine angewandte Migration.

Visuell erneut bestätigt durch beschriftete Ausschnitte: `tmp/final-layout-audit/drive-evaluate.png` und `tmp/final-layout-audit/pilot-psyniscience.png`. Details zur verlustfreien Korrektur: `docs/checkbox-row-mapping.md`.

## Positiv geprüft

- Alle 751 Feldrechtecke paarweise verglichen: keine Überschneidung mit mehr als zwei Quellpixeln in beiden Achsen.
- Textlinien und Markierungen anhand der Abdeckungskarten gegen die Originalgrafiken geprüft. Auf Charakterseite 2 und Schiff kein weiterer geometrischer Fehler festgestellt.
- 39 gezielte Kalibrierungs- und Browsertests bestanden, einschließlich Zoom und Textausrichtung (46,23 Sekunden). Eine Warnung betrifft das lokale staticfiles-Verzeichnis.
- Aktuell ausgelieferte Layoutdateien entsprechen exakt dem geprüften Stand.

Die Tests sichern Geometrie und Verhalten; sie beweisen noch keine vollständige semantische Zuordnung aller Fertigkeitszeilen. Deshalb reicht ihr Bestehen nicht für die Aussage, dass bereits alles passt. Diese Nachprüfung ändert keine produktiven Felder oder gespeicherten Daten.
