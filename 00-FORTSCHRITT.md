# Fortschritt der Wissensdatenbank

> Diese Datei dokumentiert, welche Seiten des Regelbuchs bereits ausgewertet wurden,
> damit die Arbeit in einer neuen Session nahtlos fortgesetzt werden kann.
> **Letzte Aktualisierung: Kapitel VIII (PDF 191–232) Seite für Seite gegengeprüft — 42/42 Seiten,
> Methode Fließtext per OCR + Zahlentabellen per Bild. Das mit Abstand fehlerreichste Kapitel
> bisher: mehrere falsche Zahlenwerte (Warpsbane Hull, Ryza Plasma Battery Power, Shard Cannon/
> Micro Laser Defence Grid/Gravity Sails, Default-Manoeuvre-Drehwinkel), 2 komplett fehlende
> Components (Ghost Field, Runecaster) sowie sehr viele auf einen Satz verdichtete Subsysteme
> (Weapon-Combat-Stats, Supplemental-Component-Effekte, Boarding/Ramming/Stern-Chase-Mechanik,
> Extended Actions, Crippled Ships, Depressurisation/Fire, Replenishing Morale/Crew Population,
> Gravity Tides/Ice Rings/Nebulae) in `08-Starships.md` korrigiert bzw. ausgebaut
> (Details siehe Abschnitt 4d). Kapitel V, VI, VII zuvor bereits vollständig gegengeprüft
> (Details Abschnitte 4a/4b/4c). Gesamt visuell/OCR-gegengeprüft: PDF 1–232 = 232/408.**

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
- Aktuell visuell gegengeprüft: **PDF 1–232 = 232/408**
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
| — | Umschlag / Karte / Titelei / Inhaltsverzeichnis / Einleitung | – / 1–11 | 1–15 | visuell geprüft; Seiteninventar/TOC vollständig, **Foreword-Fließtext nun in `00-Foreword.md` ersterfasst** |
| I | Character Creation | 12–34 | 16–38 | **vollständig gegengeprüft** (siehe Abschnitt 4, `01-Charaktererschaffung.md`) |
| II | Career Paths | 35–72 | 39–76 | **vollständig gegengeprüft** (siehe Abschnitt 4, `02-Karrierewege.md`) |
| III | Skills | 73–88 | 77–92 | **vollständig gegengeprüft** (Volltranskription; alle Skills/Groups/Special Uses bestätigt) |
| IV | Talents | 89–108 | 93–112 | **vollständig gegengeprüft** (Volltranskription; alle Talents/Prerequisites/Details bestätigt) |
| V | Armoury | 109–152 | 113–156 | **vollständig gegengeprüft** (verdichtet; alle Werte/Regeln bestätigt oder korrigiert) |
| VI | Psychic Powers | 153–172 | 157–176 | **vollständig gegengeprüft** (verdichtet; alle Werte/Regeln bestätigt oder korrigiert) |
| VII | Navigator Powers | 173–186 | 177–190 | **vollständig gegengeprüft** (verdichtet; alle Werte/Regeln bestätigt oder korrigiert) |
| VIII | Starships | 187–228 | 191–232 | **vollständig gegengeprüft** (verdichtet; alle Werte/Regeln bestätigt oder korrigiert) |
| IX | Playing the Game | 229–284 | 233–288 | **inhaltlich vollständig erfasst**, Critical-Effect-Tabellen (9-11 bis 9-26) zusätzlich **wortgetreu am Bild verifiziert** |
| X | The Game Master | 285–300 | 289–304 | **inhaltlich vollständig erfasst** (Ersttranskription, Flavour/GM-Ratschläge verdichtet) |
| XI | The Imperium | 301–318 | 305–322 | **inhaltlich vollständig erfasst** (reines Lore-Kapitel, kompakt als Faktenreferenz wiedergegeben) |
| XII | Rogue Traders | 319–334 | 323–338 | **inhaltlich vollständig erfasst** (reines Lore-Kapitel, kompakt als Faktenreferenz wiedergegeben) |
| XIII | The Koronus Expanse | 335–362 | 339–366 | **inhaltlich vollständig erfasst** (reines Lore-Kapitel, kompakt als Faktenreferenz wiedergegeben) |
| XIV | Adversaries & Aliens | 363–378 | 367–382 | **inhaltlich vollständig erfasst** (Traits/Mutations als Regelmechanik vollständig, Allies/Enemies/Rivals mit verdichtetem Flavour) |
| XV | Into the Maw | 379–393 | 383–396 | **inhaltlich vollständig erfasst** (Abenteuertext, NSC-Statblöcke vollständig, Beschreibungstext verdichtet) |
| — | Index / Charakterbogen / Rückseite | 394–404 | 398–408 | **inhaltlich erfasst** (`16-Index.md`: Index bewusst nur vermerkt statt transkribiert, Charakterbogen-Layout vollständig, Rückseiten-Werbematerial kurz zusammengefasst) |

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

### `05-Armoury.md` — Kapitel V, PDF 113–156 (Buch 109–152) — **vollständig gegengeprüft (44/44 Seiten)**
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
- **Gegencheck (siehe Log unter 4a) ergab:** 9 Zahlenfehler in Tabellen korrigiert (u. a. Belasco
  Dueling Pistol, Kroot Rifle (Melee), Shuriken Pistol, Manacles, Navis Prima, Launcher-Special-Spalte),
  1 komplett falsche Item-Beschreibung korrigiert (Grapplehawk war fälschlich als Grapnel-Zubehör
  beschrieben, ist tatsächlich ein fliegender Cyber-Familiar), 1 in der Wirkrichtung verdrehte Regel
  korrigiert (Utility-Mechadendrite-Räuchergefäß ist ein Nachteil, kein Bonus für den Träger), sowie
  rund 15 echte Regellücken geschlossen (u. a. Recharging Power Packs, Lascarbine/Shotgun-Pistol-
  Rückstoß, „When a Grenade Jams", Stun-/Virus-Grenade-Details, Graviton Gun, Digi-Weapon-Regel,
  Power-Sword-Mordian-/Ghost-Sword-+15-Parry, Ammo-„Used With"-Zuordnung, Bionic-Replacement-
  Sonderfälle, max. Mechadendrites = Toughness Bonus)

### `06-Psychic-Powers.md` — Kapitel VI, PDF 157–176 (Buch 153–172) — **vollständig gegengeprüft (20/20 Seiten)**
- Psyker-Typen, Starting Psy Rating, Discipline Mastery und Soul Binding
- Fettered, Unfettered und Push; Focus Power, Range, Line of Sight und Multiple Powers
- Tables 6-1 bis 6-3 vollständig, einschließlich aller Psychic Phenomena und Perils
- Telepathy: Thought Sending, Astral Telepathy, Communication und Domination Techniques
- Tables 6-4 bis 6-8, Astro-telepathic Signals, Mind Probe und Reprogram
- Divination mit Aura Reading, allen Techniques und Tables 6-9 bis 6-14
- Telekinesis mit Mind over Matter und allen Techniques aus Table 6-15
- Konvertierungsregeln zu Dark Heresy
- *Bewusst verdichtet:* historischer und atmosphärischer Psyker-Flavour
- **Gegencheck (siehe Log unter 4b) ergab:** 1 Zahlenfehler (Chronological Incontinence:
  fehlender `1d5`-Wert beim Toughness Damage), sowie mehrere echte Regellücken geschlossen:
  max. 3 Disciplines/Psy Rating 1+, Power-Scale-Regel (Effekte basieren auf Unfettered Strength),
  vollständige Prerequisites-Kette für Table 6-4 (Terrify/Mind Scan/Mental Bond/Psychic Scream),
  sowie ausführliche Detailregeln zu Puppet Master (physische/mentale Characteristics-Aufteilung,
  Tod-/Range-Break-Konsequenzen) und Reprogram (Fehlschlag-Konsequenz). Alle 15 Zahlentabellen
  (6-1 bis 6-15) wurden gegen die Seitenbilder geprüft und bis auf den einen Fehler bestätigt.

### `07-Navigator-Powers.md` — Kapitel VII, PDF 177–190 (Buch 173–186) — **vollständig gegengeprüft (14/14 Seiten)**
- Navigator Gene, Warp Eye, Great Houses und regeltechnischer Psyker-Status
- alle vier Lineages mit vollständigen Vor- und Nachteilen sowie Initial Mutations
- Gaining Navigator Powers, Mastery-Stufen und allgemeine Nutzungsregeln
- alle neun Navigator Powers jeweils auf Novice, Adept und Master
- Mutation Test und Table 7-1 mit allen dreizehn Navigator Mutations
- fünf Stages der Warp Navigation einschließlich Astronomican und Off Course
- Tables 7-2 bis 7-4: Passage Durations, Navigation Chart und Warp Encounters
- Gellar Field Failures und Verhältnis von Warp- zu Realspace-Zeit
- **Gegencheck (siehe Log unter 4c) ergab:** 1 Fehler behoben (Unchecked Mutation:
  „Challenging (-10)" → korrekt „Challenging (+0)", passend zur durchgängigen Namenskonvention
  der Difficulty-Stufen), sowie 1 echte Regellücke geschlossen („The Eye is Open" — Navigatoren
  erleiden keine Corruption Points durch Warp Shock). Alle neun Navigator Powers und alle vier
  Zahlentabellen (7-1 bis 7-4) wurden gegen die Seitenbilder geprüft und bis auf den einen Fehler
  wortgetreu bestätigt — insgesamt die sauberste Kapitelprüfung bisher.
- *Bewusst verdichtet:* House-Geschichte und atmosphärischer Navigator-Flavour

### `08-Starships.md` — Kapitel VIII, PDF 191–232 (Buch 187–228) — **vollständig gegengeprüft (42/42 Seiten)**
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
- **Gegencheck (siehe Log unter 4d) ergab: das mit Abstand fehlerreichste Kapitel bisher.**
  Fehler: Warpsbane Hull (komplett falsche Wirkung), Ryza Pattern Plasma Battery Power (8→7),
  Ancient Life Sustainer/Bridge of Antiquity/Teleportarium (fehlende Hull-Varianten bzw. SP-Fehler),
  Shard Cannon/Micro Laser Defence Grid/Gravity Sails (mehrere falsche P/S/SP-Werte), Default-
  Manoeuvre-Drehwinkel (pauschal 90° statt größenabhängig 90°/45°). Komplett fehlende Components:
  Ghost Field, Runecaster. Massive Lücken (jeweils von einem Satz auf vollständige Regeln
  ausgebaut): Combat-Stats (Strength/Damage/Crit/Range) für alle Weapon Components in Table 8-4,
  praktisch alle Supplemental-Component-Kerneffekte in Table 8-5, Crew-Rating-Wahl beim Bau,
  Ramming-Schadensformel, volle Boarding-Mechanik, Disengage-Detail, Stern-Chase-Vollmechanik,
  alle 14 Extended Actions in Table 8-11, Weapon-Arc-Zuordnung nach Mount, Crippled-Ships-Werte,
  Depressurisation/Fire-Mechanik, das komplette Subsystem „Replenishing Morale and Crew
  Population", sowie Gravity Tides/Ice Rings/Nebulae und die Deep-Void-Run-Vorratsregeln.

---

## 4a. Laufendes Gegencheck-Log Kapitel V (PDF 113–156)

Methode: Fließtext per OCR (`tmp/ocr/pageNNN.txt`), Zahlentabellen zusätzlich per Seitenbild.
Nach jeder geprüften Seite wird hier eine Zeile ergänzt.

