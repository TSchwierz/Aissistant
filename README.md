# Personal AIssistent

Pi-oriented personal hub: **single FastAPI process** as SSOT for morning briefs, personal calendar, news digests, Health Scale Hub, and Studio Climate Monitor.

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

Empty useful payload → **200** + `meta.empty_reason: "no_data"` (calm script still returned).

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
  routers/            # /health, /briefing
data/                 # PA_DATA_DIR (gitignored DBs)
```

## Opening a draft PR

Branch: `cursor/phase0-pi-fastapi-scaffold-fed9`. Origin **agent_temp** remotes cannot open PRs — after a real repo exists, push this branch and open a **draft** PR to `main`.

## Out of scope (reminders)

- Android / PC Vite apps as product shells (point clients at this API)
- Full morning-brief LLM composition
- Moving Advisor chat / Mistral key onto the Pi (still PC middleware in the old dashboard)
