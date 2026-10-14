# Personal AIssistent

Pi-oriented personal hub: **single FastAPI process** as SSOT for morning briefs, personal calendar, news digests, Health Scale Hub, and Studio Climate Monitor — plus a LAN **PC web UI** in `web/`.

## Ports (conflicts resolved)

| Former service | Former port | Unified |
| --- | --- | --- |
| Health Scale Hub | **8000** | **8741** — phone paths stay `/api/...`, dashboard `/` |
| Studio Climate | **8787** | **8741** — routes under **`/climate/...`** |
| Vite PC dashboard (dev) | 5173 | Point `VITE_PI_API_BASE` at `http://<pi>:8741/climate` |

Default bind: `127.0.0.1:8741`. On a trusted LAN Pi: `PA_HOST=0.0.0.0`. **No public exposure; auth TBD.**

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m server
```

Env (`PA_` prefix): `PA_TIMEZONE` (default `Europe/Berlin`), `PA_HOST`, `PA_PORT`, `PA_DATA_DIR` (default `./data` — holds `health.db`, `climate.db`, `calendar.db`, `news.db`, `advisor/`), `PA_CLIMATE_MOCK_SENSOR` (optional bool), `PA_NEWS_SCHEDULER_ENABLED` (default true).

### Morning scale (Pi Bluetooth)

The Pi listens for the scale's BLE broadcast itself. The phone no longer measures. Listening runs only from **06:00–12:00** local time (`PA_SCALE_LISTEN_START_HOUR` / `PA_SCALE_LISTEN_END_HOUR`), and stops for the rest of the day once a measurement is already stored. `GET /api/scale` reports the current phase. Set `PA_SCALE_SCAN_ENABLED=false` to turn it off. The Pi needs BlueZ (`bluetooth` service) and the process user in the `bluetooth` group.

### AI keys (Pi only — never ship to clients)

Provider order: **Mistral → Claude → ChatGPT → Gemini** (exponential retry per provider).

| Variable | Also accepted |
| --- | --- |
| `PA_MISTRAL_API_KEY` | `MISTRAL_API_KEY` |
| `PA_ANTHROPIC_API_KEY` | `ANTHROPIC_API_KEY` |
| `PA_OPENAI_API_KEY` | `OPENAI_API_KEY` |
| `PA_GEMINI_API_KEY` | `GEMINI_API_KEY` / `GOOGLE_API_KEY` |

With no keys configured, jobs still collect feeds and store a `skipped_summarize` digest (smoke-friendly).

Optional climate overlay: copy `config.climate.example.toml` → `config.climate.toml`. Sensor defaults to **mock** for PC smoke tests.

## Key routes

### System / morning brief (Phase 4)

| Method | Path |
| --- | --- |
| `GET` | `/health` — process liveness |
| `GET` | `/briefing/morning` — English radio-style `script` + `sections[]`; skip missing; `?refresh=1` busts 15‑min cache |
| `GET` | `/briefing/morning/latest` — alias for today |
| `GET` | `/docs` |

### Backup export (Phase 6 — light)

Download a zip of present SSOT SQLite files under `PA_DATA_DIR` (`calendar.db`, `news.db`, plus `health.db` / `climate.db` if present), optional `advisor/*.md`, and a `manifest.json` (timestamp + timezone). Live DBs are snapshotted via SQLite `backup()` so WAL is safe.

| Method | Path |
| --- | --- |
| `GET` | `/backup` — JSON plan / manifest preview (no download) |
| `GET` | `/backup/export` — zip attachment `personal-aissistent-backup-YYYYMMDD-HHMMSS.zip` |

**Restore is manual / out of scope for this slice:** stop the server, extract matching `databases/*.db` (and optional `advisor/`) into `PA_DATA_DIR`, restart. No multi-device conflict resolution; no M365.

```bash
curl -s http://127.0.0.1:8741/backup | jq .
curl -OJ http://127.0.0.1:8741/backup/export
```

PC web UI: top bar **Download backup** (same endpoint).

Empty useful payload → **200** + `meta.empty_reason: "no_data"` (calm script still returned).

### PC web UI (Phase 5)

```bash
cd web && npm install && npm run dev   # http://127.0.0.1:8742
```

Tabs: morning brief, calendar (month / 2-week + tags), climate chart, health stats (+ link to `/`), news digests, plus **Download backup**. Configurable Pi base URL (default `http://127.0.0.1:8741`). Details: [`web/README.md`](web/README.md).

### Android morning action

See [`android/README.md`](android/README.md).

| Piece | Value |
| --- | --- |
| Activity | `com.healthscale.app.MorningBriefActivity` |
| Deep link | `personaissistent://morning` |
| Flow | Fetch brief → show sections → TTS `script` → Open dashboard. **No music.** |
| Hub URL | Settings → Pi server URL (default `:8741`) |

### News topics / jobs (Phase 3)

Schedules use `Europe/Berlin`. Digests in `news.db`. Manual `POST …/run` for dev. Feed URLs: `https://…` RSS/Atom or `mock://name` for local smoke.

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/news/status` | Provider order + which keys are configured |
| `POST` | `/news/topics` | Create topic (`id`, `label`, `goal`, `feed_urls`, schedule) |
| `GET` | `/news/topics` | List |
| `GET`/`PUT`/`DELETE` | `/news/topics/{id}` | Read / update / delete |
| `POST` | `/news/topics/{id}/run` | Manual collect+summarize (`?for_date=YYYY-MM-DD`) |
| `GET` | `/news/digests` | List (`topic_id`, `date`, `limit`) |
| `GET` | `/news/digests/latest` | One latest digest per topic for a date |

### Personal calendar (Phase 2)

Timezone for day/month/2-week windows: `Europe/Berlin` (`PA_TIMEZONE`). No M365 import.

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/calendar/events` | Create (`title`, `start`, `end?`, `all_day`, `location`, `notes`, `tags[]`) |
| `GET` | `/calendar/events/{id}` | Read one |
| `PUT` | `/calendar/events/{id}` | Update (`clear_end` / `clear_location` / `clear_notes` supported) |
| `DELETE` | `/calendar/events/{id}` | Delete |
| `GET` | `/calendar/events` | List — `day=YYYY-MM-DD`, `month=YYYY-MM`, `window=2weeks`, or `from`+`to`; `tag` / `exclude_tag` (repeatable) |
| `GET` | `/calendar/day/{YYYY-MM-DD}` | Day view |
| `GET` | `/calendar/month/{YYYY-MM}` | Month view |
| `GET` | `/calendar/weeks` | Rolling 14-day window (`from=YYYY-MM-DD` optional) |
| `GET` | `/calendar/tags` | Distinct free-form tags |

PC web UI and the Android app can create, edit, and delete events (same fields: title, start, end, all-day, location, notes, tags).

### Health (phone-compatible; was :8000)

| Method | Path |
| --- | --- |
| `GET` | `/api/health` |
| `GET`/`PUT` | `/api/profile` |
| `POST`/`GET` | `/api/measurements` |
| `GET` | `/api/stats` |
| `GET` | `/` — Health dashboard |

### Climate (was :8787 → `/climate`)

| Method | Path |
| --- | --- |
| `GET` | `/climate/health` |
| `GET` | `/climate/current` |
| `GET` | `/climate/measurements` |
| `GET` | `/climate/stats` |
| `GET` | `/climate/rolling-average` |
| `GET` | `/climate/incidents`, `/climate/incidents/tags` |
| `PATCH` | `/climate/incidents/{id}` |
| `GET` | `/climate/outside`, `/climate/outside/measurements` |
| `POST` | `/climate/outside/refresh` |
| `GET`/`PUT` | `/climate/settings` |
| `GET` | `/climate/advisor/context`, `/reports`, `/info`, `/strategies` |
| `PUT` | `/climate/advisor/info`, `/strategies` |

Examples:

```bash
curl -s http://127.0.0.1:8741/health
curl -s http://127.0.0.1:8741/api/health
curl -s http://127.0.0.1:8741/climate/health
curl -s http://127.0.0.1:8741/climate/current

# Calendar
curl -s -X POST http://127.0.0.1:8741/calendar/events \
  -H 'Content-Type: application/json' \
  -d '{"title":"Dentist","start":"2026-10-15T10:30:00+02:00","end":"2026-10-15T11:00:00+02:00","tags":["health"]}'
curl -s "http://127.0.0.1:8741/calendar/day/2026-10-15"
curl -s "http://127.0.0.1:8741/calendar/month/2026-10"
curl -s "http://127.0.0.1:8741/calendar/weeks"
curl -s "http://127.0.0.1:8741/calendar/events?window=2weeks&tag=health"

# News
curl -s http://127.0.0.1:8741/news/status
curl -s -X POST http://127.0.0.1:8741/news/topics \
  -H 'Content-Type: application/json' \
  -d '{"id":"politics","label":"Politics","goal":"Short English digest.","feed_urls":["mock://politics"],"schedule_hour":5,"schedule_minute":45}'
curl -s -X POST http://127.0.0.1:8741/news/topics/politics/run
curl -s "http://127.0.0.1:8741/news/digests/latest"
curl -s "http://127.0.0.1:8741/briefing/morning"
```

## Package layout

```
server/
  app.py
  modules/health/     # Health Scale Hub
  modules/climate/    # Studio Climate (API + sensor/weather/advisor)
  modules/calendar/   # Personal calendar SSOT
  modules/news/       # Topics, feed collect, AI digests, scheduler
  modules/weather/    # day-overview hook → climate outdoor cache
  routers/            # /health, /briefing, /backup
data/                 # PA_DATA_DIR (gitignored DBs)
```

## Git remote

Canonical host: **GitHub** [`TSchwierz/Aissistant`](https://github.com/TSchwierz/Aissistant).

```bash
git remote add origin https://github.com/TSchwierz/Aissistant.git   # or: git remote set-url origin …
git push -u origin main
git push -u origin cursor/phase0-pi-fastapi-scaffold-fed9
```

## Opening a draft PR

Branch: `cursor/phase0-pi-fastapi-scaffold-fed9` → `main` on GitHub.

```bash
gh pr create --draft --base main --head cursor/phase0-pi-fastapi-scaffold-fed9 \
  --title "Phases 0–6: Pi SSOT + PC web + light backup" \
  --body "…"
```

## Out of scope (reminders)

- Automated backup restore / multi-device sync / conflict resolution
- M365 calendar import
- Full morning-brief LLM composition beyond template + digests
- Moving Advisor chat / Mistral key onto the Pi (still PC middleware in the old dashboard)
