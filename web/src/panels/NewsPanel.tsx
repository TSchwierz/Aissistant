import { useCallback, useEffect, useState } from 'react'
import { api, type NewsDigest, type NewsTopic, type NewsTopicWrite } from '../api'

const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

type EditorMode = 'create' | 'edit'

type Draft = {
  id: string
  label: string
  goal: string
  feeds: string
  schedule_enabled: boolean
  schedule_hour: string
  schedule_minute: string
  schedule_days: number[]
}

function emptyDraft(): Draft {
  return {
    id: '',
    label: '',
    goal: '',
    feeds: '',
    schedule_enabled: true,
    schedule_hour: '5',
    schedule_minute: '30',
    schedule_days: [0, 1, 2, 3, 4, 5, 6],
  }
}

function draftFromTopic(topic: NewsTopic): Draft {
  return {
    id: topic.id,
    label: topic.label,
    goal: topic.goal,
    feeds: topic.feed_urls.join('\n'),
    schedule_enabled: topic.schedule_enabled,
    schedule_hour: String(topic.schedule_hour),
    schedule_minute: String(topic.schedule_minute),
    schedule_days: [...topic.schedule_days],
  }
}

function pad2(value: number): string {
  return String(value).padStart(2, '0')
}

function formatSchedule(topic: NewsTopic): string {
  if (!topic.schedule_enabled) return 'Schedule off'
  const days =
    topic.schedule_days.length === 7
      ? 'every day'
      : topic.schedule_days.map((day) => DAY_LABELS[day] ?? String(day)).join(', ')
  return `${pad2(topic.schedule_hour)}:${pad2(topic.schedule_minute)} · ${days}`
}

function parseFeeds(text: string): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const raw of text.split(/\r?\n/)) {
    const url = raw.trim()
    if (!url || seen.has(url)) continue
    seen.add(url)
    out.push(url)
  }
  return out
}

function toWrite(draft: Draft): NewsTopicWrite {
  const hour = Number(draft.schedule_hour)
  const minute = Number(draft.schedule_minute)
  if (draft.schedule_hour.trim() === '' || !Number.isInteger(hour) || hour < 0 || hour > 23) {
    throw new Error('Hour must be 0–23')
  }
  if (draft.schedule_minute.trim() === '' || !Number.isInteger(minute) || minute < 0 || minute > 59) {
    throw new Error('Minute must be 0–59')
  }
  if (draft.schedule_days.length === 0) {
    throw new Error('Pick at least one day')
  }
  return {
    label: draft.label.trim(),
    goal: draft.goal.trim(),
    feed_urls: parseFeeds(draft.feeds),
    schedule_enabled: draft.schedule_enabled,
    schedule_hour: hour,
    schedule_minute: minute,
    schedule_days: [...draft.schedule_days].sort((a, b) => a - b),
  }
}

