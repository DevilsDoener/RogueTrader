# Offene historische Zuordnung der Fertigkeitskästchen

Die vorhandenen Controls liegen auf gedruckten Kästchen. Einige persistente Skill-IDs bezeichnen jedoch historisch die falsche Zeile. Das ist ein Zuordnungs-/Datenproblem und wird in dieser Kalibrierung nicht durch Verschieben oder Umdeuten bestehender IDs verändert.

- Links fehlen Drive custom 1 auf Y 2088; Evaluate gehört auf 2134. Forbidden Lore benötigt vier Zeilen auf 2224/2270/2316/2362; bestehende Zuordnung beginnt irrtümlich bereits bei Evaluate.
- Rechts hat Performer nur zwei gedruckte Zeilen auf 1314/1360. Die vorhandenen fünf performer_custom2-IDs liegen auf Pilot 1406, besitzen aber keine dritte Performer-Zeile.
- Pilot gehört auf 1406/1452/1498, Psyniscience auf 1544. Scholastic Lore benötigt 1636/1682/1728/1773 (custom 3 fehlt); Speak Language ist seit 2026-09-19 auf allen vier Zeilen 2186/2230/2276/2322 vollständig bedienbar; custom 3 wurde mit neuen IDs ergänzt.
- Common Lore und die übrigen normalen Fertigkeiten sind semantisch passend zugeordnet.

Eine spätere Migration muss die Bedeutung bestehender gespeicherter Werte klären: Nutzer könnten nach gedruckter Position oder nach dem bisherigen Feldnamen gearbeitet haben. Deshalb weder allein aus der ID noch allein aus der alten Position die gewünschte Fertigkeit ableiten. Vor der Umstellung Bestandswerte sichern; die fünf überzähligen performer_custom2-Werte ausdrücklich erhalten und außerhalb des gedruckten Overlays zugänglich machen, bis ihre Zuordnung geklärt ist. Neue fehlende Gruppen bekommen neue persistente IDs; doppelte Belegung derselben Druckzelle vermeiden. Erst danach die dokumentierte eindeutige Zuordnung aktivieren.

Die früheren Analyseentwürfe zur Zeilenzuordnung (Korrekturen, neue Zeilen, vollständige Zuordnung) liegen nicht im Repository. Sie waren ausschließlich Migrationsentwürfe, keine unmittelbar anzuwendenden Geometriekorrekturen; das beschriebene Ziel waren eindeutige Druckzellen und fünf separat zu erhaltende Legacy-Werte. Keine Produktionsänderungen vorgenommen.
