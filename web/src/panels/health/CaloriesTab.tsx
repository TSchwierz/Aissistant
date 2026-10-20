import { useEffect, useState } from 'react'
import { api, type FoodHit, type MealItem, type MealSummary } from '../../api'
import { errorMessage, formatWhen } from './shared'

type ProposalRow = {
  key: string
  gramsText: string
  item: MealItem
}

let rowSeq = 0

function nextKey(): string {
  rowSeq += 1
  return `food-${rowSeq}`
}

function todayLocal(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

function formatMacro(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—'
  const rounded = Math.round(value * 10) / 10
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1)
}

function formatAgainst(value: number, target?: number | null, unit?: string): string {
  const suffix = unit ? ` ${unit}` : ''
  if (target == null) return `${formatMacro(value)}${suffix}`
  return `${formatMacro(value)} / ${formatMacro(target)}${suffix}`
}

function roundMacro(value: number): number {
  return Math.round(value * 100) / 100
}

function scaleTo(item: MealItem, newGrams: number): MealItem {
  if (!(item.grams > 0)) return { ...item, grams: newGrams }
  const ratio = newGrams / item.grams
  return {
    ...item,
    grams: newGrams,
    kcal: item.kcal * ratio,
    protein_g: item.protein_g * ratio,
    carbs_g: item.carbs_g * ratio,
    fat_g: item.fat_g * ratio,
    fiber_g: item.fiber_g * ratio,
  }
}

function toRow(item: MealItem): ProposalRow {
  return { key: nextKey(), gramsText: String(item.grams), item }
}

function hitToItem(hit: FoodHit): MealItem {
  return {
    name: hit.name,
    grams: 100,
    kcal: hit.kcal_100g,
    protein_g: hit.protein_100g,
    carbs_g: hit.carbs_100g,
    fat_g: hit.fat_100g,
    fiber_g: hit.fiber_100g,
    source: hit.source,
    source_id: hit.source_id ?? null,
  }
}

function itemFromRow(row: ProposalRow): MealItem | null {
  const name = row.item.name.trim()
  if (!name) return null
  const grams = Number(row.gramsText)
  if (!Number.isFinite(grams) || grams <= 0) return null
  const scaled = grams === row.item.grams ? row.item : scaleTo(row.item, grams)
  return {
    ...(scaled.id != null ? { id: scaled.id } : {}),
    name,
    grams: roundMacro(scaled.grams),
    kcal: roundMacro(scaled.kcal),
    protein_g: roundMacro(scaled.protein_g),
    carbs_g: roundMacro(scaled.carbs_g),
    fat_g: roundMacro(scaled.fat_g),
    fiber_g: roundMacro(scaled.fiber_g),
    source: scaled.source || 'manual',
    source_id: scaled.source_id ?? null,
  }
}

