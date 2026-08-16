# Rogue-Trader-Wissensportal und Charakterverwaltung

## Ziel

Eine öffentlich erreichbare, in Docker betriebene Webanwendung verbindet die vorhandene Rogue-Trader-Wissensdatenbank mit originalgetreuen digitalen Bögen. Mehrere vom Administrator angelegte Nutzer verwalten jeweils mehrere eigene Charaktere. Normale Nutzer sehen ausschließlich ihre eigenen Charaktere; der Administrator darf alle Charaktere ansehen, fremde Charaktere jedoch weder bearbeiten noch löschen. Zusätzlich existiert zunächst ein gemeinsamer Raumschiffbogen, den alle angemeldeten Nutzer ansehen und bearbeiten dürfen. Das Datenmodell unterstützt später mehrere gemeinsame Raumschiffe ohne Schemaänderung.

Die Anwendung ist für eine private Spielrunde auf einem Proxmox-Server ausgelegt. Es gibt keine öffentliche Registrierung, keinen anonymen Zugriff und in der ersten Version keinen regelgeführten Charaktergenerator.

## Architektur

- Ein Django-Monolith rendert Seiten serverseitig. Kleine dynamische Interaktionen und feldweises Speichern erfolgen mit lokal ausgeliefertem HTMX und minimalem JavaScript.
- Ein Docker-Compose-Service enthält Webanwendung und SQLite-Laufzeit. Eine einzelne Instanz genügt für die erwartete private Spielrunde.
- Die SQLite-Datenbank liegt in einem persistenten Volume beziehungsweise Host-Mount.
- Die Markdown-Dateien werden schreibgeschützt in den Container gemountet. Sie bleiben die alleinige Quelle der Wiki-Inhalte und werden nicht in die Nutzerdatenbank kopiert.
- Beim Start liest die Anwendung die explizit konfigurierten Inhaltsdateien ein, zerlegt sie anhand ihrer Überschriften in Abschnitte und erzeugt einen In-Memory-Suchindex. Änderungen an Markdown-Dateien werden nach einem Container-Neustart sichtbar.
- Arbeitsdateien wie `00-FORTSCHRITT.md`, OCR-Rohtexte, Pläne und temporäre Dateien werden nicht indexiert. Die zulässigen Wiki-Dateien werden über eine geordnete Allowlist konfiguriert.
- Die PDF-Seiten 401 und 402 bilden die beiden Charakterseiten; PDF-Seite 403 bildet den Raumschiffbogen. Sie werden einmalig in hochauflösende, webtaugliche Hintergrundbilder extrahiert. Seite 403 wird für die Darstellung ins Querformat gedreht. Der vollständige PDF-Inhalt wird nicht an Browser ausgeliefert.
- Eine versionierte Feldschema-Datei definiert pro Bogen und Feld eine stabile ID, den Typ `text` oder `checkbox` sowie Position und Größe als prozentuale Koordinaten relativ zur Originalseite. Dadurch bleiben Hintergrund und Eingaben bei jeder Zoomstufe deckungsgleich.

## Konten und Berechtigungen

### Rollen

- **Nutzer:** Kann eigene Charaktere anlegen, ansehen, bearbeiten und löschen. Abfragen und Mutationen werden serverseitig immer auf die eigene Nutzer-ID eingeschränkt.
- **Administrator:** Kann Konten anlegen, deaktivieren, reaktivieren und ein temporäres Passwort vergeben. Er kann alle Charaktere in einer schreibgeschützten Ansicht öffnen. Schreib- und Löschendpunkte akzeptieren auch für Administratoren ausschließlich Charaktere, deren Eigentümer sie selbst sind.
- **Gemeinsame Raumschiffe:** Jeder angemeldete Nutzer darf alle gemeinsamen Raumschiffbögen ansehen und feldweise bearbeiten. In der ersten Version wird genau ein Bogen bereitgestellt; die Oberfläche zum Anlegen weiterer Schiffe bleibt noch deaktiviert.

