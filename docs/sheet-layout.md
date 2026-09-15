# Bogenlayouts bearbeiten

Die Originalgrafiken bleiben unverändert. Die bearbeitbare Layout-Quelle liegt
in `sheets/layouts/character-page-1.json`, `character-page-2.json` und
`ship-page.json`. Daraus entstehen die flachen Dateien in `sheets/data/`, die
Anwendung, Kalibrierungstests und vorhandene Werkzeuge weiterhin lesen.

## Eine Änderung übernehmen

1. Die betreffende Datei unter `sheets/layouts/` bearbeiten.
2. Im Projektordner `.venv/Scripts/python.exe -m sheets.layout` ausführen.
3. Mit `.venv/Scripts/python.exe -m sheets.layout --check` prüfen, dass Quelle
   und erzeugte Dateien übereinstimmen. Dieser Befehl schreibt nichts und liefert
   bei veralteten Dateien Exitcode 1, bei ungültigen Quellen Exitcode 2.
4. `.venv/Scripts/python.exe -m pytest sheets/tests/test_layout.py
   sheets/tests/test_schema.py sheets/tests/test_field_calibration.py` ausführen.
   Den Befehl in einer Zeile eingeben. Bei sichtbaren Änderungen zusätzlich die
   Browsertests unter `tests/e2e/` ausführen und die Kalibrierung kontrollieren.
5. Den laufenden Django-Prozess neu starten (Schema-Cache) und bei CSS-Änderungen
   die Browserseite vollständig neu laden.

Quellen und erzeugte Dateien gemeinsam versionieren. Ein Test erkennt Abweichungen.
Der Compiler validiert alle drei Seiten, bevor er die Ausgabedateien schreibt.
Es gibt keinen zusätzlichen Kompilierungsschritt beim Start der Webanwendung.

## Bereiche und Koordinaten

`sections` enthält benannte Bereiche. `origin: [x, y]` ist deren Ankerpunkt.
Ein Feld liegt bei `origin + Feldposition`. Alle Angaben sind **Prozentpunkte der
gesamten Originalseite**, auch innerhalb eines Bereichs. Breite und Höhe ändern
sich durch einen anderen Ankerpunkt nicht.

Beispiel: Bereich `[10, 20]`, Feld `x: 2, y: 3` ergibt Seite `x: 12, y: 23`.
Das Verschieben eines Ankerpunkts verschiebt alle enthaltenen Felder gleich weit.
Der Bereich ist eine Hilfe beim Bearbeiten; er erzeugt keinen zusätzlichen
HTML-Container und verändert daher weder Zoom noch Rundung der Darstellung.

Die Reihenfolge von Bereichen und Feldern bleibt die Reihenfolge im erzeugten
Schema und in der Tastaturbedienung. Manche Bereiche sind deshalb aufgeteilt,
beispielsweise in Werteboxen und später folgende Aufstiegspunkte. Ihre bisherigen
Feldpositionen und die vorhandene Tab-Reihenfolge bleiben erhalten.

## Wiederverwendbare Vorlagen

`templates` definiert nach Namen geordnete Vorlagen mit benannten Feldplätzen
(`slot`). Waffenblöcke und Eigenschaftsfelder verwenden solche Vorlagen.

```json
{
  "id": "c2_weapon_2",
  "origin": [4.9, 39.2],
  "template": "weapon",
  "fields": [
    {
      "slot": "name",
      "id": "c2_weapon_2_name",
      "label": "Weapon 2 name",
      "width": 39.5
    }
  ]
}
```

Das ist ein illustrativer Ausschnitt, keine neue Kalibrierung. Der Slot `name`
liefert beispielsweise Typ, lokale Position, Höhe, Textstil und Längenlimit.
Die Instanz überschreibt hier nur die Breite. Änderungen an einer Vorlage wirken
auf alle Instanzen, außer auf ausdrücklich überschriebene Eigenschaften.
Solche Korrekturen sind beabsichtigt: Die gedruckten Waffenblöcke sind nicht
vollständig gleichmäßig. Eine Vorlage darf keine gespeicherte Feld-ID oder
Beschriftung vorgeben; diese bleiben ausdrücklich an der jeweiligen Instanz.

