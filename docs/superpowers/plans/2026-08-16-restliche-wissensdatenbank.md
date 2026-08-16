# Restliche Wissensdatenbank Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Das vollständige Rogue Trader Core Rulebook mit dem gesamten gedruckten
Inhaltsverzeichnis und den Nachschlagedaten aller 408 PDF-Seiten in deutschsprachige,
regelgetreue Markdown-Nachschlagewerke überführen und seitenweise gegenprüfen.

**Architecture:** Jedes Regelbuchkapitel erhält genau eine nummerierte Markdown-Datei. Die Seitenbilder sind die maßgebliche Quelle; automatisches OCR dient nur als Rohentwurf und jede Tabelle, Zahl und Sonderregel wird visuell gegengeprüft. `00-FORTSCHRITT.md` bleibt die zentrale Übergabe- und Vollständigkeitskontrolle.

**Tech Stack:** Markdown, extrahierte JPEG-Seitenbilder, lokales OCR soweit verfügbar, visuelle PDF-Prüfung.

## Global Constraints

- Inhalte ausschließlich aus `737639872-Rogue-Trader-Core-Rulebook.pdf` übernehmen.
- Fließtext Deutsch; englische Regelbegriffe beibehalten.
- Werte, Tabellen, Voraussetzungen und Kosten exakt übernehmen.
- Originale Buchseitenverweise beibehalten.
- Reine Flavour-Listen ohne Regelwirkung dürfen gekennzeichnet zusammengefasst werden.
- Nach jedem Kapitel Seitenbereich und Folgeseite in `00-FORTSCHRITT.md` aktualisieren.
- Nach jeder vollständig abgeschlossenen Plan-Aufgabe `00-FORTSCHRITT.md` um Ergebnis, Prüfstand und nächsten Schritt erweitern.

### Task 0: Gesamtumfang und Frontmatter

**Files:**
- Create: `00-Inhaltsverzeichnis-und-Einleitung.md`
- Modify: `00-FORTSCHRITT.md`

- [x] OCR- und Seitenbildbestand für PDF 1–408 vollständig herstellen.
- [x] PDF 1–15 einzeln visuell prüfen und zuordnen.
- [x] Das vollständige gedruckte Inhaltsverzeichnis mit allen Unterpunkten erfassen.
- [x] Bibliografische Daten, Kartenübersicht, Einleitung und Würfelregeln erfassen.
- [x] Kapitel I, PDF 16–38, vollständig gegenprüfen und erkannte Lücken schließen.

---

### Task 1: Extraktions- und Prüfverfahren

**Files:**
- Modify: `00-FORTSCHRITT.md`
- Source: `../737639872-Rogue-Trader-Core-Rulebook.pdf`
- Source images: temporärer `scratchpad/img/pageNNN_0.jpg`-Bestand

- [x] Prüfen, ob sämtliche Seitenbilder 113–408 vorhanden und lesbar sind.
- [x] Lokal verfügbare OCR-Werkzeuge ermitteln und einen Rohtext für die relevanten Seiten erzeugen.
- [x] Kapitelgrenzen anhand der tatsächlichen Titelseiten statt der alten Schätzwerte bestimmen.
- [x] OCR-Ausgaben stets gegen Seitenbilder prüfen; nicht lesbare Zahlen direkt visuell erfassen.

### Task 2: Kapitel V – Armoury

**Files:**
- Create: `05-Armoury.md`
- Modify: `00-FORTSCHRITT.md`

- [x] Availability, Population, Time und Acquisition-Regeln mit sämtlichen Tabellen erfassen.
- [x] Craftsmanship, Weapon-Regeln, Weapon Qualities und alle Weapon Tables erfassen.
- [x] Armour, Gear, Drugs, Cybernetics und Sonderregeln erfassen.
- [x] Kapitelende und Beginn von Kapitel VI visuell prüfen.

### Task 3: Kapitel VI–VIII

**Files:**
- Create: `06-Psychic-Powers.md`
- Create: `07-Navigator-Powers.md`
- Create: `08-Starships.md`
- Modify: `00-FORTSCHRITT.md`

- [x] Psychic-Power-Grundregeln, Phenomena/Perils und alle Disciplines/Techniques erfassen.
- [x] Navigator-Grundregeln, Mutations und alle Navigator Powers erfassen.
- [x] Starship-Erschaffung, Komponenten, Werte, Kampf und alle zugehörigen Tabellen erfassen.

### Task 4: Kapitel IX–XII

**Files:**
- Create: `09-Spielregeln.md`
- Create: `10-Spielleitung.md`
- Create: `11-Das-Imperium.md`
- Create: `12-Rogue-Traders.md`
- Modify: `00-FORTSCHRITT.md`

- [ ] Tests, Combat, Damage, Healing, Movement und Environmental Rules erfassen.
- [ ] GM-Regeln, Rewards, Corruption, Insanity und Kampagnenhinweise erfassen.
- [ ] Imperiums- und Rogue-Trader-Hintergrund regelrelevant vollständig, reinen Flavour verdichtet erfassen.

### Task 5: Kapitel XIII–XV und Anhang

**Files:**
- Create: `13-Koronus-Expanse.md`
- Create: `14-Adversaries.md`
- Create: `15-Forsaken-Bounty.md`
- Create: `16-Index-und-Charakterbogen.md`
- Modify: `00-FORTSCHRITT.md`

- [ ] Orte, Fraktionen, Reise- und Abenteuerinformationen der Koronus Expanse erfassen.
- [ ] Adversary-Grundregeln, Traits, Profile, Waffen und Sonderfähigkeiten erfassen.
- [ ] Das Einführungsabenteuer strukturiert mit Szenen, Tests, Gegnern und Belohnungen erfassen.
- [ ] Index und Charakterbogen als Navigations-/Feldübersicht dokumentieren.

### Task 6: Gesamtprüfung

**Files:**
- Verify: `00-FORTSCHRITT.md`
- Verify: `01-Charaktererschaffung.md` bis `16-Index-und-Charakterbogen.md`

- [ ] Für jede PDF-Seite 1–408 eine dokumentierte Zuordnung und Erfassung nachweisen.
- [ ] Tabellenüberschriften, Würfelwerte, Boni/Mali, Reichweiten, Actions und Seitenverweise auf offensichtliche OCR-Fehler prüfen.
- [ ] Kapiteldateien auf Platzhalter und widersprüchliche Statusangaben durchsuchen.
- [ ] `00-FORTSCHRITT.md` auf 408/408 Seiten und alle Kapitel als fertig setzen.
