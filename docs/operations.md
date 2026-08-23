# Operations Guide: Proxmox Deployment

This guide covers running the Rogue Trader portal in production behind a
reverse proxy on Proxmox, plus the day-two operations (backups, restores,
account recovery, log inspection) that keep it running.

The portal itself never terminates TLS and never claims a public domain
name — a reverse proxy in front of it does both. This guide assumes that
proxy is already chosen (e.g. Caddy, Traefik, nginx) and focuses on what
the portal needs from it.

## 1. Network topology: same host vs. a separate Proxmox guest

The container's HTTP port is bound to `127.0.0.1` by default
(`APP_BIND_ADDRESS` in `.env`), which only works if the reverse proxy runs
**on the same host** as the portal container (loopback-only, unreachable
from the network).

If the reverse proxy instead runs in a **different Proxmox guest** (its
own VM/LXC container), the portal needs to listen on this guest's internal
network address instead of loopback:

1. Give this guest a private, non-publicly-routable address on the same
   internal Proxmox network/bridge as the proxy guest (e.g. `10.0.0.5`).
2. Set `APP_BIND_ADDRESS=10.0.0.5` in `.env` so `docker compose` publishes
   the port on that address instead of `127.0.0.1`.
3. On this guest's firewall, restrict inbound access on port 8000 to the
   proxy guest's address only (see §3). Never bind `0.0.0.0` and rely on
   the firewall alone as the only control — bind to the specific private
   address first.

In both layouts, the portal only ever sees traffic that already came
through the proxy.

## 2. Required proxy headers

The reverse proxy MUST forward three things on every request, or the portal
will misbehave (wrong CSRF validation, wrong `request.build_absolute_uri`
results, infinite HTTPS redirect loops, or all clients sharing one login
throttle):

- **`Host`**: the original hostname the browser requested (e.g.
  `rogue-trader.example.com`), unmodified. Do not have the proxy rewrite
  this to the portal's internal address.
- **`X-Forwarded-Proto`**: `https` when the browser's original connection
  to the proxy was HTTPS. `config/settings.py` sets
  `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`, so
  Django trusts this header (and only this header) to decide whether a
  request is secure. Never expose the portal's port directly to anything
  that isn't this trusted proxy, or a client could forge this header and
  bypass HTTPS enforcement.
- **`X-Real-IP`**: the single client address seen by the trusted reverse
  proxy. The proxy MUST overwrite this header from its actual peer address;
  it must never append to or preserve a browser-supplied value. The portal
  accepts exactly one valid IPv4 or IPv6 address, normalizes it for login
  throttling and audit logs, and falls back to the direct proxy peer address
  when the header is missing or invalid. It deliberately does not parse a
  comma-separated forwarding chain.

Example nginx proxy fragment:

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;  # or the guest's private address
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Real-IP $remote_addr;
}
```

## 3. TLS and firewalling

- **TLS terminates at the proxy.** The portal container never holds a
  certificate and never speaks HTTPS itself; it trusts the proxy's
  `X-Forwarded-Proto` header instead (see §2).
- **Firewall the portal's port to the proxy's source address only.**
  Whether same-host (loopback already achieves this) or a separate guest
  (firewall rule allowing only the proxy guest's address on port 8000),
  nothing else should ever be able to reach the portal directly.
- Once the proxy is verified to serve HTTPS correctly end-to-end, set
  `ENABLE_HSTS=1` in `.env` and redeploy (see §5). This turns on a
  one-year `Strict-Transport-Security` header. Because browsers cache HSTS
  aggressively and it's hard to undo, verify HTTPS works first with
  `ENABLE_HSTS=0`, then flip it on.

## 4. First-time setup

1. Copy the example environment file and fill in real values:

   ```powershell
   Copy-Item .env.example .env
   ```

   Edit `.env` and set at minimum:
   - `DJANGO_SECRET_KEY` — a long random value (see the generator command
     in `.env.example`). The placeholder value is rejected on startup
     whenever `DJANGO_DEBUG=false`.
   - `DJANGO_ALLOWED_HOSTS` — the exact hostname(s) the proxy forwards as
     `Host`, comma-separated. Also required (no default) in production.
   - `PUBLIC_BASE_URL` — the full public URL including scheme, e.g.
     `https://rogue-trader.example.com`. This is also used to derive
     `CSRF_TRUSTED_ORIGINS`.
   - `APP_BIND_ADDRESS` — per §1.

   `.env` is untracked (git-ignored) and must never be committed.

2. Build and start the container:

   ```powershell
   docker compose up -d --build
   ```

3. **Migrations do not run automatically.** Run them explicitly after the
   first boot and after every deploy that ships new migrations (safe to
   run every time — it is a no-op when there is nothing pending):

   ```powershell
   docker compose exec portal python manage.py migrate
   ```