## Darstellung unabhängig von Feldnamen

| Eigenschaft | Werte | Bedeutung |
|---|---|---|
| `text_style` | `line` | Gewohnter Text unten links auf der Linie |
| `text_style` | `center` | Zentrierter Text in normaler Schriftgröße |
| `text_style` | `characteristic` | Zentrierter Eigenschaftswert in größerer Schrift |
| `checkbox_style` | `square` | Schwarzer Block im gedruckten Kästchen |
| `checkbox_style` | `pip` | Gefüllter Kreis im gedruckten Aufstiegspunkt |

`align` bleibt für ältere Verbraucher verfügbar. Wenn es ausdrücklich gesetzt
ist, muss es zum Textstil passen: `left` für `line`, sonst `center`. Ohne
`text_style` wird ein vorhandenes `align: center` als normal zentrierter Text
interpretiert. Fehlt beides, gilt `line`. Ohne `checkbox_style` gilt `square`.
Feldnamen wie `_value` und `_adv_` bestimmen die Darstellung nicht mehr.

## Gespeicherte Charaktere schützen

Zum Verschieben oder Umgestalten eines Feldes niemals dessen `id` ändern.
Bereichsname und Vorlagenname sind von dieser persistenten ID unabhängig.
Eine echte Feldumbenennung braucht eine gesonderte Datenmigration.

Der vorhandene HTML-Feldmapper arbeitet mit den **erzeugten** flachen Koordinaten.
Gemessene Korrekturen müssen in die Layout-Quelle zurückübertragen werden:
`lokale Position = gemessene Seitenposition - Bereichsanker`. Ein direkt geändertes
`sheets/data/*.json` wird beim nächsten Generieren überschrieben.

## Prüfung dieses Umbaus

Bei der Umstellung wurden alle bestehenden Eigenschaften der 705 Felder
(620 Charakterfelder und 85 Schiffsfelder) mit dem vorherigen Arbeitsstand
verglichen. Der Browservergleich verwendet dieselben Originalbilder und
Testeinträge vor und nach dem Umbau; aktuelle Ergebnisse stehen im Prüfbericht
`docs/sheet-layout-verification.md`.


## Zahlen und zusätzliche Klickflächen

`input_mode: "numeric"` akzeptiert leere Eingaben oder nichtnegative ganze
Zahlen als Text und setzt im Browser die passende Eingabemethode. Die neun
Ressourcen-/Kapazitätsfelder des Schiffs verwenden diesen Modus.

`hit_padding: [links, oben, rechts, unten]` erweitert nur die Klickfläche von
Checkboxen. Die Werte sind Pixel der Originalgrafik (0 bis 200) und skalieren
mit der festen Leinwand. Eine transparente, mit dem Input verknüpfte
Beschriftungsfläche lässt die gedruckten Kreise und ihre Füllung unverändert.
Die Pads dürfen keine benachbarten Controls überdecken; ein Test prüft dies
für sämtliche Schiffs-Felder.

Die Schrift von Schiffs-Textfeldern verkleinert sich bei Bedarf bis der
komplette aktuelle Wert in die gedruckte Fläche passt. Kürzere Werte verwenden
wieder die ursprüngliche Schriftgröße. Eingaben, Konfliktauflösung und die
initiale Größenanpassung berücksichtigen diese Anpassung.


## Berechnete Bewegungsfelder

`read_only: true` markiert die drei berechneten Ergebnisse Full Move, Charge
und Run. Half Move bleibt editierbar. Die Metadaten steuern die Eingabeoberfläche
und die serverseitige Schreibprüfung; Formeln und Speicherung sind in
`sheets/movement.py` und dem Charakter-Patch-Service definiert. Details siehe
`docs/movement-calculation.md`.
