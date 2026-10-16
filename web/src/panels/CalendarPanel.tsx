import { useCallback, useEffect, useMemo, useState, type CSSProperties } from 'react'
import {
  addDays,
  addHours,
  addMonths,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  format,
  parse,
  startOfMonth,
  startOfWeek,
} from 'date-fns'
import { api, type CalendarEvent, type CalendarEventWrite, type EventList } from '../api'

type ViewMode = 'month' | 'week' | 'fortnight' | 'simple'
type EditorMode = 'create' | 'edit'

type RepeatMode = '' | 'weekly' | 'biweekly' | 'monthly'

type Draft = {
  id: string
  title: string
  allDay: boolean
  start: string
  end: string
  location: string
  notes: string
  tags: string
  repeat: RepeatMode
  repeatUntil: string
  repeatWeekdays: number[]
}

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const TAG_PALETTE = ['#5b8def', '#3d9b8f', '#d4a056', '#c46b6b', '#9b7ed4', '#6bcb8a', '#e07a5f', '#4ea8de']

function hashColor(name: string): string {
  let hash = 0
  for (let i = 0; i < name.length; i += 1) hash = (hash * 31 + name.charCodeAt(i)) >>> 0
  return TAG_PALETTE[hash % TAG_PALETTE.length]
}

function colorFor(tag: string, colors: Record<string, string>): string {
  const assigned = Object.entries(colors).find(([name]) => name.toLowerCase() === tag.toLowerCase())
  return assigned?.[1] || hashColor(tag)
}

function defaultTimedEnd(start: string): string {
  if (start.length < 16) return ''
  const parsed = parse(start.slice(0, 16), "yyyy-MM-dd'T'HH:mm", new Date())
  if (Number.isNaN(parsed.getTime())) return ''
  return format(addHours(parsed, 1), "yyyy-MM-dd'T'HH:mm")
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
  const startValue = format(start, "yyyy-MM-dd'T'HH:mm")
  return {
    id: '',
    title: '',
    allDay: false,
    start: startValue,
    end: defaultTimedEnd(startValue),
    location: '',
    notes: '',
    tags: '',
    repeat: '',
    repeatUntil: '',
    repeatWeekdays: [],
  }
}

function draftFromEvent(event: CalendarEvent): Draft {
  const anchorStart = event.series_start || event.start
  const anchorEnd = event.repeat ? event.series_end : event.end
  return {
    id: event.series_id || event.id.split('~')[0],
    title: event.title,
    allDay: event.all_day,
    start: event.all_day ? anchorStart.slice(0, 10) : toLocalInput(anchorStart),
    end: event.all_day
      ? anchorEnd
        ? anchorEnd.slice(0, 10)
        : ''
      : toLocalInput(anchorEnd),
    location: event.location ?? '',
    notes: event.notes ?? '',
    tags: event.tags.join(', '),
    repeat:
      event.repeat === 'weekly' || event.repeat === 'biweekly' || event.repeat === 'monthly'
        ? event.repeat
        : '',
    repeatUntil: event.repeat_until ?? '',
    repeatWeekdays: event.repeat_weekdays ?? [],
  }
}

function repeatLabel(ev: CalendarEvent): string {
  if (!ev.repeat) return ''
  const days = (ev.repeat_weekdays ?? []).map((day) => WEEKDAYS[day]).filter(Boolean)
  if (ev.repeat === 'monthly' && days.length) return `first ${days.join(' + ')} each month`
  if (ev.repeat === 'monthly') return 'monthly'
  const freq = ev.repeat === 'biweekly' ? 'every 2 weeks' : 'weekly'
  return days.length > 1 ? `${freq} · ${days.join(' + ')}` : freq
}

function eventClock(ev: CalendarEvent): string {
  if (ev.all_day) return ''
  const match = /T(\d{2}:\d{2})/.exec(ev.start)
  return match ? match[1] : ''
}

function eventLabel(ev: CalendarEvent): string {
  const clock = eventClock(ev)
  return clock ? `${clock} ${ev.title}` : ev.title
}

function wallMinutes(iso: string): number {
  const match = /T(\d{2}):(\d{2})/.exec(iso)
  if (!match) return 0
  return Number(match[1]) * 60 + Number(match[2])
}

