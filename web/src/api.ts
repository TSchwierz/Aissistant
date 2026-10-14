/** Pi LAN API client — no AI keys in the browser. */

const STORAGE_KEY = 'pa_api_base'

export function getApiBase(): string {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored) return stored.replace(/\/$/, '')
  return (import.meta.env.VITE_PI_API_BASE as string | undefined)?.replace(/\/$/, '')
    || 'http://127.0.0.1:8741'
}

export function setApiBase(url: string): void {
  localStorage.setItem(STORAGE_KEY, url.trim().replace(/\/$/, ''))
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${getApiBase()}${path}`)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`)
  }
  return res.json() as Promise<T>
}

export type MorningBrief = {
  meta: {
    date: string
    timezone: string
    generated_at: string
    language: string
    sections_present: string[]
    empty_reason: string | null
    freshness?: Record<string, string | null>
  }
  weather?: {
    summary?: string
    high_c?: number
    low_c?: number
    precip_chance_pct?: number
    clothing_hint?: { rain_jacket?: boolean; hoody?: boolean; notes?: string }
  }
  calendar?: {
    events: Array<{
      id: string
      title: string
      start: string
      end?: string | null
      all_day?: boolean
      tags?: string[]
      location?: string | null
    }>
    first_event_start?: string | null
  }
  news?: {
    by_topic: Array<{
      topic_id: string
      topic_label: string
      digest: string
      item_count: number
      generated_at?: string
      ai_provider?: string | null
    }>
  }
  script: string
  sections: Array<{ id: string; title: string; body: string }>
}

export type CalendarEvent = {
  id: string
  title: string
  start: string
  end?: string | null
  all_day: boolean
  location?: string | null
  notes?: string | null
  tags: string[]
}

export type EventList = {
  count: number
  timezone: string
  range_start: string
  range_end: string
  events: CalendarEvent[]
}

export type HealthStats = {
  count: number
  latest: {
    id: number
    measured_at: string
    weight_kg: number
    bmi?: number | null
    body_fat_pct?: number | null
  } | null
  avg_weight_7d?: number | null
  avg_weight_30d?: number | null
  min_weight?: number | null
  max_weight?: number | null
  profile_complete: boolean
}

export type HealthProfile = {
  id: number
  name: string
  height_cm?: number | null
  age?: number | null
  sex?: string | null
  is_complete: boolean
}

export type ClimateCurrent = {
  measurement: {
    id: number
    ts: string
    temperature_c: number
    humidity_pct: number
  } | null
  bands: Record<string, number>
  status: { overall: string }
  open_incident: { id: number; metric: string; direction: string } | null
}

export type ClimateMeasurement = {
  id: number
  ts: string
  temperature_c: number
  humidity_pct: number
}

export type NewsTopic = {
  id: string
  label: string
  goal: string
  feed_urls: string[]
  last_run_status?: string | null
  last_run_at?: string | null
  last_error?: string | null
}

export type NewsDigest = {
  id: string
  topic_id: string
  topic_label: string
  digest: string
  item_count: number
  generated_at: string
  for_date: string
  ai_provider?: string | null
  status: string
}

export const api = {
  healthLiveness: () => getJson<{ status: string; service: string }>('/health'),
  morningBrief: (refresh = false) =>
    getJson<MorningBrief>(`/briefing/morning${refresh ? '?refresh=1' : ''}`),
  calendarDay: (day: string, tag?: string) => {
    const q = new URLSearchParams()
    if (tag) q.set('tag', tag)
    const qs = q.toString()
    return getJson<EventList>(`/calendar/day/${day}${qs ? `?${qs}` : ''}`)
  },
  calendarMonth: (month: string, tag?: string) => {
    const q = new URLSearchParams()
    if (tag) q.set('tag', tag)
    const qs = q.toString()
    return getJson<EventList>(`/calendar/month/${month}${qs ? `?${qs}` : ''}`)
  },
  calendarWeeks: (from?: string, tag?: string) => {
    const q = new URLSearchParams()
    if (from) q.set('from', from)
    if (tag) q.set('tag', tag)
    const qs = q.toString()
    return getJson<EventList>(`/calendar/weeks${qs ? `?${qs}` : ''}`)
  },
  calendarTags: () => getJson<{ tags: string[] }>('/calendar/tags'),
  healthStats: () => getJson<HealthStats>('/api/stats'),
  healthProfile: () => getJson<HealthProfile>('/api/profile'),
  climateCurrent: () => getJson<ClimateCurrent>('/climate/current'),
  climateMeasurements: (limit = 288) =>
    getJson<{ count: number; measurements: ClimateMeasurement[] }>(
      `/climate/measurements?limit=${limit}`,
    ),
  climateOutside: () => getJson<Record<string, unknown>>('/climate/outside'),
  newsStatus: () =>
    getJson<{ providers_order: string[]; providers_configured: string[]; topics: number }>(
      '/news/status',
    ),
  newsTopics: () => getJson<NewsTopic[]>('/news/topics'),
  newsLatest: () => getJson<NewsDigest[]>('/news/digests/latest'),
}
