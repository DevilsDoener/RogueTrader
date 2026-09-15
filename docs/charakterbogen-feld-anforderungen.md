# Charakterbögen – Anforderungen & Konventionen

Verbindliche Vorgaben für die Feld-/Overlay-Arbeit an den Bögen
(Charakterseite 1+2, Schiffsbogen). Einstieg und Rangfolge: `AGENTS.md`.

## Rendering (Grundregel)
- Das Overlay darf beim **Zoomen** und über verschiedene **Bildschirmbreiten
  nicht verrutschen**. Umsetzung: feste Pixel-Leinwand + **ein** einziger
  `transform: scale()` auf `.sheet-canvas`, nie auf `.sheet-canvas-wrapper`.
- Der Maßstab kombiniert Einpassen in die Spaltenbreite mit der Zoomstufe des
  Nutzers (Bedienelemente in der Werkzeugleiste, 30–100 % in 10er-Schritten,
  Vorgabe 100 %, gemerkt im Browser). Ohne JavaScript rendert die Leinwand
  flüssig mit `width:100%`.
- Die **Optik des Bogens bleibt unverändert** – gleiches Hintergrundbild,
  Feldpositionen werden an den tatsächlichen Druck angepasst.

## Feld-Platzierung
- **Textfelder liegen auf den gedruckten Linien**, ausgerichtet an der
  tatsächlichen Linie – **nicht** an den Checkbox-Positionen.
- **Volle Linienlänge**: Ein Textfeld beginnt unmittelbar **nach seiner
  Beschriftung** – vor ihm bleibt kein nackter Linienanfang – und reicht bis
  zum Linienende bzw. zur Abschnitts-/Boxkante. Beide Enden jedes Feldes
  gegen die Vorlage prüfen.