| PDF-Seite | Buchseite | Ergebnis |
|---|---|---|
| 113 | — | Trenntitel, kein Text |
| 114 | 110 | ok |
| 115 | 111 | ok (Table 5-1, 5-2 bestätigt) |
| 116 | 112 | ok (Table 5-3 bestätigt) |
| 117 | 113 | ok |
| 118 | 114 | Fehler behoben: Range-Seitenverweis ergänzt (S. 247), RoF „—"-Hinweis ergänzt |
| 119 | 115 | Fehler behoben: Flame-Bonus fälschlich an „untrainierte Ziele" statt untrainierten Schützen gebunden |
| 120 | 116 | Ergänzt: Overheats (zufälliger Arm), Power Field (Damage/Pen im Profil enthalten) |
| 121 | 117 | Lücke geschlossen: Recharging Power Packs (Las) komplett ergänzt |
| 122 | 118 | Fehler behoben: Belasco Dueling Pistol Gewicht 1 → 1,5 kg (Table 5-4 sonst vollständig bestätigt) |
| 123 | 119 | Fehler behoben: 4× Special-Spalte bei Launchers „-" → „variiert"; Lücke: Lascarbine-Sonderregel ergänzt |
| 124 | 120 | Lücke geschlossen: Shotgun Pistol Rückstoß-Regel ergänzt |
| 125 | 121 | ok (Naval Pistol/Shotcannon bestätigt) |
| 126 | 122 | ok, reiner Flavour |
| 127 | 123 | ok (Plasma Maximal Mode bestätigt) |
| 128 | 124 | ok (Sling-mit-Grenade bestätigt) |
| 129 | 125 | ok (Hallucinogen-Regel bestätigt) |
| 130 | 126 | Lücken geschlossen: „When a Grenade Jams", Stun-Grenade-Regel ergänzt; Table 5-5 vollständig bestätigt |
| 131 | 127 | Lücke geschlossen: Virus-Grenade-Ausbreitungsmechanik ergänzt; Table 5-6 sonst vollständig bestätigt |
| 132 | 128 | Fehler behoben: Kroot Rifle (Melee) kg/Avail. → „-"; Shuriken Pistol 2 → 1,2 kg; Lücke: Graviton Gun-Wirkung, Digi-Weapon-Regel ergänzt |
| 133 | 129 | ok, reiner Flavour |
| 134 | 130 | Lücke geschlossen: Power Sword (Mordian) +15-Parry-Sonderbonus ergänzt |
| 135 | 131 | Lücke geschlossen: Ghost Sword +15-Parry-Sonderbonus ergänzt; Table 5-8 vollständig bestätigt |
| 136 | 132 | ok, reiner Flavour |
| 137 | 133 | ok (Table 5-9 vollständig bestätigt) |
| 138 | 134 | ok (alle Weapon-Upgrade-Beschreibungen bestätigt) |
| 139 | 135 | ok (Table 5-10, 5-11 bestätigt); Lücke geschlossen: „Used With"-Zuordnung Ammo ergänzt |
| 140 | 136 | ok (Table 5-11 Rest bestätigt) |
| 141 | 137 | ok (Armour-Craftsmanship, Mixing Armour bestätigt) |
| 142 | 138 | ok (Table 5-12 vollständig bestätigt, 20 Zeilen) |
| 143 | 139 | Fehler behoben: Power Armour „solange Energie" fälschlich ergänzt (Regel ist unbedingt); Helm-Ausnahme ergänzt |
| 144 | 140 | Präzisiert: Photo-visors (immun statt „schützt"), Rebreather (Unterwasser-Überleben ergänzt) |
| 145 | 141 | Fehler/Lücke behoben: Synskin-Ausnahme beim Tragen unter anderer Armour ergänzt (Power-Armour-Sonderfall); Void Suit (Selenite) und Frenzon/De-tox bestätigt |
| 146 | 142 | ok (Excessive Drug Use, Medikit, Obscura, Sacred Unguents, Table 5-14 bestätigt) |
| 147 | 143 | Fehler behoben: Table 5-15 Manacles und Navis Prima Gewicht „-" → 1 kg |
| 148 | 144 | Fehler behoben: Grapplehawk-Beschreibung war komplett falsch (kein Grapnel-Zubehör, sondern fliegender Cyber-Familiar) — korrigiert; Grapnel-Behelfswaffennutzung ergänzt |
| 149 | 145 | ok (Jump Pack, Magboots, Melta-bomb, Micro-bead, Multikey bestätigt) |
| 150 | 146 | Präzisiert: Renumeration Engine (Währungszähler statt „Glücksspiel"), Shipboard Emergency Kit (Inhalt detailliert ergänzt); Table-5-15-Werte bestätigt |
| 151 | 147 | Lücke geschlossen: Bionic-Replacement-Limbs-Regel um Bleeding-Ausnahme, tödlichen Critical-Effekt und Skill-Beschränkung erweitert; Stummer/Venom Ring/Vox Caster bestätigt |
| 152 | 148 | Lücke geschlossen: Max. Mechadendrites = Toughness Bonus ergänzt; Bionic Arm/Locomotion/Respiratory, Auger Array, Augmented Senses, Baleful Eye, Ballistic Mechadendrite bestätigt |
| 153 | 149 | ok (Bionic Heart, Calculus Logi Upgrade, Cortex Implants, Cranial Armour bestätigt) |
| 154 | 150 | ok (Cybernetic Senses, Locator Matrix, Manipulator/Medicae Mechadendrite, Memorance Implant, MIU bestätigt) |
| 155 | 151 | ok (MIU Weapon Interface, Optical Mechadendrite, Respiratory Filter, Scribe-tines, Subskin Armour, Synthetic Muscle Grafts bestätigt) |
| 156 | 152 | Fehler behoben: Utility-Mechadendrite-Räuchergefäß gab fälschlich einen Bonus für den Träger an — tatsächlich ist es ein Nachteil (andere finden ihn leichter per Geruch); Implantation-Regel und Voidskin/Volitor/Vox Implant bestätigt. **Kapitel V (PDF 113–156) Gegencheck vollständig: 44/44 Seiten.** |

---

## 4b. Laufendes Gegencheck-Log Kapitel VI (PDF 157–176)

Methode wie Kapitel V: Fließtext per OCR, Zahlentabellen zusätzlich per Seitenbild.

| PDF-Seite | Buchseite | Ergebnis |
|---|---|---|
| 157 | — | Trenntitel/Inhaltsübersicht, kein Regeltext |
| 158 | 154 | ok, reiner Flavour (Psyker-Typen: Astropaths) |
| 159 | 155 | ok, reiner Flavour (Sanctioned Psykers, Navigators, Latent Psykers) |
| 160 | 156 | ok, reiner Flavour (Renegades, Sorcerers, Scholastica Psykana, Xenos, Untouchables) |
| 161 | 157 | ok (Starting Psy Rating, Table 6-1 Psychic Strength, Push-Regeln, Focus Power bestätigt) |
| 162 | 158 | Lücke geschlossen: max. 3 Disciplines/Psy Rating 1+ ergänzt; Sustaining Multiple Powers, Range/LoS, Mehrere Ziele, Erkennen, Soul-Binding-Schutz bestätigt |
| 163 | 159 | Lücke geschlossen: Power-Scale-Regel (Effekte basieren auf Unfettered Strength) ergänzt; Discipline Mastery, Value/Prerequisites/Range-Spaltendefinitionen bestätigt |
| 164 | 160 | ok (Table 6-2 Psychic Phenomena vollständig bestätigt, alle 25 Zeilen korrekt) |
| 165 | 161 | Fehler behoben: Chronological Incontinence fehlender `1d5`-Wert beim Toughness Damage ergänzt; Table 6-3 Perils of the Warp sonst vollständig bestätigt (alle 19 Zeilen) |
| 166 | 162 | ok (Telepathy-Discipline-Grundregeln, Thought Sending, Astral Telepathy, Table 6-5 bestätigt) |
| 167 | 163 | ok (Table 6-5 vollständig bestätigt; Mind Link/Mind's Eye/Astropathic Relays bestätigt); Prerequisites-Sammlung begonnen |
| 168 | 164 | ok (Table 6-6 Mind Probe, Mind Scan, Psychic Scream bestätigt); Prerequisites-Sammlung fortgesetzt |
| 169 | 165 | Lücke geschlossen: Prerequisites-Kette für Table 6-4 (Terrify/Mind Scan/Mental Bond/Psychic Scream ← Mind Probe/Mind's Eye/Mind Link) ergänzt; Table 6-7 Domination Prerequisites nochmals bestätigt |
| 170 | 166 | Lücken geschlossen: Puppet Master (physische/mentale Characteristics-Aufteilung, Tod-/Range-Break-Konsequenzen) und Reprogram (Fehlschlag-Konsequenz) detailliert ergänzt; Table 6-8, Inspire bestätigt |
| 171 | 167 | ok (Sensory Deprivation, Major Reprogramming, Danger of Paradox bestätigt) |
| 172 | 168 | ok (Divination-Grundregeln, Aura Reading, Table 6-10 vollständig bestätigt); Table-6-9-Kopfzeile zu verwürfelt — Einzeltechniken werden auf Folgeseiten geprüft |
| 173 | 169 | ok (Foreshadow, In Harm's Way, Blessed by the Emperor, Divining the Future, Psycholocation, Tables 6-11/6-12 bestätigt — Table 6-9 damit vollständig verifiziert) |
| 174 | 170 | ok (Table 6-13/6-14, Psychometry, Walking the Path bestätigt) |
| 175 | 171 | ok (Telekinesis-Grundregeln, Mind over Matter, Precision Telekinesis, Force Bolt, Telekinetic Crush bestätigt) |
| 176 | 172 | ok (Telekinetic Weapon/Shield, Force Shards, Storm of Force, Dark-Heresy-Kompatibilität wortgetreu bestätigt). **Kapitel VI (PDF 157–176) Gegencheck vollständig: 20/20 Seiten.** |

---

## 4c. Laufendes Gegencheck-Log Kapitel VII (PDF 177–190)

Methode wie Kapitel V/VI: Fließtext per OCR, Zahlentabellen zusätzlich per Seitenbild.

| PDF-Seite | Buchseite | Ergebnis |
|---|---|---|
| 177 | — | Trenntitel/Inhaltsübersicht, kein Regeltext |
| 178 | 174 | ok, reiner Flavour (Einleitung, Navigator Gene, Warp Eye) |
| 179 | 175 | ok, reiner Flavour (Great Houses, Novator, Paternova) |
| 180 | 176 | ok (Nomadic Houses, Magisterial Houses vollständig bestätigt) |
| 181 | 177 | ok (Shrouded Houses vollständig bestätigt; Renegade Houses Beginn) |
| 182 | 178 | Fehler behoben: Unchecked Mutation „Challenging (-10)" → korrekt „Challenging (+0)"; Lücke geschlossen: „The Eye is Open" (Immunität gegen Corruption aus Warp Shock) ergänzt |
| 183 | 179 | ok (Standard Action, „Are Navigators Psykers?", A Cloud in the Warp, Foreshadowing, Gaze into the Abyss bestätigt) |
| 184 | 180 | ok (Held in My Gaze, The Course Untravelled, The Lidless Stare inkl. Avoiding a Navigator's Gaze bestätigt) |
| 185 | 181 | ok (Tides of Time and Space, Tracks in the Stars, Void Watcher bestätigt — alle 9 Navigator Powers damit vollständig verifiziert) |
| 186 | 182 | ok (Testing for Resisting Mutation, Table 7-1 vollständig bestätigt, alle 13 Zeilen korrekt) |
| 187 | 183 | ok (Stage One, Navigator's Estimate, Going Into the Unknown, Astronomican-Flavour bestätigt) |
| 188 | 184 | ok (Tables 7-2/7-3 vollständig bestätigt; Stage Two/Three, Gellar Field Failures Sidebar bestätigt) |
| 189 | 185 | ok (Stage Four Difficulty-Modifiers, Off Course, Encounters in the Warp bestätigt) |
| 190 | 186 | ok (Table 7-4 Rest, Stage Five bestätigt). **Kapitel VII (PDF 177–190) Gegencheck vollständig: 14/14 Seiten.** |

---

## 4d. Laufendes Gegencheck-Log Kapitel VIII (PDF 191–232)

Methode wie Kapitel V–VII: Fließtext per OCR, Zahlentabellen zusätzlich per Seitenbild.

| PDF-Seite | Buchseite | Ergebnis |
|---|---|---|
| 191 | — | Trenntitel/Inhaltsübersicht, kein Regeltext |
| 192 | 188 | ok, reiner Flavour (Einleitung, Leben an Bord) |
| 193 | 189 | ok, reiner Flavour (Bordgeräusche, Anatomie eines Starships); Characteristics-Liste bestätigt |
| 194 | 190 | ok, reiner Flavour (Hull-Grundlagen, Transports, Raiders) |
| 195 | 191 | ok, reiner Flavour (Frigates, Light Cruiser, Cruiser); Essential/Supplemental-Grundbegriffe bestätigt |
| 196 | 192 | Lücke geschlossen: Unterschied „exposed" (Component ohne Space, verwundbar) vs. `External`-Trait (kein Space, nur durch Critical Hit zerstörbar) präzisiert; Essential-Components-Liste bestätigt |
| 197 | 193 | Lücken geschlossen: Crew-Rating-Wahl beim Bau (Incompetent/Competent/Crack/Veteran gegen SP) und Regel zu dauerhaft verschobenem Crew-Population-/Morale-Maximum ergänzt |
| 198 | 194 | ok (Jericho-class Pilgrim Vessel und Vagabond-class Merchant Trader vollständig bestätigt, inkl. Cargo-Hauler-Regel) |
| 199 | 195 | ok (Hazeroth-class Privateer, Havoc-class Merchant Raider, Sword-class Frigate, Tempest-class Strike Frigate vollständig bestätigt) |
| 200 | 196 | ok (Dauntless-class Light Cruiser, Lunar-class Cruiser vollständig bestätigt — alle 8 Hulls zu 100 % korrekt) |
| 201 | 197 | ok (Table 8-1 Machine Spirit Oddities vollständig bestätigt, alle 10 Zeilen korrekt) |
| 202 | 198 | ok (Table 8-2 Past Histories vollständig bestätigt, alle 10 Zeilen korrekt) |
| 203 | 199 | Fehler behoben: Warpsbane Hull hatte falsche Wirkung („-10 auf Warp Travel Encounters" statt korrekt +10 Navigation + „zweimal würfeln, Navigator wählt" bei Table 7-4) |
| 204 | 200 | Lücken geschlossen: Kerneffekte für alle 5 Bridge-Typen (Command Bridge Critical-Vulnerability, Commerce Bridge +50 AP, Armoured Bridge 1d10/4+, Ship Master's Bridge +5/+10), M-1.r Life Sustainer (Stale Air -1 Morale) und Pressed-Crew Quarters (Cramped -2 Morale) ergänzt |
| 205 | 201 | ok (Table-8-3-Kopfzeile bestätigt; Auger-Array-External-Regel bestätigt) |
| 206 | 202 | **Großer Fund:** Table 8-4 fehlten komplett die Combat-Stats (Strength/Damage/Crit Rating/Range) für alle 8 Weapon Components — vollständig ergänzt. Dabei 1 Fehler behoben: Ryza Pattern Plasma Battery Power 8 → korrekt 7. Deep Void Auger Array Kerneffekt (+10 Detection) ergänzt |
| 207 | 203 | **Großer Fund (Fortsetzung):** Ryza-Vapourisation-Regel, sowie Kerneffekte für Cargo Hold/Compartmentalised Cargo Hold/Main Cargo Hold/Luxury Passenger Quarters/Barracks/Augmented Retro-thrusters/Reinforced Interior Bulkheads ergänzt (alle bisher ohne jeden Effekt in der Tabelle) |
| 208 | 204 | ok (Table-8-5/8-6/8-7-Kopfzeilen bestätigt) |
| 209 | 205 | Lücken geschlossen: Crew Reclamation Facility, Extended Supply Vaults, Munitorium (inkl. Volatile-Explosionsregel), Temple-shrine, Librarium Vault Kerneffekte ergänzt |
| 210 | 206 | Lücken geschlossen: Trophy Room und Observation Dome Kerneffekte ergänzt; Murder-servitors in Tabelle verschoben; Ancient Life Sustainer bestätigt |
| 211 | 207 | **Großer Fund:** Xeno-tech-Component „Ghost Field" fehlte komplett; Bridge of Antiquity/Auto-stabilised Logis-targeter/Teleportarium-Details bestätigt |
| 212 | 208 | **Großer Fund (Fortsetzung):** Table 8-6 fehlten 2 Drive-Zeilen (Jovian Class 1/2) und die zweite Bridge-of-Antiquity-Zeile; Teleportarium-SP-Fehler (2→1) behoben. Table 8-7 mehrfach fehlerhaft: Shard Cannon Power 2→0, Micro Laser Defence Grid Power/Space/SP komplett falsch (5/2/3→2/0/2), Gravity Sails SP 2→3 plus fehlende zweite Zeile; „Runecaster" komplett fehlend. Beide Tabellen vollständig neu aufgebaut inkl. aller Kerneffekte. Retrofitting-Zeitangabe (~3 Wochen, halbe Zeit bei Hive World) ergänzt |
| 213 | 209 | ok (Wolfpack Raider und Onslaught Ork Raider Statblöcke vollständig bestätigt) |
| 214 | 210 | Lücken geschlossen: Onslaught-Details (Armoured Kaptin's Bridge, Big Red Button, Stowage-Bays-Booty-Effekt) ergänzt; Wayfarer Station Statblock bestätigt |
| 215 | 211 | ok (Sabre-Statblock vollständig bestätigt) |
| 216 | 212 | Präzisiert: Initiative-Regel (feste Zehnerstelle statt „GM-Auslegung"), Actions-Struktur (Manoeuvre Pflicht, Shooting optional) ergänzt |
| 217 | 213 | Fehler behoben: Default-Manoeuvre-Drehung war pauschal 90° für alle Schiffe angegeben — korrekt: 90° nur für Transport/Raider/Frigate-Klasse, 45° für Light Cruiser/Cruiser. Lücke geschlossen: Surprise-Regel (+20 Angriffsbonus Round 1) ergänzt |
| 218 | 214 | ok (NPC-Actions-Regel, Table 8-9, Adjust Bearing/Speed/Speed&Bearing, Come to New Heading, Disengage-Beginn bestätigt) |
| 219 | 215 | **Großer Fund:** Ramming-Schadensformel (Ziel: Damage Die + eigene Prow Armour, ignoriert Shields; Rammer: gegnerische Armour + `1d5`), vollständige Boarding-Mechanik (Initiative-Sperre, Lösen-Test, Opposed-Command-Boni, Sieger-Optionen, Morale-Kapitulationswurf) und Disengage-Detail (Opposed gegen Detection+Scrutiny der Gegner, Waffensperre, kein Re-Entry, keine Stern-Chase-Einleitung) ergänzt. Stern-Chase-Vollmechanik (Exploration-Challenge-System) als riesige Lücke entdeckt, Sammlung begonnen |
| 220 | 216 | **Großer Fund (Fortsetzung):** Stern-Chase-DoS-Ziele je Schiffstyp (3/5/7) und alle Modifikatoren gesammelt; Emergency Repairs/Flank Speed/Focused Augury/Hail-the-Enemy-Details gesammelt |
| 221 | 217 | Table-8-10/8-11-Kopfzeilen bestätigt; Silent-Running-Regel und restliche Extended-Action-Details (Hit and Run, Hold Fast!, Jam Communications, Lock on Target, Prepare to Repel Boarders!, Put Your Backs Into It!, Triage) gesammelt |
| 222 | 218 | **Großer Fund abgeschlossen:** Alle 14 Extended Actions in Table 8-11 mit vollständigen Regeldetails ausgebaut (zuvor nur einzeilige, unpräzise Zweckangaben); vollständige Stern-Chase-Mechanik ergänzt (DoS-Ziele, Skills, Zeitkosten, umgekehrte Regeln als Verfolgte) |
| 223 | 219 | Lücken geschlossen: Weapon-Arc-Zuordnung nach Mount-Typ (Dorsal/Prow/Port/Starboard/Keel, inkl. Hull-Größen-Unterschied bei Prow) und Max-Range-Regel (2× Range) ergänzt |
| 224 | 220 | Lücken geschlossen: Turret-Command-Bonus (+10 bei Boarding), Range-Modifikatoren (±10), Lance-Hit-Verhältnis (pro 3 DoS statt 1), „max. 1 Critical bei kombinierter Salvo"-Regel, GM-Vereinfachung für NPC-Schiffszerstörung ergänzt |
| 225 | 221 | **Großer Fund:** Crippled-Ships-Regel war stark unterspezifiziert — konkrete Werte (-10 Manoeuvrability/Detection, Speed halbiert, Weapon Strength halbiert, automatischer Critical bei Damage über Armour) ergänzt; Wissen-über-Components-Regel für Criticals ergänzt; Beispielrechnung und Table-8-12-Flavourtexte bestätigt |
| 226 | 222 | ok (Table 8-12 Einzelbeschreibungen vollständig bestätigt gegen bereits vorhandene Zusammenfassung) |
| 227 | 223 | **Großer Fund:** Component-Zustände, Depressurisation- und Fire-Mechanik waren auf einen Satz verdichtet — vollständige Zahlenwerte (Population-/Morale-Schaden, Lösch-Regeln, Venting-Alternative, Ausbreitung) ergänzt |
| 228 | 224 | ok (Table 8-13/8-14, Zero Gravity bestätigt); Präzisiert: Morale-20-Schwelle erlaubt weiterhin Verteidigung gegen Boarding |
| 229 | 225 | ok (Mutiny-Regel inkl. Command/Charm/Intimidate-Optionen und Eskalationszyklus vollständig bestätigt, bereits korrekt in Datei) |
| 230 | 226 | **Großer Fund:** Komplettes Subsystem „Replenishing Morale and Crew Population" fehlte vollständig (AP-Bestechung, Ansprache, Hafenaufenthalt, reguläre Anwerbung, Press-Gangs, Gefängnis-Deal) — als neuer Abschnitt ergänzt |
| 231 | 227 | **Großer Fund:** Gravity Tides, Ice Rings und Nebulae waren komplett auf einen vagen Sammelsatz reduziert — alle drei Phänomene mit vollständigen Regeln (Tests, Schaden, Verzögerung, Auger-Malus) ergänzt; Asteroid-Field-Testschwierigkeit (Routine +10) ergänzt |
| 232 | 228 | **Großer Fund abgeschlossen:** Weary Machine Spirit, Deep-Void-Run-Vorratsregel (6-Monats-Grenze, Shipboard Sickness/Scurvy), eigenständige Starvation-Stufe, Extended Repairs (Wochen-Tech-Use-Akkumulation) und Repair-at-Port-Regeln (Acquisition -10 pro 5 HI, Tage pro Punkt) vollständig ergänzt; Stellar-Phenomena-Vereinfachung für Combat ergänzt. **Kapitel VIII (PDF 191–232) Gegencheck vollständig: 42/42 Seiten.** |

---

## 4e. Ersterfassung Kapitel IX (PDF 233–288)

Methode: Fließtext per OCR (`tmp/ocr/pageNNN.txt`), Zahlentabellen zusätzlich per Seitenbild
wo die OCR ambiguous war (Tables 9-5, 9-6, 9-9 explizit am Bild verifiziert). Anders als bei
V–VIII wurde hier **neu geschrieben statt gegengeprüft**, da `09-Playing-The-Game.md` zuvor
nur ein Platzhalter war.

| PDF-Seiten | Buchseiten | Ergebnis |
|---|---|---|
| 233–239 | 229–235 | Tests-Grundmechanik (Skill/Characteristic Tests, Tables 9-1/9-2), Degrees of Success/Failure, Extended Tests, Opposed Tests, Test Difficulty (Table 9-3), Assistance erfasst |
| 240–246 | 236–242 | The Role of Fate, Combat-Grundlagen (Narrative/Structured Time, Combat-Ablauf, Surprise, Actions-Übersicht Table 9-4), ausführliche Action-Beschreibungen (Aim bis Full Auto Burst) erfasst |
| 243 | 239 | Table 9-5 (Multiple Hits) per Bild verifiziert und korrigiert (nach Trefferzone des ersten Treffers indiziert, nicht linear) |
| 247–252 | 243–248 | Grappling-Actions, weitere Action-Beschreibungen (Guarded Attack bis Semi-Auto Burst), The Attack (5-Schritte-Prozess), Righteous Fury (Wortlaut präzisiert), Table 9-6 (Hit Locations, per Bild verifiziert) erfasst |
| 253–256 | 249–252 | Unarmed Combat, Grappling-Beginn, Two-Weapon Fighting, Cover (Table 9-7), weitere Combat Circumstances (Table 9-8), Table 9-9 (Target Size, per Bild verifiziert) erfasst |
| 257–259 | 253–255 | Injury-Grundlagen (Wounds/Damage, Critical Damage, Fatigue, Characteristic Damage, Table 9-10 Zero-Score-Effekte) erfasst |
| 256–263 | 252–259 | **Critical Effect Tables 9-11 bis 9-26** (Energy/Explosive/Impact/Rending × Arm/Body/Head/Leg) initial in kompakter Form erfasst, da OCR auf diesen Seiten stark durch Hintergrundgrafiken gestört war. **Am 18.08.2026 nachgeholt:** alle 16 Tabellen wortgetreu am Seitenbild (`page256_0.jpg`–`page263_0.jpg`) verifiziert und Zelle für Zelle als vollständige Markdown-Tabellen (Critical Damage 1–10+) neu eingepflegt — keine Verdichtung mehr, 1:1-Übersetzung des englischen Originaltexts |
| 264–266 | 260–262 | Conditions und Special Damage (Amputated Limbs, Blinded, Blood Loss, Deafened, Fire, Falling, Stunned, Suffocation, Unconsciousness, Useless Limbs, Vacuum) sowie Healing (Lightly/Heavily/Critically Damaged) erfasst |
| 267–268 | 263–264 | Exploration (Exploration Challenges, Table 9-27), Investigation (Table 9-28/9-29) erfasst |
| 269–273 | 265–269 | Movement (Table 9-30/9-31, Hurrying/Running/Forced Marching, Climbing, Jumping/Leaping, Swimming, Carrying/Lifting/Pushing Table 9-33, Lighting, Flying, Gravity-Effekte) erfasst |
| 274–280 | 270–276 | Profit Factor (Table 9-34), Acquisition (Tests, Modifiers Table 9-35, Starship-Komponenten Table 9-36/9-37/9-38, Upkeep Tests), Influence erfasst |
| 281–288 | 277–284 | Endeavours (Aufbau, Größenstufen, Table 9-39/9-40, Objective Themes) inkl. Beispiel-Endeavours (bewusst als Flavour verdichtet, nicht einzeln transkribiert), Misfortunes (Table 9-41/9-42) erfasst |

**Kapitel IX (PDF 233–288) inhaltlich vollständig erfasst: 56/56 Seiten.** Kein separater
Gegencheck-Durchlauf wie bei V–VIII (da Ersterfassung); die Critical-Effect-Tabellen (9-11
bis 9-26) sind als einziger Bereich explizit als bildbasiert nachzuprüfen markiert.

---

## 4f. Ersterfassung Kapitel X (PDF 289–304)

| PDF-Seiten | Buchseiten | Ergebnis |
|---|---|---|
| 289–294 | 285–290 | Rolle des GM, Grundlagen, Setting-Themen, Rogue-Trader-Dynastien, Rolle der Crew erfasst (reiner Flavour, verdichtet) |
| 295–296 | 291–292 | Rewards (XP Abstract/Detailed Method Table 10-1, Roleplaying Awards, Profit Factor Rewards, Game Rewards, Fate Points), Mass Combats (Detailed/Simple Method) erfasst |
| 297 | 293 | Interaction (Interaction Skills, Dispositions Table 10-2, Interaction und Gruppen) erfasst |
| 298–299 | 294–295 | Fear (Fear Tests, Table 10-3 Fear Test Difficulties, Table 10-4 Shock Table, Snapping Out of It) erfasst |
| 300–302 | 296–298 | Going Insane (Table 10-5 Insanity Track, Mental Trauma, Table 10-6 Mental Traumas, Disorders, Removing Insanity Points) erfasst |
| 303–304 | 299–300 | Corruption (Corruption Points, Moral Threats, Malignancy Test, Table 10-7 Corruption Track, Table 10-8 Malignancies, Mutation) erfasst |

**Kapitel X (PDF 289–304) inhaltlich vollständig erfasst: 16/16 Seiten.** GM-Ratschläge und
Setting-Flavour bewusst verdichtet; alle Zahlentabellen (10-1 bis 10-8) übernommen, einzelne
Zwischenwerte (Insanity/Corruption Track) ggf. noch bildbasiert zu verifizieren.

---

## 4g. Ersterfassung Kapitel XI (PDF 305–322)

| PDF-Seiten | Buchseiten | Ergebnis |
|---|---|---|
| 305–307 | 301–303 | Imperium-Überblick, Institutionen der Adeptus Terra (Administratum, Arbites, Astra Telepathica, Astartes, Custodes, Mechanicus), Adeptus Ministorum erfasst |
| 308–309 | — | Sektorkarte/Illustration und Flavourtext (Rogue-Trader-Ursprung, Calixis-Sektor-Geschichte), kein weiterer Regeltext |
| 310 | 304 | Imperial Guard, Officio Assassinorum, Inquisition, Imperium-im-Raum-Übersicht (Fringes, Halo Stars, Wilderness Space, Alien Worlds), Planetare Verwaltung erfasst |
| 311–312 | 305–306 | Planeten-Klassifikationen (Hive/Agri/Civilised/Dead/Death Worlds, Research Stations, Feudal/Forge Worlds) erfasst |
| 312–314 | 306–308 | Sprache (Low/High Gothic, Techna-Lingua), Kultur, Mutation, Abhumans, Kommunikation/Astropaths erfasst |
| 314–317 | 308–311 | Der Warp (Warp-Reisen, Astronomican, Zeitverschiebung, Warp-Navigation, Warp Gates/Portals, Warp-Kreaturen) erfasst |
| 317–320 | 311–314 | Crossing the Void, Segmentae Majoris, Sektoren/Sub-Sektoren, Stellar Fleets (Merchant/Civil-Fleet-Chartertypen) erfasst |
| 320–322 | 314–316 | Raumschiffe des Imperiums, Imperial-Navy-Rangfolge, Temporary Battlefleets, Enemies of the Imperium erfasst |

**Kapitel XI (PDF 305–322) inhaltlich vollständig erfasst: 18/18 Seiten.** Reines Lore-/
Hintergrundkapitel ohne Spielmechanik — bewusst als kompakte Faktenreferenz statt
wortgetreuer Fließtext-Übersetzung wiedergegeben.

---

## 4h. Ersterfassung Kapitel XII (PDF 323–338)

| PDF-Seiten | Buchseiten | Ergebnis |
|---|---|---|
| 323–325 | — /319–321 | Rogue-Trader-Grundlagen, Warrant of Trade (Wesen, Backing) erfasst |
| 325–329 | 321–325 | Wurzeln (Imperial Navy, Imperial Guard, Administratum, Merchants, Imperial Commanders, Inquisition), Vergabegründe (Military Service, Political Expediency, Self-Promotion, Virtual Exile) erfasst |
| 329–333 | 325–329 | Temperament-Typen (Scoundrel, Merchant Prince, Explorer, Missionary, Diplomat, Psychopath) erfasst |
| 333–338 | 329–334 | Trappings of Power, Conditions (Trooping the Colours, Punitive Strike, Settlement, Reclamation, Exploration), Lineage, Revocation/Forfeiture, Rewards erfasst |

**Kapitel XII (PDF 323–338) inhaltlich vollständig erfasst: 16/16 Seiten.** Reines Lore-Kapitel
ohne Spielmechanik; erzählerische Beispiel-Sidebars (Battle of Jade Reach u. a.) kompakt im
Fließtext erwähnt statt einzeln transkribiert.

---

## 4l. Ersterfassung Foreword und Index (PDF 1–14, 397–408)

Methode: Fließtext per OCR (`tmp/ocr/pageNNN.txt`), das für diese Randbereiche ebenfalls
vollständig vorhanden war. Beide Dateien waren zuvor reine Platzhalter.

**`00-Foreword.md` (PDF 1–14):** Seiten 1–4 (Cover, Doppelseitenkarte, Werbeseite) ohne
Fließtext. Das Seiteninventar sowie das gedruckte Inhaltsverzeichnis, die bibliografischen
Daten, Game Dice und Table A-1 bleiben wie zuvor in `00-Inhaltsverzeichnis-und-Einleitung.md`
und wurden hier nicht dupliziert. Neu und vollständig erfasst: das Vorwort von Alan Merrett
(Entstehungsgeschichte des Namens „Rogue Trader", Buchseite 2/PDF 10), eine Zusammenfassung
des Setting-Prologs (Buchseite 3/PDF 11 — aus Urheberrechtsgründen und wegen schlechter
OCR-Qualität nur inhaltlich wiedergegeben, nicht zitiert), der vollständige Einleitungsessay
„Ambition Knows No Bounds" samt „What is a roleplaying game?" und „What You Need to Play
Rogue Trader" (Buchseiten 4–5/PDF 12–13), sowie alle 15 gedruckten Kapitel-Kurzbeschreibungen
aus „What's in this Book?" (Buchseiten 5–6/PDF 13–14). **PDF 1–14 vollständig erfasst:
14/14 Seiten.**

**`16-Index.md` (PDF 397–408):** Der gedruckte alphabetische Sachindex (PDF 397–400,
Buchseiten 394–397) wurde bewusst **nicht** Eintrag für Eintrag übernommen — die Seiten-
verweise beziehen sich auf Buchseiten statt auf die neue Dateistruktur, und alle referenzierten
Inhalte stehen bereits in den Kapiteldateien 01–15. Stattdessen wurde der Charakterbogen
(PDF 401–402) vollständig als Feldliste erfasst (Characteristics, vollständige Skill-Liste
mit Governing Characteristics, Weapons-Tabelle, Armour-Trefferzonen-Diagramm mit
Prozentbereichen, Wounds/Fatigue/Corruption/Insanity/Fate-Points-Felder, Movement-Werte) —
relevant als Layout-Referenz für den projekteigenen Charakterbogen. Ein Rasterfeld auf
PDF 403 (Kreis-/Kästchensymbole ohne erkennbare OCR-Beschriftung) bleibt in seiner Funktion
ungeklärt, da kein Seitenbild mehr verfügbar war. PDF 404–408 enthalten keine Rogue-Trader-
Regelinhalte (Fremdwerbung für *Operation Tannhäuser*, Kartenfragment, Rückseiten-Klappentext)
und wurden nur knapp zusammengefasst. **PDF 397–408 vollständig erfasst: 12/12 Seiten.**

---

## 4k. Ersterfassung Kapitel XV (PDF 383–396)

Methode: Fließtext per OCR (`tmp/ocr/pageNNN.txt`); NSC-Statblöcke und Kernzahlen
(Achievement Points, Schwierigkeitsstufen, Distanzen, Flacker-Zyklus des Magoros-Sterns)
zusätzlich per Seitenbild verifiziert (Buchseiten 385, 387, 391, 392).

| PDF-Seiten | Buchseiten | Ergebnis |
|---|---|---|
| 383 | — | Trenntitel (Inhaltsübersicht des Kapitels) |
| 384–385 | 380–381 | Einleitung, „Legends and Lies" — vollständige Sage der Righteous Path (Lorcanus Ryn, Krystallian, Talisar) erfasst |
| 385–388 | 381–384 | Part One: Overview, Ankunft in Port Wander, An Ancient Message (Orbest Dray), Using-Endeavours-Sidebar (Endeavour-Wert 1500), A Botched Ambush (Lady Ash/Pyrexia/Armsmen, Gedränge-Regel, Swift Justice/Targos), NPC-Sidebars (Great-Grandfather, Orbest Dray, Hadarak Fel) erfasst |
| 388–389 | 384–385 | Interested Parties (Precept-Marshall Kyra Valkyran), Deciphering the Riddle (3 Wege nach Magoros), Objective „A Questionable Cargo", Leaving Port, NPC Lady Ash erfasst |
| 389–390 | 385–386 | Part Two: Overview, The Edge of the Storm, A Gathering of Wolves (Battleground, Penitent Traveller, Stygian Reavers, Leech-Mine), Open Void, Objective „Pilgrims in the Storm" erfasst |
| 391–393 | 387–389 | Part Three: Overview, Into the Expanse, Forgotten Magoros (alle 5 Himmelskörper), The Flickering Eye (102 Min./58 Sek. per Bild bestätigt), Magoros Minor, Magoros Prime/A Nest of Trouble/Orks (Bloody Skullz), Exploring-the-Magoros-System-Sidebar erfasst |
| 393–394 | 389–390 | A Lady in Trouble, A Universe Reflected (Star Mirror), Magoros Secondus, The Shard Halo, An Icy Grave (Wrack der Righteous Path, Hinterhalt, Brückenbeschreibung) erfasst |
| 394–395 | 390–391 | Battle on the Bridge, Battle in the Asteroids (Raumkampf-Sonderregeln im Asteroidenfeld), Conclusion erfasst |
| 396 | 392 | Rewards sowie alle drei NSC-Statblöcke (Hadarak Fel, Lady Ash, Pyrexia) per Bild verifiziert; 2 OCR-Fehler korrigiert (Pyrexia-Trait „Machine (4), Size (Scrawny)" statt zusammengezogen; Lady Ashs Bolt-Pistol-Schaden „I" statt Fehllesung „L") |

**Kapitel XV (PDF 383–396) inhaltlich vollständig erfasst: 14/14 Seiten.** Reiner
Vorlese-/Stimmungstext (Marktbeschreibungen, Atmosphäre) bewusst verdichtet; alle
Orte, NSC-Werte, Bedingungen, Schwierigkeitsstufen und Belohnungen vollständig
übernommen. Statblöcke der im Kapitel nur referenzierten NSCs (Orbest Dray/Voidfarer,
Armsmen/Oathsworn Bodyguard, Orks, Battle Servitors) liegen außerhalb des Kapitel-
Seitenbereichs in Kapitel XIV.

---

## 4j. Ersterfassung Kapitel XIV (PDF 367–382)

Methode: Bildbasiert (Seitenbilder `pageNNN_0.jpg` aus dem Scratchpad-Ordner
`img/`), da die Traits-, Mutations- und Statblock-Tabellen zahlenkritisch sind
und die OCR-Rohtexte auf diesen Seiten stark verrauscht waren. Alle 16 Seiten
wurden am Bild geprüft, nicht nur ausgewählte Tabellen. Kapitel XIV ist auf vier
separate Bookmark-Dateien aufgeteilt.

| PDF-Seiten | Buchseiten | Ergebnis |
|---|---|---|
| 367 | 363 | Trenntitel (Illustration, Kapitelname, gedruckte Inhaltsübersicht) — `14-Adversaries-and-Aliens.md` |
| 368–372 | 364–368 | Kapiteleinleitung, vollständige Trait-Einzelbeschreibungen (Auto-stabilised bis Warp Weapon), Sidebars „Trait: Mechanicus Implants" und „Explorator Abilities in Game Terms", Table 14-1 (Traits-Übersicht), Table 14-2 (Size) sowie die Mutations-Einleitung („Mutations"/„Gaining Mutations"/„Mutation") erfasst — `14-Traits.md` |
| 373 | 369 | Table 14-3: Mutations vollständig (alle 34 Zeilen, 01–05 bis 00) — `14-Mutations.md` |
| 374–378 | 370–374 | The Masses of Humanity (Colonist-Template mit Adept/Bloodskinner/Entertainer/Hired Gun/Scum/Voidfarer), Free Trader Captain, Mutant Outcast/Mutant Abomination, Navy Officer, Oathsworn Bodyguard, Renegade, Void Pirate Captain, Warp Witch erfasst — `14-Allies-Enemies-and-Rivals.md` |
| 379 | 375 | Servitors-Einleitung, Battle Servitor (Charron-Pattern), Grapplehawk (Falax-Pattern), Servitor Drone, Servo Skull erfasst |
| 380–382 | 376–378 | The Xenos (Eldar Corsair, Ork Freebooter, Kroot Mercenary), From Beyond (Warp Predator/Ebon Geist, Sidebar „The Daemon") erfasst |

**Kapitel XIV (PDF 367–382) inhaltlich vollständig erfasst: 16/16 Seiten, bildbasiert
geprüft.** Traits und Mutations sind reine Regelmechanik und wurden 1:1 ohne
Verdichtung übernommen (alle Werte, Boni, Sonderregeln, beide Zahlentabellen
14-1/14-2 sowie die Zufallstabelle 14-3). In Allies, Enemies & Rivals wurden alle
Statblock-Zahlenwerte (Characteristics, Wounds, Skills, Talents, Traits, Waffen-
und Rüstungsprofile, Gear) vollständig übernommen; nur die begleitenden
Flavourtext-Einleitungen zu den einzelnen Archetypen/Fraktionen wurden sinngemäß
verdichtet ins Deutsche übertragen.

---

## 4i. Ersterfassung Kapitel XIII (PDF 339–366)

Methode: Fließtext per OCR (`tmp/ocr/pageNNN.txt`). Da für dieses Kapitel kein session-
spezifisches Bild-Scratchpad mehr vorhanden war, wurde ausschließlich mit dem OCR-Rohtext
gearbeitet; die beiden Kartendoppelseiten (Buchseiten 338–339) enthalten keinen Fließtext und
sind daher noch bildbasiert zu verifizieren, falls exakte geografische Positionen benötigt werden.

| PDF-Seiten | Buchseiten | Ergebnis |
|---|---|---|
| 339 | — | Trenntitel mit Inhaltsübersicht des Kapitels |
| 340–341 | 336–337 | Kapiteleinleitung (Koronus Expanse als unerforschte Region jenseits des Calixis-Sektors) sowie „The Great Warp Storms of the Halo Margins" (Void Dancer's Roil, Screaming Vortex, Deathveil, Whispering Storm, the Maw) samt Sidebar zum Calixis-Sektor erfasst |
| 342–343 | 338–339 | Doppelseitige Sternkarte — reine Ortsnamen-Legende ohne Fließtext, alle lesbaren Namen und die Welt-Klassifikations-Legende als kompakte Liste übernommen; **noch bildbasiert zu verifizieren** |
| 344–345 | 340–341 | „Port Wander: Gateway to the Expanse" (Gründung 917.M40, Struktur der Station) sowie das Rubycon-II-System erfasst |
| 345–347 | 341–343 | „The Koronus Passage: The Maw" (Entdeckung durch Purity Lathimon, Abenicus, Mistaken Age), Stations of Passage (The Temple, Witch-Cursed World, Battleground, Hermitage), Furibundus und Footfall erfasst |
| 347–350 | 343–346 | „Winterscale's Realm" (Sebastian Winterscale, Thousand Charts, Blood and False Gold), Burnscour, Egarian Dominion, Jerazol, Foundling Worlds (Lost to the Storm, Cursed Endeavours) erfasst |
| 350–351 | 346–347 | Grace, Rain, Iniquity, Charnel Stars, Accursed Demesne (Stars and Courses Uncharted), Lathimon's Death, Processional of the Damned erfasst |
| 351–353 | 347–348 | Undred-Undred Teef (inkl. Flash Gitz, Tusk, Ork Freebooterz), Heathen Stars, Agusia erfasst — OCR auf diesen Seiten durch vermutlich zweispaltiges Layout stellenweise verschachtelt, Inhalt sinngemäß zugeordnet |
| 354–355 | 349–350 | Naduesh, Zayth, Raakata, Vaporius, „The Unbeholden Reaches" (Einleitung), Concanid erfasst |
| 355–357 | 350–352 | Illisk, Orn, Rifts of Hecaton, Melbethe, Far Corpse Stars, „Denizens of the Koronus Expanse" (Einleitung), The Ork Menace erfasst |
| 357–358 | 352–353 | Ork Freebooterz (ausführlich), Morgaash Kulgraz und Da Wurldbraka, The Stryxis erfasst |
| 359–361 | 354–356 | Die vier Chaos Gods (Khorne, Tzeentch, Slaanesh, Nurgle), Slaves to Darkness, Chaos Pirates and Renegades, Chaos Space Marines, Saynay Clan, Reavers of Karrad Vall, Followers of False Gods erfasst |
| 361–363 | 356–358 | „The Treacherous Eldar" (Webway-Sidebar, Outcasts from the Path), Predations of the Eldar (Children of Thorns, Crow Spirits, Ghost-Ship-Sidebar zur Whisper of Anaris), Rak'Gol Marauders (Beginn) erfasst |
| 363–365 | 358–360 | Disciples of Thule, Die Yu'vath, Halo Artefacts (inkl. The Transformed, The Risk and the Reward) erfasst |
| 365–366 | 360–362 | The Kroot, Rogue Traders Known Within the Expanse (Aspyce Chorda, Calligos Winterscale, Jonquin Saul, Wrath Umboldt, Tanak Valcetti), Lost Lineages of the Koronus Expanse (7 erloschene Linien) erfasst |

**Kapitel XIII (PDF 339–366) inhaltlich vollständig erfasst: 28/28 Seiten.** Reines Lore-Kapitel
ohne Spielmechanik und ohne Zahlentabellen mit Regelwerten — Fließtext bewusst verdichtet, alle
Ortsnamen, Fraktionen, Personen, Ereignisse und Klassifikationen vollständig übernommen. Die beiden
Kartendoppelseiten (Buchseiten 338–339) bleiben als einziger Bereich noch bildbasiert zu
verifizieren.

---

## 4n. Statuskorrektur Kapitel III–IV (PDF 77–112)

Anlass: Abschnitt 3 zeigte für Kapitel III (Skills) und IV (Talents) noch den Status
„visuell geprüft; Volltranskription offen", während die zugehörigen Detaileinträge in
Abschnitt 4 sowie die Seiteninventare am Ende von `03-Skills.md` und `04-Talents.md`
bereits „vollständig gegengeprüft" mit vollständigen Gegencheck-Logs (16/16 bzw. 20/20
Seiten) auswiesen — ein reiner Widerspruch zwischen Abschnitt 3 und Abschnitt 4/den
Dateien selbst, keine tatsächliche inhaltliche Lücke.

Ehrliche Prüfung (komplette Lektüre beider Dateien, `03-Skills.md` und `04-Talents.md`):

- `03-Skills.md`: Gaining Skills, Training/Mastery, Basic/Advanced-Regeln, Table 3-1
  vollständig (alle 48 Skills), Skill Descriptors, Skill Groups sowie **alle**
  Skill-Einzelbeschreibungen von Acrobatics bis Wrangling inkl. sämtlicher Special Uses
  und aller Skill-Group-Spezialisierungslisten (Common Lore, Forbidden Lore, Scholastic
  Lore, Ciphers, Secret Tongue, Speak Language, Trade usw.) sind ausformuliert vorhanden.
  Die dokumentierte gedruckte Trade/Scrimshawer-Inkonsistenz ist sauber vermerkt.
  Keine Lücken gefunden.
- `04-Talents.md`: Grundlagen, Talent Groups, Prerequisites, Table 4-1 komplett (Air of
  Authority bis Wrath of the Righteous) sowie **alle** ausführlichen Talent-Beschreibungen
  mit Voraussetzungen, Boni, Reichweiten und Sonderregeln vorhanden; die gedruckten
  Widersprüche bei Master Enginseer und Whispers sind explizit dokumentiert.
  Keine Lücken gefunden.

Beide Dateien entsprechen dem geforderten Detailgrad (Vergleich mit `05-Armoury.md`) und
enthalten keine künstlich verdichteten Regelpassagen. Es waren daher **keine inhaltlichen
Ergänzungen nötig** — es wurde ausschließlich die Statuszeile in der Kapitelübersichtstabelle
(Abschnitt 3) für Kapitel III und IV von „Volltranskription offen" auf „vollständig
gegengeprüft" korrigiert, um den Widerspruch zwischen den Abschnitten aufzulösen.

---

## 4m. Statusabgleich Kapitel I–II (PDF 16–76)

Anlass: Abschnitt 3 (Kapitelübersichtstabelle) zeigte für Kapitel I und II noch den
veralteten Status „visuell geprüft; Volltranskription offen", obwohl die Detaileinträge
in Abschnitt 4 (siehe oben, `01-Charaktererschaffung.md` und `02-Karrierewege.md`) bereits
seit dem Gegencheck vom 16.08.2026 „vollständig gegengeprüft" auswiesen — ein reiner
Alt-Widerspruch in der Übersichtstabelle, kein inhaltliches Problem.

Beide Dateien wurden vollständig neu gelesen (nicht nur die Logs geprüft):
- `01-Charaktererschaffung.md` (23/23 Seiten, PDF 16–38): ausformulierter Fließtext,
  alle sechs Home Worlds mit vollständigen Modifikatoren/Traits/Wounds/Fate Points, alle
  Lure-of-the-Void- und Trials-and-Travails-Unterwahlen, Tables 1-1 bis 1-5 sowie beide
  Namenstabellen (1-3, 1-4) vollständig ausgeschrieben, keine Verdichtung von Regelmechanik.
- `02-Karrierewege.md` (38/38 Seiten, PDF 39–76): alle acht Careers mit vollständiger
  Beschreibung, Starting Skills/Talents/Gear, kompletter Characteristic-Advance-Kostentabelle
  und allen 8×8 = 64 Rank-Advance-Tabellen (Skills, Talents, Kosten, Voraussetzungen) sowie
  allen acht Special Abilities — nichts verdichtet, nichts fehlend.

**Ergebnis:** Beide Dateien sind tatsächlich bereits vollständig und ungekürzt transkribiert.
Es waren keine inhaltlichen Ergänzungen nötig. Einzige Änderung: Status in der
Kapitelübersichtstabelle (Abschnitt 3) von „visuell geprüft; Volltranskription offen" auf
„vollständig gegengeprüft" korrigiert, um den Widerspruch zu Abschnitt 4 aufzulösen.

---

## 4o. English conversion: Foreword and Index

Anlass: Nutzerwunsch, die gesamte Wissensdatenbank von deutscher Fließtext-Prosa auf
englische Fließtext-Prosa umzustellen (Regelbegriffe waren ohnehin bereits durchgängig
Englisch). Als erste zwei Dateien wurden `00-Foreword.md` (PDF 1–14) und `16-Index.md`
(PDF 397–408) komplett neu auf Englisch geschrieben (kein reines Maschinenübersetzen,
sondern erneute Ableitung aus OCR-Rohtext bzw. Seitenbild, mit demselben Umfang/
Verdichtungsgrad wie zuvor).

- Für `00-Foreword.md` wurde zusätzlich ein altes Session-Scratchpad mit Seitenbildern
  gefunden (`.../5edf0e7f-13aa-4d56-acd9-5c6c854c4d74/scratchpad/img/page001_0.jpg` bis
  `page014_0.jpg`), das im vorigen Durchgang als „nicht mehr vorhanden" galt. Das Vorwort
  (PDF 10) und der zuvor nur stark verzerrt per OCR lesbare Setting-Prolog (PDF 11) wurden
  damit erstmals direkt am Bild geprüft — der Prolog-Text ist jetzt klar lesbar und die
  Zusammenfassung im File wurde entsprechend bestätigt/präzisiert (weiterhin nur
  zusammengefasst, nicht wörtlich zitiert, aus Urheberrechtsgründen).
- Für `16-Index.md` wurden dieselben Seitenbilder für PDF 401–403 gefunden und geprüft.
  Der Charakterbogen (PDF 401–402) wurde damit vollständig visuell bestätigt und um
  bisher fehlende Details ergänzt: exakte Skills-Spaltenstruktur (Basic/Trained/+10%/+20%/
  Bonus je Skill), exakte Movement-Formeln (Half Move = AB×1, Full Move = AB×2, Charge =
  AB×3, Run = AB×6, Base Leap = SB×1m, Base Jump = SB×20cm), drei getrennte Lifting-Felder
  (Lift/Carry/Push statt einem Sammelfeld), sowie die Erkenntnis, dass der Weapons-Bereich
  aus **fünf separaten Einzelboxen** besteht statt einer gemeinsamen Tabelle.
- **Wichtigster Fund:** Das bisher ungeklärte Kreis-/Kästchenraster auf PDF 403 (im
  vorigen Durchgang mangels Seitenbild nur als „vermutlich Tracking-Raster, Zweck
  ungeklärt" vermerkt) ist am jetzt verfügbaren Bild eindeutig als **dritte
  Charakterbogen-Seite identifiziert: ein eigenständiger Starship-Statblock-Bogen**
  (Name/Class/Speed/Manoeuvrability/Detection/Hull, Turret Rating/Shields/Armour/Hull
  Integrity, Space/Power Available-Used, Weapon Capacity mit Mount-Checkboxen Prow/
  Starboard/Dorsal/Port/Keel, Essential/Supplemental Components, Complications/Past
  History, Crew%/Morale, sowie eine Waffentabelle mit 4 Slots × Macro-Battery-/Lance-Wahl,
  Strength/Crit Rating/Damage/Range und einem Location-Kreisraster). Damit ist die
  frühere offene Frage vollständig geklärt.
- Beide Dateien enden weiterhin mit einem eigenen „Status"-Abschnitt (jetzt auf Englisch)
  und behalten die ursprünglichen Buchseiten-/PDF-Seiten-Zitate bei.
- `00-FORTSCHRITT.md` selbst bleibt wie dokumentiert eine reine deutsche Arbeitsdatei und
  wurde nicht übersetzt.

---

## 4s. English conversion: Chapters VI–VII

Anlass: Fortsetzung der Umstellung der Wissensdatenbank auf englische Fließtext-Prosa
(siehe 4o). `06-Psychic-Powers.md` (Kapitel VI, PDF 157–176, Buchseiten 153–172) und
`07-Navigator-Powers.md` (Kapitel VII, PDF 177–190, Buchseiten 173–186) wurden komplett
auf Englisch neu geschrieben. Beide Kapitel waren zuvor bereits vollständig gegengeprüft
(siehe 4b/4c, 20/20 bzw. 14/14 Seiten) — die deutschen Fassungen dienten als inhaltliche
Vorlage für Umfang und Verdichtungsgrad, wurden aber Satz für Satz neu auf Englisch
formuliert statt maschinell übersetzt.

- Das alte Session-Scratchpad mit Seitenbildern
  (`.../5edf0e7f-13aa-4d56-acd9-5c6c854c4d74/scratchpad/img/`) war weiterhin vorhanden.
  Zur erneuten Absicherung wurden zusätzlich zu den bereits dokumentierten Gegenchecks
  vier besonders zahlenkritische Tabellenseiten nochmals am Bild verglichen: Table 6-2
  (`page164_0.jpg`), Table 6-3 (`page165_0.jpg`), Table 7-1 (`page186_0.jpg`) und Table 7-4
  (`page190_0.jpg`). Alle vier stimmen zeilengenau mit der bestehenden (jetzt englischen)
  Fassung überein — keine neuen Abweichungen gefunden, die bereits dokumentierten
  Korrekturen (Chronological Incontinence `1d5` Toughness Damage; Unchecked Mutation
  „Challenging (+0)") bleiben erhalten.
- `06-Psychic-Powers.md`: alle Abschnitte (Psykers/Psychic Ability, Psychic Strength/
  Focus Power, Tables 6-1 bis 6-15, Telepathy/Divination/Telekinesis-Disziplinen mit
  allen Techniques, Dark-Heresy-Kompatibilität) vollständig auf Englisch übertragen,
  Buchseiten-Zitate beibehalten.
- `07-Navigator-Powers.md`: alle Abschnitte (Navigator Gene/Warp Eye, vier Lineages,
  alle neun Navigator Powers auf Novice/Adept/Master, Table 7-1 Mutations, fünf Stages
  der Warp Navigation, Tables 7-2 bis 7-4) vollständig auf Englisch übertragen,
  Buchseiten-Zitate beibehalten.
- Beide Dateien enden mit einem eigenen „Status"-Abschnitt auf Englisch, der die
  Vollständigkeit und die erneute Bildverifikation bestätigt.
- Dateinamen unverändert; nur der Inhalt wurde auf Englisch umgestellt.

---

## 4p. English conversion: Chapters I–II

Anlass: Fortsetzung der Umstellung der Wissensdatenbank auf englische Fließtext-Prosa
(siehe 4o, 4s). `01-Charaktererschaffung.md` (Kapitel I, PDF 16–38, Buchseiten 12–34) und
`02-Karrierewege.md` (Kapitel II, PDF 39–76, Buchseiten 35–72) wurden komplett auf
Englisch neu geschrieben, ausgehend vom bereits vollständig gegengeprüften deutschen
Text (siehe 4m) als Umfangs-/Detailvorlage — kein Kürzen, keine Verdichtung, alle
Regelbegriffe, Werte und Tabellen 1:1 übernommen.

- Für `01-Charaktererschaffung.md`: eigenhändige Übersetzung; zusätzlich Gegencheck von
  drei Seitenbildern aus dem alten Scratchpad
  (`.../5edf0e7f-13aa-4d56-acd9-5c6c854c4d74/scratchpad/img/`) — page020 (Origin Path
  Chart, Buchseite 16), page034 (Table 1-2: Heirloom Items, Starting-Experience-Text,
  Buchseite 30) und page037 (Table 1-5: Starting Profit Factor and Ship Points,
  Ambition/Hatreds-Text, Buchseite 33). Alle Werte stimmten exakt mit der bisherigen
  deutschen Fassung überein — **keine Abweichungen gefunden**.
- Für `02-Karrierewege.md` (deutlich umfangreichere Datei, alle acht Careers mit
  Rank-1-bis-8-Advance-Tabellen): Übersetzung an einen Hintergrund-Agenten delegiert, mit
  Auftrag zur vollständigen 1:1-Übernahme aller Tabellenwerte sowie stichprobenartigem
  Gegencheck der Characteristic-Advance- und Rank-Advance-Tabellen gegen die Seitenbilder
  PDF 039–076 im selben Scratchpad-Verzeichnis. Ergebnis wird nach Abschluss hier bzw. im
  Dateistatus von `02-Karrierewege.md` ergänzt.
- Beide Dateien enden mit einem eigenen „Status"-Abschnitt auf Englisch und behalten die
  ursprünglichen Buchseiten-Zitate bei (Format „S. X" → „p. X").
- `00-FORTSCHRITT.md` selbst bleibt eine reine deutsche Arbeitsdatei und wurde nicht
  übersetzt.

---

## 4t. English conversion: Chapter VIII (Starships)

Anlass: Fortsetzung der Umstellung der Wissensdatenbank auf englische Fließtext-Prosa
(siehe 4o, 4s, 4p). `08-Starships.md` (Kapitel VIII, PDF 191–232, Buchseiten 187–228)
wurde komplett auf Englisch neu geschrieben, ausgehend vom bereits vollständig
gegengeprüften deutschen Text (siehe 4d, 42/42 Seiten, das mit Abstand fehlerreichste
Kapitel bisher) als Umfangs-/Detailvorlage — kein Kürzen, keine Verdichtung, alle
Regelbegriffe, Werte und Tabellen 1:1 übernommen, einschließlich aller dort dokumentierten
Korrekturen und Lückenfüllungen (Warpsbane Hull, Ryza Pattern Plasma Battery Power 7,
Shard Cannon Battery/Micro Laser Defence Grid/Gravity Sails, Default-Manoeuvre-Drehwinkel
90°/45°, Ghost Field/Runecaster).

- Zusätzlicher Gegencheck am alten Session-Scratchpad mit Seitenbildern
  (`.../5edf0e7f-13aa-4d56-acd9-5c6c854c4d74/scratchpad/img/`), das für PDF 190–232
  vollständig vorhanden war: sieben besonders zahlenkritische Seiten erneut am Bild
  verglichen — page197 (Table 8-1: Machine Spirit Oddities), page198 (Jericho/Vagabond/
  Hazeroth-Hüllenwerte), page199 (Warpsbane Hull/Plasma-Drive-Text), page200 (Dauntless/
  Lunar-Hüllenwerte), page201 (Havoc/Sword/Tempest-Hüllenwerte), page206 (Table 8-4:
  Lances and Macrobatteries inkl. Ryza-Battery-Power), page212 (Shard Cannon Battery/
  Runecaster/Micro Laser Defence Grid/Gravity Sails), page217 (Default-Manoeuvre-
  Drehwinkel 90°/45°) sowie page232 (Extended Repairs). Alle neun stimmen zeilengenau mit
  der bestehenden (jetzt englischen) Fassung überein — **keine neuen Abweichungen
  gefunden**, sämtliche zuvor dokumentierten Korrekturen aus 4d bestätigt.
- `08-Starships.md`: alle Abschnitte (Hulls, Complications Tables 8-1/8-2, Essential
  Components Table 8-3 mit Plasma Drives/Warp Engines/Gellar Fields/Void Shields/Bridges/
  Life Sustainers/Crew Quarters/Auger Arrays, Weapon Components Tables 8-4/8-5, Archeotech/
  Xeno-tech Tables 8-6/8-7, Component Costs Table 8-8, NPC- und Quick-start-Vessels,
  Starship Combat mit Manoeuvre/Extended Actions Tables 8-9 bis 8-11, Ramming/Boarding/
  Stern-Chase/Silent-Running-Detailregeln, Weapons/Damage/Critical-Hit-Chart Table 8-12,
  Crew Population/Morale Tables 8-13/8-14, Replenishing Morale/Crew und Zero-Gravity/
  Hazard-Regeln) vollständig auf Englisch übertragen, Buchseiten-Zitate beibehalten.
- Datei endet mit eigenem „Status"-Abschnitt auf Englisch, der Vollständigkeit und
  erneute Bildverifikation bestätigt.
- Dateiname unverändert; nur der Inhalt wurde auf Englisch umgestellt.

---

## 4y. English conversion: Chapter XV (Into the Maw)

Anlass: Auf Nutzerwunsch wird die gesamte Wissensdatenbank sukzessive ins Englische
übertragen (siehe bereits 4o, 4p, 4s, 4t für andere Kapitel). Dieser Eintrag betrifft
`15-Into-The-Maw.md` (PDF 383–396, Buchseiten 379–393).

Vorgehen: Die bereits vollständig gegengeprüfte deutsche Fassung (siehe 4k) wurde
vollständig ins Englische übertragen (Einleitung, Sage der Righteous Path, alle drei
Abenteuerteile, alle vier Objectives, Rewards, alle drei NSC-Statblöcke). Zusätzlich
wurden beim Übertragen die Originalseitenbilder (`page385_0.jpg`, `page389_0.jpg`,
`page391_0.jpg`, `page396_0.jpg`) sowie der englische OCR-Rohtext (`tmp/ocr/page383.txt`
bis `page388.txt`) herangezogen, um Zitate, Kapitelüberschriften, den Flacker-Zyklus des
Magoros-Sterns (102 Minuten/58 Sekunden), den Rewards-Text und alle drei Statblöcke direkt
gegen den englischen Originaltext zu bestätigen — dabei wurden keine neuen inhaltlichen
Abweichungen zur deutschen Fassung gefunden. Rein atmosphärischer Text bleibt wie in der
deutschen Fassung sinngemäß verdichtet; alle spielrelevanten Fakten sind vollständig
enthalten. Dateiname unverändert, nur der Inhalt ist jetzt auf Englisch.

**`15-Into-The-Maw.md` ist damit vollständig ins Englische übertragen.**

---

## 4r. English conversion: Chapter V (Armoury)

Anlass: Fortsetzung der Umstellung der Wissensdatenbank auf englische Fließtext-Prosa
(siehe 4o, 4s, 4p, 4t, 4y). `05-Armoury.md` (Kapitel V, PDF 113–156, Buchseiten 109–152)
wurde komplett auf Englisch neu geschrieben, ausgehend von der bereits vollständig
gegengeprüften deutschen Fassung (siehe 4a, 44/44 Seiten bildbasiert geprüft) als
Umfangs-/Detailvorlage — kein Kürzen, keine weitere Verdichtung, alle Waffen-/Rüstungs-/
Ausrüstungs-/Cybernetics-Tabellen, alle Weapon Special Qualities und alle bereits
dokumentierten Korrekturen gegenüber dem rohen OCR (u. a. Naval Pistol verliert Tearing
ohne Sondermunition, Harlequin's Kiss addiert kein SB zum Damage, Power Sword/Ghost Sword
+15 statt +10 Parry, Las-Power-Pack-Feldladestrafen, Utility-Mechadendrite-Räuchergefäß-
Nachteil für den Träger usw.) satzweise neu auf Englisch formuliert statt maschinell
übersetzt.

- Als zusätzliche Absicherung wurden während der Übertragung 13 Seitenbilder aus dem alten
  Session-Scratchpad (`.../5edf0e7f-13aa-4d56-acd9-5c6c854c4d74/scratchpad/img/`) erneut
  mit den deutschen Zahlenwerten abgeglichen: `page113_0.jpg` (Currencies/Ammunition-
  Einleitung), `page117_0.jpg` (Heavy Stubber/Shotgun/Bolt-Weapons-Flavourtext),
  `page121_0.jpg`/`page125_0.jpg` (Las-/SP-Weapon-Flavour), `page130_0.jpg`,
  `page135_0.jpg` (Table 5-8: Melee Weapons), `page139_0.jpg` (Table 5-10/5-11: Ammo/
  Unusual Ammunition), `page140_0.jpg` (Table 5-13: Gear), `page142_0.jpg`,
  `page144_0.jpg` (Table 5-14: Drugs and Consumables), `page146_0.jpg`, `page148_0.jpg`
  (Cybernetics/Implant Systems) und `page152_0.jpg`. Alle geprüften Tabellen und
  Flavourtexte stimmen zeilengenau mit der bestehenden (jetzt englischen) Fassung
  überein — **keine neuen Abweichungen gefunden**.
- Alle Abschnitte (Availability, Craftsmanship, Wealth/Profit Factor/Ammunition, Weapons
  inkl. aller Weapon Special Qualities und Weapon Craftsmanship, Tables 5-1 bis 5-16,
  Grenades and Missiles inkl. Hallucinogen-Tabelle, Exotic Weapons, Melee Weapons, Weapon
  Upgrades, Armour, Gear, Drugs and Consumables, Tools, Cybernetics inkl. aller
  Cybernetic Effects, Implantation) vollständig auf Englisch übertragen, Buchseiten-
  Zitate beibehalten.
- Die Datei endet mit einem eigenen „Status"-Abschnitt auf Englisch, der die
  Vollständigkeit und die erneute Bildverifikation bestätigt.
- Dateiname unverändert; nur der Inhalt wurde auf Englisch umgestellt.

**`05-Armoury.md` ist damit vollständig ins Englische übertragen.**

---

## 4v. English conversion: Chapters X–XI

Anlass: Fortsetzung der Umstellung der Wissensdatenbank auf englische Fließtext-Prosa (siehe
4o, 4s, 4p, 4t, 4y, 4r). `10-The-Game-Master.md` (Kapitel X, PDF 289–304, Buchseiten 285–300)
und `11-The-Imperium.md` (Kapitel XI, PDF 305–322, Buchseiten 301–318) wurden komplett auf
Englisch neu geschrieben, ausgehend vom OCR-Text (`tmp/ocr/page289.txt`–`page322.txt`) und der
bereits inhaltlich vollständigen deutschen Fassung (4f, 4g) als Umfangs-/Detailvorlage.

- **Kapitel X — Tabellenverifikation am Seitenbild:** die deutsche Vorgängerfassung hatte bei
  Table 10-1, 10-5 und 10-7 explizit OCR-Unsicherheit vermerkt. Der alte Session-Scratchpad
  (`.../5edf0e7f-13aa-4d56-acd9-5c6c854c4d74/scratchpad/img/`) enthält Seitenbilder für PDF
  289–304 vollständig; folgende Bilder wurden geprüft: `page295_0.jpg` (Table 10-1: Encounter
  Difficulty), `page297_0.jpg` (Table 10-2: Dispositions; Table 10-7: Corruption Track),
  `page298_0.jpg` (Table 10-3: Fear Test Difficulties; Table 10-4: Shock Table), `page300_0.jpg`
  (Table 10-5: The Insanity Track), `page301_0.jpg` (Table 10-6: Mental Traumas), `page304_0.jpg`
  (Table 10-8: Malignancies). **Ergebnis — Korrekturen gegenüber der bisherigen (als unsicher
  markierten) Fassung:**
  - **Table 10-1 (Encounter Difficulty):** vollständige Werte bestätigt: Easy 50, Routine 70,
    Ordinary 100, Average 130, Challenging 170, Hard 200, Very Hard 250 (die deutsche Fassung
    hatte "Average (Challenging) 130" fälschlich zusammengefasst und Easy/Ordinary vertauscht/
    unklar gelassen).
  - **Table 10-5 (Insanity Track):** korrigiert von grob geschätzten 20er-Schritten auf die
    tatsächlichen 10er-Schritte: 0–9 Stable (n/a), 10–19/20–29/30–39 Unsettled (+10), 40–49/
    50–59 Disturbed (+0), 60–69/70–79 Unhinged (–10), 80–89/90–99 Deranged (–20), 100+
    Terminally Insane. Die bisherige Fassung hatte fälschlich nur 5 Stufen zu je 20 Punkten
    mit abweichenden Modifikatoren (+0/-10/-20/-30) angenommen.
  - **Table 10-7 (Corruption Track):** korrigiert — richtige Reihenfolge/Werte sind 01–30
    Tainted (+0), 31–60 Soiled (–10, erster Mutation-Test), 61–90 Debased (–20, zweiter Test),
    91–99 Profane (–30, dritter Test), 100 Damned. Die deutsche Fassung hatte Tainted und
    Soiled in der Reihenfolge vertauscht und die Stufe „Debased" komplett übersehen.
  - Table 10-2, 10-3, 10-4, 10-6, 10-8 waren bereits inhaltlich korrekt aus OCR erfasst;
    Bildabgleich hat hier nur die exakte Formatierung/Rundung bestätigt, keine Wertkorrekturen
    nötig.
- Alle übrigen Abschnitte (Rolle des GM, The Dark Frontier/Styles of Play, Rewards, Mass
  Combats, Interaction, Fear and Damnation/Going Insane/Corruption) vollständig auf Englisch
  neu formuliert, GM-Ratschläge sinngemäß kompakt, alle Regelwerte 1:1.
- **Kapitel XI** ist reines Lore-/Hintergrundkapitel ohne Zahlenmechanik — komplett neu auf
  Englisch als vollständige, sachlich korrekte Prosa-Referenz erfasst (High Lords/Adeptus Terra/
  Ministorum/weitere Institutionen, Planetenklassen, Sprache, Kultur/Mutation/Abhumans,
  Astropaths, der Warp inkl. Warp-Reisen/Astronomican/Zeitverschiebung/Warp Gates & Portals/
  Warp-Kreaturen, Sternflotten inkl. Segmentae Majoris/Sektoren/Flottentypen/Navy-Rangfolge/
  Raumschiffe, Feinde des Imperiums); keine Tabellen zu verifizieren.
- Beide Dateien enden mit einem eigenen „Status"-Abschnitt auf Englisch.
- Dateinamen unverändert; nur der Inhalt wurde auf Englisch umgestellt.

**`10-The-Game-Master.md` und `11-The-Imperium.md` sind damit vollständig ins Englische
übertragen, Kapitel X zusätzlich vollständig am Seitenbild gegengeprüft (keine offenen
Unsicherheiten mehr).**

---

## 4q. English conversion: Chapters III–IV

Anlass: Fortsetzung der Umstellung der Wissensdatenbank auf englische Fließtext-Prosa
(siehe 4o, 4s, 4p, 4t, 4y, 4r, 4v). `03-Skills.md` (Kapitel III, PDF 77–92, Buchseiten
73–88) und `04-Talents.md` (Kapitel IV, PDF 93–112, Buchseiten 89–108) wurden komplett
auf Englisch neu geschrieben, ausgehend von der bereits vollständig gegengeprüften
deutschen Fassung (siehe Abschnitt 4 „03-Skills.md"/„04-Talents.md" sowie 4n, 16/16 bzw.
20/20 Seiten bildbasiert geprüft) als Umfangs-/Detailvorlage — kein Kürzen, keine weitere
Verdichtung. Alle Skill-Beschreibungen (Acrobatics bis Wrangling) samt sämtlicher Special
Uses, alle Skill-Group-Spezialisierungslisten sowie alle Talent-Beschreibungen (Air of
Authority bis Wrath of the Righteous) samt Prerequisites/Boni/Reichweiten/Sonderregeln
wurden satzweise neu auf Englisch formuliert statt maschinell übersetzt.

- Als zusätzliche Absicherung wurden während der Übertragung mehrere Seitenbilder aus dem
  alten Session-Scratchpad (`.../5edf0e7f-13aa-4d56-acd9-5c6c854c4d74/scratchpad/img/`)
  erneut abgeglichen: `page079_0.jpg` (Table 3-1: Skills), `page088_0.jpg` (Trade/
  Wrangling inkl. der dokumentierten Trade/Scrimshawer-Listenabweichung), `page096_0.jpg`
  und `page097_0.jpg` (Table 4-1: Talents komplett), `page106_0.jpg` (Master Enginseer-
  Detailtext) und `page112_0.jpg` (Whispers-Detailtext), außerdem `page103_0.jpg`,
  `page109_0.jpg` und `page111_0.jpg` als weitere Stichproben der Talent-Detailtexte.
  Alle geprüften Tabellen und Detailtexte stimmen zeilengenau mit der bestehenden (jetzt
  englischen) Fassung überein — **keine neuen Abweichungen gefunden**. Die beiden bereits
  dokumentierten gedruckten Widersprüche (Master Enginseer: Tabelle „Tech-Use +10,
  Mechanicus Implants" vs. Detailtext „Tech-Use +20, Mechanicus or Explorator Implants";
  Whispers: Tabelle „Int 40, Fel 30" vs. Detailtext „Intelligence 45, Fellowship 35")
  wurden exakt wie zuvor am Bild bestätigt. Ebenso bestätigt: Table 3-1 stimmt zeilengenau,
  und die Trade-Skill-Group-Zeile führt „Trader (Fel)" ohne Scrimshawer, während die
  Einzelbeschreibungen umgekehrt Scrimshawer, aber keinen eigenen Trader-Eintrag enthalten.
- `03-Skills.md`: Gaining Skills, Training/Skill Mastery, Basic/Advanced-Regeln, Table 3-1
  (alle 48 Skills), Skill Descriptors, Skill Groups sowie alle Skill-Einzelbeschreibungen
  inkl. sämtlicher Special Uses und aller Skill-Group-Spezialisierungslisten (Common Lore,
  Forbidden Lore, Scholastic Lore, Ciphers, Secret Tongue, Speak Language, Trade)
  vollständig auf Englisch übertragen, Buchseiten-Zitate beibehalten.
- `04-Talents.md`: Grundlagen, Talent Groups, Talent Prerequisites, Table 4-1 (komplett)
  sowie alle ausführlichen Talent-Beschreibungen inkl. Voraussetzungen, Boni, Reichweiten
  und Sonderregeln vollständig auf Englisch übertragen, Buchseiten-Zitate beibehalten; die
  gedruckten Widersprüche bei Master Enginseer und Whispers bleiben als eigener Abschnitt
  dokumentiert.
- Beide Dateien enden mit einem eigenen „Status"-Abschnitt auf Englisch, der die
  Vollständigkeit und die erneute Bildverifikation bestätigt.
- Dateinamen unverändert; nur der Inhalt wurde auf Englisch umgestellt.

**`03-Skills.md` und `04-Talents.md` sind damit vollständig ins Englische übertragen.**

---

## 4w. English conversion: Chapters XII-XIII

Anlass: Fortsetzung der Umstellung der Wissensdatenbank auf englische Fließtext-Prosa (siehe 4o,
4s, 4p, 4t, 4y, 4r, 4v). `12-Rogue-Traders.md` (Kapitel XII, PDF 323–338, Buchseiten 319–334) und
`13-The-Koronus-Expanse.md` (Kapitel XIII, PDF 339–366, Buchseiten 335–362) wurden komplett auf
Englisch neu geschrieben, ausgehend von der bereits inhaltlich vollständigen deutschen Fassung
(4h, 4i) als Umfangs-/Detailvorlage; beide Kapitel sind reine Lore-/Gazetteer-Kapitel ohne
Zahlenmechanik, daher lag der Schwerpunkt auf treuer Übersetzung von Fraktionen, Orten und Personen
statt auf Tabellenprüfung.

- **Kapitel XII** (`12-Rogue-Traders.md`): vollständig auf Englisch neu formuliert — Grundlagen,
  Warrant of Trade, Wurzeln/Herkunft (Imperial Navy, Imperial Guard, Administratum, Merchants,
  Imperial Commanders, Inquisition) samt Vergabegründen, Temperament-Typen (Scoundrel, Merchant
  Prince, Explorer, Missionary, Diplomat, Psychopath), Trappings of Power, Conditions (Trooping the
  Colours, Punitive Strike, Settlement, Reclamation, Exploration), Lineage, Revocation and
  Forfeiture, Rewards. Alle Fakten 1:1 übernommen, keine inhaltlichen Lücken.
- **Kapitel XIII** (`13-The-Koronus-Expanse.md`): vollständig auf Englisch neu formuliert —
  Einleitung samt Calixis-Sektor-Sidebar, Great Warp Storms (Void Dancer's Roil, Screaming Vortex,
  Deathveil, Whispering Storm), Port Wander samt Rubycon-II-System, Koronus Passage/„the Maw" samt
  Stations of Passage (Temple, Witch-Cursed World, Battleground, Hermitage), Furibundus, Footfall,
  Winterscale's Realm samt Burnscour/Egarian Dominion/Jerazol/Foundling Worlds (Grace, Rain,
  Iniquity), Charnel Stars, Accursed Demesne (Lathimon's Death, Processional of the Damned),
  Undred-Undred Teef (inkl. Flash Gitz, Tusk, Morgaash Kulgraz/Da Wurldbraka), Heathen Stars
  (Agusia, Naduesh, Zayth, Raakata, Vaporius), Unbeholden Reaches (Concanid, Illisk, Orn, Rifts of
  Hecaton, Melbethe, Far Corpse Stars), Denizens of the Koronus Expanse (Ork Menace, Stryxis, die
  vier Chaos Gods, Chaos Pirates/Renegades inkl. Saynay Clan/Reavers of Karrad Vall, Treacherous
  Eldar inkl. Webway/Children of Thorns/Crow Spirits/Whisper of Anaris, Rak'Gol Marauders,
  Disciples of Thule, Yu'vath, Halo Artefacts, Kroot), Rogue Traders Known Within the Expanse
  (Chorda, Winterscale, Saul, Umboldt, Valcetti), Lost Lineages (7 erloschene Linien).
- **Kartendoppelseiten-Abschnitt (Buchseiten 338–339 / PDF 342–343):** wie vorgegeben **nicht**
  erneut bildbasiert verifiziert — die zuvor frisch am Bild geprüften Ortsnamen und
  Welt-Klassifikationssymbole (aus `page342_0.jpg`/`page343_0.jpg`) wurden 1:1 übernommen, nur die
  deutsche Verbindungsprosa (Legenden-Erklärung, Regionsüberschriften, Unsicherheits-Hinweis zu
  ähnlich eingefärbten Symbolen) wurde ins Englische übertragen.
- Beide Dateien enden mit einem eigenen „Status"-Abschnitt auf Englisch; Dateinamen unverändert,
  nur der Inhalt wurde auf Englisch umgestellt.

**`12-Rogue-Traders.md` und `13-The-Koronus-Expanse.md` sind damit vollständig ins Englische
übertragen.**

---

## 4x. English conversion: Chapter XIV (Adversaries/Traits/Mutations/Allies)

Anlass: Fortsetzung der Umstellung der Wissensdatenbank auf englische Fließtext-Prosa (siehe
4o, 4s, 4p, 4t, 4y, 4r, 4v, 4q, 4w). Die vier Dateien zu Kapitel XIV — `14-Adversaries-and-Aliens.md`
(PDF 367, Kapiteltrenntitel), `14-Traits.md` (PDF 368–372, Traits-Regeln inkl. Table 14-1 und
14-2), `14-Mutations.md` (PDF 373, Table 14-3: Mutations, alle 34 Zeilen) und
`14-Allies-Enemies-and-Rivals.md` (PDF 374–382, NSC-Statblöcke) — wurden vollständig auf
Englisch neu geschrieben.

- Ausgangsbasis war jeweils die bereits vollständig bildbasiert geprüfte deutsche Fassung
  (siehe 4j, Ersterfassung Kapitel XIV); die Übersetzung folgte deren Inhalt und Struktur
  1:1, mit Kreuzabgleich gegen `tmp/ocr/page367.txt`–`page382.txt`.
- Alle Zahlenwerte, Traits, Talents, Skills, Waffenprofile, Rüstungswerte und die komplette
  Mutations-Zufallstabelle (01–05 bis 00) wurden unverändert (1:1) übernommen — keine
  Regelwerte verändert oder neu interpretiert, nur der Fließtext ins Englische übertragen.
- Stichprobenkontrolle am Original-Seitenbild: `page374_0.jpg` (aus dem alten Session-
  Scratchpad `.../5edf0e7f-13aa-4d56-acd9-5c6c854c4d74/scratchpad/img/`) zeigte, dass die Seite
  ohnehin bereits im gedruckten Original auf Englisch vorliegt (Colonist-Profil, Adept,
  Bloodskinner, Entertainer, Hired Gun) — die neue Übersetzung stimmt mit dem englischen
  Originaltext praktisch wortgleich überein, was die Genauigkeit der vorherigen deutschen
  Transkription und der jetzigen Rückübersetzung bestätigt.
- Alle vier Dateien enden mit einem eigenen „Status"-Abschnitt auf Englisch. Dateinamen
  unverändert; nur der Inhalt wurde auf Englisch umgestellt.

**Kapitel XIV (`14-Adversaries-and-Aliens.md`, `14-Traits.md`, `14-Mutations.md`,
`14-Allies-Enemies-and-Rivals.md`) ist damit vollständig ins Englische übertragen.**

---

## 4u. English conversion: Chapter IX (Playing the Game)

Anlass: Fortsetzung der Umstellung der Wissensdatenbank auf englische Fließtext-Prosa (siehe
4o, 4s, 4p, 4t, 4y, 4r, 4v, 4q, 4w, 4x). `09-Playing-The-Game.md` (PDF 233–288, Buchseiten
229–284) — mit ca. 800 Zeilen die bisher längste Datei im Projekt — wurde vollständig auf
Englisch neu geschrieben, ausgehend vom bereits vollständig erfassten deutschen Fließtext
(Tests, Degrees of Success, Extended/Opposed Tests, Test Difficulty, Assistance, Fate, Combat-
Grundlagen, alle Actions, Hit Locations, Injury, Critical Effects, Conditions/Special Damage,
Healing, Exploration, Investigation, Movement, Profit Factor, Acquisition, Influence,
Endeavours, Misfortunes).

- Die Critical-Effect-Tabellen (9-11 bis 9-26, Energy/Explosive/Impact/Rending × Arm/Body/
  Head/Leg) waren aus einem vorherigen Durchgang bereits wortgetreu am Seitenbild
  (PDF 256–263) verifiziert. Statt aus dem Deutschen zurückzuübersetzen, wurden alle 16
  Tabellen erneut direkt an denselben Seitenbildern
  (`.../5edf0e7f-13aa-4d56-acd9-5c6c854c4d74/scratchpad/img/page256_0.jpg`–`page263_0.jpg`)
  frisch auf Englisch transkribiert — Stichprobenvergleich mit der deutschen Fassung bestätigt
  deren Genauigkeit.
- Zusätzlich wurden mehrere im deutschen Entwurf als Auszug/Näherung/unsicher markierte
  Tabellen gezielt an den zugehörigen Seitenbildern (PDF 236, 269, 271–282, 287–288, alle im
  selben Scratchpad-Ordner) neu geprüft und dabei **korrigiert bzw. erstmals vollständig
  erfasst**:
  - **Table 9-3** (Test Difficulty): voller 13-stufiger Bereich (Trivial +60 bis Hellish -60)
    bestätigt — der deutsche Entwurf hatte Trivial, Simple, Routine und Arduous nur vermutet
    bzw. weggelassen.
  - **Table 9-27 bis 9-29** (Exploration/Investigation Benchmarks, Reliability): vollständig
    aus dem Seitenbild übernommen statt nur beispielhaft zusammengefasst.
  - **Table 9-30/9-31** (Movement): vollständige AB-0-bis-10-Reihen statt der zuvor nur
    linear interpolierten Beispielwerte.
  - **Table 9-33** (Carrying/Lifting/Pushing): vollständige SB+TB-0-bis-20-Reihen statt
    Beispielwerten.
  - **Table 9-34** (Profit and Power): vollständige Liste statt Auszug.
  - **Table 9-35** (Acquisition Modifiers) sowie die bisher nur referenzierten **Tables 9-36
    bis 9-38** (Starship Component Acquisitions, Acquisition Quality, Acquisition Rarity):
    erstmals vollständig transkribiert.
  - **Table 9-39/9-40** (Endeavour Scale, Achievement Point Awards): korrigierte Werte
    (Lesser 900/Greater 1.200/Grand 1.500 Achievement Points; Punkteskala Easy 10 bis Very
    Hard 300) statt der zuvor nur geschätzten Zahlen.
  - **Table 9-41/9-42** (Misfortunes/Misfortune Details): der deutsche Entwurf hatte hier
    explizit als unsicher markierte, tatsächlich **falsche** d100-Bereiche (66–89 statt
    korrekt 66–90 für „Grim" sowie „1d10"/„2d10" Profit-Factor-Verlust statt korrekt 2 bzw.
    1d5). Am Seitenbild (PDF 288) korrigiert; zusätzlich wurde die volle 20-zeilige
    Misfortune-Details-Tabelle (bisher nur als Themen-Aufzählung wiedergegeben) erstmals
    komplett transkribiert.
- Die Endeavour-Beispieltexte (Kolonie Grace, Tvalde IV, Lucin's Breath, Cold Trade, Zayth-
  Handelsroute, Guilder-Route Port Wander–Drusus Marches, S. 279–284) bleiben bewusst
  kompakt wiedergegeben — reiner erzählerischer Vorlagen-Content ohne Regelwert.
- Die Datei endet mit einem eigenen „Status"-Abschnitt auf Englisch, der die frisch
  bildverifizierten bzw. korrigierten Tabellen einzeln auflistet. Dateiname unverändert.

**Kapitel IX (`09-Playing-The-Game.md`) ist damit vollständig ins Englische übertragen, mit
mehreren inhaltlichen Korrekturen gegenüber dem vorherigen deutschen Entwurf.**

---

## 4z. Final audit of gameplay-critical tables — Chapter IX

Anlass: gezielter Audit-Durchgang (auf Wunsch des Nutzers) speziell für die Tabellen aus
`09-Playing-The-Game.md`, die am Spieltisch am häufigsten live gebraucht werden (Tests,
Kampfaktionen, Trefferzonen, Deckung, kritische Effekte). Jede Zelle wurde erneut gegen die
Seitenbilder geprüft (PDF 233–263 / Buchseiten 229–259), auch wenn die Datei zuvor schon als
verifiziert galt.

Geprüfte Tabellen und Ergebnis:

- **Table 9-1** (Skill Tests): **korrigiert.** Zeilenreihenfolge angepasst; die Mastered-Skill-
  Zeile war falsch ("full Characteristic or +20" statt korrekt **+10 oder +20**, und betrifft
  Mastered *Basic or Advanced* Skills).
- **Table 9-2** (Characteristics Tests): **korrigiert.** Die Zeile für **Weapon Skill** fehlte
  komplett. Mehrere Beispieltexte waren freie Umschreibungen statt der wörtlichen Buchbeispiele
  — ersetzt.
- **Table 9-3** (Test Difficulty): unverändert, bereits korrekt.
- **Table 9-4** (Combat Actions): **korrigiert — größte Lücke im Audit.** Neun Aktionszeilen
  fehlten komplett (**Grapple, Jump or Leap, Manoeuvre, Multiple Attacks, Parry, Reload,
  Standard Attack, Suppressing Fire, Use a Skill**). Zusätzlich falsch: Knock-Down war als
  "Full" statt korrekt **"Half"** gelistet; Semi-Auto Burst hatte **+20 BS** statt korrekt
  **+10 BS** (der Fließtext an anderer Stelle hatte den richtigen Wert, nur die Tabellenzeile
  war falsch); bei Called Shot, Guarded Attack und Tactical Advance fehlte das Subtype
  "Concentration"; Focus Power war gegenüber dem Buch ("Varies"/"Varies") überspezifiziert.
- **Table 9-5** (Multiple Hits): unverändert, bereits korrekt.
- **Table 9-6** (Hit Locations): unverändert, bereits korrekt.
- **Table 9-7** (Cover Examples): **korrigiert.** Drei von fünf Deckungsarten fehlten komplett
  (Armour-glas/Generatoria-Rohre/dünnes Metall = AP 4; Cogitator-Bank/Stasis-Pod = AP 12;
  Armaplas/Bulkhead/Plasteel = AP 32). Nur AP 8 und AP 16 waren vorhanden.
- **Table 9-8** (Combat Difficulty Summary): **korrigiert.** Die eigentliche Tabelle fehlte
  komplett — es gab nur eine Aufzählung derselben Regeln in Fließtextform. Vollständige Tabelle
  (Difficulty / Skill Modifier / Example, 7 Zeilen Easy bis Very Hard) ergänzt; die vorhandene
  Aufzählung bleibt als zusätzliche Referenz erhalten.
- **Table 9-9** (Target Size Modifiers): unverändert, bereits korrekt.
- **Table 9-10** (Effects of Zero Characteristic Scores): **korrigiert.** Sechs verschiedene
  Characteristics (Weapon Skill, Ballistic Skill, Strength, Agility, Perception, Fellowship)
  waren fälschlich zu einer Zeile ("Tests nicht möglich") zusammengefasst, was nur für Weapon
  Skill/Ballistic Skill stimmt. Tatsächlich: **Strength 0** = Bewusstlosigkeit; **Agility 0** =
  gelähmt/hilflos, keine Aktionen; **Perception 0** = -30 auf alle Tests außer Toughness (nicht
  "keine Tests"); **Fellowship 0** = katatonisch, kann nicht sprechen. Auf neun einzelne Zeilen
  gemäß Buch aufgeteilt.
- **Tables 9-11 bis 9-26** (Critical Effect Tables): stichprobenartig geprüft (9-11, 9-12,
  9-17, 9-18, 9-23, 9-24, je 2-3 Zeilen gegen Seitenbild). Alle korrekt, keine Änderungen nötig
  — bestätigt die bereits dokumentierte Vollverifikation dieses Tabellenblocks.

**Ergebnis:** Die Lücken in Tables 9-2, 9-4, 9-7, 9-8 und 9-10 stammten aus früheren Durchgängen,
die Zeilen stillschweigend gekürzt oder weggelassen hatten (keine Fehlübersetzung einzelner
Werte). Alle betroffenen Tabellen wurden anhand der Originalbilder vollständig wiederhergestellt.
Die Datei `09-Playing-The-Game.md` enthält jetzt einen zusätzlichen Abschnitt "Final Audit
(gameplay-critical tables)" mit derselben Auflistung auf Englisch.

---

## 4za. Final audit of gameplay-critical tables — Chapter V (weapons/armour)

Anlass: gezielter Audit-Durchgang (auf Wunsch des Nutzers) speziell für die Tabellen aus
`05-Armoury.md`, die am Spieltisch am häufigsten live gebraucht werden (Waffenprofile,
Nahkampfwaffen, Granaten/Raketen, Exotische Waffen, Waffen-Upgrades, Munition, Rüstung). Jede
Zelle wurde erneut direkt gegen die Seitenbilder geprüft (PDF 113–144 / Buchseiten 109–140),
auch wenn die Datei zuvor schon als vollständig image-verifiziert galt.

Geprüfte Tabellen und Ergebnis:

- **Table 5-3** (Craftsmanship and Time Taken), PDF 116: **korrigiert.** Common Craftsmanship
  hat im Original "—" (kein Multiplikator/Basiswert) stehen, nicht "×1" wie zuvor transkribiert.
- **Table 5-4** (Ranged Weapons — Las, Solid Projectile, Bolt, Melta, Plasma, Flame, Primitive
  Weapons, Launchers), PDF 122–123: unverändert, jede Zelle (Class, Range, RoF, Damage, Pen,
  Clip, Rld, Special, kg, Availability) stimmt exakt mit der Quelle überein, inklusive des
  bereits dokumentierten Belasco-Dueling-Pistol-Gewichts (1,5 kg).
- **Table 5-6** (Grenades and Missiles), PDF 131: unverändert, bereits korrekt.
- **Table 5-7** (Exotic Weapons), PDF 132: unverändert, bereits korrekt, inklusive der bereits
  dokumentierten Kroot-Rifle-(Melee)-Werte und des Shuriken-Pistol-Gewichts (1,2 kg).
- **Table 5-8** (Melee Weapons), PDF 135: unverändert, bereits korrekt.
- **Table 5-9** (Weapon Upgrades), PDF 137: unverändert, bereits korrekt.
- **Table 5-10** (Ammo) und **Table 5-11** (Unusual Ammunition), PDF 139–140: unverändert,
  bereits korrekt.
- **Table 5-12** (Armour), PDF 142: unverändert, jede AP-/Location-/kg-/Availability-Zelle
  stimmt.
- **Table 5-13** (Gear), PDF 144 (nebenbei mitgeprüft, nicht auf der ursprünglichen
  Prioritätsliste): **korrigiert.** "Clothing (Merchant Guilded)" war ein Schreibfehler; die
  Quelle schreibt "Clothing (Merchant Guilder)".

**Ergebnis:** Nur eine echte Datenabweichung gefunden (Table 5-3, Common-Zeile), plus ein
Nebenbefund außerhalb des priorisierten Umfangs (Table 5-13, Rechtschreibfehler). Alle übrigen
priorisierten Tabellen (5-4, 5-6, 5-7, 5-8, 5-9, 5-10, 5-11, 5-12) sind zellengenau gegen die
Quellbilder bestätigt korrekt, keine weiteren Änderungen nötig. `05-Armoury.md` enthält jetzt
einen zusätzlichen Abschnitt "Final Audit (gameplay-critical weapon/armour tables)" mit
derselben Auflistung auf Englisch.

---

## 4zb. Final audit of gameplay-critical tables — Skills and Starship combat

Anlass: gezielter Audit-Durchgang (auf Wunsch des Nutzers) für die Tabellen, die am
Spieltisch ständig live gebraucht werden — Table 3-1 (Skills, jeder Skill-Test überhaupt)
sowie die Starship-Combat-Kerntabellen aus `08-Starships.md` (jede Weltraumschlacht). Jede
Zelle wurde erneut direkt gegen die Seitenbilder geprüft, auch wenn beide Dateien zuvor
schon als vollständig image-verifiziert galten.

Geprüfte Tabellen und Ergebnis:

- **Table 3-1** (Skills, alle 48 Zeilen: Type/Characteristic/Descriptor), PDF 79/Buchseite 75:
  **unverändert, zellengenau bestätigt.** Alle 48 Skills stimmen exakt mit der Quelle überein.
- **Die acht Hull-Statblöcke** (Baseline Characteristics + Weapon Capacity: Jericho-class
  Pilgrim Vessel, Vagabond-class Merchant Trader, Hazeroth-class Privateer, Havoc-class
  Merchant Raider, Sword-class Frigate, Tempest-class Strike Frigate, Dauntless-class Light
  Cruiser, Lunar-class Cruiser), PDF 199–200/Buchseiten 195–196: **unverändert, alle 8 zu
  100 % korrekt.**
- **Table 8-4** (Lances and Macrobatteries — Strength/Damage/Crit Rating/Range für alle 8
  Weapon Components), PDF 206/Buchseite 202: **unverändert, bereits korrekt** — inklusive
  Ryza Pattern Plasma Battery Power 7 (bestätigt gegen die eigentliche Waffenwerte-Tabelle
  8-4). Hinweis: Die separate Zusammenfassungstabelle 8-5 auf PDF 208/Buchseite 204 druckt
  für dieselbe Waffe abweichend Power 8 — ein echter Druckfehler im Quellbuch zwischen den
  beiden Tabellen. `08-Starships.md` übernimmt bewusst nur den Wert aus der eigentlichen
  Waffentabelle 8-4 (Power 7) und dupliziert die Waffenwerte nicht in der Komponentenliste,
  wodurch dieser Druckfehler dort gar nicht erst auftreten kann.
- **Table 8-9** (NPC Crew Ratings), PDF 219/Buchseite 214: unverändert, bereits korrekt.
- **Table 8-10** (Manoeuvre Actions) und **Table 8-11** (Extended Actions), PDF 221/Buchseite
  217: unverändert, alle Tests (Challenging/Hard/Difficult/Opposed) und Skill-Zuordnungen
  bestätigt korrekt.
- **Table 8-12** (Critical Hits, alle 12 Zeilen inkl. Space Hulk/Plasma Drive Explosion/Warp
  Drive Explosion), PDF 223/Buchseite 219: **kleine Lücke geschlossen.** Bei "Catastrophic
  Damage" (Wurf 11) fehlte der Buchhinweis, dass ein Schiff ohne Warp Drive bei einer 10 statt
  einer Warp-Drive-Explosion eine Plasma-Drive-Explosion erleidet.

**Ergebnis:** Nur ein kleiner Lückenfund (Table 8-12, fehlender Sonderfall-Hinweis bei
Catastrophic Damage), plus Dokumentation eines bereits im Quellbuch selbst vorhandenen
Druckfehlers zwischen den Tabellen 8-4 und 8-5 (Ryza Pattern Plasma Battery Power 7 vs. 8),
der in der Markdown-Datei durch die gewählte Struktur ohnehin nicht auftritt. Alle anderen
geprüften Tabellen (3-1 komplett, alle 8 Hull-Statblöcke, Table 8-4, 8-9, 8-10, 8-11) sind
zellengenau gegen die Quellbilder bestätigt korrekt. Beide Dateien (`03-Skills.md` und
`08-Starships.md`) enthalten jetzt einen zusätzlichen Abschnitt "Final Audit (gameplay-critical
tables)" mit derselben Auflistung auf Englisch.

---

## 5. Nächster Schritt

**Kapitel V, VI, VII und VIII sind vollständig gegengeprüft (PDF 113–232, 120/120 Seiten).**
Kapitel VIII (`08-Starships.md`) war dabei das mit Abstand fehlerreichste bisher — siehe
Zusammenfassung in Abschnitt 4 und vollständiges Log in Abschnitt 4d.

**Kapitel IX (`09-Playing-The-Game.md`, PDF 233–288) ist nun inhaltlich vollständig erfasst**
(Ersttranskription, siehe Log 4e). Die Critical-Effect-Tabellen 9-11 bis 9-26 sollten bei
Gelegenheit noch am Seitenbild nachverifiziert werden.

Weiter mit den restlichen noch offenen Kapiteln in gleicher Weise (Ersterfassung aus
OCR/Bild, da bislang nur Platzhalter): **Kapitel X (The Game Master, PDF 289–304),
XI (The Imperium, PDF 305–322), XII (Rogue Traders, PDF 323–338), XIII (The Koronus
Expanse, PDF 339–366), XIV (Adversaries & Aliens/Traits/Mutations/Allies-Enemies-Rivals,
PDF 367–382), XV (Into the Maw, PDF 383–397), Index/Charakterbogen/Rückseite (PDF 398–408)**,
sowie `00-Foreword.md` (PDF 1–15, ebenfalls noch Platzhalter). Nach jeder Seite wird ein
Log-Eintrag in einem neuen Abschnitt (4f, 4g, …) ergänzt.

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
