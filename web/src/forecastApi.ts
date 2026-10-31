/** Hourly outside forecast. Kept out of api.ts so that client stays unchanged. */

import { apiFetch } from './api.ts'

export type HourlyForecastPoint = {
  ts: string
  temperature_c: number | null
  humidity_pct: number | null
  condition: string | null
  condition_label: string
  precipitation_probability: number | null
  wind_kph: number | null
  provider_count: number
  fetched_at: string | null
}

export type HourlyForecast = {
  timezone: string
  window_hours: number
  from: string
  to: string
  points: HourlyForecastPoint[]
}

export async function fetchHourlyForecast(): Promise<HourlyForecast> {
  const response = await apiFetch('/climate/outside/hourly')
  if (response.status === 401) throw new Error('API key rejected')
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text.slice(0, 200) || `HTTP ${response.status}`)
  }
  return response.json() as Promise<HourlyForecast>
}