4. Bootstrap the first portal administrator (a non-superuser account with
   `is_portal_admin=True`, distinct from Django's own superuser concept):

   ```powershell
   docker compose exec portal python manage.py bootstrap_admin --username <name>
   ```

   This prompts for a password interactively (or pass `--password`, not
   recommended outside of scripted, throwaway test environments since
   shell history and process listings can capture it).

5. Confirm the container is healthy:

   ```powershell
   docker compose ps
   Invoke-RestMethod http://127.0.0.1:8000/healthz/
   ```

   `/healthz/` returns `{"status": "ok", "database": "ok"}` and requires
   no login; the Dockerfile's `HEALTHCHECK` polls the same endpoint.

## 5. Routine deploys

For any subsequent code change:

```powershell
docker compose up -d --build
docker compose exec portal python manage.py migrate
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/healthz/
```

## 6. Account recovery

There is no self-service "forgot password" flow. If a user (including a
portal admin) is locked out:

1. An existing portal admin can reset the affected account from the
   admin-facing account management UI (see the accounts app), which sets
   `must_change_password` so the user is forced to pick a new password on
   next login.
2. If no portal admin account is usable either, an operator with shell
   access can reset a password directly:

   ```powershell
   docker compose exec portal python manage.py changepassword <username>
   ```

   Both the assignment above and any password entered here should be
   communicated to the user out-of-band and changed on first login — the
   portal never logs password or session values (see §8), so there is no
   way to recover a forgotten password from logs.
3. If no portal admin exists at all (e.g. lost during a disaster
   recovery), create a fresh one with `bootstrap_admin` as in §4 step 4.

## 7. Backups

`scripts/backup.ps1` takes a consistent snapshot of the live SQLite
database without stopping the container, using SQLite's online backup API
(the same mechanism as the `.backup` dot-command) so a snapshot in
progress never sees a half-written page. It then verifies
`PRAGMA integrity_check` against the copy and writes a manifest with a
SHA-256 checksum next to it.

```powershell
.\scripts\backup.ps1 -Destination D:\backups\rogue-trader-portal
```

This writes `db-<UTC timestamp>.sqlite3` and a matching
`.manifest.json` into the given directory. The destination directory must
already exist — the script deliberately does not create directory trees
or guess a location on your behalf.

**Schedule:** run this at least daily via Windows Task Scheduler /
`cron` / a Proxmox host cron job, pointed at storage outside the Proxmox
guest running the portal (e.g. a separate backup target, NAS, or Proxmox
Backup Server dataset) so a lost guest does not also lose its backups.
Retain enough history to recover from a slow-to-notice data problem, not
just the most recent crash.

## 8. Restore rehearsal

Practice this periodically against disposable test data, not only when a
real incident happens.

`scripts/restore.ps1` requires the container to be **stopped** first
(restoring into a database the app is actively writing to would corrupt
it):

```powershell
docker compose stop portal
.\scripts\restore.ps1 -BackupFile D:\backups\rogue-trader-portal\db-20260101-020000.sqlite3
docker compose up -d portal
```

The script:

1. Refuses to run if the service is still reported as running.
2. Recomputes the backup file's SHA-256 and compares it against its
   `.manifest.json` — refuses to proceed on a mismatch.
3. Runs `PRAGMA integrity_check` against the backup file itself, via a
   disposable one-off container (this works even with the service
   stopped).
4. Copies whatever database currently exists in the volume to
   `db.sqlite3.recovery-<UTC timestamp>` *before* touching anything, so a
   bad restore is itself always reversible. This recovery copy is never
   deleted automatically — remove it yourself once you've confirmed the
   restore is good.
5. Only then copies the validated backup over the live database.

After `docker compose up -d portal`, confirm `/healthz/` and spot-check
recently restored content before considering the rehearsal (or a real
recovery) complete.

## 9. Logs

```powershell
docker compose logs --no-color -f portal
```

`config/settings.py` configures `django.request` (technical errors) and
`django.security` (security-relevant middleware events) to log to the
container's console, which `docker compose logs` captures. The dedicated
`accounts.audit` logger records login success, login failure, throttle blocks,
and managed-account create, update, deactivate, reactivate, and password-reset
actions. Those records contain only the event kind, relevant username(s), and
the normalized client source address for login events. Passwords, password
fields, session identifiers/cookies, CSRF tokens, character or ship field
values, and sheet contents are never logged.

## 10. Restart after Markdown edits

The Wiki content served under `WIKI_CONTENT_ROOT` is read from the
repository's Markdown source files at process start. After editing any of
those Markdown files, restart the container so the new content is picked
up:

```powershell
docker compose restart portal
```

This does not require a rebuild (`--build`) unless the Dockerfile or
Python dependencies also changed — only the running process needs to
re-read the files.
