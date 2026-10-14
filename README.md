# Personal AIssistent

Pi-oriented personal hub: **single source of truth** on a Raspberry Pi for morning briefs, personal calendar, news digests, Health Scale Hub, and (later) Studio Climate.

One **FastAPI process** serves liveness, the morning-brief stub, and the Health Scale Hub API + dashboard.

## Architecture (locked)

| Piece | Role |
| --- | --- |
| **Pi SSOT** | This server — shared data and services |
| **Clients** | Android app (morning + scale sync) + PC browser dashboard |
| **Morning brief** | `GET /briefing/morning` — weather + today’s events + news digests + English TTS `script` |
| **Health Scale Hub** | Mounted module: phone routes at `/api/...`, dashboard at `/` |

## Network posture (LAN-trusted)

- Bind for **local / trusted home LAN** use only (same posture as the former Health hub / Studio Climate).
- Default bind: `127.0.0.1:8741`. On the Pi, set `PA_HOST=0.0.0.0` only if the LAN is trusted.
- **No auth** in this codebase. **Do not** expose publicly.
- Point the Health Android app hub base URL at this server (e.g. `http://<pi-lan-ip>:8741`). Phone paths stay `/api/health`, `/api/measurements`, etc.

## Requirements

- Python 3.11+

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run locally

```bash
python -m server
```

Or:

```bash
uvicorn server.app:app --host 127.0.0.1 --port 8741
```

Env overrides (`PA_` prefix):

| Variable | Default | Notes |
| --- | --- | --- |
| `PA_TIMEZONE` | `Europe/Berlin` | Brief “today” |
| `PA_HOST` | `127.0.0.1` | Use `0.0.0.0` on trusted LAN |
| `PA_PORT` | `8741` | Unified listen port (replaces standalone Health `:8000`) |
| `PA_DATA_DIR` | `<repo>/data` | SQLite `health.db` lives here |

No secrets or keystores required for the server.

## Endpoints

### System / morning brief

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/health` | Process liveness (timezone, version) |
| `GET` | `/briefing/morning` | Stub morning brief (`?date=YYYY-MM-DD` optional) |
| `GET` | `/docs` | OpenAPI UI |

### Health Scale Hub (phone-compatible)

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Connection test → `{"status":"ok","service":"health-scale-hub"}` |
| `GET`/`PUT` | `/api/profile` | Single-user profile |
| `POST` | `/api/measurements` | Ingest one / list / `{ "measurements": [...] }` |
| `GET` | `/api/measurements` | List (`from`, `to`, `limit`) |
| `PUT`/`DELETE` | `/api/measurements/{id}` | Edit / delete |
| `GET` | `/api/stats` | Latest + averages |
| `POST` | `/api/measurements/recalculate` | Re-run BIA after profile change |
| `GET` | `/api/measurements/export.csv` | CSV export |
| `GET` | `/` | Dashboard HTML |
| | `/static/*` | Dashboard assets |

Examples:

```bash
curl -s "http://127.0.0.1:8741/health"
curl -s "http://127.0.0.1:8741/briefing/morning"
curl -s "http://127.0.0.1:8741/api/health"
curl -s "http://127.0.0.1:8741/api/profile"
curl -s -X POST "http://127.0.0.1:8741/api/measurements" \
  -H "Content-Type: application/json" \
  -d '{"client_id":"demo-1","measured_at":"2026-10-14T08:00:00Z","weight_kg":78.5}'
```

## Package layout

```
server/
  app.py                 # Unified FastAPI app
  config.py              # PA_* settings
  __main__.py
  models/                # Morning-brief response shapes
  routers/               # /health liveness, /briefing/*
  modules/
    health/              # Health Scale Hub (API + BIA + dashboard)
    calendar/ news/ weather/ climate/   # stubs / placeholders
data/
  .gitkeep               # health.db created at runtime (gitignored)
```

## Opening a draft PR (after a real repo exists)

This work lives on branch `cursor/phase0-pi-fastapi-scaffold-fed9`.

If the remote is still an agent temporary repo, Origin cannot open PRs (`repoKind=agent_temp`). After creating a standard repository:

1. Push the branch (or re-push after the remote URL updates).
2. Open a **draft** PR into `main` with title like `feat: Phase 0/1 Pi FastAPI + Health Scale Hub`.
3. Describe: unified process, Health mounted at phone `/api/*` paths, morning-brief stub retained, LAN-trusted posture.

## Out of scope (reminders)

- Android APK / keystore (not in this tree)
- Studio Climate full port
- Real LLM / weather / news for morning brief
- Public internet exposure / auth
