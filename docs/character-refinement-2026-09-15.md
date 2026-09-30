# Charakterbogen: Bonus, Textlinien und Adv. Taken

> **Historisches Dokument — nicht verbindlich.** Es hält den Stand zum Zeitpunkt
> seiner Entstehung fest und wird nicht nachgeführt. Verbindlich sind `AGENTS.md`
> und die dort genannten aktiven Fachdokumente; bei Widerspruch gelten Code,
> Schemas und Tests. Dieses Dokument erklärt das *Warum*, nicht das *Jetzt*.

- 63 Bonus-Zellen sind jetzt zentrierte Zahlenfelder für 0 bis 99 (oder leer). Frühere boolesche Markierungen werden über Migration 0004 im Änderungsprotokoll archiviert, die Bonusfelder geleert und ihre Versionen erhöht. Aus Häkchen werden keine Zahlen abgeleitet. Der vorhandene Mustercharakter erhält anschließend beispielhaft den Bonus 10.
- Special Abilities: gemeinsame linke Kante bei Quellpixel 908, Breite 525. Psychic Disciplines: ebenfalls 908, Breite 522. Höhe jeweils 34.
- Psychic Techniques: einheitliche Spaltenpositionen und gemeinsame y-Koordinate innerhalb jeder Zeile.
- Insanity: beschriftete Zeilen beginnen hinter ihrem Label; die unbeschriftete Fortsetzung nutzt mit x 1848/Breite 502 wieder die komplette Drucklinie.
- Alle 36 Seite-1-Pips einzeln gegen die Originalgrafik gefittet: 21×21 Quellpixel. Der leichte Versatz der gedruckten Kreise wird beibehalten.

Messbelege: tmp/current-lines und tmp/current-pips. Gesicherter Stand vor der Änderung: tmp/character-refinement/*-before.json. Bilddateien und Schiffs-Layout unverändert.

Prüfungen decken Zahlenvalidierung, alte Markierungen, Schema-Referenzen, gleichmäßige Textkanten/-linien und Speichern/Neuladen im Browser ab. Die bekannte historische Zuordnung einiger Spezialfertigkeits-IDs bleibt eine separate Aufgabe (docs/checkbox-row-mapping.md).


## Verifiziert und aktiviert

416 Tests bestanden. Neuer Build gestartet; Migration 0004 erfolgreich angewandt.
Sicherung: /data/backups/before-character-bonus-20260915T120331.sqlite3 (integrity: ok).
63 frühere Bonusmarkierungen archiviert und im bestehenden Beispielcharakter durch
den Beispielwert 10 ergänzt. Alle 665 Felder des Beispiels bleiben ausgefüllt.
Übrige Charakterwerte und sämtliche Schiffswerte stimmen mit der Sicherung überein.
Layoutquellen und generierte Daten aktuell; Health-Endpunkt HTTP200.
