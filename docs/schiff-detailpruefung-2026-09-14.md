# Detailprüfung der Schiffsseite

## Ergebnis

Die bisherige Aussage, auf der Schiffsseite passe alles, war zu weitgehend. Die geometrische Platzierung stimmt weitgehend; bei Werteingabe und Bedienbarkeit bestehen konkrete Einschränkungen. Es wurden keine produktiven Felder oder gespeicherten Werte verändert.

## Befunde

1. **Schadenswerte werden abgeschnitten.** In allen vier Damage-Feldern wird der gespeicherte Testwert `1d10+2` nicht vollständig angezeigt. Im Browser bleiben etwa `1d1` sichtbar. Die Schrift benötigt 151,8 Quellpixel, die nutzbare Eingabebreite beträgt nur 71,5 Quellpixel. Das tritt bei 1024 und 1440 Pixel Fensterbreite gleichermaßen auf. Die Rechtecke liegen richtig auf den gedruckten Werteboxen; die Schrift passt nicht zum verfügbaren Platz. Der bisherige Test mit `9` erfasst diesen Fall nicht. Auch längere Class-/Hull-Texte können horizontal abgeschnitten werden.
2. **Neun als Ressourcen/Kapazitäten beschriftete Flächen sind Checkboxen.** Space Available/Used, Power Available/Used und Weapon Capacity Dorsal/Prow/Keel/Port/Starboard akzeptieren nur boolesche Werte. Zahlen lassen sich dort nicht eingeben. Aus Beschriftung und Funktion folgt als Korrekturempfehlung, diese zu Wertefeldern umzubauen. Bereits gespeicherte boolesche Werte müssen dabei ausdrücklich erhalten oder behandelt werden.
3. **Die 28 kleinen Kreise besitzen sehr kleine Klickflächen.** Bei 1024 Pixel Fensterbreite liegen deren Breiten bei 4,30–4,75 CSS-Pixeln; bei 1440 Pixeln bei 6,70–7,40. Ihre Mittelpunkte treffen die richtigen DOM-Controls; die sichtbaren Füllungen verwenden Kreis-SVGs. Für bequemes Anklicken ist die Fläche dennoch klein. Eine größere unsichtbare Trefferfläche muss die benachbarten Macro-Battery-/Lance-Kreise getrennt halten.

## Positiv bestätigt

- Alle 86 Controls im Testbrowser bei beiden Fensterbreiten einzeln per Hit-Test am Mittelpunkt geprüft: jeweils 86 Treffer auf dem richtigen Eingabeelement.
- Alle 37 Markierungen aktiviert dargestellt: 28 mit Kreisfüllung, neun mit eckiger Füllung. Die 28 Kreise folgen den zugehörigen Typ- und Positionsbeschriftungen ohne den auf Charakterseite 1 gefundenen Zeilenversatz.
- Alle 49 Textfelder mit Testwerten gerendert; Waffenfelder Strength, Crit Rating und Range zeigen den Testwert `12` vollständig.
- Originalgrafik und aktuelle Feldumrisse für Kopf, Ressourcen, Komponenten und Waffen verglichen. Keine zusätzliche gravierende geometrische Verschiebung gefunden.
- Beide Browserprüfungen bestanden; sie prüfen Treffer und Form, während die zusätzlich protokollierte Textbreitenprüfung die beschriebenen Überläufe aufdeckt. Ein Testbestehen ist deshalb keine vollständige Layoutfreigabe.

## Belege

- `tmp/ship-deep-audit/browser-1024.json` und `browser-1440.json`: alle Control-Messungen.
- `tmp/ship-deep-audit/filled-1024.png` und `filled-1440.png`: tatsächlich gerenderte Browserbilder.
- `tmp/ship-deep-audit/weapons-browser-1440.png`: vergrößerter Browserausschnitt mit abgeschnittenen Schadenswerten.
- `tmp/ship-deep-audit/weapons.png`, `resources.png`, `header.png`: Originalgrafik mit aktuellen Feldumrissen.
- `tmp/ship-deep-audit/test_ship_audit_probe.py`: Diagnoseprogramm, für den Lauf vorübergehend unter tests/e2e abgelegt, danach dorthin archiviert. Testdaten ausschließlich in der isolierten Testdatenbank.


## Korrektur am 15.09.2026

Die drei oben genannten Befunde sind umgesetzt:

- Neun Ressourcen-/Kapazitätsfelder sind zentrierte Zahlenfelder (leer oder nichtnegative ganze Zahl bis vier Stellen).
- Schiffs-Textfelder passen ihre Schrift bei langen Werten automatisch an die vorhandene Breite an. Kürzere Werte erhalten wieder die ursprüngliche Schriftgröße.
- Die 28 Kreise behalten ihre gedruckte Position und Größe. Unsichtbare Label-Flächen erweitern den Klickbereich; bei den acht Waffentyp-Kreisen umfasst dieser auch die Beschriftung. Die erweiterten Bereiche überschneiden weder einander noch andere Eingabefelder.
- Migration `0003_ship_resource_numbers` archiviert vorhandene boolesche Ressourcenwerte im bestehenden Änderungsverlauf und leert die neuen Zahlenfelder. Sie erhöht die Feldversionen, damit alte Browserstände nicht unbemerkt überschreiben. Es werden keine Zahlen aus Häkchen abgeleitet.

Datenbanksicherung vor der Umstellung im Docker-Datenvolume: `/data/backups/before-ship-fields-20260914T211049.sqlite3` (SQLite integrity_check: ok).

Vollsuite: 412 Tests bestanden; lokale Warnungen betreffen das nicht angelegte staticfiles-Verzeichnis. Docker erzeugt die statischen Dateien beim Build. Layout-Compiler-Prüfung und Migrationsprüfung ohne Befund. Browserbilder nach der Korrektur: `tmp/ship-fixed/ship-1024.png`, `ship-1440.png`.


### Abschluss

Das alte Damage-Limit von sechs Zeichen wurde zusätzlich auf zwölf erhöht.
Auch `2d10+12` bleibt nach Speichern und Neuladen vollständig erhalten und sichtbar.
Nach dieser letzten Änderung bestanden 125 gezielte Tests einschließlich aller
vergrößerten Klickflächen bei beiden Fensterbreiten.

Aktueller Build: `6bf29368ec3fb38f59778841c93babfd876a4d626dcdcfc84e29af24b790bdd2`.
Vor dem Start wurde eine frische Datenbanksicherung erstellt:
`/data/backups/before-ship-fields-20260915T065017.sqlite3`. Der Container führt
Migrationen nicht selbst aus; `manage.py migrate sheets --noinput` wurde daher
anschließend ausdrücklich ausgeführt. Die Migration wurde als angewandt geprüft.
Sieben alte Ressourcen-Markierungen sind im Verlauf gesichert; sämtliche übrigen
gespeicherten Schiffswerte stimmen mit der Sicherung überein. Health-Endpunkt: HTTP 200.