Die Anwendung verwendet einen eigenen Administrationsbereich und stellt Charaktermodelle nicht zur Bearbeitung über Djangos Standard-Admin bereit. Der Schutz gilt innerhalb der Website; ein Betreiber mit direktem Zugriff auf Server und SQLite-Datei kann die gespeicherten Daten technisch lesen.

### Anmeldung

- Es gibt keine Selbstregistrierung.
- Der erste Administrator wird einmalig über einen Django-Management-Befehl im laufenden Container angelegt.
- Vom Administrator angelegte Konten erhalten ein temporäres Passwort und müssen es beim ersten Login ändern.
- Deaktivierte Konten verlieren ihre aktiven Sitzungen und können sich nicht erneut anmelden.
- Sitzungen verwenden sichere, HTTP-only Cookies. In Produktion sind HTTPS, sichere Cookies, CSRF-Schutz, korrekte Proxy-Header und eine explizite Domain-Allowlist verpflichtend.
- Wiederholte fehlgeschlagene Anmeldungen werden pro Konto und Quelladresse zeitlich gedrosselt, ohne erkennen zu lassen, ob ein Benutzername existiert.

## Wissensdatenbank

- Eine Kapitelansicht zeigt die Wiki-Dateien in der festgelegten Buchreihenfolge.
- Markdown-Überschriften erzeugen eine Abschnittsnavigation und stabile, URL-taugliche Sprungmarken.
- Tabellen, Listen, Hervorhebungen und interne Links werden unterstützt; eingebettetes Roh-HTML wird nicht ausgeführt.
- Die globale Suche durchsucht Überschriften und Fließtext aller Wiki-Abschnitte. Überschriftentreffer werden höher gewichtet. Ergebnisse zeigen Kapitel, Abschnitt, einen kurzen hervorgehobenen Ausschnitt und einen direkten Link zur Fundstelle.
- Leere beziehungsweise noch nicht ausgearbeitete Kapitel erscheinen in der Navigation mit einem klaren Hinweis, ohne die Anwendung oder Suche zu beeinträchtigen.
- Eine fehlerhafte einzelne Markdown-Datei wird protokolliert und als nicht verfügbar markiert; alle übrigen Kapitel bleiben nutzbar.

## Originalgetreue Bögen

### Darstellung

Jeder Nutzer kann mehrere Charaktere anlegen. Ein Charakter besitzt eine stabile ID, einen Eigentümer, Erstellungs- und Änderungszeitpunkt, eine Versionsnummer und Feldwerte für die beiden Originalseiten 401 und 402. Die Seiten werden in ihrer vollständigen Originalgestaltung angezeigt; es wird kein neues Raster und keine alternative Formularansicht darübergelegt.

Interaktiv sind ausschließlich die bereits vorgedruckten Eingabebereiche:

- Jede leere Linie und jedes rechteckige Wertefeld erhält ein transparentes Texteingabefeld exakt über der Druckposition.
- Jedes vorgedruckte kleine Kästchen oder jeder Markierungskreis erhält eine deckungsgleiche Checkbox.
- Überschriften, Beschriftungen, Illustrationen, Rahmen, Tabellenlinien und alle anderen Druckelemente bleiben vollständig nicht interaktiv.
- Eingabetext verwendet eine gut lesbare dunkle Schrift, bleibt innerhalb des vorgedruckten Bereichs und verändert weder dessen Größe noch die Seitengeometrie.
- Fokus, Tastaturnavigation und ein dezenter Fokusindikator machen Felder bedienbar, ohne das Original im Ruhezustand sichtbar zu verändern.

Die Feldwerte werden als typisierte Schlüssel-Wert-Daten anhand stabiler Schema-IDs gespeichert. Textfelder akzeptieren nur Text bis zur je Feld festgelegten Maximallänge; Checkboxen speichern ausschließlich Wahrheitswerte. Nicht im aktiven Feldschema vorhandene Schlüssel werden vom Server abgewiesen.

