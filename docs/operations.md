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

The reverse proxy MUST forward these on every request, or the portal will
misbehave (wrong CSRF validation, wrong `request.build_absolute_uri` results,
infinite HTTPS redirect loops, or all clients sharing one login throttle):

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
- **The client address**, in one header the proxy *sets itself* (see the
  recipes below) -- plus the setting that tells the portal which peer may
  be believed:

  | Variable | Default | Meaning |
  | --- | --- | --- |
  | `TRUSTED_PROXY_IPS` | empty | Comma-separated IPs/CIDRs of the proxy **as the container sees it** (the direct peer, `REMOTE_ADDR`). |
  | `TRUSTED_PROXY_HEADER` | `x-real-ip` | `x-real-ip` (one address the proxy overwrites) or `x-forwarded-for` (the rightmost entry that is not itself a trusted proxy). |

  **By default the portal ignores both headers** and uses the direct peer
  address for the login throttle and the audit log. Only when the peer is
  listed in `TRUSTED_PROXY_IPS` is the configured header believed (a missing
  or malformed header falls back to the peer). Only the one configured
  header is ever read, so a client cannot smuggle an address through the
  other one. If you leave `TRUSTED_PROXY_IPS` empty behind a proxy, nothing
  breaks, but every player then shares the proxy's address for the
  per-address login limit (see section 11) and the audit log shows the
  proxy's address; `manage.py check --deploy` warns about this
  (`accounts.W001`).

Set both variables in `.env` (and pass them through in `compose.yaml`'s
`environment:` block, like `PUBLIC_BASE_URL`).

**Which value is "the proxy as the container sees it"?**

- Proxy on the **same host** as the container, port published as
  `127.0.0.1:8000:8000`: Docker NAT shows the container the compose
  network's gateway, usually in `172.16.0.0/12`. Use
  `TRUSTED_PROXY_IPS=127.0.0.1,::1,172.16.0.0/12`. Only the local proxy can
  reach the port, so trusting the whole Docker range is safe.
- Proxy in a **separate guest** (section 1): the proxy guest's address, e.g.
  `TRUSTED_PROXY_IPS=10.0.0.2`.
- Not sure? Do the smoke test below; the audit log shows what the portal
  sees as `source_ip`.

### Recipes

nginx (`X-Real-IP` mode, the default):

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;  # or the guest's private address
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Real-IP $remote_addr;   # replaces whatever the client sent
}
```

Optionally cap login attempts at the proxy as well (nginx, `http {}` level,
then inside `server {}`):

```nginx
limit_req_zone $binary_remote_addr zone=portal_login:10m rate=30r/m;

location = /account/login/ {
    limit_req zone=portal_login burst=10 nodelay;
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Real-IP $remote_addr;
}
```

Caddy (`X-Real-IP` mode, the default). Caddy sets `Host` and
`X-Forwarded-Proto` itself but does **not** set `X-Real-IP`, so add it
explicitly; `header_up` replaces any value the client sent:

```caddyfile
rogue-trader.example.com {
    reverse_proxy 127.0.0.1:8000 {
        header_up X-Real-IP {remote_host}
    }
}
```

If Caddy itself sits behind another proxy or CDN, tell it about that
(`trusted_proxies` in the global `servers` options) or `{remote_host}` is
the CDN's address.

Traefik (`X-Forwarded-For` mode). Traefik does not give you an `X-Real-IP`
you can rely on, but it replaces `X-Forwarded-*` headers from untrusted
clients and appends the real peer to `X-Forwarded-For`, which is exactly what
the portal's rightmost-untrusted rule reads. Set
`TRUSTED_PROXY_HEADER=x-forwarded-for` in `.env`. A file-provider
configuration needs nothing special (`Host` is passed through by default,
`X-Forwarded-Proto` is set by Traefik):

```yaml
http:
  routers:
    rogue-trader:
      rule: Host(`rogue-trader.example.com`)
      entryPoints: [websecure]
      tls: {}
      service: rogue-trader
  services:
    rogue-trader:
      loadBalancer:
        servers:
          - url: http://127.0.0.1:8000