- Felder dürfen **nicht in gedruckte Beschriftungen hineinschneiden**
  (z. B. „Current", Fertigkeitsnamen, Labels).
- **Spezialisierungs-Zeilen**: Jede leere Spezialisierungs-Zeile bekommt ein
  eigenes Textfeld – bei Common Lore, Forbidden Lore, Scholastic Lore,
  Speak Language, Performer, Pilot und Drive.
- **Characteristics-Werteboxen**: volle Boxgröße (wie WS/BS), nicht nur die
  halbe/Kreis-Seite.
- **Checkboxen** sitzen auf ihren **gedruckten Kästchen**, ausgerichtet mit dem
  jeweiligen Fertigkeits-Label (nicht eine Reihe versetzt).

## Darstellung (explizite Metadaten, nicht Feldnamen)

Die Darstellung wird ausschließlich über Schema-Eigenschaften gesteuert.
Feldnamen wie `_value` oder `_adv_` bestimmen sie **nicht** mehr.

| Eigenschaft | Wert | Wirkung |
|---|---|---|
| `text_style` | `line` | Text unten links auf der Linie (Standard) |
| `text_style` | `center` | Text mittig in der Box, normale Schriftgröße |
| `text_style` | `characteristic` | Text mittig und größer (zweistelliger Wert) |
| `checkbox_style` | `square` | Eckiges gedrucktes Kästchen (Standard) |
| `checkbox_style` | `pip` | Runder gedruckter Aufstiegspunkt |

- **Characteristics**: `text_style: "characteristic"`. **Experience/XP** und
  Werteboxen ohne gedruckte Linie (Bewegung, Lifting, Fate): `"center"`.
- Alle anderen Textfelder: `"line"`.

## Checkbox-Darstellung (angekreuzter Zustand)
- **Eckige Kästchen** (`square`) zeigen im angekreuzten Zustand ein
  **schwarzes X**, zentriert und auf 70 % der Feldfläche eingerückt. Das
  gedruckte Kästchen bleibt der einzige Rahmen; native Browser-Chrome ist
  unterdrückt.
- **Pips** (`pip`) zeigen einen **gefüllten schwarzen Kreis**, der den
  gedruckten Punkt voll ausfüllt. Das gilt für die „Adv. Taken"-Punkte beider
  Charakterseiten und für die runden Waffenmarkierungen des Schiffsbogens.
  Die Kreise folgen den **individuellen gedruckten Mittelpunkten**, auch wenn
  diese in der Originalgrafik leicht versetzt sind.
- **Ungekreuzt fügt ein Feld keine sichtbare Fläche hinzu** – der gedruckte
  Bogen sieht aus wie ohne Overlay.
- `hit_padding: [links, oben, rechts, unten]` vergrößert nur die **Klickfläche**
  einer Checkbox (Pixel der Originalgrafik, 0–200). Die gedruckten Kreise und
  ihre Füllung bleiben unverändert; Pads dürfen keine Nachbarcontrols
  überdecken.

## Zahlenfelder
- `input_mode: "numeric"` erlaubt leere Eingaben oder nichtnegative ganze
  Zahlen als Text und setzt im Browser die passende Eingabemethode. Die
  Ressourcen-/Kapazitätsfelder des Schiffsbogens nutzen diesen Modus.
- **Charakterwerte** sind leer oder ein- bis zweistellig (`0`–`99`,
  einschließlich `00`). Direkte API-Eingaben werden gleich geprüft.
- Die Schrift von Schiffs-Textfeldern verkleinert sich bei Bedarf, bis der
  komplette Wert in die gedruckte Fläche passt, und kehrt bei kürzeren Werten
  zur Ausgangsgröße zurück.

## Synchronisierte Charakterwerte
Die neun Charakterwerte und ihre je vier Adv.-Taken-Kreise sind auf
Charakterseite 1 und 2 **dasselbe Feld**. Eine Änderung erscheint sofort auf
der anderen Seite, wird atomar mit dem Ausgangsfeld gespeichert, erhält
dieselbe Feldversion (damit Konflikte erkannt werden) und steht doppelt im
Änderungsprotokoll. Beim Verschieben oder Neuanlegen dieser Felder die
Kopplung nicht aufbrechen. Details: `docs/characteristic-sync.md`.

## Berechnete Bewegungsfelder
Half Move ist der einzige Eingabewert. Full Move = ×2, Charge = ×3, Run = ×6
sind **schreibgeschützt** (`read_only: true`), werden im Browser sofort
vorausberechnet und serverseitig gemeinsam mit Half Move in einer Transaktion
geschrieben. Direkte API-Schreibversuche auf die Ergebnisfelder werden
abgewiesen; ein leerer Half Move leert die Ergebnisse. Details:
`docs/movement-calculation.md`.

## Arbeitsweise (so gehe ich vor)
- **Seite für Seite.** Für jede Seite eine **Abdeckungskarte** erzeugen
  (`tools/render_field_coverage.py`): alle definierten Felder über die
  Original-Vorlage einzeichnen (rot = Textfeld, blau = Checkbox,
  grün = neu/geändert). Ich schicke sie dir zur Kontrolle.
- Du markierst, was fehlt oder falsch sitzt; ich korrigiere gezielt und
  belege jede Änderung mit einem Verifikations-Ausschnitt
  (`tools/render_checkbox_contacts.py` für Checkbox-Detailausschnitte).
- Positionen immer an den **gedruckten Linien/Kästchen** der Vorlage messen,
  nie an möglicherweise schon verschobenen Nachbarfeldern.
- Änderungen gehen in `sheets/layouts/*.json`;
  `.venv/Scripts/python.exe -m sheets.layout` erzeugt daraus
  `sheets/data/*.json`. Ein direkt geändertes `sheets/data/*.json` wird beim
  nächsten Generieren überschrieben. Der Speicher-/Patch-Pfad bleibt unberührt.
- **Feld-IDs niemals ändern** – sie sind persistente Datenschlüssel. Eine echte
  Umbenennung braucht eine gesonderte Datenmigration.
- Am Ende **aufräumen**: alte/kaputte Zwischenversionen der Review-Bilder löschen.

## Tests
- **Alle Tests müssen grün bleiben.** Bei Kalibrierungs-Änderungen die
  gepinnten Erwartungen mitziehen – sie sind die Quelle für die jeweils
  gültigen Zahlen, nicht diese Dokumentation:
  - `tests/fixtures/checkbox-rectangles.json` und
    `tests/fixtures/text-line-rectangles.json` plus die SHA im
    `checkbox-calibration-manifest.json`
  - Contract-Hash und Feldzahlen in `sheets/tests/test_schema.py`
  - Geometrie-Pins in `sheets/tests/test_field_calibration.py`
  - ggf. Textfeld-Anzahl in `tests/e2e/test_continuous_sheet_layout.py`
- Läufe: `.venv/Scripts/python.exe -m sheets.layout --check` und
  `.venv/Scripts/python.exe -m pytest` (Unit + Playwright-e2e).

## Lokal testen
- DB-Ordner anlegen (`data/`), `manage.py migrate`, Test-Nutzer + Charakter
  anlegen, `manage.py runserver 127.0.0.1:8000` (DEBUG=true). Login unter
  `/account/login/`. Bei CSS-Änderungen im Browser **hart neu laden**
  (Cache), und den Server neu starten, damit das gecachte Schema (`lru_cache`)
  neu geladen wird.
