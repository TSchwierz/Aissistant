# Changelog

## 2026-10-30

### Climate

The climate dashboard still shows the next 4 hours. A new Forecast tab on the web and the phone charts the next 24 stored hours: temperature with humidity, and rain probability with wind. Condition is a label on each hour. Hours the providers did not return stay as gaps. `GET /climate/outside/hourly` is the new route. The stored forecast horizon now defaults to 24 hours.

### Calendar

Events can be imported from an `.ics` file, a Google Calendar `.zip` of `.ics` files, or an Outlook CSV. The server parses the file. A repeat is kept only when it is weekly, every two weeks, or monthly. Anything else is stored once, and the import result says the repeat was not kept. Importing the same ICS uid again updates that event.

Each event has one reminder or none, stored as minutes before the start (1 to 10080). The web shows a browser notification only while a page of the app is open. The phone schedules an Android notification from the events it has stored, including while the app is closed.

On the web week and fortnight grids, dragging across empty time opens the create form with that range, snapped to 15 minutes. Dragging a non-repeating event moves it and saves on drop. A repeating event does not move by drag.

### Health

The scale still stops for the day after today's reading is stored. The default auto window is 08:00 inclusive to 10:00 exclusive. Web and phone settings change those hours on the Pi (`scale_window.json`). Both health screens show the window the server returns.

### Phone

Away from home, the phone reaches the Pi through Tailscale at `http://<tailscale-ipv4>:8741`. The app does not include a VPN, and port 8741 stays closed on the router. The home LAN address still works on the home network.

The phone keeps calendar events that overlap today at 00:00 through 00:00 seven days later, in the Pi timezone. If the server cannot be reached, that copy is what the calendar shows. Days outside it are empty. Creating, editing, and deleting still require the server.

### Morning brief

Today's brief is written to `morning_brief.json` in the data directory. The news scheduler writes it at 04:00 in the Pi timezone, and writes it again after a news digest for that day finishes. A restart serves the file. `?refresh=1` replaces it. A request for another date is composed and not saved. The 15-minute memory cache is gone.

### API

Every endpoint requires `PA_API_KEY`, including reads, backup, and `/health`. The process will not start if the key is empty. Clients send `Authorization: Bearer` or `X-API-Token`. The web and the phone store the key in their own settings and send it on every request. The server does not return the key. A key in the query string is ignored.
