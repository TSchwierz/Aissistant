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
import { api, type CalendarEvent, type CalendarEventWrite, type EventList } from '../api'

type ViewMode = 'month' | 'weeks'
type EditorMode = 'create' | 'edit'

type Draft = {
  id: string
  title: string
  allDay: boolean
  start: string
  end: string
  location: string
  notes: string
  tags: string
}

function eventDayKey(ev: CalendarEvent): string {
  return ev.start.slice(0, 10)
}

function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return ''
  const noZone = iso.replace(/Z$/, '').replace(/[+-]\d{2}:\d{2}$/, '')
  return noZone.slice(0, 16)
}

function emptyDraft(): Draft {
  const start = new Date()
  start.setMinutes(0, 0, 0)
  start.setHours(start.getHours() + 1)
  return {
    id: '',
    title: '',
    allDay: false,
    start: format(start, "yyyy-MM-dd'T'HH:mm"),
    end: '',
    location: '',
    notes: '',
    tags: '',
  }
}

function draftFromEvent(event: CalendarEvent): Draft {
  return {
    id: event.id,
    title: event.title,
    allDay: event.all_day,
    start: event.all_day ? event.start.slice(0, 10) : toLocalInput(event.start),
    end: event.all_day ? (event.end ? event.end.slice(0, 10) : '') : toLocalInput(event.end),
    location: event.location ?? '',
    notes: event.notes ?? '',
    tags: event.tags.join(', '),
  }
}

function parseTags(text: string): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const raw of text.split(',')) {
    const tag = raw.trim()
    if (!tag || seen.has(tag.toLowerCase())) continue
    seen.add(tag.toLowerCase())
    out.push(tag)
  }
  return out
}

function toApiStamp(value: string, allDay: boolean): string {
  if (allDay) return `${value.slice(0, 10)}T00:00:00`
  return value.length === 16 ? `${value}:00` : value
}

function toWrite(draft: Draft, mode: EditorMode): CalendarEventWrite {
  const title = draft.title.trim()
  if (!title) throw new Error('Title is required')
  if (!draft.start) throw new Error('Start is required')
  const start = toApiStamp(draft.start, draft.allDay)
  const end = draft.end.trim() ? toApiStamp(draft.end, draft.allDay) : null
  const location = draft.location.trim()
  const notes = draft.notes.trim()
  return {
    title,
    start,
    end,
    all_day: draft.allDay,
    location: location || null,
    notes: notes || null,
    tags: parseTags(draft.tags),
    clear_end: mode === 'edit' && !end,
    clear_location: mode === 'edit' && !location,
    clear_notes: mode === 'edit' && !notes,
  }
}

export function CalendarPanel() {
  const [mode, setMode] = useState<ViewMode>('weeks')
  const [tag, setTag] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [list, setList] = useState<EventList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [cursor, setCursor] = useState(() => new Date())
  const [editor, setEditor] = useState<EditorMode | null>(null)
  const [draft, setDraft] = useState<Draft>(emptyDraft)
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

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

  function openCreate() {
    setEditor('create')
    setDraft(emptyDraft())
    setFormError(null)
  }

  function openEdit(event: CalendarEvent) {
    setEditor('edit')
    setDraft(draftFromEvent(event))
    setFormError(null)
  }

  async function saveEvent() {
    setSaving(true)
    setFormError(null)
    try {
      const body = toWrite(draft, editor === 'edit' ? 'edit' : 'create')
      if (editor === 'edit') await api.updateCalendarEvent(draft.id, body)
      else await api.createCalendarEvent(body)
      setEditor(null)
      await load()
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  async function removeEvent() {
    if (!draft.id) return
    if (!window.confirm(`Delete “${draft.title}”?`)) return
    setSaving(true)
    setFormError(null)
    try {
      await api.deleteCalendarEvent(draft.id)
      setEditor(null)
      await load()
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="panel">
      <h2>Calendar</h2>
      <p className="lede">Personal events on the Pi (Europe/Berlin). No M365.</p>
      <div className="panel-actions">
        <button type="button" className="primary" onClick={openCreate}>
          New event
        </button>
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
      {editor && (
        <form
          className="topic-form"
          onSubmit={(event) => {
            event.preventDefault()
            void saveEvent()
          }}
        >
          <h3>{editor === 'create' ? 'New event' : 'Edit event'}</h3>
          <label>
            Title
            <input
              value={draft.title}
              required
              maxLength={300}
              onChange={(event) => setDraft({ ...draft, title: event.target.value })}
            />
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={draft.allDay}
              onChange={(event) => {
                const allDay = event.target.checked
                setDraft((current) => ({
                  ...current,
                  allDay,
                  start: allDay
                    ? current.start.slice(0, 10)
                    : current.start.length === 10
                      ? `${current.start}T09:00`
                      : current.start,
                  end:
                    !current.end
                      ? ''
                      : allDay
                        ? current.end.slice(0, 10)
                        : current.end.length === 10
                          ? `${current.end}T10:00`
                          : current.end,
                }))
              }}
            />
            All day
          </label>
          <div className="time-row">
            <label>
              Start
              <input
                type={draft.allDay ? 'date' : 'datetime-local'}
                required
                value={draft.allDay ? draft.start.slice(0, 10) : draft.start}
                onChange={(event) => setDraft({ ...draft, start: event.target.value })}
              />
            </label>
            <label>
              End
              <input
                type={draft.allDay ? 'date' : 'datetime-local'}
                value={draft.allDay ? draft.end.slice(0, 10) : draft.end}
                onChange={(event) => setDraft({ ...draft, end: event.target.value })}
              />
            </label>
          </div>
          <label>
            Location
            <input
              value={draft.location}
              maxLength={500}
              onChange={(event) => setDraft({ ...draft, location: event.target.value })}
            />
          </label>
          <label>
            Notes
            <textarea
              rows={3}
              maxLength={4000}
              value={draft.notes}
              onChange={(event) => setDraft({ ...draft, notes: event.target.value })}
            />
          </label>
          <label>
            Tags
            <input
              value={draft.tags}
              placeholder="health, work"
              onChange={(event) => setDraft({ ...draft, tags: event.target.value })}
            />
            <span className="hint">Comma-separated. Times are stored in the Pi timezone.</span>
          </label>
          {formError && <div className="error-box">{formError}</div>}
          <div className="panel-actions">
            <button type="submit" className="primary" disabled={saving}>
              {saving ? 'Saving…' : editor === 'create' ? 'Create event' : 'Save changes'}
            </button>
            {editor === 'edit' && (
              <button type="button" onClick={() => void removeEvent()} disabled={saving}>
                Delete
              </button>
            )}
            <button type="button" onClick={() => setEditor(null)} disabled={saving}>
              Cancel
            </button>
          </div>
        </form>
      )}
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
                        <li key={ev.id}>
                          <button type="button" className="linkish" onClick={() => openEdit(ev)}>
                            {ev.title}
                          </button>
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
                  <div className="card-head">
                    <div>
                      <div className="when">
                        {ev.all_day ? `${eventDayKey(ev)} · all day` : ev.start}
                        {eventDayKey(ev) === todayKey ? ' · today' : ''}
                      </div>
                      <strong>{ev.title}</strong>
                    </div>
                    <button type="button" onClick={() => openEdit(ev)}>
                      Edit
                    </button>
                  </div>
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
