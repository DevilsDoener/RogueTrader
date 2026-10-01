# Synchronisierte Charakterwerte

Die neun Charakterwerte WS, BS, S, T, Ag, Int, Per, WP und Fel sowie ihre
jeweils vier Adv.-Taken-Kreise bilden auf Charakterseite 1 und 2 gemeinsame
Felder. Eine Änderung auf einer Seite wird unmittelbar auf der anderen Seite
angezeigt und zusammen mit dem Ausgangsfeld atomar gespeichert. Die Zuordnung
der Gegenfelder kommt aus `sheets/characteristics.py` und wird als JSON
(`sheet-client-rules`) an den Browser gegeben.

Charakterwerte sind leere oder ein- bis zweistellige nichtnegative ganze
Zahlen (`0` bis `99`, einschließlich Eingaben wie `00`). Direkte API-Eingaben
werden nach denselben Regeln geprüft. Beide Kopien erhalten dieselbe
Feldversion, damit eine zwischenzeitliche Änderung auf der anderen Seite als
Versionskonflikt erkannt wird. Beide Änderungen stehen im Änderungsprotokoll.

Migration 0006 gleicht vorhandene gültige Werte ab. Wenn beide Seiten einen
Wert enthalten, ist Seite 1 die Quelle; fehlt er dort, wird Seite 2 verwendet.
Historische Werte außerhalb des neuen Zahlenformats bleiben erhalten, damit
keine Daten automatisch abgeschnitten oder umgedeutet werden. Sobald ein
gültiger Wert eingegeben wird, werden beide Seiten wieder gemeinsam geführt.
