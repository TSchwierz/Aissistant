import { useCallback, useEffect, useState } from 'react'
import { api, type MorningBrief } from '../api'

export function BriefPanel() {
  const [brief, setBrief] = useState<MorningBrief | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async (refresh = false) => {
    setLoading(true)
    setError(null)
    try {
      setBrief(await api.morningBrief(refresh))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load(false)
  }, [load])

  return (
    <section className="panel">
      <h2>Morning brief</h2>
      <p className="lede">Pi-composed English script and sections. TTS stays on the phone.</p>
      <div className="panel-actions">
        <button type="button" className="primary" onClick={() => void load(true)}>
          Refresh
        </button>
      </div>
      {loading && <p className="muted">Loading…</p>}
      {error && <div className="error-box">{error}</div>}
      {brief && !loading && (
        <>
          <div className="grid-2" style={{ marginBottom: '0.85rem' }}>
            <div className="stat">
              <div className="label">Date</div>
              <div className="value" style={{ fontSize: '1.05rem' }}>
                {brief.meta.date}
              </div>
            </div>
            <div className="stat">
              <div className="label">Sections</div>
              <div className="value" style={{ fontSize: '1.05rem' }}>
                {brief.meta.sections_present.join(', ') || '—'}
              </div>
            </div>
          </div>
          {brief.meta.empty_reason && (
            <p className="muted">Empty reason: {brief.meta.empty_reason}</p>
          )}
          <h3 className="muted" style={{ fontSize: '0.85rem', marginBottom: '0.35rem' }}>
            Script
          </h3>
          <div className="script-box">{brief.script || '—'}</div>
          {brief.sections.map((s) => (
            <div className="section-card" key={s.id}>
              <h3>{s.title}</h3>
              <p style={{ margin: 0 }}>{s.body}</p>
            </div>
          ))}
        </>
      )}
    </section>
  )
}
