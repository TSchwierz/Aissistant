/** Pi LAN API client — no AI keys in the browser. */

const STORAGE_KEY = 'pa_api_base'
const API_KEY_STORAGE = 'pa_api_key'

export function getApiBase(): string {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored) return stored.replace(/\/$/, '')
  return (import.meta.env.VITE_PI_API_BASE as string | undefined)?.replace(/\/$/, '')
    || 'http://192.168.178.23:8741'
}

export function setApiBase(url: string): void {
  localStorage.setItem(STORAGE_KEY, url.trim().replace(/\/$/, ''))
}

export function getApiKey(): string {
  return localStorage.getItem(API_KEY_STORAGE) ?? ''
}

export function setApiKey(key: string): void {
  localStorage.setItem(API_KEY_STORAGE, key.trim())
}

function authHeaders(init?: HeadersInit): Headers {
  const headers = new Headers(init)
  const key = getApiKey().trim()
  if (key) headers.set('Authorization', `Bearer ${key}`)
  return headers
}

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${getApiBase()}${path}`, {
    ...init,
    headers: authHeaders(init?.headers),
  })
}

async function ensureOk(res: Response): Promise<void> {
  if (res.status === 401) throw new Error('API key rejected')
  if (!res.ok) throw new Error(await readApiError(res))
}

async function readApiError(res: Response): Promise<string> {
  const text = await res.text()
  try {
    const data = JSON.parse(text) as { detail?: unknown }
    if (typeof data.detail === 'string') return data.detail
    if (Array.isArray(data.detail)) {
      const parts = data.detail.map((item) => {
        if (typeof item === 'string') return item
        if (item && typeof item === 'object' && 'msg' in item) {
          const rec = item as { msg: unknown; loc?: unknown }
          const loc = Array.isArray(rec.loc)
            ? rec.loc.filter((part) => part !== 'body').join('.')
            : ''
          const msg = String(rec.msg)
          return loc ? `${loc}: ${msg}` : msg
        }
        return JSON.stringify(item)
      })
      if (parts.length) return parts.join('; ')
    }
  } catch {
    /* fall through to raw body */
  }
  return `HTTP ${res.status}: ${text.slice(0, 200)}`
}

async function getJson<T>(path: string): Promise<T> {
  const res = await apiFetch(path)
  await ensureOk(res)
  return res.json() as Promise<T>
}

async function sendJson<T>(method: string, path: string, body: unknown): Promise<T> {
  const res = await apiFetch(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  await ensureOk(res)
  return res.json() as Promise<T>
}

async function sendForm<T>(path: string, body: FormData): Promise<T> {
  const res = await apiFetch(path, { method: 'POST', body })
  await ensureOk(res)
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
  series_id?: string | null
  series_start?: string | null
  series_end?: string | null
  repeat?: 'weekly' | 'biweekly' | 'monthly' | null
  repeat_until?: string | null
  repeat_weekdays?: number[]
  remind_before_minutes?: number | null
  ics_uid?: string | null
}

export type CalendarEventWrite = {
  title: string
  start: string
  end?: string | null
  all_day: boolean
  location?: string | null
  notes?: string | null
  tags: string[]
  clear_end?: boolean
  clear_location?: boolean
  clear_notes?: boolean
  repeat?: 'weekly' | 'biweekly' | 'monthly' | null
  repeat_until?: string | null
  repeat_weekdays?: number[]
  clear_repeat?: boolean
  clear_repeat_until?: boolean
  remind_before_minutes?: number | null
  clear_remind?: boolean
}

export type CalendarImportIssue = {
  title: string
  uid?: string | null
  detail: string
}

export type CalendarImportResult = {
  created: number
  updated: number
  skipped: number
  repeat_dropped: CalendarImportIssue[]
  alarm_dropped: CalendarImportIssue[]
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
    body_fat_kg?: number | null
    muscle_mass_kg?: number | null
    muscle_pct?: number | null
    water_pct?: number | null
    water_kg?: number | null
    bone_mass_kg?: number | null
    bone_pct?: number | null
    bmr?: number | null
  } | null
  avg_weight_7d?: number | null
  avg_weight_30d?: number | null
  min_weight?: number | null
  max_weight?: number | null
  profile_complete: boolean
  nutrition?: NutritionTarget | null
}

export type NutritionTarget = {
  activity_level: string
  activity_factor: number
  target_fat_pct?: number | null
  meals_per_day: number
  bmr?: number | null
  target_calories?: number | null
  protein_g?: number | null
  fiber_g?: number | null
  per_meal_calories?: number | null
  per_meal_protein_g?: number | null
  per_meal_fiber_g?: number | null
}

export type HealthProfile = {
  id: number
  name: string
  height_cm?: number | null
  age?: number | null
  sex?: string | null
  activity_level?: string
  target_fat_pct?: number | null
  meals_per_day?: number
  is_complete: boolean
  nutrition?: NutritionTarget | null
}

export type HealthProfileWrite = {
  name: string
  height_cm?: number | null
  age?: number | null
  sex?: string | null
  activity_level: string
  target_fat_pct?: number | null
  meals_per_day: number
}

export type HealthMeasurement = {
  id: number
  measured_at: string
  weight_kg: number
  body_fat_pct?: number | null
  body_fat_kg?: number | null
  muscle_mass_kg?: number | null
  muscle_pct?: number | null
  water_pct?: number | null
  water_kg?: number | null
  bmi?: number | null
}

export type FoodHit = {
  name: string
  source: 'ciqual' | 'off' | 'manual'
  source_id?: string | null
  kcal_100g: number
  protein_100g: number
  carbs_100g: number
  fat_100g: number
  fiber_100g: number
}

export type MealItem = {
  id?: number
  name: string
  grams: number
  kcal: number
  protein_g: number
  carbs_g: number
  fat_g: number
  fiber_g: number
  source: 'ciqual' | 'off' | 'manual'
  source_id?: string | null
}

export type Meal = {
  id: number
  eaten_at: string
  note: string
  source: 'text' | 'barcode' | 'photo'
  items: MealItem[]
}

export type MealSummary = {
  day: string
  totals: { kcal: number; protein_g: number; carbs_g: number; fat_g: number; fiber_g: number }
  targets: { target_calories?: number | null; protein_g?: number | null; fiber_g?: number | null } | null
  meals: Meal[]
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

export type ClimateProviderReport = {
  name: string
  ok: boolean
  error?: string | null
  temperature_c?: number | null
  humidity_pct?: number | null
  condition?: string | null
  updated_at?: string | null
}

export type ClimateOutside = {
  providers?: string[]
  provider_reports?: ClimateProviderReport[]
  reading?: {
    temperature_c?: number
    humidity_pct?: number
    condition?: string
    sources?: string[]
  } | null
  comparison?: {
    ventilation?: { action?: string; reason?: string; delta_c?: number | null }
  }
}

export type ClimateSettings = {
  humidity_min: number
  humidity_max: number
  temp_min: number
  temp_max: number
  sample_interval_seconds: number
}

export type NewsTopic = {
  id: string
  label: string
  goal: string
  feed_urls: string[]
  schedule_enabled: boolean
  schedule_hour: number
  schedule_minute: number
  schedule_days: number[]
  last_run_status?: string | null
  last_run_at?: string | null
  last_error?: string | null
}

export type NewsTopicWrite = {
  label: string
  goal: string
  feed_urls: string[]
  schedule_enabled: boolean
  schedule_hour: number
  schedule_minute: number
  schedule_days: number[]
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
  calendarWeeks: (from?: string, tag?: string, days = 14) => {
    const q = new URLSearchParams()
    if (from) q.set('from', from)
    if (tag) q.set('tag', tag)
    q.set('days', String(days))
    const qs = q.toString()
    return getJson<EventList>(`/calendar/weeks${qs ? `?${qs}` : ''}`)
  },
  calendarTags: () => getJson<{ tags: string[]; colors?: Record<string, string> }>('/calendar/tags'),
  setCalendarTagColor: (tag: string, color: string) =>
    sendJson<{ tags: string[]; colors?: Record<string, string> }>('PUT', '/calendar/tags', {
      tag,
      color,
    }),
  createCalendarEvent: (body: CalendarEventWrite) =>
    sendJson<CalendarEvent>('POST', '/calendar/events', body),
  updateCalendarEvent: (id: string, body: CalendarEventWrite) =>
    sendJson<CalendarEvent>('PUT', `/calendar/events/${encodeURIComponent(id)}`, body),
  deleteCalendarEvent: (id: string) =>
    sendJson<{ deleted: boolean; id: string }>(
      'DELETE',
      `/calendar/events/${encodeURIComponent(id)}`,
      {},
    ),
  importCalendar: (file: File) => {
    const body = new FormData()
    body.append('file', file)
    return sendForm<CalendarImportResult>('/calendar/import', body)
  },
  healthStats: () => getJson<HealthStats>('/api/stats'),
  scaleStatus: () =>
    getJson<{
      phase: string
      detail: string
      recorded_today: boolean
      window: string
      mode?: string
      last_weight_kg?: number | null
    }>('/api/scale'),
  setScaleMode: (action: 'start' | 'stop' | 'auto') =>
    sendJson<{ phase: string; detail: string; mode?: string }>('POST', '/api/scale/mode', {
      action,
    }),
  healthProfile: () => getJson<HealthProfile>('/api/profile'),
  updateHealthProfile: (body: HealthProfileWrite) =>
    sendJson<HealthProfile>('PUT', '/api/profile', body),
  healthMeasurements: (limit = 500) =>
    getJson<HealthMeasurement[]>(`/api/measurements?limit=${limit}`),
  updateMeasurement: (id: number, body: { weight_kg?: number }) =>
    sendJson<HealthMeasurement>('PUT', `/api/measurements/${id}`, body),
  deleteMeasurement: (id: number) =>
    sendJson<{ deleted: boolean; id: number }>('DELETE', `/api/measurements/${id}`, {}),
  searchFoods: (q: string) =>
    getJson<{ foods: FoodHit[] }>(`/api/foods/search?q=${encodeURIComponent(q)}`),
  parseMeal: (text: string) =>
    sendJson<{ items: MealItem[] }>('POST', '/api/nutrition/parse', { text }),
  createMeal: (body: {
    eaten_at?: string
    note?: string
    source: 'text' | 'barcode' | 'photo'
    items: MealItem[]
  }) => sendJson<Meal>('POST', '/api/meals', body),
  deleteMeal: (id: number) =>
    sendJson<{ deleted?: boolean; id?: number }>('DELETE', `/api/meals/${id}`, {}),
  mealSummary: (day: string) =>
    getJson<MealSummary>(`/api/meals/summary?day=${encodeURIComponent(day)}`),
  climateCurrent: () => getJson<ClimateCurrent>('/climate/current'),
  climateMeasurements: (limit = 288, from?: string) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (from) params.set('from', from)
    return getJson<{ count: number; measurements: ClimateMeasurement[] }>(
      `/climate/measurements?${params}`,
    )
  },
  climateOutside: () => getJson<ClimateOutside>('/climate/outside'),
  climateSettings: () => getJson<ClimateSettings>('/climate/settings'),
  updateClimateSettings: (body: Partial<ClimateSettings>) =>
    sendJson<ClimateSettings>('PUT', '/climate/settings', body),
  refreshClimateOutside: () => sendJson<ClimateOutside>('POST', '/climate/outside/refresh', {}),
  climateStrategies: () => getJson<{ markdown: string }>('/climate/advisor/strategies'),
  newsStatus: () =>
    getJson<{ providers_order: string[]; providers_configured: string[]; topics: number }>(
      '/news/status',
    ),
  newsTopics: () => getJson<NewsTopic[]>('/news/topics'),
  newsLatest: () => getJson<NewsDigest[]>('/news/digests/latest'),
  createNewsTopic: (body: NewsTopicWrite & { id: string }) =>
    sendJson<NewsTopic>('POST', '/news/topics', body),
  updateNewsTopic: (id: string, body: NewsTopicWrite) =>
    sendJson<NewsTopic>('PUT', `/news/topics/${encodeURIComponent(id)}`, body),
  /** Trigger browser download of SSOT zip (Phase 6 light backup). */
  downloadBackup: async (): Promise<void> => {
    const res = await apiFetch('/backup/export')
    if (res.status === 401) throw new Error('API key rejected')
    if (!res.ok) {
      const text = await res.text()
      throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`)
    }
    const blob = await res.blob()
    const cd = res.headers.get('Content-Disposition') || ''
    const match = /filename="?([^";]+)"?/i.exec(cd)
    const filename = match?.[1] || 'personal-aissistent-backup.zip'
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
}
