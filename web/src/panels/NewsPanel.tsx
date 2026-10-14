import { useCallback, useEffect, useState } from 'react'
import { api, type NewsDigest, type NewsTopic } from '../api'

export function NewsPanel() {
  const [topics, setTopics] = useState<NewsTopic[]>([])
  const [digests, setDigests] = useState<NewsDigest[]>([])
  const [providers, setProviders] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [status, t, d] = await Promise.all([
        api.newsStatus(),
        api.newsTopics(),
        api.newsLatest(),
      ])
      setProviders(status.providers_configured)
      setTopics(t)
      setDigests(d)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <section className="panel">
      <h2>News</h2>
      <p className="lede">
        Topic digests from the Pi. AI keys stay on the server (
        {providers.length ? providers.join(' → ') : 'none configured — summarize skipped'}).
      </p>
      <div className="panel-actions">
        <button type="button" className="primary" onClick={() => void load()}>
          Refresh
        </button>
      </div>
      {loading && <p className="muted">Loading…</p>}
      {error && <div className="error-box">{error}</div>}
      {!loading && (
        <>
          <h3 className="muted" style={{ fontSize: '0.85rem' }}>
            Topics ({topics.length})
          </h3>
          {topics.length === 0 && <div className="list-empty">No topics yet. Create via API or README curl.</div>}
          {topics.map((t) => (
            <div className="section-card" key={t.id}>
              <h3>
                {t.label} <span className="muted">({t.id})</span>
              </h3>
              <p className="muted" style={{ margin: 0 }}>
                Last run: {t.last_run_status ?? '—'}
                {t.last_run_at ? ` · ${t.last_run_at}` : ''}
                {t.last_error ? ` · ${t.last_error}` : ''}
              </p>
            </div>
          ))}
          <h3 className="muted" style={{ fontSize: '0.85rem', marginTop: '1rem' }}>
            Latest digests
          </h3>
          {digests.length === 0 && <div className="list-empty">No digests for today yet.</div>}
          {digests.map((d) => (
            <div className="digest-card" key={d.id}>
              <h3>
                {d.topic_label}{' '}
                <span className="muted">
                  · {d.status}
                  {d.ai_provider ? ` · ${d.ai_provider}` : ''}
                </span>
              </h3>
              <p style={{ margin: 0 }}>{d.digest}</p>
              <p className="muted" style={{ margin: '0.5rem 0 0', fontSize: '0.8rem' }}>
                {d.item_count} items · {d.generated_at}
              </p>
            </div>
          ))}
        </>
      )}
    </section>
  )
}
