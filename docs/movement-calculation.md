# Aktive Bewegungsberechnung

Half Move ist der Eingabewert AB. Full Move = AB×2, Charge = AB×3, Run = AB×6.
Die drei Ergebnisse sind schreibgeschützte Textfelder. Half Move akzeptiert
nichtnegative ganze Zahlen bis sechs Stellen oder einen leeren Wert. Die
Ergebnisfelder erlauben sieben Stellen, damit auch das maximale Ergebnis passt.

Der Browser zeigt Ergebnisse unmittelbar beim Eingeben an. Der Server berechnet
und speichert sie zusammen mit Half Move in einer atomaren Transaktion. Direkte
API-Schreibversuche auf Ergebnisfelder werden abgewiesen. Alle vier Änderungen
werden versioniert und protokolliert; ein Versionskonflikt ändert keinen Wert.
Leeren von Half Move leert auch die Ergebnisse. Bei Konfliktübernahme aktualisiert
sich die Vorschau; verzögerte Antworten überschreiben keine neuere lokale Eingabe.

Migration0005 gleicht vorhandene Ergebnisse mit gültigen Half-Move-Werten ab und
bewahrt abweichende frühere Werte im Änderungsprotokoll. Nicht numerische Altwerte
werden nicht geraten oder automatisch umgedeutet. Der nächste gültige Half-Move-
Eintrag berechnet diese Ergebnisse.

Prüfungen: normale Werte,0,leere Eingabe,oberer Wertebereich,unzulässige Eingaben,
direkte Ergebnisänderungen,Versionskonflikte,Datenmigration und zwei Browsertests
mit Speichern/Neuladen sowie Konfliktübernahme.

Aktiviert am 15.09.2026. Vollständige Testsuite: 424 bestanden. Migration 0005
angewendet, Layoutprüfung erfolgreich und laufender Dienst mit HTTP 200 geprüft.
Datenbanksicherung: `/data/backups/before-movement-calculation-20260915T122616.sqlite3`.
