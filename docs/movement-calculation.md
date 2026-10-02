# Aktive Bewegungsberechnung

Half Move ist der Eingabewert AB. Full Move = AB×2, Charge = AB×3, Run = AB×6.
Die drei Ergebnisse sind schreibgeschützte Textfelder. Half Move akzeptiert
nichtnegative ganze Zahlen bis sechs Stellen oder einen leeren Wert. Die
Ergebnisfelder erlauben sieben Stellen, damit auch das maximale Ergebnis passt.

Der Browser zeigt Ergebnisse unmittelbar beim Eingeben an; Faktoren und Stellenzahl
liest er als JSON aus `sheets/movement.py` (`sheet-client-rules` im Bogen), es gibt
keine zweite Kopie im JavaScript. Der Server berechnet
und speichert sie zusammen mit Half Move in einer atomaren Transaktion. Direkte
API-Schreibversuche auf Ergebnisfelder werden abgewiesen. Alle vier Änderungen
werden versioniert und protokolliert; ein Versionskonflikt ändert keinen Wert.
Leeren von Half Move leert auch die Ergebnisse. Bei Konfliktübernahme aktualisiert
sich die Vorschau; verzögerte Antworten überschreiben keine neuere lokale Eingabe.

Migration 0005 gleicht vorhandene Ergebnisse mit gültigen Half-Move-Werten ab und
bewahrt abweichende frühere Werte im Änderungsprotokoll. Nicht numerische Altwerte
werden nicht geraten oder automatisch umgedeutet. Der nächste gültige Half-Move-
Eintrag berechnet diese Ergebnisse.

Prüfungen (`sheets/tests/test_movement_calculation.py`,
`tests/e2e/test_movement_calculation.py`): normale Werte, 0, leere Eingabe, oberer
Wertebereich, unzulässige Eingaben, direkte Ergebnisänderungen, Versionskonflikte,
Datenmigration sowie Browsertests mit Speichern/Neuladen und Konfliktübernahme.
