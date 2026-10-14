# Personal AIssistent Android (Health Scale + Morning brief)

Package `com.healthscale.app`. The phone is a read-only dashboard for the Pi: morning brief, climate, health stats, and news digests. The calendar matches the PC (month, two weeks, tags, create, edit, delete). The Pi URL is the only setting stored on the phone. The scale is read by the Pi over Bluetooth, not by this app. Morning brief remains the Modes & Routines entry.

**No keystores in git.** Copy `local.properties.example` → `local.properties` (SDK path). Signing stays machine-local under `keystore/` if you create it.

## Pi base URL

Settings → **Pi server URL** (default `http://192.168.1.100:8741`). Health ingest stays `/api/...`; morning brief uses `GET /briefing/morning`.

## Morning brief

| Piece | Value |
| --- | --- |
| Activity | `com.healthscale.app.MorningBriefActivity` |
| Deep link | `personaissistent://morning` |
| Explicit action | `com.healthscale.app.action.MORNING_BRIEF` |
| Behavior | Fetch brief → show sections → TTS `script` → optional Open dashboard. **No in-app music.** |

### Modes & Routines (Android 15)

1. Install / sideload the APK; open Settings once and set the Pi LAN URL; Test connection.
2. Modes & Routines → your morning routine → **Add action**.
3. Prefer **Open app** / **Open URL / deep link** / **Browse URL** (wording varies by OEM):
   - Deep link: `personaissistent://morning`
   - Or pick app **Health Scale** → activity **Morning brief** if listed.
4. Optional: separate Routines step to open Spotify (outside this app).
5. Test the routine; you should see sections and hear TTS of the Pi `script`.

ADB smoke:

```bash
adb shell am start -a android.intent.action.VIEW -d "personaissistent://morning"
# or
adb shell am start -n com.healthscale.app/.MorningBriefActivity
```

## Build

Windows helpers: `build-apk.bat` / `build-apk.ps1`. Or Android Studio / Gradle on a machine with the SDK. This Cloud VM may not build the APK.