```

Do not list your own trusted IPs in Traefik's `forwardedHeaders.trustedIPs`
unless the Traefik sits behind another proxy.

### Smoke test after any proxy change

1. From a machine that is **not** the proxy, send one failed login with
   forged address headers through the public URL (bash):

   ```bash
   URL=https://rogue-trader.example.com
   curl -s -o /dev/null -c jar.txt "$URL/account/login/"
   TOKEN=$(awk '$6=="csrftoken"{print $7}' jar.txt)
   curl -s -o /dev/null -b jar.txt -H "X-CSRFToken: $TOKEN" -H "Referer: $URL/account/login/"         -H "X-Real-IP: 1.2.3.4" -H "X-Forwarded-For: 5.6.7.8"         -d "username=smoke&password=x" "$URL/account/login/"
   ```

2. `docker compose logs --no-color --tail 5 portal` shows
   `login_failure username='smoke' source_ip=<your real address>`. If it shows
   `1.2.3.4` or `5.6.7.8`, the proxy is not overwriting the header; if it
   shows the proxy's/Docker gateway's address, `TRUSTED_PROXY_IPS` does not
   match the peer.

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

### Automatic daily backups

The `backup` service in `compose.yaml` runs `python manage.py backup_db` once
when it starts and then every 24 hours (a failed run is retried after an
hour). It uses the same image as the portal and mounts the `portal-data`
volume read-only, because the command only reads the live database.

- **Where:** `./backups` next to `compose.yaml` on the host (mounted as
  `/backups`, `BACKUP_DIR` inside the container), so the copies survive the
  loss of the `portal-data` volume. The directory is git-ignored. On a Linux
  host create it before the first start and make it writable for the
  container user: `mkdir backups; chown 10001 backups`.
- **Format:** `db-YYYYMMDD-HHMMSS.sqlite3`, a consistent copy made with
  SQLite's online backup API while the portal keeps running. The command runs
  `PRAGMA integrity_check` on the copy and fails (non-zero exit, copy
  deleted) if the result is not `ok`.
- **Retention:** copies older than `BACKUP_KEEP_DAYS` (default 14, env var,
  by file modification time) are deleted after each successful backup.
- **Still off-host:** `./backups` is on the same machine. Copy it to separate
  storage as described below, or the guest is still a single point of loss.

Trigger one by hand:

```powershell
docker compose run --rm backup python manage.py backup_db
# or inside the running service
docker compose exec backup python manage.py backup_db
```

Restore a copy from this folder:

```powershell
docker compose stop portal backup
docker compose cp .\backups\db-20260101-020000.sqlite3 portal:/data/db.sqlite3
docker compose up -d portal backup
```

`docker compose cp` works on a stopped container and writes into its
`/data` volume. Keep the current database aside first (copy it out with
`docker compose cp portal:/data/db.sqlite3 .`) if you are not sure the copy is
the right one. `scripts/restore.ps1` (section 8) is the checksum-verified
variant with an automatic recovery copy, but it needs the manifest written by
`scripts/backup.ps1` next to the file, which the daily copies do not have.

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
container's console, which `docker compose logs` captures.

The dedicated `accounts.audit` logger is the audit trail. It goes to the
console **and**, in production, to a size-rotating file that survives
`docker compose up -d --build` (which re-creates the container and drops its
console log): `AUDIT_LOG_FILE`, by default `logs/audit.log` next to the
database, i.e. `/data/logs/audit.log` in the `portal-data` volume. It rotates
at 5 MiB and keeps 5 old files (`audit.log.1` ... `audit.log.5`). Read it with:

```powershell
docker compose exec portal tail -n 50 /data/logs/audit.log
```

Set `AUDIT_LOG_FILE` in the environment to move it; in development
(`DJANGO_DEBUG=true`) the file is off unless that variable is set. If you ever
run gunicorn with several workers, switch rotation off or move the file to
syslog/a collector instead: rotation by several processes at once is not
safe. The `backup` service mounts `/data` read-only and never writes audit
records, so it is not affected.

What is recorded (event kind, username(s), the throttle's source address for
requests; usernames are cut at 150 characters):

- `login_success`, `login_failure`, `login_throttle_blocked`, `logout`,
  `password_changed` (the user's own change);
- `managed_account_created`, `_updated` (with `old_username`, `new_username`,
  `active`), `_deactivated`, `_reactivated`, `_password_reset`;
- `managed_account_denied` (an admin tried something the rules forbid:
  deactivating themselves, resetting their own password, deactivating the
  last active portal admin) and `admin_access_denied` (a non-admin was
  refused on a `/portal-admin/` route, with method and path);
- `bootstrap_admin_created`.

Passwords, password fields, session identifiers/cookies, CSRF tokens,
character or ship field values, and sheet contents are never logged.

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

Before restarting, `manage.py check` verifies the content tree: it fails if an
allow-listed chapter is missing or unreadable, and warns about a Markdown file
under the content root that is not served. Adding a chapter therefore means
adding it to `wiki/manifest.py` — the single source of truth for the chapter
list, its reading order, each chapter's URL slug, and its grouping on the
overview page.

`WIKI_STRICT_CONTENT` is on in the container: if the wiki loads no chapters at
all — the usual cause being a wrong or missing content mount — the process
fails to boot instead of coming up and serving an empty wiki. Note that a
missing mount does not raise on its own; each unreadable file is logged and
skipped, so the guard is the "no chapters loaded" check rather than an
exception. Losing *some* chapters is caught earlier, by `manage.py check`.

> **Action for the project owner:** `.env` still carries a
> `WIKI_CONTENT_ALLOWLIST=` line listing all chapters. It currently matches
> `wiki/manifest.py` exactly, so nothing is broken — but it pins the old list
> and will silently override future manifest changes. Delete that line from
> `.env`. (Agents are blocked from editing `.env`, so this has to be done by
> hand.)

## 11. Login protection, sessions and database locking

**Login throttle.** Three counters, each over a 15-minute window, all kept in
the database (keys are HMACs, no username or address in clear):

| Counter | Limit | Why |
| --- | --- | --- |
| username + source address | 5 failures | what a player who mistypes meets |
| username, any address | 20 failures | an attacker who rotates addresses still has a ceiling per account |
| source address, any username | 20 failures | a flood of made-up usernames stops before it costs a password hash each |

When a counter has reached its limit the attempt is refused with the same
"Benutzername oder Passwort ungültig." as any wrong password (no way to tell
"blocked" from "wrong"), and **no password hash is computed**. A block lifts
by itself after 15 minutes. Consequences to know about:

- Anyone can lock a *username* out for 15 minutes by failing 20 logins
  against it; that is the price of a ceiling that address rotation cannot
  dodge. If a player is locked out and cannot wait, clear the counters:
  `docker compose exec portal python manage.py shell -c "from accounts.models import LoginThrottle; LoginThrottle.objects.all().delete()"`.
- Players behind one shared address (one household, one NAT) share the
  per-address budget of 20. Without `TRUSTED_PROXY_IPS` (section 2) that
  is *every* player.
- The same mechanism limits wrong "current password" attempts on the
  password-change page (10 per 15 minutes per account).

**Passwords.** Argon2 is preferred; PBKDF2 stays in `PASSWORD_HASHERS` only so
old hashes still verify, and they upgrade to Argon2 on the next successful
login. Django equalises the response time of an unknown username by hashing a
dummy password with the *preferred* hasher, so unknown and Argon2 accounts
take equally long; an account whose hash is still PBKDF2 would take
measurably longer and so reveal that it exists. To check whether any such
account is left:
`docker compose exec portal python manage.py shell -c "from accounts.models import User; print(list(User.objects.exclude(password__startswith='argon2$').values_list('username', flat=True)))"`.
Reset those accounts (portal admin UI) and the question is closed.

**Sessions.** A login lasts 14 days from the *last request* (the expiry
slides, `SESSION_SAVE_EVERY_REQUEST`), so players who play regularly are not
signed out and an abandoned cookie dies after two weeks. Expired session rows
stay in the database until `manage.py clearsessions` removes them; it runs once
every time the portal container starts (the image's start command, before
gunicorn; the `backup` service mounts the data volume read-only and cannot),
and by hand:

```powershell
docker compose exec portal python manage.py clearsessions
```

**Database locking.** SQLite allows one writer at a time. The portal opens
every write transaction with `BEGIN IMMEDIATE` and waits up to 20 seconds
for the lock, so two players saving at the same moment queue up and the
second one gets the normal "someone else changed this field" conflict (409)
instead of a "database is locked" error (500). Nothing to configure.

