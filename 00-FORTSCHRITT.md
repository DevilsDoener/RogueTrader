# Fortschritt der Wissensdatenbank

> Diese Datei dokumentiert, welche Seiten des Regelbuchs bereits ausgewertet wurden,
> damit die Arbeit in einer neuen Session nahtlos fortgesetzt werden kann.
> **Letzte Aktualisierung: 20-Datei-Struktur nach PDF-Lesezeichen angelegt. Neue Zielvorgabe: vollständige Transkription aller 408 Seiten ohne Verdichtung.**

> **Wichtige Statuskorrektur:** Die vorhandenen Dateien 01–08 sind überwiegend
> verdichtete Wissensfassungen. Sie gelten deshalb trotz früherem Seitengegencheck
> **nicht als vollständig transkribiert** und werden nun durch Vollfassungen ersetzt.

---

## 1. Quelle

- Datei: `737639872-Rogue-Trader-Core-Rulebook.pdf`
- 408 PDF-Seiten, **reines Scan-PDF ohne Textebene** (227 MB)
- **Seiten-Offset: PDF-Seite = Buchseite + 4** (Buchseite 1 = PDF-Seite 5)

---

## 2. Technisches Setup (in neuer Session ggf. neu erzeugen)

Das PDF hat keine Textebene und ist zu groß (>100 MB) für das direkte Lesen mit dem
Read-Tool. Auf diesem Rechner sind **kein Python, kein Tesseract, kein Poppler
(außer `pdftotext`), kein Ghostscript und kein ImageMagick** vorhanden — aber
**Node.js** ist installiert. Funktionierender Weg:

1. Ins Scratchpad wechseln, `npm init -y` und `npm install pdf-lib`.
2. `split.mjs` zerlegt das PDF in 20-Seiten-Chunks (Node mit `--max-old-space-size=8192`
   starten, sonst Heap-Fehler).
3. `extract.mjs` zieht aus jeder Seite das eingebettete JPEG heraus.
   Jede Buchseite ist genau **ein DCTDecode-Bild**, ca. 1230 × 1620 px — gut lesbar.
4. Die Einzelbilder heißen `page001_0.jpg` … `page408_0.jpg` und werden mit dem
   Read-Tool als Bilder gelesen und ausgewertet.

### OCR-Rohtext für den Restbestand

Am 16.08.2026 wurde für **alle PDF-Seiten 113–408** zusätzlich lokaler OCR-Rohtext
erzeugt. Grundlage ist die in Windows integrierte `Windows.Media.Ocr`-Engine; das
Hilfsskript liegt unter `tools/ocr-pages.ps1`, die seitenweisen Zwischenergebnisse
unter `tmp/ocr/page113.txt` bis `tmp/ocr/page408.txt`.

- Seitenbilder insgesamt geprüft: **408/408 vorhanden**
- Fehlende Bilder im Restbereich 113–408: **0**
- OCR-Rohtexte im Restbereich: **296/296 erzeugt**
- Der OCR-Text ist nur Arbeitshilfe. Tabellenwerte, Würfelnotationen, Boni/Mali,
  Actions und schwer lesbare Eigennamen werden weiterhin am Seitenbild geprüft.

### Vollständiger Gegencheck (begonnen am 16.08.2026)

Auf Nutzerwunsch werden **sämtliche 408 PDF-Seiten** gegen die Scanbilder geprüft.
Der technische Vorbereitungsschritt ist abgeschlossen:

- OCR-Rohtext für **PDF-Seiten 1–408 vollständig: 408/408**
- Fehlende OCR-Seiten im Prüfbereich: **0**
- Prüfbereich umfasst Umschlag/Titelei, Inhaltsverzeichnis, Einleitung, Kapitel I–XV,
  Index, Charakterbogen und Rückseiten
- zusätzliche Navigationskontrolle anhand aller **20 PDF-Lesezeichen**; die separat
  geführten Punkte **Traits**, **Mutations** und **Allies, Enemies & Rivals** werden
  innerhalb von Kapitel XIV jeweils eigenständig abgehakt