function isUpcoming(ev: CalendarEvent, now = Date.now()): boolean {
  const end = ev.end || ev.start
  const parsed = Date.parse(end)
  return Number.isNaN(parsed) ? true : parsed >= now
}

const HOUR_PX = 42

function daySegment(ev: CalendarEvent, dayKey: string): { startMin: number; endMin: number } | null {
  if (ev.all_day) return null
  const startDay = eventDayKey(ev)
  const endDay = (ev.end || ev.start).slice(0, 10)
  const startMin = wallMinutes(ev.start)
  let endMin = ev.end ? wallMinutes(ev.end) : startMin + 60
  if (endDay === startDay && endMin <= startMin) endMin = startMin + 60
  if (dayKey === startDay && dayKey === endDay) return { startMin, endMin }
  if (dayKey === startDay && endDay > startDay) return { startMin, endMin: 24 * 60 }
  if (dayKey > startDay && dayKey < endDay) return { startMin: 0, endMin: 24 * 60 }
  if (dayKey === endDay && endDay > startDay) return { startMin: 0, endMin: Math.max(endMin, 15) }
  return null
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
    repeat: draft.repeat || null,
    repeat_until: draft.repeat ? draft.repeatUntil || null : null,
    repeat_weekdays: draft.repeat ? draft.repeatWeekdays : [],
    clear_repeat: mode === 'edit' && !draft.repeat,
    clear_repeat_until: mode === 'edit' && !draft.repeatUntil,
  }
}