### Gemeinsamer Raumschiffbogen

PDF-Seite 403 wird nach demselben Overlay-Prinzip als querformatiger Raumschiffbogen umgesetzt. Das System legt initial genau einen gemeinsamen Bogen an. Alle angemeldeten Nutzer dürfen ihn lesen und bearbeiten; jede Feldänderung speichert Nutzer, Zeitpunkt, alten Wert und neuen Wert in einem Änderungsprotokoll. Die Datenbankstruktur verwendet bereits ein eigenständiges `ShipSheet`-Objekt, sodass später mehrere Schiffe angelegt werden können, ohne bestehende Daten umzubauen.

### Speichern und Konflikte

Textfelder werden nach kurzer Eingabepause oder beim Verlassen des Feldes gespeichert; Checkboxen unmittelbar nach dem Umschalten. Jede Anfrage übermittelt Feld-ID, Wert und zuletzt bekannte Bogenversion. Änderungen an unterschiedlichen Feldern werden zusammengeführt. Wurde dasselbe Feld seit der geladenen Version bereits verändert, antwortet der Server mit einem Konflikt und dem aktuellen Wert; die Oberfläche überschreibt nichts automatisch und lässt den Nutzer zwischen aktuellem und eigenem Wert wählen.

## Oberfläche

- Visuelle Richtung: **Brücken-Hybrid** mit dunklem Blaugrün, Messing- und Goldakzenten, klaren Konsolenflächen und zurückhaltender Rogue-Trader-Atmosphäre.
- Startseite: **Doppelte Kommandozentrale** mit globaler Suche sowie gleichwertigen Einstiegen in Lexikon und eigene Charaktere.
- Desktop: feste linke Hauptnavigation und kompakte Kopfleiste mit Suche, aktivem Charakter und Kontomenü.
- Die Originalbögen erscheinen in einem neutralen Arbeitsbereich mit Umschaltung zwischen Seite 1, Seite 2 und Raumschiff. Eine kompakte Werkzeugleiste enthält ausschließlich Seitenwahl, Zoom, Anpassung an Breite beziehungsweise Seite und Speicherstatus.
- Auf kleinen Bildschirmen bleibt die Originalgeometrie erhalten. Der Nutzer zoomt und verschiebt den Bogen; Felder werden nicht umsortiert und es gibt keine abweichende mobile Formularansicht.
- Die Anwendung merkt sich die zuletzt verwendete Seite und Zoomstufe pro Nutzer und Bogen.
- Admins sehen zusätzlich Kontoverwaltung und eine schreibgeschützte Liste aller Charaktere; normale Nutzer sehen diese Navigation nicht.

## Betrieb und Sicherheit

- Docker Compose baut ein reproduzierbares Image, führt ausstehende Migrationen kontrolliert aus und startet die Anwendung mit einem produktionsgeeigneten WSGI-Server.
- Der HTTP-Port wird standardmäßig nur an `127.0.0.1` gebunden. Für einen Reverse Proxy in einem anderen Proxmox-Gast kann die Bind-Adresse explizit per Umgebungsvariable auf das interne Netz gesetzt werden.
- Ein vorgeschalteter Reverse Proxy stellt Domain und HTTPS bereit und übermittelt den ursprünglichen Host sowie das HTTPS-Schema.
- Geheimschlüssel, erlaubte Hosts, öffentliche Basis-URL und Bind-Adresse kommen aus einer nicht eingecheckten `.env`-Datei. Eine `.env.example` dokumentiert alle erforderlichen Werte ohne Geheimnisse.
- Ein Healthcheck prüft einen nicht authentifizierungspflichtigen Endpunkt, der nur Prozess- und Datenbankbereitschaft meldet.
- Die Datenbank wird regelmäßig gesichert. Die Betriebsdokumentation enthält Befehle für Backup, Wiederherstellung, Migration, Admin-Bootstrap und Markdown-Neuindexierung per Neustart.
- Anmeldeversuche, Kontenverwaltung und technische Fehler werden protokolliert. Passwörter, Sitzungswerte und Charakterinhalte erscheinen nicht in Logs.

