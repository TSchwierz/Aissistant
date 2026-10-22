# Personal AIssistent

Home hub on a Raspberry Pi. One API is the source of truth for the morning brief, personal calendar, news digests, weight and meals, and the studio climate monitor. A PC web UI in `web/` and an Android app talk to that API on the LAN. AI keys stay on the Pi.

On the Pi, `start-server.sh` runs four processes and restarts whichever one exits: the API, the climate sampler, the Bluetooth scale scanner, and the news scheduler. A crash in the scale scan does not take the API down. For local development, `python -m server` runs those workers as threads inside the API process instead.

## Ports

| Service | Port |
| --- | --- |
| API | **8741** — health under `/api/...`, climate under `/climate/...`, plus calendar, news, briefing, and backup |
| PC web UI (Vite) | **8742** |

Default bind is `127.0.0.1:8741`. The Pi boot script listens on `0.0.0.0:8741`. There is no login. Do not expose **8741** on the router.

The old Health Scale Hub (`:8000`) and Studio Climate (`:8787`) are this process now. `GET /` still serves the old health HTML page. The PC and phone apps use their own Health screens instead.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m server
```

On the Pi, after the venv is installed:

```bash
chmod +x start-server.sh
./start-server.sh
```

Boot (user crontab). The script binds `0.0.0.0:8741` and starts the supervisor:

```bash
@reboot /home/pi/Aissistant/start-server.sh >> /home/pi/Aissistant/data/server.log 2>&1
```

### Environment

Prefix is `PA_`. A `.env` file in the repo root is read as well.

| Variable | Default | Role |
| --- | --- | --- |
| `PA_TIMEZONE` | `Europe/Berlin` | Calendar windows, scale day, news schedules |
| `PA_HOST` | `127.0.0.1` | `0.0.0.0` on the Pi via `start-server.sh` |
| `PA_PORT` | `8741` | |
| `PA_DATA_DIR` | see below | SQLite and scale status, outside the git checkout |
| `PA_EMBED_WORKERS` | `true` | `false` under the supervisor, so workers are separate processes |
| `PA_CLIMATE_MOCK_SENSOR` | climate config | Optional override. Mock is the PC-friendly default |
| `PA_NEWS_SCHEDULER_ENABLED` | `true` | |
| `PA_SCALE_SCAN_ENABLED` | `true` | `false` turns the morning listen off. Manual Start still scans |
| `PA_SCALE_LISTEN_START_HOUR` | `6` | Inclusive, local time |
| `PA_SCALE_LISTEN_END_HOUR` | `12` | Exclusive, local time |

`PA_DATA_DIR` defaults to `~/.local/share/personal-aissistent` on Linux and `%LOCALAPPDATA%\PersonalAissistent` on Windows. The first start copies any `health.db`, `climate.db`, `calendar.db`, `news.db`, scale JSON, or `advisor/` files still sitting in `./data`. A later `git pull` does not wipe them.

### Morning scale (Pi Bluetooth)

The Pi listens for the scale. The phone does not measure.

From **06:00–12:00** local time it listens until a measurement for that calendar day is stored, then it stops. **Start scan** in the Health screen listens immediately, including outside that window and after today's reading exists, until **Stop scan**. **Use schedule** returns to the morning window. `GET /api/scale` reports the phase. `POST /api/scale/mode` takes `{"action":"start"|"stop"|"auto"}`.

The scale repeats its broadcast while someone is standing on it, and the Pi's Bluetooth controller drops later packets from the same device. The scanner restarts discovery every few seconds so the locked weight, and a follow-up impedance reading, can get through. A locked weight with impedance is stored at once. A lock without impedance is held a few seconds in case body composition arrives.

The Pi needs BlueZ (`bluetooth` running) and the process user in the `bluetooth` group.

### AI keys (Pi only — never ship to clients)

Provider order: **Mistral → Claude → ChatGPT → Gemini** (exponential retry per provider).

| Variable | Also accepted |
| --- | --- |
| `PA_MISTRAL_API_KEY` | `MISTRAL_API_KEY` |
| `PA_ANTHROPIC_API_KEY` | `ANTHROPIC_API_KEY` |
| `PA_OPENAI_API_KEY` | `OPENAI_API_KEY` |
| `PA_GEMINI_API_KEY` | `GEMINI_API_KEY` / `GOOGLE_API_KEY` |

With no keys configured, news jobs still collect feeds and store a `skipped_summarize` digest.

Optional climate overlay: copy `config.climate.example.toml` → `config.climate.toml`. The sensor defaults to **mock** for PC smoke tests. On the Pi, set `mock_sensor = false` and a real sample interval (the collector default is 60 seconds). Indoor temperature and humidity are sampled around the clock.

Outside air comes from Open-Meteo, Bright Sky (DWD), and OpenWeatherMap. OpenWeatherMap needs its own key in the climate config. The climate screen shows each provider and whether airing out would help.

## PC web UI

```bash
cd web && npm install && npm run dev   # http://127.0.0.1:8742
```

A left sidebar holds Morning brief, Calendar, Climate, Health, News, and Settings. On a narrow screen the sidebar is behind **Menu**. Settings stores the Pi URL (default `http://192.168.178.23:8741`), tests `GET /health`, downloads a backup, and sets the theme (system / dark / light, and teal / blue / amber / rose). Override the default URL with `VITE_PI_API_BASE` set to the server origin, for example `http://192.168.178.23:8741` — not `/climate`.

