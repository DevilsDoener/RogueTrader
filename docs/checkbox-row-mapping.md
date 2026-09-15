# Offene historische Zuordnung der Fertigkeitskästchen

Die vorhandenen Controls liegen auf gedruckten Kästchen. Einige persistente Skill-IDs bezeichnen jedoch historisch die falsche Zeile. Das ist ein Zuordnungs-/Datenproblem und wird in dieser Kalibrierung nicht durch Verschieben oder Umdeuten bestehender IDs verändert.

- Links fehlen Drive custom1 auf Y2088; Evaluate gehört auf2134. Forbidden Lore benötigt vier Zeilen auf2224/2270/2316/2362; bestehende Zuordnung beginnt irrtümlich bereits bei Evaluate.
- Rechts hat Performer nur zwei gedruckte Zeilen auf1314/1360. Die vorhandenen fünf performer_custom2-IDs liegen auf Pilot1406, besitzen aber keine dritte Performer-Zeile.
- Pilot gehört auf1406/1452/1498, Psyniscience auf1544. Scholastic Lore benötigt1636/1682/1728/1773 (custom3 fehlt); Speak Language benötigt2186/2230/2276/2322 (custom3 fehlt).
- Common Lore und die übrigen normalen Fertigkeiten sind semantisch passend zugeordnet.

Eine spätere Migration muss die Bedeutung bestehender gespeicherter Werte klären: Nutzer könnten nach gedruckter Position oder nach dem bisherigen Feldnamen gearbeitet haben. Deshalb weder allein aus der ID noch allein aus der alten Position die gewünschte Fertigkeit ableiten. Vor der Umstellung Bestandswerte sichern; die fünf überzähligen performer_custom2-Werte ausdrücklich erhalten und außerhalb des gedruckten Overlays zugänglich machen, bis ihre Zuordnung geklärt ist. Neue fehlende Gruppen bekommen neue persistente IDs; doppelte Belegung derselben Druckzelle vermeiden. Erst danach die dokumentierte eindeutige Zuordnung aktivieren.

Analyseartefakte corrections-checkbox-rows.json und new-checkbox-rows.json sind ausschließlich Migrationsentwürfe, NICHT unmittelbar anzuwendende Geometriekorrekturen. complete-checkbox-row-mapping.json beschreibt ein mögliches Ziel mit325 eindeutigen Druckzellen und fünf separat zu erhaltenden Legacy-Werten. Keine Produktionsänderungen vorgenommen.
