import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  addDays,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  format,
  startOfMonth,
  startOfWeek,
} from 'date-fns'
import { api, type CalendarEvent, type EventList } from '../api'

type ViewMode = 'month' | 'weeks'

function eventDayKey(ev: CalendarEvent): string {
  return ev.start.slice(0, 10)
}

export function CalendarPanel() {
  const [mode, setMode] = useState<ViewMode>('weeks')
  const [tag, setTag] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [list, setList] = useState<EventList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [cursor, setCursor] = useState(() => new Date())

  const monthKey = format(cursor, 'yyyy-MM')
  const todayKey = format(new Date(), 'yyyy-MM-dd')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const tagArg = tag || undefined
      const [tagList, events] = await Promise.all([
        api.calendarTags(),
        mode === 'month'
          ? api.calendarMonth(monthKey, tagArg)
          : api.calendarWeeks(format(cursor, 'yyyy-MM-dd'), tagArg),
      ])
      setTags(tagList.tags)
      setList(events)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [mode, monthKey, tag, cursor])

  useEffect(() => {
    void load()
  }, [load])

  const byDay = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>()
    for (const ev of list?.events ?? []) {
      const key = eventDayKey(ev)
      const arr = map.get(key) ?? []
      arr.push(ev)
      map.set(key, arr)
    }
    return map
  }, [list])

  const monthCells = useMemo(() => {
    const start = startOfWeek(startOfMonth(cursor), { weekStartsOn: 1 })
    const end = endOfWeek(endOfMonth(cursor), { weekStartsOn: 1 })
    return eachDayOfInterval({ start, end })
  }, [cursor])

  return (
    <section className="panel">
      <h2>Calendar</h2>
      <p className="lede">Personal events on the Pi (Europe/Berlin). No M365.</p>
      <div className="panel-actions">
        <button
          type="button"
          className={mode === 'weeks' ? 'primary' : undefined}
          onClick={() => setMode('weeks')}
        >
          2 weeks
        </button>
        <button
          type="button"
          className={mode === 'month' ? 'primary' : undefined}
          onClick={() => setMode('month')}
        >
          Month
        </button>
        <button type="button" onClick={() => setCursor(addDays(cursor, mode === 'month' ? -30 : -14))}>
          ←
        </button>
        <button type="button" onClick={() => setCursor(new Date())}>
          Today
        </button>
        <button type="button" onClick={() => setCursor(addDays(cursor, mode === 'month' ? 30 : 14))}>
          →
        </button>
        <button type="button" onClick={() => void load()}>
          Reload
        </button>
      </div>
      <div className="tags" style={{ marginBottom: '0.85rem' }}>
        <button
          type="button"
          className={`chip ${tag === '' ? 'active' : ''}`}
          onClick={() => setTag('')}
        >
          All tags
        </button>
        {tags.map((t) => (
          <button
            key={t}
            type="button"
            className={`chip ${tag === t ? 'active' : ''}`}
            onClick={() => setTag(t)}
          >
            {t}
          </button>
        ))}
      </div>
      {loading && <p className="muted">Loading…</p>}
      {error && <div className="error-box">{error}</div>}
      {list && !loading && (
        <>
          <p className="muted">
            {list.count} event(s) · {list.range_start.slice(0, 10)} → {list.range_end.slice(0, 10)}
          </p>
          {mode === 'month' ? (
            <div className="month-grid">
              {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d) => (
                <div className="dow" key={d}>
                  {d}
                </div>
              ))}
              {monthCells.map((day) => {
                const key = format(day, 'yyyy-MM-dd')
                const events = byDay.get(key) ?? []
                return (
                  <div className="month-cell" key={key}>
                    <div className="daynum">{format(day, 'd')}</div>
                    <ul>
                      {events.slice(0, 3).map((ev) => (
                        <li key={ev.id} title={ev.title}>
                          {ev.title}
                        </li>
                      ))}
                    </ul>
                  </div>
                )
              })}
            </div>
          ) : (
            <>
              {(list.events.length === 0 && <div className="list-empty">No events in this window.</div>) ||
                null}
              {list.events.map((ev) => (
                <div className="event-row" key={ev.id}>
                  <div className="when">
                    {ev.all_day ? `${eventDayKey(ev)} · all day` : ev.start}
                    {eventDayKey(ev) === todayKey ? ' · today' : ''}
                  </div>
                  <strong>{ev.title}</strong>
                  <div className="muted">
                    {[ev.location, ev.tags?.join(', ')].filter(Boolean).join(' · ') || '—'}
                  </div>
                </div>
              ))}
            </>
          )}
        </>
      )}
    </section>
  )
}