| Section | What it does |
| --- | --- |
| Morning brief | Today's script and sections |
| Calendar | Week, two weeks, month, and a simplified list. Tags and tag colours. Create, edit, delete. Events can repeat weekly, every two weeks, or monthly, with an optional end date |
| Climate | Current indoor reading and ventilation advice. History for 12 hours, 24 hours, 7 days, or 30 days. Outside providers. Temperature and humidity bands, and the sample interval |
| Health | Scale listener (start, stop, schedule), latest weight and body composition, charts, measurements, meals and calories, profile and targets |
| News | Topics and the latest digests |
| Settings | Pi URL, connection test, backup download, theme |

The Vite app lives in [`web/`](web/).

## Android

Package `com.healthscale.app`. The drawer matches the PC: Brief, Calendar, Climate, Health, News, Settings. The scale is read by the Pi. Health includes the scale controls, measurements, meals (including a camera for a barcode or a photo), and profile. Climate history has the same ranges as the PC. Calendar editing matches the PC. Settings stores the Pi URL, theme, and backup download.

Morning brief is still the Modes & Routines entry. See [`android/README.md`](android/README.md).

| Piece | Value |
| --- | --- |
| Activity | `com.healthscale.app.MorningBriefActivity` |
| Deep link | `personaissistent://morning` |
| Flow | Fetch brief → show sections → TTS `script`. **No music.** |
| Hub URL | Settings → Pi server URL (default `http://192.168.178.23:8741`) |

Build on a machine with JDK 17 and the Android SDK (`android/build-apk.bat` or Gradle).

### Phone away from home

Do not open port **8741** on the router. Use a VPN so the phone joins the home network, then keep the same server URL.

On this LAN the Pi is `192.168.178.23`. Confirm it with `ping -4 raspberrypi.fritz.box` from the PC, or `hostname -I` on the Pi. At home the phone setting is `http://192.168.178.23:8741`.

**Tailscale** (stays connected on mobile data):

1. Install Tailscale on the Pi and on the phone. Sign both in to the same account.
2. On the Pi, `tailscale ip -4` prints the overlay address (`100.x.x.x`).
3. In the phone app, set the Pi server URL to `http://100.x.x.x:8741`.

**Fritz!Box WireGuard** (turn the VPN on when you want the app): after the phone connects to the Fritz VPN, `http://192.168.178.23:8741` works as if the phone were at home.

## Key routes

### System / morning brief

| Method | Path |
| --- | --- |
| `GET` | `/health` — process liveness |
| `GET` | `/briefing/morning` — English `script` + `sections[]`; skip missing parts; `?refresh=1` busts the 15‑min cache |
| `GET` | `/briefing/morning/latest` — alias for today |
| `GET` | `/docs` |

Empty useful payload → **200** + `meta.empty_reason: "no_data"` (a calm script is still returned).

### Backup

A zip of the SQLite files present under `PA_DATA_DIR` (`calendar.db`, `news.db`, plus `health.db` / `climate.db` if present), optional `advisor/*.md`, and a `manifest.json`. Live databases are copied with SQLite `backup()` so a WAL is safe.

| Method | Path |
| --- | --- |
| `GET` | `/backup` — JSON plan, no download |
| `GET` | `/backup/export` — `personal-aissistent-backup-YYYYMMDD-HHMMSS.zip` |

Restore by hand: stop the server, extract `databases/*.db` (and optional `advisor/`) into `PA_DATA_DIR`, start again. There is no multi-device merge.

```bash
curl -s http://127.0.0.1:8741/backup | jq .
curl -OJ http://127.0.0.1:8741/backup/export
```

The PC and the phone download the same zip from Settings.

### News

