# Charakter-Netzwerk

Das gemeinsame Kampagnengedächtnis der Runde: die Hauptcharaktere der Spieler
und alle Figuren, denen die Gruppe begegnet ist, mit ihren Verbindungen. Es
wächst über die Sitzungen. Seite: **Netzwerk** (`/network/`), App `network/`.

## Was es gibt

- **Hauptcharaktere** sind keine eigenen Einträge, sondern der Favorit jedes
  Spielers (`CharacterSheet.is_favorite`, Stern auf Karte und Bogen). Wechselt
  ein Spieler den Favoriten, wechselt der Hauptknoten. Ihr Name kommt immer aus
  dem Bogen und ist im Netzwerk nicht bearbeitbar.
- **Figuren** (`NetworkFigure`): Name (Pflicht), Fraktion, „Getroffen in“,
  Beschreibung (mehrzeilig). Die Fraktion ist freier Text; das Formular schlägt
  vorhandene Fraktionen vor (`<datalist>`), der Graph färbt nach Fraktion.
- **Verbindungen** (`NetworkLink`): gerichtet und mit Beziehungsart (Pflicht),
  gelesen „Von → Beziehung → Zu“, z. B. „Kara → Schwester von → Elias“. Jedes
  Ende ist eine Figur oder ein Charakterbogen (je genau eins, per
  Check-Constraint). Löscht man ein Ende, verschwindet die Verbindung mit.
- **Verlauf** (`NetworkChange`): jedes Anlegen, Ändern und Löschen von Figuren
  und Verbindungen mit Nutzer, Zeitpunkt und Text-Schnappschuss (`/network/history/`).

Beim Anlegen einer Figur gibt es das Auswahlfeld „Verbindung zu“: zuerst
„keine“, dann die Hauptcharaktere, dann die Nebenfiguren. „keine“ ist erlaubt;
wählt man jemanden, ist die Beziehung Pflicht. Weitere Verbindungen fügt man
auf der Detailseite der Figur oder über „Neue Verbindung“ hinzu. Auswählbar
sind nur Hauptcharaktere (Favoriten) und Figuren. Eine Verbindung zu einem
Charakter, der nicht mehr Favorit ist, bleibt bestehen; der Graph zeigt ihn
dann als kleinen, gedämpften Knoten.

## Rechte und Privatsphäre

- Jeder angemeldete Nutzer sieht und bearbeitet das ganze Netzwerk, auch
  Figuren, die andere angelegt haben (wie beim gemeinsamen Schiff).
- Von Hauptcharakteren zeigt das Netzwerk nur **Name und Spieler**. Die Werte
  des Bogens (`values`) werden nie geladen (`network.nodes.main_characters`
  lädt nur die nötigen Spalten). Den Link zum Bogen bekommt nur dessen Besitzer.
- Alle Schreibzugriffe laufen über `network/services.py`, damit der Verlauf nicht
  übersprungen werden kann.

## Darstellung

- `static/js/network-graph.js` lädt `/network/graph.json` und zeichnet mit
  vis-network (`static/vendor/vis-network/`, Herkunft und Update-Hinweise in der
  dortigen `README.md`). Klick auf einen Knoten füllt das Seitenpanel,
  Doppelklick öffnet die Seite der Figur bzw. den eigenen Bogen.
- Es wird der *peer*-Build verwendet: der *standalone*-Build fügt sein CSS per
  `<style>` ein, was die CSP (`style-src 'self'`) blockiert.
  `tests/e2e/test_network_graph.py` prüft, dass die Seite ohne CSP-Verstoß zeichnet.
- Texte vom Server landen nur über `textContent` im DOM; Knotenbeschriftungen
  zeichnet vis-network auf das Canvas.
- Ohne JavaScript zeigt die Seite dieselben Inhalte als Liste.
