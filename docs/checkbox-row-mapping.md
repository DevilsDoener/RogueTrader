# Zuordnung der Fertigkeitskästchen (Charakterbogen Seite 1) – gelöst

Stand: 2026-10-01. Die Zuordnung ist abgeschlossen; dieses Dokument hält fest,
was falsch war und welche IDs heute gelten.

## Was falsch war

Alle Fertigkeits-Controls lagen auf den richtigen gedruckten Kästchen. In zwei
Blöcken trugen die persistenten Feld-IDs aber den Namen der **darüberliegenden
bzw. darunterliegenden** gedruckten Zeile, also um eine Zeile verschoben:

- Links (Drive bis Forbidden Lore): `evaluate` lag auf der zweiten Drive-Zeile,
  `forbidden_lore` auf Evaluate, und die vier Forbidden-Lore-Zeilen begannen
  erst bei `forbidden_lore_custom_1`. Die vierte Forbidden-Lore-Zeile hatte kein
  Feld.
- Rechts (Performer bis Scholastic Lore): `performer_custom_2` lag auf der
  ersten Pilot-Zeile (Performer hat nur zwei gedruckte Zeilen), und alle
  folgenden Pilot-, Psyniscience- und Scholastic-Lore-IDs waren um eine Zeile
  verschoben (die erste Scholastic-Lore-Zeile hieß `psyniscience`, die vierte
  `scholastic_lore_custom_2`).

Common Lore, Speak Language und die übrigen Fertigkeiten waren und sind
korrekt benannt.

## Endgültige Zuordnung

Geändert wurden ausschließlich die Namen (`c1_skill_<stem>_{basic,trained,plus10,plus20,bonus}`
und die zugehörigen `label`-Texte). Position, Größe und Darstellung jedes
Controls sind unverändert; jedes Feld liegt weiter auf demselben gedruckten
Kästchen. Gespeicherte Werte und Feldversionen wandern mit der Position.

| bisheriger Stamm | neuer Stamm | gedruckte Zeile |
|---|---|---|
| `evaluate` | `drive_custom_1` | Drive, zweite Zeile |
| `forbidden_lore` | `evaluate` | Evaluate |
| `forbidden_lore_custom_1` | `forbidden_lore` | Forbidden Lore, Zeile 1 |
| `forbidden_lore_custom_2` | `forbidden_lore_custom_1` | Forbidden Lore, Zeile 2 |
| `forbidden_lore_custom_3` | `forbidden_lore_custom_2` | Forbidden Lore, Zeile 3 |
| `performer_custom_2` | `pilot` | Pilot, Zeile 1 |
| `pilot` | `pilot_custom_1` | Pilot, Zeile 2 |
| `pilot_custom_1` | `pilot_custom_2` | Pilot, Zeile 3 |
| `pilot_custom_2` | `psyniscience` | Psyniscience |
| `psyniscience` | `scholastic_lore` | Scholastic Lore, Zeile 1 |
| `scholastic_lore` | `scholastic_lore_custom_1` | Scholastic Lore, Zeile 2 |
| `scholastic_lore_custom_1` | `scholastic_lore_custom_2` | Scholastic Lore, Zeile 3 |
| `scholastic_lore_custom_2` | `scholastic_lore_custom_3` | Scholastic Lore, Zeile 4 |

Die fünf Werte, die bisher unter `performer_custom_2` standen, liegen jetzt
unter `pilot` – an derselben Position, auf derselben gedruckten Zeile. Es ging
nichts verloren und nichts muss separat erhalten werden. Performer besitzt
damit nur noch `performer` und `performer_custom_1`, passend zu den zwei
gedruckten Zeilen.

Nicht umbenannt wurden die Notizfelder `c1_skill_*_note` und die
Spezialisierungsfelder `c1_*_spec_*`; sie waren bereits richtig zugeordnet.

## Neue Zeile

Forbidden Lore besitzt vier gedruckte Zeilen. Die vierte bekam die neuen
Felder `c1_skill_forbidden_lore_custom_3_{basic,trained,plus10,plus20,bonus}`.
Sie kopieren die Felder von `forbidden_lore_custom_2` (gleiche x, Breite, Höhe,
Stile, Eingabemodus und Längenlimit; das Bonusfeld ist wie alle anderen
Bonusfelder eine zweistellige Zahl) und sind um den gemessenen Zeilenabstand der
Forbidden-Lore-Zeilen nach unten versetzt. Die Lage wurde an den gedruckten
Quadraten der Originalgrafik geprüft.

## Migration

`sheets/migrations/0007_realign_skill_row_ids.py` benennt die Schlüssel in
`CharacterSheet.values` und `field_versions` gleichzeitig um (erst alle alten
Schlüssel lesen und entfernen, dann die neuen schreiben), damit die Kette sich
nicht selbst überschreibt. Unbekannte Schlüssel bleiben unangetastet. Der
Änderungsverlauf (`SheetChange`) ist append-only und behält die IDs, unter denen
die Änderung geschrieben wurde.

Die Rückwärtsmigration wendet die umgekehrte Zuordnung an. Werte unter den
neuen `forbidden_lore_custom_3_*`-Schlüsseln lassen sich nicht zurückführen,
weil das frühere Layout dafür kein Feld hat; sie werden dort verworfen.

Geprüft wird das durch `sheets/tests/test_skill_row_realignment.py` sowie durch
die fixierten IDs und Rechtecke in `tests/fixtures/checkbox-rectangles.json`,
`tests/fixtures/text-line-rectangles.json` und `sheets/tests/test_schema.py`.
