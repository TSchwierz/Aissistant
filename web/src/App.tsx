import { useCallback, useEffect, useState } from 'react'
import { api, getApiBase } from './api'
import { BriefPanel } from './panels/BriefPanel'
import { CalendarReminders } from './calendarReminders'
import { CalendarPanel } from './panels/CalendarPanel.tsx'
import { ClimatePanel } from './panels/ClimatePanel'
import { HealthPanel } from './panels/HealthPanel'
import { NewsPanel } from './panels/NewsPanel'
import { SettingsPanel } from './panels/SettingsPanel'
import { applyTheme } from './theme'
import './App.css'

applyTheme()

type Tab = 'brief' | 'calendar' | 'climate' | 'health' | 'news' | 'settings'

const TABS: { id: Tab; label: string }[] = [
  { id: 'brief', label: 'Morning brief' },
  { id: 'calendar', label: 'Calendar' },
  { id: 'climate', label: 'Climate' },
  { id: 'health', label: 'Health' },
  { id: 'news', label: 'News' },
  { id: 'settings', label: 'Settings' },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('brief')
  const [conn, setConn] = useState<'unknown' | 'ok' | 'err'>('unknown')
  const [connDetail, setConnDetail] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const [navOpen, setNavOpen] = useState(false)

  const probe = useCallback(async () => {
    try {
      const health = await api.healthLiveness()
      setConn('ok')
      setConnDetail(`${health.service ?? 'ok'} · ${getApiBase()}`)
    } catch (e) {
      setConn('err')
      setConnDetail(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => {
    void probe()
  }, [probe, reloadKey])

  useEffect(() => {
    applyTheme()
  }, [])

  useEffect(() => {
    if (!navOpen) return
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setNavOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [navOpen])

  function selectTab(id: Tab) {
    setTab(id)
    setNavOpen(false)
  }

  return (
    <div className="app-frame">
      <CalendarReminders />
      <aside id="app-sidebar" className={navOpen ? 'sidebar open' : 'sidebar'}>
        <div className="brand">
          <h1>Personal AIssistent</h1>
          <p>LAN web UI for the Pi SSOT.</p>
        </div>
        <nav className="sidebar-nav" aria-label="Sections">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={tab === item.id ? 'active' : undefined}
              aria-current={tab === item.id ? 'page' : undefined}
              onClick={() => selectTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-status">
          <span
            className={`status-pill ${conn === 'ok' ? 'ok' : conn === 'err' ? 'err' : ''}`}
            title={connDetail || undefined}
          >
            {conn === 'unknown' ? '…' : conn === 'ok' ? 'connected' : 'offline'}
          </span>
          {connDetail ? <p className="sidebar-detail">{connDetail}</p> : null}
        </div>
      </aside>
      {navOpen ? (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-label="Close menu"
          onClick={() => setNavOpen(false)}
        />
      ) : null}
      <div className="app-main">
        <button
          type="button"
          className="menu-toggle"
          aria-expanded={navOpen}
          aria-controls="app-sidebar"
          onClick={() => setNavOpen((open) => !open)}
        >
          Menu
        </button>
        <main key={`${tab}-${reloadKey}`}>
          {tab === 'brief' && <BriefPanel />}
          {tab === 'calendar' && <CalendarPanel />}
          {tab === 'climate' && <ClimatePanel />}
          {tab === 'health' && <HealthPanel />}
          {tab === 'news' && <NewsPanel />}
          {tab === 'settings' && (
            <SettingsPanel onReload={() => setReloadKey((key) => key + 1)} />
          )}
        </main>
      </div>
    </div>
  )
}