export function CalendarPanel() {
  const [mode, setMode] = useState<ViewMode>('fortnight')
  const [upcomingOnly, setUpcomingOnly] = useState(false)
  const [tag, setTag] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [tagColors, setTagColors] = useState<Record<string, string>>({})
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
      const span = mode === 'week' ? 7 : 14
      const fromDate =
        mode === 'week' || mode === 'fortnight'
          ? startOfWeek(cursor, { weekStartsOn: 1 })
          : cursor
      const [tagList, events] = await Promise.all([
        api.calendarTags(),
        mode === 'month'
          ? api.calendarMonth(monthKey, tagArg)
          : api.calendarWeeks(format(fromDate, 'yyyy-MM-dd'), tagArg, span),
      ])
      setTags(tagList.tags)
      setTagColors(tagList.colors ?? {})
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

  const rasterDays = useMemo(() => {
    const start = startOfWeek(cursor, { weekStartsOn: 1 })
    const count = mode === 'week' ? 6 : 13
    return eachDayOfInterval({ start, end: addDays(start, count) })
  }, [cursor, mode])

  const visibleEvents = useMemo(() => {
    const events = list?.events ?? []
    if (mode === 'simple' && upcomingOnly) return events.filter((ev) => isUpcoming(ev))
    return events
  }, [list, mode, upcomingOnly])

  function openCreate() {
    setEditor('create')
    setDraft(emptyDraft())
    setFormError(null)
  }

  function openCreateAt(day: Date, hour: number) {
    const start = new Date(day)
    start.setHours(hour, 0, 0, 0)
    const startValue = format(start, "yyyy-MM-dd'T'HH:mm")
    setEditor('create')
    setDraft({ ...emptyDraft(), start: startValue, end: defaultTimedEnd(startValue) })
    setFormError(null)
  }

  function eventStyle(ev: CalendarEvent): CSSProperties | undefined {
    const tag = ev.tags[0]
    if (!tag) return undefined
    const color = colorFor(tag, tagColors)
    return {
      borderColor: color,
      background: `color-mix(in srgb, ${color} 32%, transparent)`,
    }
  }

  async function saveTagColor(name: string, color: string) {
    setTagColors((current) => ({ ...current, [name]: color }))
    try {
      const saved = await api.setCalendarTagColor(name, color)
      setTagColors(saved.colors ?? {})
      setTags(saved.tags)
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e))
    }
  }

  function shift(direction: number) {
    if (mode === 'month') setCursor(addMonths(cursor, direction))
    else if (mode === 'week') setCursor(addDays(cursor, direction * 7))
    else setCursor(addDays(cursor, direction * 14))
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
          className={mode === 'week' ? 'primary' : undefined}
          onClick={() => setMode('week')}
        >
          Week
        </button>
        <button
          type="button"
          className={mode === 'fortnight' ? 'primary' : undefined}
          onClick={() => setMode('fortnight')}
        >
          2 weeks
        </button>
        <button
          type="button"
          className={mode === 'simple' ? 'primary' : undefined}
          onClick={() => setMode('simple')}
        >
          Simplified
        </button>
        <button
          type="button"
          className={mode === 'month' ? 'primary' : undefined}
          onClick={() => setMode('month')}
        >
          Month
        </button>
        {mode === 'simple' && (
          <label className="check" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <input
              type="checkbox"
              checked={upcomingOnly}
              onChange={(event) => setUpcomingOnly(event.target.checked)}
            />
            Only upcoming
          </label>
        )}
        <button type="button" onClick={() => shift(-1)}>
          ←
        </button>
        <button type="button" onClick={() => setCursor(new Date())}>
          Today
        </button>
        <button type="button" onClick={() => shift(1)}>
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
              Repeat
              <select
                value={draft.repeat}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    repeat: event.target.value as Draft['repeat'],
                  })
                }
              >
                <option value="">Does not repeat</option>
                <option value="weekly">Every week</option>
                <option value="biweekly">Every two weeks</option>
                <option value="monthly">Every month</option>
              </select>
            </label>
            <label>
              Repeat until
              <input
                type="date"
                value={draft.repeatUntil}
                disabled={!draft.repeat}
                onChange={(event) => setDraft({ ...draft, repeatUntil: event.target.value })}
              />
            </label>
          </div>
          {draft.repeat && (
            <fieldset>
              <legend>Days</legend>
              <div className="weekday-row">
                {WEEKDAYS.map((label, day) => (
                  <button
                    key={label}
                    type="button"
                    className={draft.repeatWeekdays.includes(day) ? 'primary' : undefined}
                    onClick={() =>
                      setDraft((current) => {
                        const selected = current.repeatWeekdays.includes(day)
                          ? current.repeatWeekdays.filter((value) => value !== day)
                          : [...current.repeatWeekdays, day].sort((a, b) => a - b)
                        return { ...current, repeatWeekdays: selected }
                      })
                    }
                  >
                    {label}
                  </button>
                ))}
              </div>
              <span className="hint">
                {draft.repeat === 'monthly'
                  ? 'Selected days repeat in the first week of each month. Leave them empty to repeat on the same date.'
                  : 'Select every day this should occur. Leave them empty to follow the start day only.'}
              </span>
            </fieldset>
          )}
          <div className="time-row">
            <label>
              Start
              <input
                type={draft.allDay ? 'date' : 'datetime-local'}
                required
                value={draft.allDay ? draft.start.slice(0, 10) : draft.start}
                onChange={(event) => {
                  const start = event.target.value
                  setDraft((current) => {
                    const previousDefault = defaultTimedEnd(current.start)
                    const keepAutoEnd =
                      !current.allDay && (current.end === '' || current.end === previousDefault)
                    return {
                      ...current,
                      start,
                      end: keepAutoEnd ? defaultTimedEnd(start) : current.end,
                    }
                  })
                }}
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
          {parseTags(draft.tags).length > 0 && (
            <div className="weekday-row">
              {parseTags(draft.tags).map((name) => (
                <label key={name} className="tag-chip">
                  {name}
                  <input
                    type="color"
                    aria-label={`Colour for ${name}`}
                    value={colorFor(name, tagColors)}
                    onChange={(event) => void saveTagColor(name, event.target.value)}
                  />
                </label>
              ))}
            </div>
          )}
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
          <span key={t} className="tag-chip">
            <button
              type="button"
              className={`chip ${tag === t ? 'active' : ''}`}
              style={{ borderColor: colorFor(t, tagColors) }}
              onClick={() => setTag(t)}
            >
              {t}
            </button>
            <input
              type="color"
              aria-label={`Colour for ${t}`}
              value={colorFor(t, tagColors)}
              onChange={(event) => void saveTagColor(t, event.target.value)}
            />
          </span>
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
                const inMonth = day.getMonth() === cursor.getMonth()
                return (
                  <div
                    className={`month-cell ${inMonth ? '' : 'outside'}`}
                    key={key}
                    onClick={() => openCreateAt(day, 9)}
                  >
                    <div className="daynum">{format(day, 'd')}</div>
                    <ul>
                      {events.slice(0, 4).map((ev) => (
                        <li key={ev.id}>
                          <button
                            type="button"
                            className="linkish"
                            style={eventStyle(ev)}
                            onClick={(event) => {
                              event.stopPropagation()
                              openEdit(ev)
                            }}
                          >
                            {eventLabel(ev)}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )
              })}
            </div>
          ) : mode === 'week' || mode === 'fortnight' ? (
            <div className="raster">
              <div
                className="raster-head"
                style={{ gridTemplateColumns: `52px repeat(${rasterDays.length}, minmax(0, 1fr))` }}
              >
                <div />
                {rasterDays.map((day) => (
                  <div key={format(day, 'yyyy-MM-dd')} className={format(day, 'yyyy-MM-dd') === todayKey ? 'today' : undefined}>
                    {format(day, 'EEE d')}
                  </div>
                ))}
              </div>
              <div
                className="raster-allday"
                style={{ gridTemplateColumns: `52px repeat(${rasterDays.length}, minmax(0, 1fr))` }}
              >
                <div className="raster-label">all day</div>
                {rasterDays.map((day) => {
                  const key = format(day, 'yyyy-MM-dd')
                  const events = (byDay.get(key) ?? []).filter((ev) => ev.all_day)
                  return (
                    <div key={key}>
                      {events.map((ev) => (
                        <button key={ev.id} type="button" className="raster-event static" style={eventStyle(ev)} onClick={() => openEdit(ev)}>
                          {ev.title}
                        </button>
                      ))}
                    </div>
                  )
                })}
              </div>
              <div className="raster-scroll">
                <div
                  className="raster-body"
                  style={{ gridTemplateColumns: `52px repeat(${rasterDays.length}, minmax(0, 1fr))` }}
                >
                  <div>
                    {Array.from({ length: 24 }, (_, hour) => (
                      <div key={hour} className="raster-label" style={{ height: HOUR_PX }}>
                        {String(hour).padStart(2, '0')}:00
                      </div>
                    ))}
                  </div>
                  {rasterDays.map((day) => {
                    const key = format(day, 'yyyy-MM-dd')
                    const events = (byDay.get(key) ?? []).filter((ev) => !ev.all_day)
                    return (
                      <div className="raster-col" key={key}>
                        {Array.from({ length: 24 }, (_, hour) => (
                          <button
                            key={hour}
                            type="button"
                            className="raster-slot"
                            style={{ height: HOUR_PX }}
                            aria-label={`New event ${key} ${hour}:00`}
                            onClick={() => openCreateAt(day, hour)}
                          />
                        ))}
                        {events.map((ev) => {
                          const segment = daySegment(ev, key)
                          if (!segment) return null
                          const top = (segment.startMin / (24 * 60)) * 24 * HOUR_PX
                          const height = Math.max(
                            18,
                            ((segment.endMin - segment.startMin) / (24 * 60)) * 24 * HOUR_PX,
                          )
                          return (
                            <button
                              key={ev.id}
                              type="button"
                              className="raster-event"
                              style={{ top, height, ...eventStyle(ev) }}
                              onClick={() => openEdit(ev)}
                            >
                              {eventLabel(ev)}
                            </button>
                          )
                        })}
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          ) : (
            <>
              {(visibleEvents.length === 0 && <div className="list-empty">No events in this window.</div>) ||
                null}
              {visibleEvents.map((ev) => (
                <div className="event-row" key={ev.id} style={eventStyle(ev)}>
                  <div className="card-head">
                    <div>
                      <div className="when">
                        {ev.all_day ? `${eventDayKey(ev)} · all day` : ev.start}
                        {eventDayKey(ev) === todayKey ? ' · today' : ''}
                        {ev.repeat ? ` · ${repeatLabel(ev)}` : ''}
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
