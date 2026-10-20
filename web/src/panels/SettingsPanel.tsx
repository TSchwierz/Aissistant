import { useState } from 'react'
import { api, getApiBase, setApiBase } from '../api'
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
  const [testBusy, setTestBusy] = useState(false)
  const [testMsg, setTestMsg] = useState('')
  const [testOk, setTestOk] = useState(false)
  const [backupBusy, setBackupBusy] = useState(false)
  const [backupMsg, setBackupMsg] = useState('')
  const [backupIsError, setBackupIsError] = useState(false)
  const [mode, setMode] = useState(readThemeMode)
  const [accent, setAccent] = useState(readThemeAccent)

  function saveUrl() {
    setApiBase(baseDraft)
    setBaseDraft(getApiBase())
    onReload()
  }

  async function testConnection() {
    setTestBusy(true)
    setTestMsg('')
    try {
      const health = await api.healthLiveness()
      setTestOk(true)
      setTestMsg(`ok · ${health.service ?? 'ok'} · ${getApiBase()}`)
    } catch (e) {
      setTestOk(false)
      setTestMsg(`error · ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setTestBusy(false)
    }
  }

  async function downloadBackup() {
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
        Pi API address and appearance for this browser. Theme is not stored on the Pi.
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
      <div className="settings-msgs" aria-live="polite">
        {testMsg ? <p className={testOk ? 'settings-note ok' : 'error-box'}>{testMsg}</p> : null}
        {backupMsg ? (
          <p className={backupIsError ? 'error-box' : 'settings-note'}>{backupMsg}</p>
        ) : null}
      </div>

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
