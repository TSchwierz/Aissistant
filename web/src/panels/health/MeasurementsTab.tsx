import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, type HealthMeasurement } from '../../api'
import { errorMessage, formatWhen } from './shared'

function Amount({ pct, kg }: { pct?: number | null; kg?: number | null }) {
  if (pct == null && kg == null) return <span>—</span>
  return (
    <span className="health-pair">
      <span>{pct == null ? '—' : `${pct.toFixed(1)}%`}</span>
      <span className="muted">{kg == null ? '—' : `${kg.toFixed(1)} kg`}</span>
    </span>
  )
}

export function MeasurementsTab() {
  const [rows, setRows] = useState<HealthMeasurement[]>([])
  const [drafts, setDrafts] = useState<Record<number, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setRows(await api.healthMeasurements())
      setDrafts({})
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const sorted = useMemo(
    () =>
      [...rows].sort(
        (a, b) => new Date(b.measured_at).getTime() - new Date(a.measured_at).getTime(),
      ),
    [rows],
  )

  function clearDraft(id: number) {
    setDrafts((prev) => {
      if (!(id in prev)) return prev
      const next = { ...prev }
      delete next[id]
      return next
    })
  }

  async function saveWeight(row: HealthMeasurement) {
    const text = (drafts[row.id] ?? String(row.weight_kg)).trim()
    const weight = Number(text)
    if (!text || !Number.isFinite(weight) || weight <= 0) {
      setError('Enter a weight in kg')
      return
    }
    setBusyId(row.id)
    setError(null)
    try {
      await api.updateMeasurement(row.id, { weight_kg: weight })
      clearDraft(row.id)
      await load()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusyId(null)
    }
  }

  async function remove(id: number) {
    setBusyId(id)
    setError(null)
    try {
      await api.deleteMeasurement(id)
      clearDraft(id)
      await load()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <>
      <div className="panel-actions">
        <button type="button" className="primary" onClick={() => void load()}>
          Refresh
        </button>
      </div>
      {loading && <p className="muted">Loading…</p>}
      {error && <div className="error-box">{error}</div>}
      {!loading && sorted.length === 0 && !error && (
        <div className="list-empty">No measurements yet.</div>
      )}
      {sorted.length > 0 && (
        <div className="health-scroll">
          <div className="health-head">
            <span>Time</span>
            <span>Weight</span>
            <span>Body fat</span>
            <span>Muscle</span>
            <span>Water</span>
            <span />
          </div>
          {sorted.map((row) => (
            <div className="health-row" key={row.id}>
              <span>{formatWhen(row.measured_at)}</span>
              <div className="health-weight">
                <input
                  type="number"
                  min={0}
                  step="0.1"
                  aria-label={`Weight on ${formatWhen(row.measured_at)}`}
                  value={drafts[row.id] ?? String(row.weight_kg)}
                  disabled={busyId === row.id}
                  onChange={(event) =>
                    setDrafts((prev) => ({ ...prev, [row.id]: event.target.value }))
                  }
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') void saveWeight(row)
                  }}
                />
                <span className="muted">kg</span>
              </div>
              <Amount pct={row.body_fat_pct} kg={row.body_fat_kg} />
              <Amount pct={row.muscle_pct} kg={row.muscle_mass_kg} />
              <Amount pct={row.water_pct} kg={row.water_kg} />
              <div className="health-row-actions">
                <button
                  type="button"
                  className="health-btn"
                  disabled={busyId === row.id}
                  onClick={() => void saveWeight(row)}
                >
                  Save
                </button>
                <button
                  type="button"
                  className="health-btn"
                  disabled={busyId === row.id}
                  onClick={() => void remove(row.id)}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  )
}
