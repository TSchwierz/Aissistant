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
import { api, type HealthMeasurement } from '../../api'
import { themeChartColors } from '../../theme'
import { errorMessage } from './shared'

ChartJS.register(CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend, Filler)

type RangeId = 30 | 90 | 365 | 'all'

const RANGES: { id: RangeId; label: string }[] = [
  { id: 30, label: '30 days' },
  { id: 90, label: '90 days' },
  { id: 365, label: '365 days' },
  { id: 'all', label: 'All' },
]

function healthChartOptions() {
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

function withinRange(iso: string, range: RangeId): boolean {
  if (range === 'all') return true
  const time = new Date(iso).getTime()
  if (Number.isNaN(time)) return false
  return time >= Date.now() - range * 24 * 60 * 60 * 1000
}

function axisLabel(iso: string, range: RangeId): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  if (range === 30) {
    return date.toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }
  if (range === 90) {
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
  }
  return date.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })
}

export function ChartsTab() {
  const [rows, setRows] = useState<HealthMeasurement[]>([])
  const [range, setRange] = useState<RangeId>(30)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setRows(await api.healthMeasurements(5000))
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const points = useMemo(() => {
    return rows
      .filter((row) => withinRange(row.measured_at, range))
      .sort((a, b) => new Date(a.measured_at).getTime() - new Date(b.measured_at).getTime())
  }, [rows, range])

  const chartData = useMemo(() => {
    const colors = themeChartColors()
    return {
      labels: points.map((row) => axisLabel(row.measured_at, range)),
      datasets: [
        {
          label: 'Weight kg',
          data: points.map((row) => row.weight_kg),
          borderColor: colors.accent,
          backgroundColor: colors.accentFill,
          tension: 0.25,
          yAxisID: 'y',
          fill: true,
          pointRadius: 2,
        },
        {
          label: 'Body fat %',
          data: points.map((row) => row.body_fat_pct ?? null),
          borderColor: '#e0a45a',
          backgroundColor: 'transparent',
          tension: 0.25,
          yAxisID: 'y1',
          pointRadius: 2,
        },
        {
          label: 'Muscle kg',
          data: points.map((row) => row.muscle_mass_kg ?? null),
          borderColor: colors.secondary,
          backgroundColor: 'transparent',
          tension: 0.25,
          yAxisID: 'y',
          pointRadius: 2,
        },
      ],
    }
  }, [points, range])

  return (
    <>
      <div className="panel-actions">
        {RANGES.map((item) => (
          <button
            key={item.id}
            type="button"
            className={range === item.id ? 'primary' : undefined}
            onClick={() => setRange(item.id)}
          >
            {item.label}
          </button>
        ))}
        <button type="button" onClick={() => void load()}>
          Refresh
        </button>
      </div>
      {loading && <p className="muted">Loading…</p>}
      {error && <div className="error-box">{error}</div>}
      {!loading && !error && points.length === 0 && (
        <div className="list-empty">No measurements in this range.</div>
      )}
      {!loading && points.length > 0 && (
        <div className="chart-wrap">
          <Line
            data={chartData}
            options={healthChartOptions()}
          />
        </div>
      )}
    </>
  )
}
