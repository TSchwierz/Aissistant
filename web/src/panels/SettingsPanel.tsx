import { useEffect, useState } from 'react'
import { api, getApiBase, getApiKey, setApiBase, setApiKey } from '../api'
import { fetchScaleWindow, saveScaleWindow } from '../scaleWindowApi'
import {
  applyTheme,
  readThemeAccent,
  readThemeMode,
  writeThemeAccent,
  writeThemeMode,
  type ThemeAccent,
  type ThemeMode,
} from '../theme'

const MODES: { id: ThemeMode; label: string }[] = [
  { id: 'system', label: 'System' },
  { id: 'dark', label: 'Dark' },
  { id: 'light', label: 'Light' },
]

const ACCENTS: { id: ThemeAccent; label: string }[] = [
  { id: 'teal', label: 'Teal' },
  { id: 'blue', label: 'Blue' },
  { id: 'amber', label: 'Amber' },
  { id: 'rose', label: 'Rose' },
]

export function SettingsPanel({ onReload }: { onReload: () => void }) {
  const [baseDraft, setBaseDraft] = useState(getApiBase)
  const [keyDraft, setKeyDraft] = useState(getApiKey)
  const [testBusy, setTestBusy] = useState(false)
  const [testMsg, setTestMsg] = useState('')
  const [testOk, setTestOk] = useState(false)
  const [backupBusy, setBackupBusy] = useState(false)
  const [backupMsg, setBackupMsg] = useState('')
  const [backupIsError, setBackupIsError] = useState(false)
  const [mode, setMode] = useState(readThemeMode)
  const [accent, setAccent] = useState(readThemeAccent)
  const [startHour, setStartHour] = useState('')
  const [endHour, setEndHour] = useState('')
  const [windowLabel, setWindowLabel] = useState('')
  const [windowLoaded, setWindowLoaded] = useState(false)
  const [windowBusy, setWindowBusy] = useState(false)
  const [windowMsg, setWindowMsg] = useState('')
  const [windowOk, setWindowOk] = useState(false)

  useEffect(() => {
    let cancelled = false
    void fetchScaleWindow()
      .then((status) => {
        if (cancelled) return
        setStartHour(String(status.start_hour))
        setEndHour(String(status.end_hour))
        setWindowLabel(status.window)
        setWindowMsg('')
      })
      .catch((error: unknown) => {
        if (cancelled) return
        setWindowOk(false)
        setWindowMsg(error instanceof Error ? error.message : String(error))
      })
      .finally(() => {
        if (!cancelled) setWindowLoaded(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  function parseHour(value: string): number | null {
    if (!/^\d{1,2}$/.test(value.trim())) return null
    const hour = Number(value)
    if (!Number.isInteger(hour) || hour < 0 || hour > 23) return null
    return hour
  }

  async function saveWindow() {
    const start = parseHour(startHour)
    const end = parseHour(endHour)
    if (start === null || end === null) {
      setWindowOk(false)
      setWindowMsg('Use whole hours from 0 to 23.')
      return
    }
    if (end <= start) {
      setWindowOk(false)
      setWindowMsg('End hour must be later than the start hour on the same day.')
      return
    }
    setWindowBusy(true)
    setWindowMsg('')
    try {
      const status = await saveScaleWindow(start, end)
      setStartHour(String(status.start_hour))
      setEndHour(String(status.end_hour))
      setWindowLabel(status.window)
      setWindowOk(true)
      setWindowMsg(`Saved ${status.window}`)
    } catch (error) {
      setWindowOk(false)
      setWindowMsg(error instanceof Error ? error.message : String(error))
    } finally {
      setWindowBusy(false)
    }
  }

  function saveUrl() {
    setApiBase(baseDraft)
    setBaseDraft(getApiBase())
    onReload()
  }

  function saveKey() {
    setApiKey(keyDraft)
    setKeyDraft(getApiKey())
    onReload()
  }

  function isAuthFailure(error: unknown): boolean {
    const msg = error instanceof Error ? error.message : String(error)
    return msg === 'API key rejected' || /\b401\b/.test(msg)
  }

  async function testConnection() {
    setApiKey(keyDraft)
    setTestBusy(true)
    setTestMsg('')
    try {
      const health = await api.healthLiveness()
      setTestOk(true)
      setTestMsg(`ok · ${health.service ?? 'ok'} · ${getApiBase()}`)
    } catch (e) {
      setTestOk(false)
      setTestMsg(
        isAuthFailure(e)
          ? 'Auth failed: API key rejected'
          : `error · ${e instanceof Error ? e.message : String(e)}`,
      )
    } finally {
      setTestBusy(false)
    }
  }

  async function downloadBackup() {
    setApiKey(keyDraft)
    setBackupBusy(true)
    setBackupMsg('')
    setBackupIsError(false)
    try {
      await api.downloadBackup()
      setBackupMsg('Backup zip downloaded. Restore is manual — see Pi README.')
    } catch (e) {
      setBackupIsError(true)
      setBackupMsg(e instanceof Error ? e.message : String(e))
    } finally {
      setBackupBusy(false)
    }
  }

  function selectMode(next: ThemeMode) {
    setMode(next)
    writeThemeMode(next)
    applyTheme(next, accent)
  }

  function selectAccent(next: ThemeAccent) {
    setAccent(next)
    writeThemeAccent(next)
    applyTheme(mode, next)
  }

  return (
    <section className="panel">
      <h2>Settings</h2>
      <p className="lede">
        Pi API address, API key, and appearance for this browser. The key stays in this
        browser. Theme is not stored on the Pi.
      </p>

      <h3 className="settings-heading">Connection</h3>
      <form
        className="settings-bar"
        onSubmit={(event) => {
          event.preventDefault()
          saveUrl()
        }}
      >
        <input
          aria-label="Pi API base URL"
          value={baseDraft}
          onChange={(event) => setBaseDraft(event.target.value)}
          placeholder="http://192.168.178.23:8741"
          inputMode="url"
          spellCheck={false}
        />
        <button type="submit" className="primary">
          Save URL
        </button>
        <button type="button" disabled={testBusy} onClick={() => void testConnection()}>
          {testBusy ? 'Testing…' : 'Test'}
        </button>
        <button
          type="button"
          disabled={backupBusy}
          onClick={() => void downloadBackup()}
          title="Download SSOT databases as a zip (restore is manual)"
        >
          {backupBusy ? 'Backing up…' : 'Download backup'}
        </button>
      </form>
      <form
        className="settings-bar"
        onSubmit={(event) => {
          event.preventDefault()
          saveKey()
        }}
      >
        <input
          aria-label="API key"
          type="password"
          value={keyDraft}
          onChange={(event) => setKeyDraft(event.target.value)}
          placeholder="API key"
          autoComplete="off"
          spellCheck={false}
        />
        <button type="submit" className="primary">
          Save API key
        </button>
      </form>
      <p className="settings-note">Stored in this browser and sent on every request. The Pi never returns it.</p>
      <div className="settings-msgs" aria-live="polite">
        {testMsg ? <p className={testOk ? 'settings-note ok' : 'error-box'}>{testMsg}</p> : null}
        {backupMsg ? (
          <p className={backupIsError ? 'error-box' : 'settings-note'}>{backupMsg}</p>
        ) : null}
      </div>

      <h3 className="settings-heading">Scale listen window</h3>
      <p className="settings-note">
        {windowLabel
          ? `Pi window ${windowLabel}. `
          : 'Whole hours in the Pi timezone. '}
        Listening starts at the start hour and stops before the end hour, on the same day. Today&apos;s
        reading still ends the scan. Manual start and stop ignore this window.
      </p>
      <form
        className="settings-bar"
        onSubmit={(event) => {
          event.preventDefault()
          void saveWindow()
        }}
      >
        <label className="settings-label">
          Start hour
          <input
            aria-label="Scale listen start hour"
            type="number"
            min={0}
            max={23}
            step={1}
            inputMode="numeric"
            value={startHour}
            onChange={(event) => setStartHour(event.target.value)}
            style={{ width: '6rem', minWidth: '6rem', flex: '0 0 auto', display: 'block', marginTop: '0.25rem' }}
          />
        </label>
        <label className="settings-label">
          End hour
          <input
            aria-label="Scale listen end hour"
            type="number"
            min={0}
            max={23}
            step={1}
            inputMode="numeric"
            value={endHour}
            onChange={(event) => setEndHour(event.target.value)}
            style={{ width: '6rem', minWidth: '6rem', flex: '0 0 auto', display: 'block', marginTop: '0.25rem' }}
          />
        </label>
        <button type="submit" className="primary" disabled={!windowLoaded || windowBusy}>
          {windowBusy ? 'Saving…' : 'Save window'}
        </button>
      </form>
      {windowMsg ? <p className={windowOk ? 'settings-note ok' : 'error-box'}>{windowMsg}</p> : null}

      <h3 className="settings-heading">Appearance</h3>
      <div className="settings-block">
        <div className="settings-label" id="theme-mode-label">
          Mode
        </div>
        <div className="choice-row" role="group" aria-labelledby="theme-mode-label">
          {MODES.map((item) => (
            <button
              key={item.id}
              type="button"
              className={mode === item.id ? 'primary' : undefined}
              aria-pressed={mode === item.id}
              onClick={() => selectMode(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
      <div className="settings-block">
        <div className="settings-label" id="theme-accent-label">
          Accent
        </div>
        <div className="choice-row" role="group" aria-labelledby="theme-accent-label">
          {ACCENTS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={accent === item.id ? 'primary' : undefined}
              aria-pressed={accent === item.id}
              onClick={() => selectAccent(item.id)}
            >
              <span className={`accent-dot accent-dot-${item.id}`} aria-hidden="true" />
              {item.label}
            </button>
          ))}
        </div>
      </div>
    </section>
  )
}