- Vorgehen je Kapitel: Seiteninventar → Tabellen-/Zahlenvergleich → visuelle Kontrolle
  kritischer Stellen → Korrekturen → eigener Prüfeintrag in dieser Datei
- Die bisherigen Statusangaben „fertig“ bedeuten bis zum jeweiligen Prüfeintrag noch
  **inhaltlich erfasst**, nicht bereits vollständig gegengeprüft. Der Gegencheck ist
  erst abgeschlossen, wenn die Gesamtabdeckung **408/408** bestätigt wurde.
- Aktuell visuell gegengeprüft: **PDF 1–112 = 112/408**
- Aktuell nach der neuen Vorgabe vollständig und ungekürzt transkribiert: **0/408**
- Dateistruktur nach allen PDF-Lesezeichen angelegt: **20/20 Dateien**
- PDF-Outlines technisch ausgelesen und alle Seiten eindeutig den 20 Dateien
  zugeordnet: **408/408 Seiten zugeordnet**

### Verbindliche lückenlose Seitenpartition

`Foreword` 1–14; `Chapter 1` 15–38; `Chapter 2` 39–76; `Chapter 3` 77–92;
`Chapter 4` 93–112; `Chapter 5` 113–156; `Chapter 6` 157–176;
`Chapter 7` 177–190; `Chapter 8` 191–232; `Chapter 9` 233–288;
`Chapter 10` 289–304; `Chapter 11` 305–322; `Chapter 12` 323–338;
`Chapter 13` 339–366; `Chapter 14` 367; `Traits` 368–372; `Mutations` 373;
`Allies, Enemies & Rivals` 374–382; `Chapter 15` 383–396; `Index` 397–408.

Die vor dem ersten Bookmark liegenden Seiten 1–9 gehören zur `Foreword`-Datei.
Kapiteltrenntitel liegen jeweils eine Seite vor dem technischen Bookmark-Ziel und
gehören zur entsprechenden Kapiteldatei. Die nach dem Index liegenden unmarkierten
Schlussseiten bleiben in `16-Index.md` enthalten.

### Verbindliche Dateiabbildung der 20 PDF-Lesezeichen

| PDF-Lesezeichen | Markdown-Datei |
|---|---|
| Foreword | `00-Foreword.md` |
| Chapter 1 - Character Creation | `01-Charaktererschaffung.md` |
| Chapter 2 - Career Paths | `02-Karrierewege.md` |
| Chapter 3 - Skills | `03-Skills.md` |
| Chapter 4 - Talents | `04-Talents.md` |
| Chapter 5 - Armoury | `05-Armoury.md` |
| Chapter 6 - Psychic Powers | `06-Psychic-Powers.md` |
| Chapter 7 - Navigators | `07-Navigator-Powers.md` |
| Chapter 8 - Starships | `08-Starships.md` |
| Chapter 9 - Playing The Game | `09-Playing-The-Game.md` |
| Chapter 10 - The Game Master | `10-The-Game-Master.md` |
| Chapter 11 - The Imperium | `11-The-Imperium.md` |
| Chapter 12 - Rogue Traders | `12-Rogue-Traders.md` |
| Chapter 13 - The Koronus Expanse | `13-The-Koronus-Expanse.md` |
| Chapter 14 - Adversaries & Aliens | `14-Adversaries-and-Aliens.md` |
| Traits | `14-Traits.md` |
| Mutations | `14-Mutations.md` |
| Allies, Enemies & Rivals | `14-Allies-Enemies-and-Rivals.md` |
| Chapter 15 - Into The Maw | `15-Into-The-Maw.md` |
| Index | `16-Index.md` |

`00-FORTSCHRITT.md` und `00-Inhaltsverzeichnis-und-Einleitung.md` sind reine
Arbeits-/Kontrolldateien und zählen nicht zu diesen 20 Inhaltsdateien.

