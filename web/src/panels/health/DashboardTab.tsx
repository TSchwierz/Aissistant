import { useCallback, useEffect, useState } from 'react'
import { api, type HealthProfile, type HealthStats } from '../../api'
import { errorMessage, pair } from './shared'
import { TargetsBlock } from './TargetsBlock'

function spokenWindow(windowLabel: string | null): string | null {
  if (!windowLabel) return null
  const parts = windowLabel.split('-')
  if (parts.length === 2 && parts[0] && parts[1]) return `${parts[0]} to ${parts[1]}`
  return windowLabel
}

export function DashboardTab() {
  const [stats, setStats] = useState<HealthStats | null>(null)
  const [profile, setProfile] = useState<HealthProfile | null>(null)
  const [scale, setScale] = useState<string | null>(null)
  const [listenWindow, setListenWindow] = useState<string | null>(null)
  const [mode, setMode] = useState('auto')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [s, p, scan] = await Promise.all([
        api.healthStats(),
        api.healthProfile(),
        api.scaleStatus().catch(() => null),
      ])
      setStats(s)
      setProfile(p)
      setMode(scan?.mode || 'auto')
      setListenWindow(scan ? scan.window : null)
      setScale(
        scan
          ? `${scan.mode || 'auto'} · ${scan.window} · ${scan.phase}${scan.detail ? ` — ${scan.detail}` : ''}`
          : null,
      )
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setLoading(false)
    }
  }, [])

  const refreshScale = useCallback(async () => {
    const scan = await api.scaleStatus().catch(() => null)
    if (!scan) return
    setMode(scan.mode || 'auto')
    setListenWindow(scan.window)
    setScale(
      `${scan.mode || 'auto'} · ${scan.window} · ${scan.phase}${scan.detail ? ` — ${scan.detail}` : ''}`,
    )
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    const timer = window.setInterval(() => {
      void refreshScale()
    }, 3000)
    return () => window.clearInterval(timer)
  }, [refreshScale])

  useEffect(() => {
    if (!scale || !/Stored|recorded/i.test(scale)) return
    let cancelled = false
    void api.healthStats().then((next) => {
      if (!cancelled) setStats(next)
    }).catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [scale])

  async function setScan(action: 'start' | 'stop' | 'auto') {
    setBusy(true)
    setError(null)
    try {
      const scan = await api.setScaleMode(action)
      setMode(scan.mode || action)
      await load()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const latest = stats?.latest
  const nutrition = stats?.nutrition ?? profile?.nutrition
  const meals = profile?.meals_per_day || nutrition?.meals_per_day || 3
  const listenRange = spokenWindow(listenWindow)

  return (
    <>
      <p className="lede">
        The Pi records the scale over Bluetooth{' '}
        {listenRange ? `from ${listenRange}` : 'during the saved morning window'}, then stops once
        today&apos;s measurement is stored. Height, age, and sex stay on the health dashboard.
      </p>
      <div className="panel-actions">
        <button type="button" className="primary" onClick={() => void load()}>
          Refresh
        </button>
        <button type="button" disabled={busy || mode === 'on'} onClick={() => void setScan('start')}>
          Start scan
        </button>
        <button type="button" disabled={busy || mode === 'off'} onClick={() => void setScan('stop')}>
          Stop scan
        </button>
        <button type="button" disabled={busy || mode === 'auto'} onClick={() => void setScan('auto')}>
          Use schedule
        </button>
      </div>
      {loading && <p className="muted">Loading…</p>}
      {error && <div className="error-box">{error}</div>}
      {stats && profile && !loading && (
        <div className="grid-2">
          <div className="stat">
            <div className="label">Latest weight</div>
            <div className="value">
              {stats.latest ? `${stats.latest.weight_kg.toFixed(1)} kg` : '—'}
            </div>
          </div>
          <div className="stat">
            <div className="label">7d average</div>
            <div className="value">
              {stats.avg_weight_7d != null ? `${stats.avg_weight_7d.toFixed(1)} kg` : '—'}
            </div>
          </div>
          <div className="stat">
            <div className="label">Measurements</div>
            <div className="value">{stats.count}</div>
          </div>
          {scale && (
            <div className="stat">
              <div className="label">Scale listener</div>
              <div className="value" style={{ fontSize: '1.05rem' }}>
                {scale}
              </div>
            </div>
          )}
          <div className="stat">
            <div className="label">Profile</div>
            <div className="value" style={{ fontSize: '1.05rem' }}>
              {profile.name || '—'} · {profile.is_complete ? 'complete' : 'incomplete'}
            </div>
          </div>
          {latest?.bmi != null && (
            <div className="stat">
              <div className="label">BMI</div>
              <div className="value">{latest.bmi.toFixed(1)}</div>
            </div>
          )}
          {latest && (latest.body_fat_pct != null || latest.body_fat_kg != null) && (
            <div className="stat">
              <div className="label">Body fat</div>
              <div className="value" style={{ fontSize: '1.05rem' }}>
                {pair(latest.body_fat_pct, latest.body_fat_kg)}
              </div>
            </div>
          )}
          {latest && (latest.muscle_pct != null || latest.muscle_mass_kg != null) && (
            <div className="stat">
              <div className="label">Muscle</div>
              <div className="value" style={{ fontSize: '1.05rem' }}>
                {pair(latest.muscle_pct, latest.muscle_mass_kg)}
              </div>
            </div>
          )}
          {latest && (latest.water_pct != null || latest.water_kg != null) && (
            <div className="stat">
              <div className="label">Water</div>
              <div className="value" style={{ fontSize: '1.05rem' }}>
                {pair(latest.water_pct, latest.water_kg)}
              </div>
            </div>
          )}
          {latest && (latest.bone_pct != null || latest.bone_mass_kg != null) && (
            <div className="stat">
              <div className="label">Bone</div>
              <div className="value" style={{ fontSize: '1.05rem' }}>
                {pair(latest.bone_pct, latest.bone_mass_kg)}
              </div>
            </div>
          )}
          {nutrition && (
            <div className="stat" style={{ gridColumn: '1 / -1' }}>
              <TargetsBlock
                nutrition={nutrition}
                meals={meals}
                currentFatPct={latest?.body_fat_pct}
              />
            </div>
          )}
        </div>
      )}
    </>
  )
}
