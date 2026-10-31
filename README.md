# Personal AIssistent

Home hub on a Raspberry Pi. One API is the source of truth for the morning brief, personal calendar, news digests, weight and meals, and the studio climate monitor. A PC web UI in `web/` and an Android app talk to that API on the LAN. AI keys stay on the Pi.

On the Pi, `start-server.sh` runs four processes and restarts whichever one exits: the API, the climate sampler, the Bluetooth scale scanner, and the news scheduler. A crash in the scale scan does not take the API down. For local development, `python -m server` runs those workers as threads inside the API process instead.

## Ports

| Service | Port |
| --- | --- |
| API | **8741** — health under `/api/...`, climate under `/climate/...`, plus calendar, news, briefing, and backup |
| PC web UI (Vite) | **8742** |

Default bind is `127.0.0.1:8741`. The Pi boot script listens on `0.0.0.0:8741`. Every request needs `PA_API_KEY`. Do not expose **8741** on the router.

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
| `PA_API_KEY` | *(none)* | Required. The process refuses to start when this is empty |
| `PA_SCALE_SCAN_ENABLED` | `true` | `false` turns the morning listen off. Manual Start still scans |
| `PA_SCALE_LISTEN_START_HOUR` | `8` | Inclusive, local time. Used only until `scale_window.json` exists |
| `PA_SCALE_LISTEN_END_HOUR` | `10` | Exclusive, local time. Used only until `scale_window.json` exists |

`PA_DATA_DIR` defaults to `~/.local/share/personal-aissistent` on Linux and `%LOCALAPPDATA%\PersonalAissistent` on Windows. The first start copies any `health.db`, `climate.db`, `calendar.db`, `news.db`, scale JSON, or `advisor/` files still sitting in `./data`. A later `git pull` does not wipe them.

### Morning scale (Pi Bluetooth)

The Pi listens for the scale. The phone does not measure.

The default listen window is **08:00–10:00** local time (start inclusive, end exclusive). Settings on the web and the phone change it; the Pi stores the hours in `scale_window.json` next to `scale_mode.json`. The scanner still stops once a measurement for that calendar day is stored. **Start scan** listens immediately, including outside the window and after today's reading exists, until **Stop scan**. **Use schedule** returns to the saved window. `GET /api/scale` reports `start_hour`, `end_hour`, `window`, and the phase. `POST /api/scale/window` takes `{"start_hour":8,"end_hour":10}`. `POST /api/scale/mode` takes `{"action":"start"|"stop"|"auto"}`.

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

A left sidebar holds Morning brief, Calendar, Climate, Health, News, and Settings. On a narrow screen the sidebar is behind **Menu**. Settings stores the Pi URL (default `http://192.168.178.23:8741`), the API key, the scale listen hours, a connection test, a backup download, and the theme (system / dark / light, and teal / blue / amber / rose). The key stays in this browser and is sent as `Authorization: Bearer`. Override the default URL with `VITE_PI_API_BASE` set to the server origin, for example `http://192.168.178.23:8741` — not `/climate`.

| Section | What it does |
| --- | --- |
| Morning brief | Today's script and sections |
| Calendar | Week, two weeks, month, and a simplified list. Tags and tag colours. Create, edit, delete. On the week and fortnight grids, drag a range to prefill the form, or drag a non-repeating event to move it. One optional reminder, in minutes or hours. Import an `.ics` file, a Google Calendar `.zip`, or an Outlook CSV. Events can repeat weekly, every two weeks, or monthly, with an optional end date |
| Climate | Current indoor reading and ventilation advice. The 4-hour outside summary stays on the dashboard. A Forecast tab charts the next 24 stored hours. History for 12 hours, 24 hours, 7 days, or 30 days. Outside providers. Temperature and humidity bands, and the sample interval |
| Health | Scale listener (start, stop, schedule), latest weight and body composition, charts, measurements, meals and calories, profile and targets |
| News | Topics and the latest digests |
| Settings | Pi URL, API key, scale listen window, connection test, backup download, theme |

The Vite app lives in [`web/`](web/).

## Android

Package `com.healthscale.app`. The drawer matches the PC: Brief, Calendar, Climate, Health, News, Settings. The scale is read by the Pi. Health includes the scale controls, measurements, meals (including a camera for a barcode or a photo), and profile. Climate has the same history ranges as the PC, plus the 24-hour Forecast tab. Calendar editing matches the PC, including file import and one reminder per event. The phone keeps events that overlap today through the next 7 days in the Pi timezone and shows that copy when the server cannot be reached. Creates, edits, and deletes still need the server. Reminders in that window are scheduled as Android notifications and fire while the app is closed. Settings stores the Pi URL, the API key, the scale listen window, theme, and backup download.

Morning brief is still the Modes & Routines entry. See [`android/README.md`](android/README.md).