export function NewsPanel() {
  const [topics, setTopics] = useState<NewsTopic[]>([])
  const [digests, setDigests] = useState<NewsDigest[]>([])
  const [providers, setProviders] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [editor, setEditor] = useState<EditorMode | null>(null)
  const [draft, setDraft] = useState<Draft>(emptyDraft)
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [section, setSection] = useState<'topics' | 'digests'>('topics')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [status, t] = await Promise.all([api.newsStatus(), api.newsTopics()])
      setProviders(status.providers_configured)
      setTopics(t)
      try {
        setDigests(await api.newsLatest())
      } catch (e) {
        setDigests([])
        setError(e instanceof Error ? e.message : String(e))
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  function openCreate() {
    setEditor('create')
    setDraft(emptyDraft())
    setFormError(null)
  }

  function openEdit(topic: NewsTopic) {
    setEditor('edit')
    setDraft(draftFromTopic(topic))
    setFormError(null)
  }

  function closeEditor() {
    setEditor(null)
    setFormError(null)
  }

  function toggleDay(day: number) {
    setDraft((current) => {
      const has = current.schedule_days.includes(day)
      const schedule_days = has
        ? current.schedule_days.filter((value) => value !== day)
        : [...current.schedule_days, day].sort((a, b) => a - b)
      return { ...current, schedule_days }
    })
  }

  async function saveTopic() {
    setSaving(true)
    setFormError(null)
    try {
      const body = toWrite(draft)
      if (editor === 'create') {
        const id = draft.id.trim().toLowerCase()
        if (!id) throw new Error('Id is required')
        await api.createNewsTopic({ id, ...body })
      } else if (editor === 'edit') {
        await api.updateNewsTopic(draft.id, body)
      }
      closeEditor()
      await load()
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="panel">
      <h2>News</h2>
      <p className="lede">
        Topic digests from the Pi. AI keys stay on the server (
        {providers.length ? providers.join(' → ') : 'none configured — summarize skipped'}).
      </p>
      <div className="panel-actions">
        <button type="button" className="primary" onClick={openCreate}>
          New topic
        </button>
        <button type="button" onClick={() => void load()}>
          Refresh
        </button>
      </div>
      {editor && (
        <form
          className="topic-form"
          onSubmit={(event) => {
            event.preventDefault()
            void saveTopic()
          }}
        >
          <h3>{editor === 'create' ? 'New topic' : `Edit ${draft.id}`}</h3>
          <label>
            Id
            <input
              value={draft.id}
              disabled={editor === 'edit'}
              required
              autoComplete="off"
              spellCheck={false}
              placeholder="politics"
              onChange={(event) => setDraft({ ...draft, id: event.target.value })}
            />
            <span className="hint">Lowercase slug. Cannot be changed later.</span>
          </label>
          <label>
            Label
            <input
              value={draft.label}
              required
              maxLength={120}
              onChange={(event) => setDraft({ ...draft, label: event.target.value })}
            />
          </label>
          <label>
            Goal
            <textarea
              value={draft.goal}
              maxLength={2000}
              rows={3}
              placeholder="Short English digest of what changed."
              onChange={(event) => setDraft({ ...draft, goal: event.target.value })}
            />
          </label>
          <label>
            Feed URLs
            <textarea
              value={draft.feeds}
              rows={4}
              spellCheck={false}
              placeholder={'https://example.com/rss\nmock://politics'}
              onChange={(event) => setDraft({ ...draft, feeds: event.target.value })}
            />
            <span className="hint">One URL per line. http(s) or mock://</span>
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={draft.schedule_enabled}
              onChange={(event) =>
                setDraft({ ...draft, schedule_enabled: event.target.checked })
              }
            />
            Run on a schedule
          </label>
          <div className="time-row">
            <label>
              Hour
              <input
                type="number"
                min={0}
                max={23}
                value={draft.schedule_hour}
                onChange={(event) => setDraft({ ...draft, schedule_hour: event.target.value })}
              />
            </label>
            <label>
              Minute
              <input
                type="number"
                min={0}
                max={59}
                value={draft.schedule_minute}
                onChange={(event) =>
                  setDraft({ ...draft, schedule_minute: event.target.value })
                }
              />
            </label>
          </div>
          <fieldset>
            <legend>Days</legend>
            <div className="tags">
              {DAY_LABELS.map((label, day) => (
                <button
                  key={label}
                  type="button"
                  className={`chip ${draft.schedule_days.includes(day) ? 'active' : ''}`}
                  onClick={() => toggleDay(day)}
                >
                  {label}
                </button>
              ))}
            </div>
          </fieldset>
          {formError && <div className="error-box">{formError}</div>}
          <div className="panel-actions">
            <button type="submit" className="primary" disabled={saving}>
              {saving ? 'Saving…' : editor === 'create' ? 'Create topic' : 'Save changes'}
            </button>
            <button type="button" onClick={closeEditor} disabled={saving}>
              Cancel
            </button>
          </div>
        </form>
      )}
      {loading && <p className="muted">Loading…</p>}
      {error && <div className="error-box">{error}</div>}
      {!loading && (
        <>
          <div className="subnav" role="tablist" aria-label="News sections">
            <button
              type="button"
              className={section === 'topics' ? 'active' : undefined}
              onClick={() => setSection('topics')}
            >
              Topics ({topics.length})
            </button>
            <button
              type="button"
              className={section === 'digests' ? 'active' : undefined}
              onClick={() => setSection('digests')}
            >
              Latest digests ({digests.length})
            </button>
          </div>
          {section === 'topics' && (
            <>
          <h3 className="muted" style={{ fontSize: '0.85rem' }}>
            Topics ({topics.length})
          </h3>
          {topics.length === 0 && <div className="list-empty">No topics yet.</div>}
          {topics.map((topic) => (
            <div className="section-card" key={topic.id}>
              <div className="card-head">
                <h3>
                  {topic.label} <span className="muted">({topic.id})</span>
                </h3>
                <button type="button" onClick={() => openEdit(topic)}>
                  Edit
                </button>
              </div>
              {topic.goal && <p style={{ margin: '0 0 0.35rem' }}>{topic.goal}</p>}
              <p className="muted" style={{ margin: 0 }}>
                {formatSchedule(topic)}
                {topic.feed_urls.length
                  ? ` · ${topic.feed_urls.length} feed${topic.feed_urls.length === 1 ? '' : 's'}`
                  : ' · no feeds'}
              </p>
              <p className="muted" style={{ margin: '0.25rem 0 0' }}>
                Last run: {topic.last_run_status ?? '—'}
                {topic.last_run_at ? ` · ${topic.last_run_at}` : ''}
                {topic.last_error ? ` · ${topic.last_error}` : ''}
              </p>
            </div>
          ))}
            </>
          )}
          {section === 'digests' && (
            <>
          <h3 className="muted" style={{ fontSize: '0.85rem', marginTop: '1rem' }}>
            Latest digests
          </h3>
          {digests.length === 0 && <div className="list-empty">No digests for today yet.</div>}
          {digests.map((digest) => (
            <div className="digest-card" key={digest.id}>
              <h3>
                {digest.topic_label}{' '}
                <span className="muted">
                  · {digest.status}
                  {digest.ai_provider ? ` · ${digest.ai_provider}` : ''}
                </span>
              </h3>
              <p style={{ margin: 0 }}>{digest.digest}</p>
              <p className="muted" style={{ margin: '0.5rem 0 0', fontSize: '0.8rem' }}>
                {digest.item_count} items · {digest.generated_at}
              </p>
            </div>
          ))}
            </>
          )}
        </>
      )}
    </section>
  )
}
