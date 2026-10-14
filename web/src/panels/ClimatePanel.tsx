import { useCallback, useEffect, useMemo, useState } from 'react'
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
import { api, type ClimateCurrent, type ClimateMeasurement } from '../api'
import { getApiBase } from '../api'

ChartJS.register(CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend, Filler)

export function ClimatePanel() {
  const [current, setCurrent] = useState<ClimateCurrent | null>(null)
  const [rows, setRows] = useState<ClimateMeasurement[]>([])
  const [outside, setOutside] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [cur, meas, out] = await Promise.all([
        api.climateCurrent(),
        api.climateMeasurements(288),
        api.climateOutside().catch(() => null),
      ])
      setCurrent(cur)
      setRows(meas.measurements)
      setOutside(out)
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

  const m = current?.measurement
  const reading = outside?.reading as
    | { temperature_c?: number; humidity_pct?: number; condition?: string }
    | null
    | undefined

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