export function CaloriesTab() {
  const [day, setDay] = useState(todayLocal)
  const [summary, setSummary] = useState<MealSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState('')
  const [proposal, setProposal] = useState<ProposalRow[]>([])
  const [proposed, setProposed] = useState(false)
  const [proposing, setProposing] = useState(false)
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<FoodHit[]>([])
  const [searched, setSearched] = useState(false)
  const [searching, setSearching] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [reloadToken, setReloadToken] = useState(0)
  const [loadedDay, setLoadedDay] = useState<string | null>(null)

  useEffect(() => {
    let cancel = false
    setLoading(true)
    setError(null)
    api
      .mealSummary(day)
      .then((data) => {
        if (cancel) return
        setSummary(data)
        setLoadedDay(day)
      })
      .catch((e: unknown) => {
        if (!cancel) setError(errorMessage(e))
      })
      .finally(() => {
        if (!cancel) setLoading(false)
      })
    return () => {
      cancel = true
    }
  }, [day, reloadToken])

  function updateRow(key: string, next: ProposalRow) {
    setProposal((rows) => rows.map((row) => (row.key === key ? next : row)))
  }

  async function propose() {
    if (!note.trim()) {
      setError('Describe a meal first.')
      return
    }
    setProposing(true)
    setError(null)
    try {
      const parsed = await api.parseMeal(note)
      setProposal((parsed.items ?? []).map(toRow))
      setProposed(true)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setProposing(false)
    }
  }

  async function runSearch() {
    const q = query.trim()
    if (!q) {
      setHits([])
      setSearched(false)
      return
    }
    setSearching(true)
    setError(null)
    try {
      const result = await api.searchFoods(q)
      setHits(result.foods ?? [])
      setSearched(true)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setSearching(false)
    }
  }

  function addHit(hit: FoodHit) {
    setProposal((rows) => [...rows, toRow(hitToItem(hit))])
    setProposed(true)
  }

  async function saveMeal() {
    if (proposal.length === 0) {
      setError('Add at least one food.')
      return
    }
    const items: MealItem[] = []
    for (const row of proposal) {
      const item = itemFromRow(row)
      if (!item) {
        setError('Each food needs a name and grams greater than 0.')
        return
      }
      items.push(item)
    }
    setSaving(true)
    setError(null)
    try {
      await api.createMeal({
        eaten_at: `${day}T12:00:00`,
        note,
        source: 'text',
        items,
      })
      setProposal([])
      setNote('')
      setProposed(false)
      setReloadToken((token) => token + 1)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setSaving(false)
    }
  }

  async function removeMeal(id: number) {
    setDeletingId(id)
    setError(null)
    try {
      await api.deleteMeal(id)
      setReloadToken((token) => token + 1)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setDeletingId(null)
    }
  }

  const shown = loadedDay === day ? summary : null
  const targets = shown?.targets

  return (
    <>
      <div className="topic-form">
        <label>
          Day
          <input
            type="date"
            value={day}
            onChange={(event) => {
              const next = event.target.value
              if (!next || next === day) return
              setLoading(true)
              setError(null)
              setDay(next)
            }}
          />
        </label>
      </div>
      {loading && <p className="muted">Loading…</p>}
      {error && <div className="error-box">{error}</div>}
      {shown && (
        <>
          <div className="grid-2">
            <div className="stat">
              <div className="label">Calories</div>
              <div className="value" style={{ fontSize: '1.05rem' }}>
                {formatAgainst(shown.totals.kcal, targets?.target_calories, 'kcal')}
              </div>
            </div>
            <div className="stat">
              <div className="label">Protein</div>
              <div className="value" style={{ fontSize: '1.05rem' }}>
                {formatAgainst(shown.totals.protein_g, targets?.protein_g, 'g')}
              </div>
            </div>
            <div className="stat">
              <div className="label">Fiber</div>
              <div className="value" style={{ fontSize: '1.05rem' }}>
                {formatAgainst(shown.totals.fiber_g, targets?.fiber_g, 'g')}
              </div>
            </div>
            <div className="stat">
              <div className="label">Carbs</div>
              <div className="value" style={{ fontSize: '1.05rem' }}>
                {formatAgainst(shown.totals.carbs_g, null, 'g')}
              </div>
            </div>
            <div className="stat">
              <div className="label">Fat</div>
              <div className="value" style={{ fontSize: '1.05rem' }}>
                {formatAgainst(shown.totals.fat_g, null, 'g')}
              </div>
            </div>
          </div>
          <h3 className="muted" style={{ fontSize: '0.85rem' }}>
            Meals
          </h3>
          {shown.meals.length === 0 && <div className="list-empty">No meals logged for this day.</div>}
          {shown.meals.map((meal) => (
            <div className="section-card" key={meal.id}>
              <div className="card-head">
                <div>
                  <h3>
                    {formatWhen(meal.eaten_at)}
                    {meal.note ? ` · ${meal.note}` : ''}
                  </h3>
                  <div className="muted">{meal.source}</div>
                </div>
                <button
                  type="button"
                  disabled={deletingId === meal.id}
                  onClick={() => void removeMeal(meal.id)}
                >
                  Delete meal
                </button>
              </div>
              {meal.items.length === 0 ? (
                <p className="muted" style={{ margin: '0.45rem 0 0' }}>
                  No items.
                </p>
              ) : (
                <ul className="meal-items">
                  {meal.items.map((item, index) => (
                    <li key={item.id ?? `${meal.id}-${index}`}>
                      {item.name} · {formatMacro(item.grams)} g · {formatMacro(item.kcal)} kcal ·{' '}
                      {formatMacro(item.protein_g)} g protein · {formatMacro(item.carbs_g)} g carbs ·{' '}
                      {formatMacro(item.fat_g)} g fat · {formatMacro(item.fiber_g)} g fiber
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </>
      )}
      <div className="topic-form">
        <h3>Log a meal</h3>
        <label>
          Describe the meal
          <textarea
            rows={3}
            placeholder="Two slices of bread and a banana"
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
        </label>
        <div className="panel-actions">
          <button type="button" onClick={() => void propose()} disabled={proposing}>
            {proposing ? 'Proposing…' : 'Propose foods'}
          </button>
        </div>
        {proposing && <p className="muted">Proposing foods…</p>}
        {proposed && proposal.length === 0 && !proposing && (
          <p className="muted">No foods proposed.</p>
        )}
        {proposal.map((row) => (
          <div className="proposal-row" key={row.key}>
            <label>
              Name
              <input
                value={row.item.name}
                onChange={(event) =>
                  updateRow(row.key, {
                    ...row,
                    item: { ...row.item, name: event.target.value },
                  })
                }
              />
            </label>
            <label>
              Grams
              <input
                type="number"
                min={0}
                step="any"
                value={row.gramsText}
                onChange={(event) => {
                  const text = event.target.value
                  const trimmed = text.trim()
                  const newGrams = Number(trimmed)
                  if (trimmed === '' || !Number.isFinite(newGrams) || newGrams === 0) {
                    updateRow(row.key, { ...row, gramsText: text })
                    return
                  }
                  updateRow(row.key, {
                    ...row,
                    gramsText: text,
                    item: newGrams === row.item.grams ? row.item : scaleTo(row.item, newGrams),
                  })
                }}
              />
            </label>
            <div className="proposal-remove">
              <button
                type="button"
                className="health-btn"
                onClick={() => setProposal((rows) => rows.filter((item) => item.key !== row.key))}
              >
                Remove
              </button>
            </div>
            <p className="proposal-macros">
              {formatMacro(row.item.kcal)} kcal · {formatMacro(row.item.protein_g)} g protein ·{' '}
              {formatMacro(row.item.carbs_g)} g carbs · {formatMacro(row.item.fat_g)} g fat ·{' '}
              {formatMacro(row.item.fiber_g)} g fiber
            </p>
          </div>
        ))}
        <div className="health-search">
          <label>
            Search foods
            <input
              value={query}
              placeholder="Food name"
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault()
                  void runSearch()
                }
              }}
            />
          </label>
          <button type="button" className="health-btn" onClick={() => void runSearch()} disabled={searching}>
            Search
          </button>
        </div>
        {searching && <p className="muted">Searching…</p>}
        {searched && !searching && hits.length === 0 && (
          <p className="muted">No matching foods.</p>
        )}
        {hits.length > 0 && (
          <div className="health-hits">
            {hits.map((hit, index) => (
              <button
                key={`${hit.source}-${hit.source_id ?? hit.name}-${index}`}
                type="button"
                className="health-btn"
                onClick={() => addHit(hit)}
              >
                {hit.name} · {formatMacro(hit.kcal_100g)} kcal/100 g · {formatMacro(hit.protein_100g)} g
                protein · {hit.source}
              </button>
            ))}
          </div>
        )}
        <div className="panel-actions">
          <button
            type="button"
            className="primary"
            disabled={saving || proposal.length === 0}
            onClick={() => void saveMeal()}
          >
            {saving ? 'Saving…' : 'Save meal'}
          </button>
        </div>
      </div>
    </>
  )
}
