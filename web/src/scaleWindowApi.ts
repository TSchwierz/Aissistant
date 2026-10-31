/** Scale listen-window calls. Hours live on the Pi, not in this browser. */

import { apiFetch } from './api'

export type ScaleWindowStatus = {
  phase: string
  detail: string
  recorded_today: boolean
  window: string
  start_hour: number
  end_hour: number
  mode?: string
  enabled?: boolean
  last_weight_kg?: number | null
  last_error?: string | null
}

async function readError(res: Response): Promise<string> {
  const text = await res.text()
  try {
    const data = JSON.parse(text) as { detail?: unknown }
    if (typeof data.detail === 'string') return data.detail
    if (Array.isArray(data.detail)) {
      const parts = data.detail.map((item) => {
        if (typeof item === 'string') return item
        if (item && typeof item === 'object' && 'msg' in item) return String((item as { msg: unknown }).msg)
        return JSON.stringify(item)
      })
      if (parts.length) return parts.join('; ')
    }
  } catch {
    /* fall through to the raw body */
  }
  return `HTTP ${res.status}: ${text.slice(0, 200)}`
}

async function send(path: string, init?: RequestInit): Promise<ScaleWindowStatus> {
  const res = await apiFetch(path, init)
  if (res.status === 401) throw new Error('API key rejected')
  if (!res.ok) throw new Error(await readError(res))
  return res.json() as Promise<ScaleWindowStatus>
}

export function fetchScaleWindow(): Promise<ScaleWindowStatus> {
  return send('/api/scale')
}

export function saveScaleWindow(startHour: number, endHour: number): Promise<ScaleWindowStatus> {
  return send('/api/scale/window', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ start_hour: startHour, end_hour: endHour }),
  })
}
