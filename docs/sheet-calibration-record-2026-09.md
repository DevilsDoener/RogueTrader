# Sheet calibration record (dated)

> **Historisches Dokument — nicht verbindlich.** Es hält den Stand zum Zeitpunkt
> seiner Entstehung fest und wird nicht nachgeführt. Verbindlich sind `AGENTS.md`
> und die dort genannten aktiven Fachdokumente; bei Widerspruch gelten Code,
> Schemas und Tests. Dieses Dokument erklärt das *Warum*, nicht das *Jetzt*.

Split out of [sheet-calibration.md](sheet-calibration.md). The sections below
state what was true on their date and are deliberately not updated; where they
conflict with the active document or with the code, the code wins.

## 2026-09-20: vollständiger Rahmen aus der Standalone-PDF

Die beiden beschnittenen Charakterseiten aus dem Regelbuchscan wurden durch
die vollständigen Seiten der separaten Character-Sheet-PDF ersetzt. Beide
Hintergründe enthalten jetzt den kompletten linken und rechten Zierrahmen sowie
die ursprünglichen Seitenränder. Gespeicherte PDF-Formularwerte werden beim
Rendern mit `-hide-annotations` ausgeblendet.

Alle bestehenden Felder und IDs blieben erhalten. Die Koordinaten wurden pro
Seite über lokale Bildmerkmale registriert, als affine Abbildung auf die neuen
2691 × 3435-Pixel-Seiten übertragen und anschließend auf vollständigen
Abdeckungskarten kontrolliert. Checkbox- und Textlinienreferenzen sowie die
Quellbild-Hashes wurden auf das neue Druckbild nachgezogen.

## 2026-09-19: Rüstungspunkte je Trefferzone

Jede Trefferzone ist ein gedruckter Kasten mit Name und Trefferbereich oben,
freier Fläche für den Rüstungswert und einer `TYPE:`-Zeile unten. Nur die
Typ-Zeile hatte ein Feld; der Wert selbst konnte nirgends eingetragen werden.
Aufgefallen beim Übernehmen eines ausgefüllten Bogens: sechs Zahlen fanden im
Schema kein Ziel.

Sechs neue Textfelder `c2_armour_<zone>_ap`, je unmittelbar **vor** der
zugehörigen Typ-Zeile, damit die Tabulator-Reihenfolge einer Zone dem
gedruckten Aufbau von oben nach unten folgt. `text_style: "center"` wie bei den
anderen Werteboxen ohne gedruckte Linie, `input_mode: "numeric"`.

Die Felder nehmen 45 % der freien Kastenbreite ein und sind darin zentriert.
Über die volle Breite gezogen lasen sie sich wie eine Schreiblinie statt wie
eine Wertebox; der Wert ist ein- bis zweistellig.

Die Kästen wurden in der Originalgrafik vermessen: Hell-/Dunkelschwellen für
die Kastenkanten, danach die größte druckfreie Zeilenfolge innerhalb des
Kastens. Die Unterkante wurde auf 0,15 Prozentpunkte über die Typ-Zeile
gezogen, damit sich beide nicht überlappen. Gegenprobe: die Positionen der
sechs Werte aus einem real ausgefüllten PDF fallen alle in die gemessenen
Flächen.

Beim ersten Durchgang zählte die Tintenerkennung anteilig zur Kastenbreite.
Die kurze, mittige Bereichszahl („11–20") blieb darunter, und die Felder
begannen oberhalb davon — sichtbar erst auf der Abdeckungskarte, nicht in den
Zahlen. Die Erkennung zählt jetzt absolute Dunkelpixel.

Seite 2: 175 → 181 Felder. Contract-Hash und Feldzahlen in
`sheets/tests/test_schema.py` nachgezogen.

## Characteristic value boxes (2026-08-26 / 2026-08-27)

Owner convention (`docs/charakterbogen-feld-anforderungen.md`): every
characteristic value box spans the **full** printed box (like WS/BS), with
the value **centred**, rather than the older layout that kept the field clear
of the printed bonus circle in the box's left half. (Centring was expressed as
`align: "center"` at the time; today it is `text_style: "characteristic"`.)

