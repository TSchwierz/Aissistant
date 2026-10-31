import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  type ChartData,
  type ChartOptions,
  type TooltipItem,
} from 'chart.js'
import { Line } from 'react-chartjs-2'
import {
  fetchHourlyForecast,
  type HourlyForecast,
  type HourlyForecastPoint,
} from '../../forecastApi'
import { themeChartColors } from '../../theme'

ChartJS.register(CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend)

type Slot = {
  label: string
  point: HourlyForecastPoint | null
}

function formatInZone(epochMs: number, timeZone: string, withDate: boolean): string {
  const text = new Intl.DateTimeFormat('en-GB', {
    timeZone,
    ...(withDate ? { day: 'numeric' as const, month: 'short' as const } : {}),
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(new Date(epochMs))
  return text.replace(/\u202f/g, ' ')
}

function buildSlots(forecast: HourlyForecast): Slot[] | null {
  const startMs = Date.parse(forecast.from)
  if (Number.isNaN(startMs)) return null
  const hours = forecast.window_hours > 0 ? forecast.window_hours : 24
  const zone = forecast.timezone || 'Europe/Berlin'
  const slots: Slot[] = Array.from({ length: hours }, (_, index) => ({
    label: formatInZone(startMs + index * 3_600_000, zone, false),
    point: null,
  }))
  for (const point of forecast.points) {
    const at = Date.parse(point.ts)
    if (Number.isNaN(at)) continue
    const index = Math.floor((at - startMs) / 3_600_000)
    if (index < 0 || index >= hours) continue
    slots[index] = { ...slots[index], point }
  }
  return slots
}

function seriesValues(
  slots: Slot[],
  pick: (point: HourlyForecastPoint) => number | null,
): (number | null)[] {
  return slots.map((slot) => {
    if (!slot.point) return null
    const value = pick(slot.point)
    return value == null || Number.isNaN(value) ? null : value
  })
}

function caption(forecast: HourlyForecast): string {
  const zone = forecast.timezone || 'Europe/Berlin'
  const points = forecast.points
  if (points.length === 0) return `No stored hours in the next 24 hours (${zone}).`
  const counts = points.map((point) => point.provider_count)
  const min = Math.min(...counts)
  const max = Math.max(...counts)
  const providers =
    min === max ? `${min} ${min === 1 ? 'provider' : 'providers'}` : `${min}–${max} providers`
  const fetched = points
    .map((point) => point.fetched_at)
    .filter((value): value is string => Boolean(value))
    .sort()
    .at(-1)
  const when = fetched ? formatInZone(Date.parse(fetched), zone, true) : 'unknown time'
  return `${providers} · fetched ${when} · ${zone}`
}

function lineSeries(
  label: string,
  color: string,
  data: (number | null)[],
  yAxisID: 'y' | 'y1',
) {
  return {
    label,
    data,
    borderColor: color,
    backgroundColor: 'transparent' as const,
    tension: 0.25,
    yAxisID,
    spanGaps: false,
    pointRadius: 3,
    pointHoverRadius: 4,
  }
}

function forecastChartOptions(left: string, right: string): ChartOptions<'line'> {
  const colors = themeChartColors()
  const ticks = { color: colors.muted }
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { labels: { color: colors.muted } },
      tooltip: {
        callbacks: {
          label: (item: TooltipItem<'line'>) => {
            const y = item.parsed.y
            if (y == null || Number.isNaN(y)) return item.dataset.label ?? ''
            return `${item.dataset.label}: ${y}`
          },
        },
      },
    },
    scales: {
      x: {
        ticks: { ...ticks, maxTicksLimit: 8 },
        grid: { color: colors.grid },
      },
      y: {
        position: 'left',
        title: { display: true, text: left, color: colors.muted, font: { size: 12 } },
        ticks,
        grid: { color: colors.grid },
      },
      y1: {
        position: 'right',
        title: { display: true, text: right, color: colors.muted, font: { size: 12 } },
        ticks,
        grid: { drawOnChartArea: false },
      },
    },
  }
}

export function ForecastTab({ reloadToken = 0 }: { reloadToken?: number }) {
  const [forecast, setForecast] = useState<HourlyForecast | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setForecast(await fetchHourlyForecast())
    } catch (e) {
      setForecast(null)
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load, reloadToken])

  const slots = useMemo(() => (forecast ? buildSlots(forecast) : null), [forecast])
  const colors = themeChartColors()

  const temperature = useMemo<ChartData<'line', (number | null)[], string> | null>(() => {
    if (!slots) return null
    return {
      labels: slots.map((slot) => slot.label),
      datasets: [
        lineSeries(
          'Temperature °C',
          colors.accent,
          seriesValues(slots, (point) => point.temperature_c),
          'y',
        ),
        lineSeries(
          'Humidity %',
          colors.secondary,
          seriesValues(slots, (point) => point.humidity_pct),
          'y1',
        ),
      ],
    }
  }, [slots, colors.accent, colors.secondary])

  const precipitation = useMemo<ChartData<'line', (number | null)[], string> | null>(() => {
    if (!slots) return null
    return {
      labels: slots.map((slot) => slot.label),
      datasets: [
        lineSeries(
          'Precipitation %',
          colors.accent,
          seriesValues(slots, (point) => point.precipitation_probability),
          'y',
        ),
        lineSeries(
          'Wind km/h',
          colors.secondary,
          seriesValues(slots, (point) => point.wind_kph),
          'y1',
        ),
      ],
    }
  }, [slots, colors.accent, colors.secondary])

  const tempOptions = useMemo(() => forecastChartOptions('°C', '%'), [])
  const precipOptions = useMemo(() => forecastChartOptions('%', 'km/h'), [])

  return (
    <>
      <div className="panel-actions">
        <button type="button" onClick={() => void load()}>
          Refresh forecast
        </button>
      </div>
      {loading && <p className="muted">Loading…</p>}
      {error && <div className="error-box">{error}</div>}
      {forecast && slots && (
        <>
          <p className="muted" style={{ marginTop: 0 }}>
            {caption(forecast)}
          </p>
          {forecast.points.length === 0 ? (
            <div className="list-empty">No hourly forecast stored for the next 24 hours.</div>
          ) : (
            <>
              <div className="section-card">
                <h3>Temperature and humidity</h3>
                <div className="chart-wrap">
                  {temperature && <Line data={temperature} options={tempOptions} />}
                </div>
              </div>
              <div className="section-card">
                <h3>Precipitation and wind</h3>
                <div className="chart-wrap">
                  {precipitation && <Line data={precipitation} options={precipOptions} />}
                </div>
              </div>
              <div className="section-card">
                <h3>Condition</h3>
                <ul className="forecast-hours">
                  {slots.map((slot, index) => (
                    <li key={`${index}-${slot.label}`}>
                      {slot.label}{' '}
                      {slot.point ? slot.point.condition_label || '—' : '—'}
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </>
      )}
      {forecast && !slots && (
        <div className="error-box">Forecast window is missing a start time.</div>
      )}
    </>
  )
}