## Fehlerbehandlung

- Formularfehler bewahren alle Eingaben und markieren die betroffenen Felder.
- Nicht vorhandene oder nicht berechtigte Charakter-IDs liefern dieselbe neutrale Nicht-gefunden-Antwort, damit fremde IDs nicht bestätigt werden.
- Unbekannte, falsch typisierte oder zu lange Feldwerte werden abgewiesen, ohne vorhandene Werte zu verändern.
- Feldkonflikte zeigen beide Werte und überschreiben keine fremde Änderung automatisch.
- Bei Datenbankfehlern zeigt die Anwendung eine neutrale Fehlermeldung und protokolliert die technische Ursache serverseitig.
- Ein Fehler beim Indexieren eines Kapitels beeinträchtigt weder Charakterverwaltung noch andere Wiki-Kapitel.

## Tests und Abnahme

Automatisierte Tests prüfen:

- Login, Logout, sicheren Passwortwechsel und erzwungenen Wechsel beim ersten Login
- Kontoanlage, Deaktivierung, Reaktivierung und Zurücksetzen auf ein temporäres Passwort
- vollständige Mandantentrennung zwischen normalen Nutzern
- schreibgeschützte Sicht des Administrators auf fremde Charaktere
- Anlage, Bearbeitung, Löschung und parallele Änderung eigener Charaktere
- Rechte und Änderungsprotokoll des gemeinsamen Raumschiffbogens
- Feldschema-Validierung, Typen, Längenlimits und Zurückweisung unbekannter Feld-IDs
- pixelgenaue Zuordnung der Overlay-Felder bei mehreren Zoomstufen
- visuelle Regression der zwei Charakterseiten und des gedrehten Raumschiffbogens gegenüber den extrahierten Originalseiten
- Markdown-Rendering, stabile Abschnittsanker, Allowlist und fehlerhafte Kapitel
- Volltextsuche, Gewichtung und direkte Trefferlinks
- sichere Antworten für fehlende und fremde Charakter-IDs
- Healthcheck, Migrationen und Neustart mit persistenter Datenbank

Die manuelle Abnahme umfasst:

1. Admin anlegen und zwei normale Konten erstellen.
2. Mit beiden Konten mehrere Charaktere anlegen und gegenseitige Unsichtbarkeit prüfen.
3. Als Admin alle Charaktere ansehen und erfolglose Änderungs- beziehungsweise Löschversuche bestätigen.
4. Mit beiden Konten den gemeinsamen Raumschiffbogen bearbeiten, Protokollierung und Konfliktanzeige prüfen.
5. Wiki-Kapitel, Abschnittsnavigation und Suche prüfen.
6. Deckungsgleichheit aller interaktiven Linien, Wertefelder, Kästchen und Kreise auf Desktop und Smartphone sowie bei mehreren Zoomstufen prüfen.
7. Container neu erstellen und Persistenz von Konten, Charakter- und Raumschiffdaten bestätigen.
8. Backup wiederherstellen und die Anwendung mit den wiederhergestellten Daten starten.

## Abgrenzungen der ersten Version

- kein öffentlicher oder anonymer Zugriff
- keine Selbstregistrierung, E-Mail-Einladungen oder E-Mail-Passwortwiederherstellung
- kein geführter oder automatisch regelvalidierter Charaktergenerator
- keine alternative, neu gestaltete oder responsive Formularansicht für Charakter- und Raumschiffbögen
- keine Bearbeitung der Markdown-Wissensdatenbank im Browser
- keine Live-Cursor oder gleichzeitige Echtzeitdarstellung fremder Eingaben; Konflikte werden beim Speichern erkannt
- kein PDF-Export und keine externe API
