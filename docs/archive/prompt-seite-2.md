# Beispiel-Prompt für eine neue Session (Charakterseite 2)

> **Überholt und archiviert.** Dieser Beispiel-Prompt stammt aus der
> Kalibrierung von Charakterseite 2 und ist nicht mehr aktuell: Layouts werden
> heute in `sheets/layouts/*.json` gepflegt, die Darstellung über
> `text_style`/`checkbox_style` gesteuert, und die genannten Feldzahlen sind
> überholt. Verbindlich sind `AGENTS.md` und
> `docs/charakterbogen-feld-anforderungen.md`.

Diesen Text in einer neuen Session als erste Nachricht mitgeben:

---

Ich arbeite am **Rogue Trader Portal** unter
`C:\Prv\pnp\RogueTraider\Character sheet\Wissensdatenbank` — ein Django-Portal,
das Charakterbögen als **pixelgenaue Overlays** über die Original-Grafiken legt
(Felder in `sheets/data/*.json` als Prozentkoordinaten).

**Charakterseite 1 ist fertig kalibriert. Jetzt ist Charakterseite 2 dran.**
Bereiche auf Seite 2: Movement, Characteristics, 5 Weapon-Blöcke, Gear,
Acquisitions, Mutations, Corruption, Wounds, Insanity, Armour, Lifting,
Fate Points.

**Meine Konventionen** stehen in `docs/charakterbogen-feld-anforderungen.md` —
bitte zuerst lesen und genau befolgen. Kurzfassung:
- Rendering darf beim Zoomen/über Breiten nicht verrutschen; Optik unverändert.
- Textfelder liegen auf den **gedruckten Linien**, decken die **volle
  Linienlänge** ab (bis kurz vor die Checkbox-Spalte) und schneiden **nicht in
  gedruckte Labels**.
- **Jede leere Spezialisierungs-Zeile** bekommt ein Textfeld.
- **Characteristics**: volle Boxgröße, Text **mittig** und **größer**
  (`align:"center"`, `2.6cqw` für `*_value`).
- **„Adv. Taken"-Pips** (`*_adv_*`): **runde, gefüllte Kreise**, zentriert auf
  dem gedruckten Pip, füllen ihn voll (Feld = Pip, ~17px).
- **Checkboxen** sitzen auf ihren gedruckten Kästchen, ausgerichtet mit dem
  jeweiligen Label; Skill-Kästchen bleiben eckig.

**Ablauf** (wie bei Seite 1): Erzeuge eine **Abdeckungskarte** für Seite 2 —
alle definierten Felder über `sheets/static/sheets/images/character-page-2.webp`
gezeichnet (rot = Textfeld, blau = Checkbox, grün = neu/geändert) — und schick
sie mir. Ich markiere, was fehlt oder falsch sitzt; du korrigierst iterativ und
belegst jede Änderung mit einem Verifikations-Ausschnitt. Miss Positionen an den
**gedruckten Linien/Kästchen** der Vorlage, nicht an evtl. schon verschobenen
Nachbarfeldern.

**Tests**: müssen grün bleiben — `.venv/Scripts/python.exe -m pytest`. Bei
Kalibrierungs-Änderungen die gepinnten Fixtures mitziehen:
`tests/fixtures/checkbox-rectangles.json` + SHA im
`checkbox-calibration-manifest.json`, Contract-Hash + Feldzahlen in
`sheets/tests/test_schema.py`, Textfeld-Anzahl in
`tests/e2e/test_continuous_sheet_layout.py`.

**Live testen** (optional): `docker compose up -d --build` (Port 8000) oder
`manage.py runserver 127.0.0.1:8000`; Login unter `/account/login/`. Bei
CSS-Änderungen Browser hart neu laden, Server bei Schema-Änderung neu starten.

---
