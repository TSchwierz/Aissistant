# Personal AIssistent

Pi-oriented personal hub: **single source of truth** on a Raspberry Pi for morning briefs, personal calendar, news digests, and (later) Health + Studio Climate.

Phase 0 is a **single FastAPI process** with health check, a stub morning-brief endpoint, and placeholder domain modules. No real LLM or provider integrations yet.

## Architecture (locked)

| Piece | Role |
| --- | --- |
| **Pi SSOT** | This server — shared data and services |
| **Clients** | Android app (primary morning flow) + optional PC dashboard |
| **Morning brief** | `GET /briefing/morning` — weather + today’s events + news digests + English TTS `script` |

Design contracts (Agent Store / project docs): morning brief API sketch; project context.

## Network posture (LAN-trusted)

- Bind for **local / trusted home LAN** use only (same posture as Health hub / Studio Climate today).
- Default bind: `127.0.0.1:8741`. On the Pi, set `PA_HOST=0.0.0.0` only if the LAN is trusted.
- **Do not** expose this service to the public internet. Auth details TBD with the rest of the Pi surface.

## Requirements

- Python 3.11+

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional editable install (same deps):

```bash
pip install -e .
```

## Run locally

```bash
python -m server
```

Or:

```bash
uvicorn server.app:app --host 127.0.0.1 --port 8741
```

Override defaults with env vars (`PA_` prefix), e.g.:

```bash
PA_TIMEZONE=Europe/Berlin PA_HOST=127.0.0.1 PA_PORT=8741 python -m server
```

## Endpoints (Phase 0)

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/health` | Liveness; reports timezone |
| `GET` | `/briefing/morning` | Stub morning brief. Optional `?date=YYYY-MM-DD` (omit → today in Pi timezone). Returns illustrative empty/partial JSON (`meta.empty_reason: "no_data"` until providers exist). |
| `GET` | `/docs` | OpenAPI UI (FastAPI) |

Example:

```bash
curl -s "http://127.0.0.1:8741/health"
curl -s "http://127.0.0.1:8741/briefing/morning"
curl -s "http://127.0.0.1:8741/briefing/morning?date=2026-10-15"
```

## Package layout

```
server/
  app.py              # FastAPI app
  config.py           # Settings (timezone default Europe/Berlin)
  __main__.py         # python -m server
  models/             # Response shapes (morning brief)
  routers/            # health, briefing
  modules/
    calendar/         # Personal calendar SSOT (stub)
    news/             # Topic digests (stub)
    weather/          # Day overview (stub)
    health/           # Health Scale Hub — placeholder only
    climate/          # Studio Climate — placeholder only
```

Health and Studio Climate full ports are **out of scope** for this Phase 0 scaffold (separate workstreams).

## Out of scope (V1 reminders)

- In-app / Spotify morning music
- Microsoft 365 work calendar
- Non-English briefs
- Public internet exposure
