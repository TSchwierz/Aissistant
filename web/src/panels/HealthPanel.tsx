import { useCallback, useEffect, useState } from 'react'
import { api, getApiBase, type HealthProfile, type HealthStats } from '../api'

export function HealthPanel() {
  const [stats, setStats] = useState<HealthStats | null>(null)
  const [profile, setProfile] = useState<HealthProfile | null>(null)
  const [scale, setScale] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

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
      setScale(
        scan
          ? `${scan.window} · ${scan.phase}${scan.detail ? ` — ${scan.detail}` : ''}`
          : null,
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const dashUrl = `${getApiBase()}/`

  return (
    <section className="panel">
      <h2>Health</h2>
      <p className="lede">
        The Pi records the scale over Bluetooth from 06:00 to 12:00, then stops once today&apos;s
        measurement is stored. Profile editing stays on the HTML dashboard.
      </p>
      <div className="panel-actions">
        <button type="button" className="primary" onClick={() => void load()}>
          Refresh
        </button>
        <a href={dashUrl} target="_blank" rel="noreferrer">
          <button type="button">Open Health dashboard</button>
        </a>
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
          {stats.latest?.bmi != null && (
            <div className="stat">
              <div className="label">BMI</div>
              <div className="value">{stats.latest.bmi.toFixed(1)}</div>
            </div>
          )}
          {stats.latest?.body_fat_pct != null && (
            <div className="stat">
              <div className="label">Body fat</div>
              <div className="value">{stats.latest.body_fat_pct.toFixed(1)}%</div>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
