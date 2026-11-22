@AGENTS.md

## Zusätzlich für Claude Code

- **Zwei Datenbanken:** `data/db.sqlite3` ist nur die Dev-DB. Das Portal auf
  http://127.0.0.1:8000 (Container `wissensdatenbank-portal-1`) nutzt das
  Volume `portal-data`. Echte Spieldaten dort ändern:
  `docker compose exec -T portal python manage.py shell ...`, vorher
  `scripts/backup.ps1 -Destination <Ordner>`.
- **Deployen:** mit `/deploy` (Skill `.claude/skills/deploy`): build → backup →
  migrate mit dem neuen Image → `up -d` → `/healthz/` muss 200 liefern.
- **CSP:** Keine Fremdbibliothek, die `<style>` einfügt oder `eval` nutzt.
  Vendored-Code liegt in `static/vendor/` und ist per SHA-256 in
  `core/tests/test_security_headers.py` fixiert.
- **Flaky unter Last:** Fällt in der vollen Suite ein einzelner e2e-Test aus,
  die Datei einzeln wiederholen, bevor man den Code verdächtigt.
- **Zeilenenden:** Viele Dateien haben CRLF und sollen es behalten.
