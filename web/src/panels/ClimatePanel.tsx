import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  CategoryScale,
  Chart as ChartJS,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  Legend,
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
import { themeChartColors } from '../theme'
import { ForecastTab } from './climate/ForecastTab'

ChartJS.register(CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend)

type ClimateSection = 'now' | 'history' | 'outside' | 'forecast' | 'settings'
type HistoryRange = '12h' | '24h' | '7d' | '30d'

const HISTORY_RANGES: { id: HistoryRange; label: string; hours: number }[] = [
  { id: '12h', label: '12 hours', hours: 12 },
  { id: '24h', label: '24 hours', hours: 24 },
  { id: '7d', label: '7 days', hours: 24 * 7 },
  { id: '30d', label: '30 days', hours: 24 * 30 },
]

function decimate<T>(rows: T[], maxPoints: number): T[] {
  if (rows.length <= maxPoints) return rows
  const step = (rows.length - 1) / (maxPoints - 1)
  const picked: T[] = []
  for (let index = 0; index < maxPoints; index += 1) {
    picked.push(rows[Math.round(index * step)])
  }
  return picked
}

function climateChartOptions() {
  const colors = themeChartColors()
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { labels: { color: colors.muted } } },
    scales: {
      x: {
        ticks: { color: colors.muted, maxTicksLimit: 8 },
        grid: { color: colors.grid },
      },
      y: {
        position: 'left' as const,
        ticks: { color: colors.muted },
        grid: { color: colors.grid },
      },
      y1: {
        position: 'right' as const,
        ticks: { color: colors.muted },
        grid: { drawOnChartArea: false },
      },
    },
  }
}

export function ClimatePanel() {
  const [section, setSection] = useState<ClimateSection>('now')
  const [historyRange, setHistoryRange] = useState<HistoryRange>('24h')
  const [current, setCurrent] = useState<ClimateCurrent | null>(null)
  const [rows, setRows] = useState<ClimateMeasurement[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [outside, setOutside] = useState<ClimateOutside | null>(null)
  const [settings, setSettings] = useState<ClimateSettings | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [forecastReload, setForecastReload] = useState(0)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [cur, out, cfg] = await Promise.all([
        api.climateCurrent(),
        api.climateOutside().catch(() => null),
        api.climateSettings().catch(() => null),
      ])
      setCurrent(cur)
      setOutside(out)
      setSettings(cfg)
      setForecastReload((value) => value + 1)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (section !== 'history') return
    const range = HISTORY_RANGES.find((item) => item.id === historyRange) ?? HISTORY_RANGES[1]
    let cancelled = false
    setHistoryLoading(true)
    void (async () => {
      try {
        const from = new Date(Date.now() - range.hours * 60 * 60 * 1000).toISOString()
        const meas = await api.climateMeasurements(50_000, from)
        if (!cancelled) {
          setRows(meas.measurements)
          setError(null)
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      } finally {
        if (!cancelled) setHistoryLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [section, historyRange])

  const chartRows = useMemo(() => decimate(rows, 800), [rows])

  const chartData = useMemo(() => {
    const colors = themeChartColors()
    const span =
      chartRows.length > 1
        ? new Date(chartRows[chartRows.length - 1].ts).getTime() - new Date(chartRows[0].ts).getTime()
        : 0
    const labels = chartRows.map((row) => {
      const when = new Date(row.ts)
      return span > 36 * 60 * 60 * 1000
        ? when.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
        : when.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    })
    return {
      labels,
      datasets: [
        {
          label: 'Temp °C',
          data: chartRows.map((r) => r.temperature_c),
          borderColor: colors.accent,
          backgroundColor: 'transparent',
          tension: 0.25,
          yAxisID: 'y',
          fill: false,
          pointRadius: chartRows.length > 120 ? 0 : 2,
        },
        {
          label: 'Humidity %',
          data: chartRows.map((r) => r.humidity_pct),
          borderColor: colors.secondary,
          backgroundColor: 'transparent',
          tension: 0.25,
          yAxisID: 'y1',
        },
      ],
    }
  }, [chartRows])

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
          <div className="subnav" role="tablist" aria-label="Climate sections">
            <button
              type="button"
              className={section === 'now' ? 'active' : undefined}
              onClick={() => setSection('now')}
            >
              Now
            </button>
            <button
              type="button"
              className={section === 'history' ? 'active' : undefined}
              onClick={() => setSection('history')}
            >
              History
            </button>
            <button
              type="button"
              className={section === 'outside' ? 'active' : undefined}
              onClick={() => setSection('outside')}
            >
              Outside
            </button>
            <button
              type="button"
              className={section === 'forecast' ? 'active' : undefined}
              onClick={() => setSection('forecast')}
            >
              Forecast
            </button>
            <button
              type="button"
              className={section === 'settings' ? 'active' : undefined}
              onClick={() => setSection('settings')}
            >
              Settings
            </button>
          </div>
          {section === 'now' && (
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
              </div>
              <div className="section-card" style={{ marginTop: '0.85rem' }}>
                <h3>Humidity</h3>
                <p style={{ margin: 0 }}>
                  {ventilation?.reason || 'No ventilation advice yet.'}
                </p>
              </div>
              {current.open_incident && (
                <div className="section-card">
                  <h3>Open incident</h3>
                  <p style={{ margin: 0 }}>
                    #{current.open_incident.id} · {current.open_incident.metric}{' '}
                    {current.open_incident.direction}
                  </p>
                </div>
              )}
            </>
          )}
          {section === 'history' && (
            <>
              <div className="subnav" role="group" aria-label="History range">
                {HISTORY_RANGES.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={historyRange === item.id ? 'active' : undefined}
                    onClick={() => setHistoryRange(item.id)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              <div className="chart-wrap">
                {historyLoading && chartRows.length === 0 ? (
                  <p className="muted">Loading…</p>
                ) : chartRows.length > 0 ? (
                  <Line data={chartData} options={climateChartOptions()} />
                ) : (
                  <div className="list-empty">No indoor measurements in this range.</div>
                )}
              </div>
            </>
          )}
          {section === 'outside' && (
            <>
              <div className="grid-2">
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
              {formError && <div className="error-box">{formError}</div>}
            </>
          )}
          {section === 'forecast' && <ForecastTab reloadToken={forecastReload} />}
          {section === 'settings' && settings && (
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
        </>
      )}
    </section>
  )
}