- Character page 1 was widened to full box on 2026-08-26.
- Character page 2 followed on 2026-08-27: `c2_s_value` … `c2_fel_value`
  widths were measured from the printed box borders (detected right-edge
  columns at 34.52 / 44.85 / 55.19 / 65.54 / 75.85 / 86.21 / 96.56 % of the
  2484 px canvas) and extended to ~9.1–9.2 %, matching the WS/BS boxes, while
  keeping the existing left `x` (already at the box's left border).
  `sheets/tests/test_field_calibration.py::test_characteristic_value_field_covers_full_box`
  now guards this against re-narrowing.

## Page 2 field additions & value-box centring (2026-08-28)

Owner review of the page-2 coverage map added 8 text fields (167 → 175 at the
time) so every printed writable line carries a field (full-line length):

- **Weapon "Special Rules" — two lines each.** Every weapon block has two
  printed rule lines. The existing field sat on the lower (continuation) line
  only; the line beside the "Special Rules" label was empty. The single
  `c2_weapon_N_special_rules` was renamed to `…_special_rules_2` (continuation)
  and a new `…_special_rules_1` added on the label line, starting after the
  printed label and running to the block's right edge.
- **Corruption:** two continuation lines under "Malignancies" now have
  `c2_corruption_malignancies_2` / `…_3` (full column width, no label).
- **Insanity:** the continuation line under "Disorders" now has
  `c2_insanity_disorders_2`.

The value boxes with **no printed line** (page-2 movement ×6, lifting ×3,
fate ×2) were switched to centred text so their single value centres in the
box like the characteristics (they keep the normal font size).
`_all_text_metrics` (e2e) excludes all `.sheet-text--center` fields.

**Adv.-Taken pips levelled.** Owner asked for a flat pip row; the printed pips
drift ~8px down left-to-right, so all page-2 `*_adv_*` were set to a common
`y=22.7357` (top=738/bottom=753 px, the drift-range midpoint, worst case ~4px
off a printed circle). Fixture `checkbox-rectangles.json` + manifest SHA and
the `c2_ws_adv_1` geometry pin were updated to match.
*(Superseded on 2026-09-14 — see below.)*

**Full-line coverage review (owner emphasis).** Every page-2 text field must
span the whole printed line — from just after its label to the line end /
section edge — not sit short. The audit found two groups starting too far right:

- **Wounds + Insanity** value fields began ~65–105px right of their labels,
  leaving the front of each printed line bare. Moved left to start just after
  the label (same right edge at x=2350px), covering the full line.
- **Armour TYPE** fields began ~30–64px after "TYPE:" and overshot the box's
  right border. Repositioned to start just after "TYPE:" and end at the box's
  inner right edge (full line within each location box).

Weapon sub-fields, gear/acquisitions/mutations, corruption and the added
continuation lines already reached their line ends. Pinned expectations in
`test_page_2_right_column_fields_start_after_their_printed_labels` updated.

## 2026-09-14: Ausrichtung an der tatsächlichen Vorlage

Die frühere Begradigung der Seite-2-Pips ist abgelöst: alle 36 Kreise folgen
nun ihren individuellen gedruckten Mittelpunkten. Die Originalbilder bleiben
unverändert. 28 runde Waffenmarkierungen des Schiffsbogens verwenden runde
Füllungen. Eckige Kästchen bleiben eckig.

Textfelder wurden anhand der sichtbaren Linienanfänge und -enden vermessen.
Gear und Acquisitions belegen jede gedruckte Zeile mit einem durchgehenden
Feld; die bisher ausgelassene erste Zeile wird genutzt und die bisher geteilte
letzte Zeile entfällt. Bestehende IDs und Werte bleiben erhalten.
44 Fertigkeitsnotizfelder, die erste Talentzeile und die fehlende vierte
Essential-Component-Zeile sind zusätzlich beschreibbar. Die neuen Felder werden
an die bestehende Schema-Reihenfolge angehängt, um deren Vertrag zu erhalten.

Feldzahlen an diesem Tag: Charakterseite 1: 490, Charakterseite 2: 175,
Schiff: 86. Gemessene Textrechtecke: `tests/fixtures/text-line-rectangles.json`.
Checkbox-Referenz und SHA-Manifest sind auf die vermessenen Rechtecke aktualisiert.

## 2026-08-23 / 2026-08-25: Checkbox-Kontaktprüfung

Die Prüfung vom 2026-08-23 kontrollierte jeden Ausschnitt. Die Rechtecke deckten
durchgehend die freie Markierungsfläche ab und ließen den gedruckten Kreis- bzw.
Kastenrand außerhalb des Overlays. Keine Gruppe überschritt die damalige Toleranz
von zwei Pixeln pro Kante, daher waren keine Schema-Korrekturen nötig und es gibt
keine Vorher/Nachher-Tafeln. Am 2026-08-25 wurde auf 0 px pro Kante verschärft
(inklusive aller "Adv. Taken"-Pips beider Charakterseiten); auch dabei waren
keine Koordinatenänderungen nötig.
