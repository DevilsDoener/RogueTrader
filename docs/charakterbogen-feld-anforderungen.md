# Charakterbögen – Anforderungen & Konventionen

Kurzfassung meiner Vorgaben für die Feld-/Overlay-Arbeit an den Bögen
(Charakterseite 1+2, Schiffsbogen). In einer neuen Session einfach diesen
Text mitgeben, dann ist der Kontext wieder da.

## Rendering (Grundregel)
- Das Overlay darf beim **Zoomen** und über verschiedene **Bildschirmbreiten
  nicht verrutschen**. (Umsetzung: feste Pixel-Leinwand + **ein** einziger
  `transform: scale()`; der Transform liegt auf `.sheet-canvas`, nie auf
  `.sheet-canvas-wrapper`.)
- Die **Optik des Bogens bleibt unverändert** – gleiches Hintergrundbild,
  Feldpositionen werden an den tatsächlichen Druck angepasst.

## Feld-Platzierung
- **Textfelder liegen auf den gedruckten Linien**, ausgerichtet an der
  tatsächlichen Linie – **nicht** an den Checkbox-Positionen.
- **Volle Linienlänge**: Ein Textfeld deckt die ganze Linie ab, vom
  Linienanfang bis kurz vor die Checkbox-Spalte bzw. die Abschnittskante.
- Felder dürfen **nicht in gedruckte Beschriftungen hineinschneiden**
  (z. B. „Current", Fertigkeitsnamen, Labels).
- **Spezialisierungs-Zeilen**: Jede leere Spezialisierungs-Zeile bekommt ein
  eigenes Textfeld – bei Common Lore, Forbidden Lore, Scholastic Lore,
  Speak Language, Performer, Pilot und Drive.
- **Characteristics-Werteboxen**: volle Boxgröße (wie WS/BS), nicht nur die
  halbe/Kreis-Seite.
- **Checkboxen** sitzen auf ihren **gedruckten Kästchen**, ausgerichtet mit dem
  jeweiligen Fertigkeits-Label (nicht eine Reihe versetzt).

## Text-Ausrichtung
- **Characteristics** und **Experience/XP**: Text **mittig** in der Box
  (horizontal + vertikal), Schema-Property `text_style: "center"` bzw. `"characteristic"`.
- **Characteristics** zusätzlich mit **größerer Schrift** (dort steht nur eine
  2-stellige Zahl) – gesteuert durch `text_style: "characteristic"`.
- Alle anderen Textfelder: Text **unten-links** auf der Linie (Standard).

## Checkbox-Darstellung
- **„Adv. Taken"-Pips** (`*_adv_*`): werden als **gefüllter Kreis** dargestellt
  (nicht eckig), **zentriert** auf dem gedruckten Pip und so groß, dass sie den
  Pip **voll ausfüllen** (Maße individuell aus der Vorlage). Umsetzung: `checkbox_style: "pip"`.
  Die Kreise folgen auch dem leichten Versatz der Originalgrafik.
- Die runden Waffenmarkierungen des Schiffsbogens verwenden ebenfalls `pip`.
- **Skill-/sonstige Kästchen**: bleiben **eckig** (schwarzer Inset-Block).

## Arbeitsweise (so gehe ich vor)
- **Seite für Seite.** Für jede Seite eine **Abdeckungskarte** erzeugen: alle
  definierten Felder über die Original-Vorlage einzeichnen (rot = Textfeld,
  blau = Checkbox, grün = neu/geändert). Ich schicke sie dir zur Kontrolle.
- Du markierst, was fehlt oder falsch sitzt; ich korrigiere gezielt und
  belege jede Änderung mit einem Verifikations-Ausschnitt.
- Änderungen an den Feldern gehen in `sheets/layouts/*.json`;
  `python -m sheets.layout` erzeugt daraus `sheets/data/*.json`
  (Prozentkoordinaten der Originalseite). Der Speicher-/Patch-Pfad bleibt
  unberührt.
- Am Ende **aufräumen**: alte/kaputte Zwischenversionen der Review-Bilder löschen.

## Tests
- **Alle Tests müssen grün bleiben.** Bei Kalibrierungs-Änderungen die
  gepinnten Fixtures/Erwartungen mitziehen:
  - `tests/fixtures/checkbox-rectangles.json` + SHA im
    `checkbox-calibration-manifest.json`
  - Contract-Hash und Feldzahlen in `sheets/tests/test_schema.py`
  - ggf. Textfeld-Anzahl in `tests/e2e/test_continuous_sheet_layout.py`
- Lauf: `.venv/Scripts/python.exe -m pytest` (Unit + Playwright-e2e).

## Lokal testen
- DB-Ordner anlegen (`data/`), `manage.py migrate`, Test-Nutzer + Charakter
  anlegen, `manage.py runserver 127.0.0.1:8000` (DEBUG=true). Login unter
  `/account/login/`. Bei CSS-Änderungen im Browser **hart neu laden**
  (Cache), und den Server neu starten, damit das gecachte Schema (`lru_cache`)
  neu geladen wird.