Scratchpad-Pfad der bisherigen Session:
`C:\Users\NIKOLA~1\AppData\Local\Temp\claude\C--Prv-pnp-Rouge-Traider-Character-sheet\5edf0e7f-13aa-4d56-acd9-5c6c854c4d74\scratchpad`
mit den Unterordnern `chunks\` und `img\`.
**Achtung:** Das Scratchpad ist session-spezifisch und kann gelöscht sein — dann
Schritte 1–3 wiederholen.

### split.mjs (Kern)
```js
import { PDFDocument } from 'pdf-lib';
// PDF laden, in 20er-Blöcke kopieren, als p001-020.pdf usw. speichern
```

### extract.mjs (Kern)
```js
// pro Seite: page.node.Resources() -> XObject -> PDFRawStream mit Subtype /Image
// Filter /DCTDecode -> stream.getContents() direkt als .jpg schreiben
```

---

## 3. Kapitelübersicht des Buches

| Kapitel | Titel | Buchseiten | PDF-Seiten | Status |
|---|---|---|---|---|
| — | Umschlag / Karte / Titelei / Inhaltsverzeichnis / Einleitung | – / 1–11 | 1–15 | visuell geprüft; Volltranskription offen |
| I | Character Creation | 12–34 | 16–38 | visuell geprüft; Volltranskription offen |
| II | Career Paths | 35–72 | 39–76 | visuell geprüft; Volltranskription offen |
| III | Skills | 73–88 | 77–92 | visuell geprüft; Volltranskription offen |
| IV | Talents | 89–108 | 93–112 | visuell geprüft; Volltranskription offen |
| V | Armoury | 109–152 | 113–156 | verdichtete Arbeitsfassung; Volltranskription offen |
| VI | Psychic Powers | 153–172 | 157–176 | verdichtete Arbeitsfassung; Volltranskription offen |
| VII | Navigator Powers | 173–186 | 177–190 | verdichtete Arbeitsfassung; Volltranskription offen |
| VIII | Starships | 187–228 | 191–232 | verdichtete Arbeitsfassung; Volltranskription offen |
| IX | Playing the Game | 229–284 | 233–288 | offen |
| X | The Game Master | 285–300 | 289–304 | offen |
| XI | The Imperium | 301–318 | 305–322 | offen |
| XII | Rogue Traders | 319–334 | 323–338 | offen |
| XIII | The Koronus Expanse | 335–362 | 339–366 | offen |
| XIV | Adversaries & Aliens | 363–378 | 367–382 | offen |
| XV | Into the Maw | 379–393 | 383–397 | offen |
| — | Index / Charakterbogen / Rückseite | 394–404 | 398–408 | offen |

> Die Seitenbereiche ab Kapitel V wurden am 16.08.2026 anhand der tatsächlichen Kapitel-
> und Trenntitelseiten im vollständigen OCR-/Bildbestand 113–408 korrigiert.

---

## 4. Detaillierter Stand pro Datei

### `00-Inhaltsverzeichnis-und-Einleitung.md` — PDF 1–15 — **vollständig gegengeprüft**
- Alle 15 Seiten einzeln am Seitenbild kontrolliert
- vollständiges gedrucktes Inhaltsverzeichnis mit sämtlichen Kapitel- und
  Unterkapiteleinträgen sowie Buchseiten übernommen
- vollständige PDF-Lesezeichenstruktur mit allen 20 Einträgen ergänzt; Abweichung
  zwischen PDF-Navigation und gedruckter Kapitel-XIV-Hierarchie dokumentiert
- Frontcover, Doppelseitenkarte, Werbeseite, Innentitel, Credits, Foreword,
  Setting-Prolog, Einleitung und Kapitel-I-Trenntitel im Seiteninventar zugeordnet
- bibliografische Kerndaten und Karten-Großräume erfasst
- Rollenspielrollen, benötigtes Spielmaterial und alle Game-Dice-Regeln erfasst
- Table A-1 vollständig und visuell geprüft
- Gegencheck-Abdeckung: **PDF 1–15 = 15/15 Seiten**

### `01-Charaktererschaffung.md` — Kapitel I, PDF 16–38 (Buch 12–34) — **vollständig gegengeprüft**
- Ablauf Stages 1–7, die neun Characteristics + Characteristic Bonus
- Würfelmethode (2d10+25, ein Reroll) und Punktverteilungs-Alternative
- Origin Path: Regeln, Intersections, GM-Optionen, doppelte Ergebnisse
- Origin Path Chart komplett (alle 6 Zeilen)
- Alle 6 **Home Worlds** mit Modifikatoren, Skills, Traits, Wounds, Fate Points
- Table 1-1 Suggested Home Worlds
- **Birthright**, **Lure of the Void** (alle 3 Unterwahlen je Option),
  **Trials and Travails**, **Motivation**
- Table 1-2 Heirloom Items (1d100)
- XP-Regeln (4.500 + 500 = 5.000), Verhältnis zu Dark Heresy
- Table 1-5 Starting Profit Factor and Ship Points
- Ausrüstungswahl (eine Acquisition, Modifier +0)
- Tables 1-3 / 1-4 mit allen männlichen und weiblichen Beispielnamen vollständig
- alle sechs Nature-Leitfragen und alle neun vorgeschlagenen Demeanours
- unnummerierte Characteristic-Beispieltabelle von Buchseite 14
- Seiteninventar für PDF 16–38; **23/23 Seiten** einzeln am Scanbild kontrolliert
- Gegencheck-Korrekturen: Mutations-Auswahlbereich eindeutig auf 01–75 gefasst;
  zuvor fehlende Namenstabellen und Nature-Angaben ergänzt

### `02-Karrierewege.md` — Kapitel II, PDF 39–76 (Buch 35–72) — **vollständig gegengeprüft**
- Advance-Grundregeln, 4 Stufen der Characteristic Advances (kumulative Kosten)
- Table 2-1 Careers, Table 2-2 Ranks (XP-Schwellen 5.000–34.999)
- Kaufvorgang, Multiplikatoren, Prerequisites, ~500 xp pro Sitzung
- Elite Advances (Grundkosten 500 xp), eigene Career Paths
- **Alle 8 Careers vollständig**: Rogue Trader, Arch-militant, Astropath Transcendent,
  Explorator, Missionary, Navigator, Seneschal, Void-master
  — je mit Beschreibung, Starting Skills/Talents/Gear,
    Characteristic-Advance-Kostentabelle und **allen Rank-1-bis-8-Advance-Tabellen**
- Special Abilities aller 8 Careers (Buchseite 72)
- vollständiges Seiteninventar einschließlich Kapitel-II-Trenntitel
- alle 38 Seiten einzeln am Scanbild kontrolliert; Characteristic-Advance-Tabellen,
  sämtliche 64 Rank-Tabellen, Starting Skills/Talents/Gear und Special Abilities
  mit dem Original abgeglichen
- Grenzkorrektur: PDF-Seite 77 ist bereits der Kapitel-III-Trenntitel und wird dort
  geprüft; Gegencheck-Abdeckung Kapitel II: **PDF 39–76 = 38/38 Seiten**

### `03-Skills.md` — Kapitel III, PDF 77–92 (Buch 73–88) — **vollständig gegengeprüft**
- Gaining Skills, Training und Skill Mastery (+10 / +20, max. 3×)
- Basic vs. Advanced Skills, Advanced als Basic behandeln
- **Table 3-1** komplett (alle 48 Skills mit Typ, Characteristic, Descriptor)
- Skill Descriptors (Crafting, Exploration, Interaction, Investigation, Movement, Operator)
- Skill Groups
- **Alle Skill-Beschreibungen** von Acrobatics bis Wrangling, inklusive aller
  Special Uses (Disengage, Jump & Leap, Inspire, Con, Escape Bonds/Grapple,
  Squeeze Through, Manufacture/Place/Defuse Explosives, First Aid, Extended Care,
  Diagnose, Charming/Enthralling Performance, Astropathic Interference,
  Hunt for Sedition, Inspection, Security Systems)
- Alle Skill-Group-Spezialisierungen ausgeschrieben: Common Lore (14), Forbidden Lore (11),
  Scholastic Lore (16), Ciphers (5), Secret Tongue (7), Speak Language (7),
  Trade (13), Navigation (3), Pilot (3), Drive (3), Performer (4)
- vollständiges Seiteninventar einschließlich Kapitel-III-Trenntitel; **16/16 Seiten**
  einzeln am Scanbild kontrolliert
- Gegencheck-Korrekturen: Quellenbereich auf PDF 77–92 berichtigt; falsches
  Skill-Group-Zeichen bei Tech-Use aus Table 3-1 entfernt
- gedruckte Trade-Inkonsistenz festgehalten: Trader steht in der Gruppenzeile ohne
  Einzelbeschreibung, Scrimshawer besitzt eine Einzelbeschreibung ohne Eintrag in
  der Gruppenzeile

### `04-Talents.md` — Kapitel IV, PDF 93–112 (Buch 89–108) — **vollständig gegengeprüft**
- Grundlagen: Talents vs. Skills, Gaining Talents
- Talent Groups inkl. „Universal"-Gruppe, Talent Prerequisites
- **Table 4-1 komplett**: alle Talents mit Voraussetzung und Kurznutzen
  (Air of Authority bis Wrath of the Righteous)
- **Alle ausführlichen Talent-Beschreibungen** von Air of Authority bis Wrath of the Righteous
- Sämtliche Voraussetzungen, Talent Groups, Aktionsarten, Boni, Reichweiten und Sonderregeln
- Korrigierter Kapitelumfang: Kapitel IV endet auf Buchseite 108, nicht 120
- vollständiges Seiteninventar; **20/20 Seiten** einzeln am Scanbild kontrolliert
- gedruckte Widersprüche bei den Voraussetzungen von Master Enginseer und Whispers
  ausdrücklich mit Tabellen- und Detailtextfassung dokumentiert

### `05-Armoury.md` — Kapitel V, PDF 113–156 (Buch 109–152) — **fertig**
- Availability und Technology; Table 5-1 vollständig
- Availability and Time; Table 5-2 vollständig
- Craftsmanship und Table 5-3 vollständig
- Wealth, Profit Factor und Ammunition-Grundlagen
- Weapon-Klassen, Profilwerte und Weapon Craftsmanship
- Alle Weapon Special Qualities von Accurate bis Unwieldy
- Table 5-4 vollständig; alle regelrelevanten Ergänzungen der Einzelbeschreibungen
- Tables 5-5 bis 5-8: Hallucinogen Effects, Grenades/Missiles, Exotic und Melee Weapons
- Table 5-9 und alle Weapon Upgrades mit Effekten und zulässigen Waffengruppen
- Tables 5-10/5-11: Standard- und Unusual Ammunition mit allen Sonderwirkungen
- Armour Craftsmanship, Mixing Armour, Primitive/Flak/Power Armour und Table 5-12
- Gear, Drugs/Consumables und Tools: Tables 5-13 bis 5-15 samt regelrelevanten Effekten
- Cybernetics: Table 5-16, Craftsmanship, alle Implantatwirkungen und Implantation
- *Bewusst verdichtet:* reine Herkunfts-, Aussehens- und Nutzer-Flavourtexte einzelner Waffen

### `06-Psychic-Powers.md` — Kapitel VI, PDF 157–176 (Buch 153–172) — **fertig**
- Psyker-Typen, Starting Psy Rating, Discipline Mastery und Soul Binding
- Fettered, Unfettered und Push; Focus Power, Range, Line of Sight und Multiple Powers
- Tables 6-1 bis 6-3 vollständig, einschließlich aller Psychic Phenomena und Perils
- Telepathy: Thought Sending, Astral Telepathy, Communication und Domination Techniques
- Tables 6-4 bis 6-8, Astro-telepathic Signals, Mind Probe und Reprogram
- Divination mit Aura Reading, allen Techniques und Tables 6-9 bis 6-14
- Telekinesis mit Mind over Matter und allen Techniques aus Table 6-15
- Konvertierungsregeln zu Dark Heresy
- *Bewusst verdichtet:* historischer und atmosphärischer Psyker-Flavour

### `07-Navigator-Powers.md` — Kapitel VII, PDF 177–190 (Buch 173–186) — **fertig**
- Navigator Gene, Warp Eye, Great Houses und regeltechnischer Psyker-Status
- alle vier Lineages mit vollständigen Vor- und Nachteilen sowie Initial Mutations
- Gaining Navigator Powers, Mastery-Stufen und allgemeine Nutzungsregeln
- alle neun Navigator Powers jeweils auf Novice, Adept und Master
- Mutation Test und Table 7-1 mit allen zwölf Navigator Mutations
- fünf Stages der Warp Navigation einschließlich Astronomican und Off Course
- Tables 7-2 bis 7-4: Passage Durations, Navigation Chart und Warp Encounters
- Gellar Field Failures und Verhältnis von Warp- zu Realspace-Zeit
- *Bewusst verdichtet:* House-Geschichte und atmosphärischer Navigator-Flavour

### `08-Starships.md` — Kapitel VIII, PDF 191–232 (Buch 187–228) — **fertig**
- Starship Characteristics, Essential/Supplemental Components und Bauablauf
- alle acht spielbaren Hulls mit vollständigen Baseline Characteristics und Weapon Capacity
- Table 8-3 Essential Components mit Power, Space und SP
- Weapon-, Cargo-, Enhancement- und Facility-Components aus Tables 8-4/8-5
- Archeotech und Xeno-tech aus Tables 8-6/8-7 sowie Kernwirkungen
- Table 8-8 Availability und Regeln für SP, Acquisitions und Retrofitting
- Tables 8-1/8-2 vollständig: Machine Spirit Oddities und Past Histories
- NPC/Quick-start Vessels: Wolfpack, Onslaught, Wayfarer Station und Sabre
- Strategic Rounds, NPC Crew Ratings und Manoeuvre/Extended Actions, Tables 8-9 bis 8-11
- Ramming, Boarding, Stern Chase, Silent Running und Starship Weapon Resolution
- Void Shields, Turrets, Damage, Critical Hits und Catastrophic Damage, Table 8-12
- Crew Population/Morale samt Mutiny, Tables 8-13/8-14
- Zero Gravity, Celestial Hazards, Repairs und Langzeitbetrieb
- *Bewusst verdichtet:* Shipboard-Flavour und ausgeschmückte NPC-Schiffshistorien

---

## 5. Nächster Schritt

**PDF-Seiten 113–156 (Buchseiten 109–152)** — Kapitel V vollständig gegenprüfen und
erkannte Abweichungen in `05-Armoury.md` korrigieren. Anschließend Kapitel VI–VIII
gegenprüfen und danach die noch fehlenden Kapitel IX–XV sowie Index,
Charakterbogen und Rückseiten erfassen.

---

## 6. Arbeitsweise / Konventionen

- Inhalte werden **ausschließlich** aus dem Regelbuch übernommen, kein Zusatzwissen.
- Fließtext auf Deutsch, **Regelbegriffe bleiben Englisch** (Weapon Skill, Fate Point,
  Degrees of Success …), damit sie mit dem Buch und dem Charakterbogen zusammenpassen.
- Werte, Tabellen, Voraussetzungen und Kosten werden **1:1** übernommen.
- Buchseitenverweise aus dem Original (z. B. „S. 271") bleiben erhalten.
- Sämtliche Seiten erhalten eine dokumentierte Zuordnung. Regelwerte, Tabellen,
  Definitionen, Schauplätze, Fraktionen, Profile und andere Nachschlagedaten werden
  übernommen; erzählerischer Fließtext darf sinngemäß verdichtet werden.
