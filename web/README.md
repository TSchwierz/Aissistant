# Personal AIssistent — PC web UI

LAN React (Vite) client for the unified Pi API on **`:8741`**. No AI keys in the browser.

## Run

Terminal 1 — Pi API (repo root):

```bash
python -m server
```

Terminal 2 — web UI:

```bash
cd web
npm install
npm run dev
```

Open [http://127.0.0.1:8742](http://127.0.0.1:8742).

Optional: `VITE_PI_API_BASE=http://192.168.178.23:8741 npm run dev` or set the URL in the top bar (saved to `localStorage`).

Production build:

```bash
npm run build
npm run preview   # also :8742
```

## UI sections (in-app routes / tabs)

| Tab | Pi APIs used |
| --- | --- |
| Morning brief | `GET /briefing/morning` |
| Calendar | `/calendar/weeks`, `/calendar/month/{YYYY-MM}`, `/calendar/tags`, create / edit / delete `/calendar/events` |
| Climate | `/climate/current`, `/climate/measurements`, `/climate/outside` |
| Health | `/api/stats`, `/api/profile` + link to HTML `/` |
| News | `/news/status`, `/news/topics` (list, create, edit), `/news/digests/latest` |

Top bar also has **Download backup** → `GET /backup/export` (zip of SSOT DBs + manifest). Restore is manual; see root README.

CORS: the Pi server allows `http://127.0.0.1:8742` (and common Vite ports). On another LAN host, either proxy through Vite or extend server CORS for that origin.
