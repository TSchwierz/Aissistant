import { useEffect } from 'react'
import { api, type CalendarEvent } from './api.ts'

const timeoutIds = new Set<number>()
const fired = new Set<string>()
let generation = 0
let asked = false

function reminderAt(event: CalendarEvent): number | null {
  if (!event.remind_before_minutes) return null
  const start = Date.parse(event.start)
  if (Number.isNaN(start)) return null
  return start - event.remind_before_minutes * 60_000
}

function arm(events: CalendarEvent[]) {
  for (const id of timeoutIds) window.clearTimeout(id)
  timeoutIds.clear()
  if (typeof Notification === 'undefined') return
  const now = Date.now()
  for (const event of events) {
    const at = reminderAt(event)
    if (at == null || at <= now) continue
    const key = `${event.id}@${at}`
    if (fired.has(key)) continue
    const delay = at - now
    if (delay > 2_147_000_000) continue
    const handle = window.setTimeout(() => {
      timeoutIds.delete(handle)
      fired.add(key)
      if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return
      const when = event.all_day ? 'All day' : `Starts ${event.start.slice(11, 16)}`
      try {
        new Notification(event.title, { body: when, tag: key })
      } catch {
        /* the page can stay open when notifications are unavailable */
      }
    }, delay)
    timeoutIds.add(handle)
  }
}

export function requestCalendarReminderPermission(): void {
  if (typeof Notification === 'undefined') return
  if (Notification.permission !== 'default') {
    window.dispatchEvent(new Event('calendar-notify-permission'))
    return
  }
  void Notification.requestPermission()
    .catch(() => 'default' as NotificationPermission)
    .then(() => {
      window.dispatchEvent(new Event('calendar-notify-permission'))
    })
}

export function refreshCalendarReminders(): void {
  window.dispatchEvent(new Event('calendar-reminders-refresh'))
}

function maybeAsk(events: CalendarEvent[]) {
  if (asked) return
  if (!events.some((event) => event.remind_before_minutes)) return
  asked = true
  requestCalendarReminderPermission()
}

/** Browser notifications while any page of the app is open. A closed tab does not catch up. */
export function CalendarReminders() {
  useEffect(() => {
    const gen = ++generation

    async function load() {
      const ticket = generation
      try {
        const list = await api.calendarWeeks(undefined, undefined, 31)
        if (ticket !== generation) return
        maybeAsk(list.events)
        arm(list.events)
      } catch {
        /* the rest of the app still works when the calendar is unreachable */
      }
    }

    void load()
    const timer = window.setInterval(() => void load(), 5 * 60 * 1000)
    const onSaved = () => void load()
    const onVisible = () => {
      if (document.visibilityState === 'visible') void load()
    }
    window.addEventListener('calendar-reminders-refresh', onSaved)
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      if (generation === gen) generation += 1
      window.clearInterval(timer)
      window.removeEventListener('calendar-reminders-refresh', onSaved)
      document.removeEventListener('visibilitychange', onVisible)
      for (const id of timeoutIds) window.clearTimeout(id)
      timeoutIds.clear()
    }
  }, [])

  return null
}
