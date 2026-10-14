import { useCallback, useEffect, useState } from 'react'
import { api, getApiBase, setApiBase } from './api'
import { BriefPanel } from './panels/BriefPanel'
import { CalendarPanel } from './panels/CalendarPanel'
import { ClimatePanel } from './panels/ClimatePanel'
import { HealthPanel } from './panels/HealthPanel'
import { NewsPanel } from './panels/NewsPanel'
import './App.css'

type Tab = 'brief' | 'calendar' | 'climate' | 'health' | 'news'

const TABS: { id: Tab; label: string }[] = [
  { id: 'brief', label: 'Morning brief' },
  { id: 'calendar', label: 'Calendar' },
  { id: 'climate', label: 'Climate' },
  { id: 'health', label: 'Health' },
  { id: 'news', label: 'News' },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('brief')
  const [baseDraft, setBaseDraft] = useState(getApiBase)
  const [conn, setConn] = useState<'unknown' | 'ok' | 'err'>('unknown')
  const [connDetail, setConnDetail] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  const probe = useCallback(async () => {
    try {
      const h = await api.healthLiveness()
      setConn('ok')
      setConnDetail(`${h.service ?? 'ok'} · ${getApiBase()}`)
    } catch (e) {
      setConn('err')
      setConnDetail(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => {
    void probe()
  }, [probe, reloadKey])

  function applyBase() {
    setApiBase(baseDraft)
    setBaseDraft(getApiBase())
    setReloadKey((k) => k + 1)
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <h1>Personal AIssistent</h1>
          <p>LAN web UI for the Pi SSOT — no AI keys in the browser.</p>
        </div>
        <div className="settings-bar">
          <input
            aria-label="Pi API base URL"
            value={baseDraft}
            onChange={(e) => setBaseDraft(e.target.value)}
            placeholder="http://127.0.0.1:8741"
          />
          <button type="button" className="primary" onClick={applyBase}>
            Save URL
          </button>
          <button type="button" onClick={() => void probe()}>
            Test
          </button>
          <span className={`status-pill ${conn === 'ok' ? 'ok' : conn === 'err' ? 'err' : ''}`}>
            {conn === 'unknown' ? '…' : conn === 'ok' ? 'connected' : 'offline'}
          </span>
        </div>
      </header>
      {connDetail && (
        <p className="muted" style={{ marginTop: '-0.5rem', marginBottom: '0.85rem' }}>
          {connDetail}
        </p>
      )}

      <nav className="nav" aria-label="Sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={tab === t.id ? 'active' : undefined}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main key={`${tab}-${reloadKey}`}>
        {tab === 'brief' && <BriefPanel />}
        {tab === 'calendar' && <CalendarPanel />}
        {tab === 'climate' && <ClimatePanel />}
        {tab === 'health' && <HealthPanel />}
        {tab === 'news' && <NewsPanel />}
      </main>
    </div>
  )
}
