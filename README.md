# Personal AIssistent

Pi-oriented personal hub: **single FastAPI process** as SSOT for morning briefs, Health Scale Hub, and Studio Climate Monitor (plus stubs for calendar/news).

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

Env (`PA_` prefix): `PA_TIMEZONE` (default `Europe/Berlin`), `PA_HOST`, `PA_PORT`, `PA_DATA_DIR` (default `./data` — holds `health.db`, `climate.db`, `advisor/`), `PA_CLIMATE_MOCK_SENSOR` (optional bool).

Optional climate overlay: copy `config.climate.example.toml` → `config.climate.toml`. Sensor defaults to **mock** for PC smoke tests.

## Key routes

### System / morning brief

| Method | Path |
| --- | --- |
| `GET` | `/health` — process liveness |
| `GET` | `/briefing/morning` — stub brief; includes weather section when climate outdoor cache has data |
| `GET` | `/docs` |

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
curl -s http://127.0.0.1:8741/briefing/morning
```

## Package layout

```
server/
  app.py
  modules/health/     # Health Scale Hub
  modules/climate/    # Studio Climate (API + sensor/weather/advisor)
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