| Piece | Value |
| --- | --- |
| Activity | `com.healthscale.app.MorningBriefActivity` |
| Deep link | `personaissistent://morning` |
| Flow | Fetch brief → show sections → TTS `script`. **No music.** |
| Hub URL | Settings → Pi server URL (default `http://192.168.178.23:8741`) |

Build on a machine with JDK 17 and the Android SDK (`android/build-apk.bat` or Gradle).

### Phone away from home

Do not open port **8741** on the router. Tailscale is how the phone reaches the Pi from outside the house. The app does not contain a VPN. Install Tailscale on the Pi and on the phone, and sign both into the same tailnet. The URL stays `http://` because WireGuard encrypts the tunnel. The API key is still required.

On this LAN the Pi is `192.168.178.23`. Confirm it with `ping -4 raspberrypi.fritz.box` from the PC, or `hostname -I` on the Pi. At home the phone setting is `http://192.168.178.23:8741`.

Away from home:

1. On the Pi, `tailscale ip -4` prints the overlay address (`100.x.x.x`).
2. In the phone app, set the Pi server URL to `http://100.x.x.x:8741`.
3. Set the same `PA_API_KEY` the Pi was started with.

## Key routes

### System / morning brief

| Method | Path |
| --- | --- |
| `GET` | `/health` — process liveness |
| `GET` | `/briefing/morning` — today's brief is the file `morning_brief.json` in `PA_DATA_DIR`. The news scheduler writes it at 04:00 local time and again after a digest for today. `?refresh=1` composes a new copy. Any other `date` is composed and not saved |
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

Windows use `PA_TIMEZONE`. Repeating events are `weekly`, `biweekly`, or `monthly`, with optional `repeat_until` and `repeat_weekdays` (0 = Monday). Editing or deleting a series changes the series. Tag colours are `PUT /calendar/tags`.

`POST /calendar/import` accepts a multipart file named `file`: one `.ics`, a `.zip` of `.ics` files (a Google Calendar export), or an Outlook CSV. A repeat is stored only when it is weekly, every two weeks, or monthly. Anything else is one event, and the response lists it under `repeat_dropped`. The same ICS `UID` updates that event on a later import. A CSV row updates an event with the same title, start, and end.

`remind_before_minutes` is `null` or an integer from 1 to 10080. The web notifies with the browser Notification API only while a page is open. The phone schedules its own notifications from the stored 7-day window.

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/calendar/import` | Multipart `file`: `.ics`, `.zip` of `.ics`, or Outlook CSV |
| `POST` | `/calendar/events` | Create. Optional `remind_before_minutes` |
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
| `GET` | `/api/scale` — includes `start_hour`, `end_hour`, and `window` |
| `POST` | `/api/scale/window` — `{"start_hour","end_hour"}` |
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
| `GET` | `/climate/outside` — current reading and the 4-hour summary |
| `GET` | `/climate/outside/hourly` — next 24 stored hours, gaps left empty |
| `GET` | `/climate/outside/measurements` |
| `POST` | `/climate/outside/refresh` |
| `GET`/`PUT` | `/climate/settings` |
| `GET` | `/climate/incidents`, `/climate/incidents/tags` |
| `PATCH` | `/climate/incidents/{id}` |
| `GET` | `/climate/advisor/context`, `/reports`, `/info`, `/strategies` |
| `PUT` | `/climate/advisor/info`, `/strategies` |

Advisor notes are markdown under `PA_DATA_DIR/advisor/`. There is no advisor chat in the web or phone UI.

Send the key on every call. A missing or wrong key is `401`. A query-string key is ignored.

```bash
curl -s http://127.0.0.1:8741/health -H "Authorization: Bearer $PA_API_KEY"
curl -s http://127.0.0.1:8741/api/scale -H "Authorization: Bearer $PA_API_KEY"
curl -s http://127.0.0.1:8741/climate/current -H "Authorization: Bearer $PA_API_KEY"
curl -s http://127.0.0.1:8741/climate/outside/hourly -H "Authorization: Bearer $PA_API_KEY"
curl -s "http://127.0.0.1:8741/climate/measurements?from=2026-10-20T00:00:00Z&limit=5000" \
  -H "Authorization: Bearer $PA_API_KEY"

curl -s -X POST http://127.0.0.1:8741/calendar/events \
  -H "Authorization: Bearer $PA_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Dentist","start":"2026-10-15T10:30:00+02:00","end":"2026-10-15T11:00:00+02:00","tags":["health"],"remind_before_minutes":60}'
curl -s "http://127.0.0.1:8741/calendar/weeks?days=7" -H "Authorization: Bearer $PA_API_KEY"

curl -s http://127.0.0.1:8741/news/status -H "Authorization: Bearer $PA_API_KEY"
curl -s "http://127.0.0.1:8741/briefing/morning" -H "Authorization: Bearer $PA_API_KEY"
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
