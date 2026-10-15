import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  CategoryScale,
  Chart as ChartJS,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import { Line } from 'react-chartjs-2'
import {
  api,
  type ClimateCurrent,
  type ClimateMeasurement,
  type ClimateOutside,
  type ClimateSettings,
} from '../api'
import { getApiBase } from '../api'

ChartJS.register(CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend, Filler)

export function ClimatePanel() {
  const [current, setCurrent] = useState<ClimateCurrent | null>(null)
  const [rows, setRows] = useState<ClimateMeasurement[]>([])
  const [outside, setOutside] = useState<ClimateOutside | null>(null)
  const [settings, setSettings] = useState<ClimateSettings | null>(null)
  const [strategies, setStrategies] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [cur, meas, out, cfg, advice] = await Promise.all([
        api.climateCurrent(),
        api.climateMeasurements(288),
        api.climateOutside().catch(() => null),
        api.climateSettings().catch(() => null),
        api.climateStrategies().catch(() => ({ markdown: '' })),
      ])
      setCurrent(cur)
      setRows(meas.measurements)
      setOutside(out)
      setSettings(cfg)
      setStrategies(advice.markdown)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const chartData = useMemo(() => {
    const labels = rows.map((r) =>
      new Date(r.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    )
    return {
      labels,
      datasets: [
        {
          label: 'Temp °C',
          data: rows.map((r) => r.temperature_c),
          borderColor: '#3db8a0',
          backgroundColor: 'rgba(61,184,160,0.15)',
          tension: 0.25,
          yAxisID: 'y',
          fill: true,
        },
        {
          label: 'Humidity %',
          data: rows.map((r) => r.humidity_pct),
          borderColor: '#7aa2d6',
          backgroundColor: 'transparent',
          tension: 0.25,
          yAxisID: 'y1',
        },
      ],
    }
  }, [rows])

  async function saveSettings(event: FormEvent) {
    event.preventDefault()
    if (!settings) return
    setSaving(true)
    setFormError(null)
    try {
      const saved = await api.updateClimateSettings({
        humidity_min: Number(settings.humidity_min),
        humidity_max: Number(settings.humidity_max),
        temp_min: Number(settings.temp_min),
        temp_max: Number(settings.temp_max),
        sample_interval_seconds: Number(settings.sample_interval_seconds),
      })
      setSettings(saved)
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  async function refreshOutside() {
    setFormError(null)
    try {
      setOutside(await api.refreshClimateOutside())
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e))
    }
  }

  const m = current?.measurement
  const reading = outside?.reading
  const ventilation = outside?.comparison?.ventilation
  const reports = outside?.provider_reports ?? []

  return (
    <section className="panel">
      <h2>Climate</h2>
      <p className="lede">
        Studio Climate under <code>/climate</code>. Full JSON also at{' '}
        <a href={`${getApiBase()}/climate/current`} target="_blank" rel="noreferrer">
          /climate/current
        </a>
        .
      </p>
      <div className="panel-actions">
        <button type="button" className="primary" onClick={() => void load()}>
          Refresh
        </button>
      </div>
      {loading && <p className="muted">Loading…</p>}
      {error && <div className="error-box">{error}</div>}
      {current && !loading && (
        <>
          <div className="grid-2">
            <div className="stat">
              <div className="label">Indoor temp</div>
              <div className="value">{m ? `${m.temperature_c.toFixed(1)}°C` : '—'}</div>
            </div>
            <div className="stat">
              <div className="label">Indoor humidity</div>
              <div className="value">{m ? `${m.humidity_pct.toFixed(1)}%` : '—'}</div>
            </div>
            <div className="stat">
              <div className="label">Band status</div>
              <div className="value" style={{ fontSize: '1.05rem' }}>
                {current.status?.overall ?? '—'}
              </div>
            </div>
            <div className="stat">
              <div className="label">Outside</div>
              <div className="value" style={{ fontSize: '1.05rem' }}>
                {reading
                  ? `${reading.temperature_c?.toFixed?.(1) ?? '—'}°C · ${reading.condition ?? '—'}`
                  : '—'}
              </div>
            </div>
          </div>
          <div className="section-card" style={{ marginTop: '0.85rem' }}>
            <div className="card-head">
              <h3>Outside providers</h3>
              <button type="button" onClick={() => void refreshOutside()}>
                Refresh outside
              </button>
            </div>
            {reports.length === 0 && (
              <p className="muted" style={{ margin: 0 }}>
                No provider readings stored yet. The sampler polls Open-Meteo, OpenWeatherMap, and
                Bright Sky on its own; Refresh outside asks them now.
              </p>
            )}
            <div className="grid-2">
              {reports.map((report) => (
                <div key={report.name}>
                  <strong>{report.name}</strong>
                  <div className="muted">
                    {report.ok
                      ? `${report.temperature_c ?? '—'}°C · ${report.humidity_pct ?? '—'}% · ${report.condition ?? '—'}`
                      : report.error || 'unavailable'}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="section-card">
            <h3>Humidity</h3>
            <p style={{ margin: 0 }}>
              {ventilation?.reason || 'No ventilation advice yet.'}
            </p>
            {strategies.trim() && (
              <pre className="script-box" style={{ marginTop: '0.75rem', maxHeight: 160 }}>
                {strategies}
              </pre>
            )}
          </div>
          {settings && (
            <form className="topic-form" onSubmit={(event) => void saveSettings(event)}>
              <h3>Bands and sample interval</h3>
              <div className="time-row">
                <label>
                  Humidity min %
                  <input
                    type="number"
                    step="0.1"
                    value={settings.humidity_min}
                    onChange={(event) =>
                      setSettings({ ...settings, humidity_min: Number(event.target.value) })
                    }
                  />
                </label>
                <label>
                  Humidity max %
                  <input
                    type="number"
                    step="0.1"
                    value={settings.humidity_max}
                    onChange={(event) =>
                      setSettings({ ...settings, humidity_max: Number(event.target.value) })
                    }
                  />
                </label>
              </div>
              <div className="time-row">
                <label>
                  Temp min °C
                  <input
                    type="number"
                    step="0.1"
                    value={settings.temp_min}
                    onChange={(event) =>
                      setSettings({ ...settings, temp_min: Number(event.target.value) })
                    }
                  />
                </label>
                <label>
                  Temp max °C
                  <input
                    type="number"
                    step="0.1"
                    value={settings.temp_max}
                    onChange={(event) =>
                      setSettings({ ...settings, temp_max: Number(event.target.value) })
                    }
                  />
                </label>
              </div>
              <label>
                Sample every (seconds)
                <input
                  type="number"
                  min={2}
                  value={settings.sample_interval_seconds}
                  onChange={(event) =>
                    setSettings({
                      ...settings,
                      sample_interval_seconds: Number(event.target.value),
                    })
                  }
                />
                <span className="hint">Indoor temperature and humidity are recorded around the clock.</span>
              </label>
              {formError && <div className="error-box">{formError}</div>}
              <div className="panel-actions">
                <button type="submit" className="primary" disabled={saving}>
                  {saving ? 'Saving…' : 'Save bands'}
                </button>
              </div>
            </form>
          )}
          {current.open_incident && (
            <div className="section-card" style={{ marginTop: '0.85rem' }}>
              <h3>Open incident</h3>
              <p style={{ margin: 0 }}>
                #{current.open_incident.id} · {current.open_incident.metric}{' '}
                {current.open_incident.direction}
              </p>
            </div>
          )}
          <div className="chart-wrap">
            {rows.length > 0 ? (
              <Line
                data={chartData}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: { legend: { labels: { color: '#8b9aab' } } },
                  scales: {
                    x: {
                      ticks: { color: '#8b9aab', maxTicksLimit: 8 },
                      grid: { color: 'rgba(42,53,68,0.6)' },
                    },
                    y: {
                      position: 'left',
                      ticks: { color: '#8b9aab' },
                      grid: { color: 'rgba(42,53,68,0.6)' },
                    },
                    y1: {
                      position: 'right',
                      ticks: { color: '#8b9aab' },
                      grid: { drawOnChartArea: false },
                    },
                  },
                }}
              />
            ) : (
              <div className="list-empty">No indoor measurements yet (mock sensor seeds on API start).</div>
            )}
          </div>
        </>
      )}
    </section>
  )
}