Schedules use `PA_TIMEZONE`. Digests live in `news.db`. Feed URLs are `https://…` RSS/Atom, or `mock://name` for a local smoke test.

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/news/status` | Provider order and which keys are set |
| `POST` | `/news/topics` | Create (`id`, `label`, `goal`, `feed_urls`, schedule) |
| `GET` | `/news/topics` | List |
| `GET`/`PUT`/`DELETE` | `/news/topics/{id}` | Read / update / delete |
| `POST` | `/news/topics/{id}/run` | Collect and summarize (`?for_date=YYYY-MM-DD`) |
| `GET` | `/news/digests` | List (`topic_id`, `date`, `limit`) |
| `GET` | `/news/digests/latest` | One latest digest per topic for a date |

### Calendar

Windows use `PA_TIMEZONE`. No Microsoft 365 import. Repeating events are `weekly`, `biweekly`, or `monthly`, with optional `repeat_until` and `repeat_weekdays` (0 = Monday). Editing or deleting a series changes the series. Tag colours are `PUT /calendar/tags`.

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/calendar/events` | Create |
| `GET` | `/calendar/events/{id}` | Read one |
| `PUT` | `/calendar/events/{id}` | Update (`clear_end`, `clear_location`, `clear_notes`, `clear_repeat`) |
| `DELETE` | `/calendar/events/{id}` | Delete |
| `GET` | `/calendar/events` | `day=`, `month=YYYY-MM`, `window=2weeks`, or `from`+`to`; `tag` / `exclude_tag` |
| `GET` | `/calendar/day/{YYYY-MM-DD}` | Day |
| `GET` | `/calendar/month/{YYYY-MM}` | Month |
| `GET` | `/calendar/weeks` | `from=YYYY-MM-DD`, `days` (default 14, max 31) |
| `GET`/`PUT` | `/calendar/tags` | Tag names and colours |

### Health

| Method | Path |
| --- | --- |
| `GET` | `/api/health` |
| `GET`/`PUT` | `/api/profile` |
| `GET` | `/api/stats` |
| `GET` | `/api/scale` |
| `POST` | `/api/scale/mode` — `start`, `stop`, or `auto` |
| `POST`/`GET` | `/api/measurements` |
| `PUT`/`DELETE` | `/api/measurements/{id}` |
| `GET` | `/api/meals`, `/api/meals/summary?day=YYYY-MM-DD` |
| `POST` | `/api/meals` |
| `GET` | `/api/foods/search`, `/api/foods/barcode/{code}` |
| `POST` | `/api/nutrition/parse`, `/api/nutrition/parse-image` |
| `GET` | `/` — old HTML dashboard |

### Climate

Routes are under `/climate`. History accepts `from`, `to`, and `limit`. When a limit cuts the window short, the newest samples are kept.

| Method | Path |
| --- | --- |
| `GET` | `/climate/health`, `/climate/current` |
| `GET` | `/climate/measurements`, `/climate/stats`, `/climate/rolling-average` |
| `GET` | `/climate/outside`, `/climate/outside/measurements` |
| `POST` | `/climate/outside/refresh` |
| `GET`/`PUT` | `/climate/settings` |
| `GET` | `/climate/incidents`, `/climate/incidents/tags` |
| `PATCH` | `/climate/incidents/{id}` |
| `GET` | `/climate/advisor/context`, `/reports`, `/info`, `/strategies` |
| `PUT` | `/climate/advisor/info`, `/strategies` |

Advisor notes are markdown under `PA_DATA_DIR/advisor/`. There is no advisor chat in the web or phone UI.

```bash
curl -s http://127.0.0.1:8741/health
curl -s http://127.0.0.1:8741/api/scale
curl -s http://127.0.0.1:8741/climate/current
curl -s "http://127.0.0.1:8741/climate/measurements?from=2026-10-20T00:00:00Z&limit=5000"

curl -s -X POST http://127.0.0.1:8741/calendar/events \
  -H 'Content-Type: application/json' \
  -d '{"title":"Dentist","start":"2026-10-15T10:30:00+02:00","end":"2026-10-15T11:00:00+02:00","tags":["health"]}'
curl -s "http://127.0.0.1:8741/calendar/weeks?days=7"

curl -s http://127.0.0.1:8741/news/status
curl -s "http://127.0.0.1:8741/briefing/morning"
```

## Package layout

```
start-server.sh           # Pi boot: supervisor, bind 0.0.0.0:8741
server/
  app.py                  # FastAPI app
  supervisor.py           # API, climate, scale, and news as separate processes
  workers/                # python -m server.workers climate|scale|news
  modules/health/         # measurements, meals, BLE scale parser and scanner
  modules/climate/        # indoor sampler, outside providers, advisor files
  modules/calendar/
  modules/news/
  routers/                # /health, /briefing, /backup
web/                      # PC UI on :8742
android/                  # phone app
```

`./data` in the checkout is only a legacy copy. Live databases are in `PA_DATA_DIR`.

## Git remote

Canonical host: **GitHub** [`TSchwierz/Aissistant`](https://github.com/TSchwierz/Aissistant), branch `main`.

```bash
git remote add origin https://github.com/TSchwierz/Aissistant.git   # or: git remote set-url origin …
git push -u origin main
```
