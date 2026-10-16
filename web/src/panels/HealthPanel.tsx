import { useCallback, useEffect, useState } from 'react'
import { api, getApiBase, type HealthProfile, type HealthStats } from '../api'

const ACTIVITIES = [
  { id: 'sedentary', label: 'Sedentary' },
  { id: 'light', label: 'Light' },
  { id: 'moderate', label: 'Moderate' },
  { id: 'active', label: 'Active' },
  { id: 'very_active', label: 'Very active' },
]

function pair(pct?: number | null, kg?: number | null): string {
  if (pct == null && kg == null) return '—'
  const left = pct == null ? '—' : `${pct.toFixed(1)}%`
  const right = kg == null ? '—' : `${kg.toFixed(1)} kg`
  return `${left} · ${right}`
}

export function HealthPanel() {
  const [stats, setStats] = useState<HealthStats | null>(null)
  const [profile, setProfile] = useState<HealthProfile | null>(null)
  const [scale, setScale] = useState<string | null>(null)
  const [mode, setMode] = useState('auto')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [activity, setActivity] = useState('moderate')
  const [targetFat, setTargetFat] = useState('')
  const [meals, setMeals] = useState(3)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [s, p, scan] = await Promise.all([
        api.healthStats(),
        api.healthProfile(),
        api.scaleStatus().catch(() => null),
      ])
      setStats(s)
      setProfile(p)
      setActivity(p.activity_level || 'moderate')
      setTargetFat(p.target_fat_pct != null ? String(p.target_fat_pct) : '')
      setMeals(p.meals_per_day || p.nutrition?.meals_per_day || 3)
      setMode(scan?.mode || 'auto')
      setScale(
        scan
          ? `${scan.mode || 'auto'} · ${scan.window} · ${scan.phase}${scan.detail ? ` — ${scan.detail}` : ''}`
          : null,
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  async function setScan(action: 'start' | 'stop' | 'auto') {
    setBusy(true)
    setError(null)
    try {
      const scan = await api.setScaleMode(action)
      setMode(scan.mode || action)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function saveTargets(next?: { activity?: string; meals?: number; fat?: string }) {
    if (!profile) return
    const activityLevel = next?.activity ?? activity
    const mealCount = next?.meals ?? meals
    const fatText = next?.fat ?? targetFat
    setBusy(true)
    setError(null)
    try {
      await api.updateHealthProfile({
        name: profile.name,
        height_cm: profile.height_cm,
        age: profile.age,
        sex: profile.sex,
        activity_level: activityLevel,
        target_fat_pct: fatText.trim() ? Number(fatText) : null,
        meals_per_day: mealCount,
      })
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const dashUrl = `${getApiBase()}/`
  const latest = stats?.latest
  const nutrition = stats?.nutrition ?? profile?.nutrition
  const perMealCalories =
    nutrition?.target_calories != null ? Math.round(nutrition.target_calories / meals) : null
  const perMealProtein =
    nutrition?.protein_g != null ? (nutrition.protein_g / meals).toFixed(1) : null
  const perMealFiber = nutrition?.fiber_g != null ? (nutrition.fiber_g / meals).toFixed(1) : null

  return (
    <section className="panel">
      <h2>Health</h2>
      <p className="lede">
        The Pi records the scale over Bluetooth from 06:00 to 12:00, then stops once today&apos;s
        measurement is stored. Height, age, and sex stay on the health dashboard.
      </p>
      <div className="panel-actions">
        <button type="button" className="primary" onClick={() => void load()}>
          Refresh
        </button>
        <button type="button" disabled={busy || mode === 'on'} onClick={() => void setScan('start')}>
          Start scan
        </button>
        <button type="button" disabled={busy || mode === 'off'} onClick={() => void setScan('stop')}>
          Stop scan
        </button>
        <button type="button" disabled={busy || mode === 'auto'} onClick={() => void setScan('auto')}>
          Use schedule
        </button>
        <a href={dashUrl} target="_blank" rel="noreferrer">
          <button type="button">Open Health dashboard</button>
        </a>
      </div>
      {loading && <p className="muted">Loading…</p>}
      {error && <div className="error-box">{error}</div>}
      {stats && profile && !loading && (
        <div className="grid-2">
          <div className="stat">
            <div className="label">Latest weight</div>
            <div className="value">
              {stats.latest ? `${stats.latest.weight_kg.toFixed(1)} kg` : '—'}
            </div>
          </div>
          <div className="stat">
            <div className="label">7d average</div>
            <div className="value">
              {stats.avg_weight_7d != null ? `${stats.avg_weight_7d.toFixed(1)} kg` : '—'}
            </div>
          </div>
          <div className="stat">
            <div className="label">Measurements</div>
            <div className="value">{stats.count}</div>
          </div>
          {scale && (
            <div className="stat">
              <div className="label">Scale listener</div>
              <div className="value" style={{ fontSize: '1.05rem' }}>
                {scale}
              </div>
            </div>
          )}
          <div className="stat">
            <div className="label">Profile</div>
            <div className="value" style={{ fontSize: '1.05rem' }}>
              {profile.name || '—'} · {profile.is_complete ? 'complete' : 'incomplete'}
            </div>
          </div>
          {latest?.bmi != null && (
            <div className="stat">
              <div className="label">BMI</div>
              <div className="value">{latest.bmi.toFixed(1)}</div>
            </div>
          )}
          {latest && (latest.body_fat_pct != null || latest.body_fat_kg != null) && (
            <div className="stat">
              <div className="label">Body fat</div>
              <div className="value" style={{ fontSize: '1.05rem' }}>
                {pair(latest.body_fat_pct, latest.body_fat_kg)}
              </div>
            </div>
          )}
          {latest && (latest.muscle_pct != null || latest.muscle_mass_kg != null) && (
            <div className="stat">
              <div className="label">Muscle</div>
              <div className="value" style={{ fontSize: '1.05rem' }}>
                {pair(latest.muscle_pct, latest.muscle_mass_kg)}
              </div>
            </div>
          )}
          {latest && (latest.water_pct != null || latest.water_kg != null) && (
            <div className="stat">
              <div className="label">Water</div>
              <div className="value" style={{ fontSize: '1.05rem' }}>
                {pair(latest.water_pct, latest.water_kg)}
              </div>
            </div>
          )}
          {latest && (latest.bone_pct != null || latest.bone_mass_kg != null) && (
            <div className="stat">
              <div className="label">Bone</div>
              <div className="value" style={{ fontSize: '1.05rem' }}>
                {pair(latest.bone_pct, latest.bone_mass_kg)}
              </div>
            </div>
          )}
          {nutrition && (
            <div className="stat" style={{ gridColumn: '1 / -1' }}>
              <div className="label">Daily targets</div>
              <div className="value" style={{ fontSize: '1.05rem' }}>
                {nutrition.target_calories != null ? `${nutrition.target_calories} kcal` : '—'}
                {nutrition.protein_g != null ? ` · ${nutrition.protein_g} g protein` : ''}
                {nutrition.fiber_g != null ? ` · ${nutrition.fiber_g} g fiber` : ''}
              </div>
              <p className="muted" style={{ margin: '0.35rem 0 0.6rem' }}>
                {nutrition.bmr
                  ? `BMR ${Math.round(nutrition.bmr)} × ${nutrition.activity_factor}. Fiber is 14 g per 1,000 kcal.`
                  : 'A measurement with BMR is needed before calories can be calculated.'}
                {nutrition.target_fat_pct != null
                  ? ` Fat goal ${nutrition.target_fat_pct}%${
                      latest?.body_fat_pct != null ? ` (now ${latest.body_fat_pct.toFixed(1)}%)` : ''
                    }.`
                  : ''}
              </p>
              <div className="topic-form" style={{ margin: '0.6rem 0 0' }}>
              <div className="time-row">
                <label>
                  Activity
                  <select
                    value={activity}
                    onChange={(event) => {
                      const value = event.target.value
                      setActivity(value)
                      void saveTargets({ activity: value })
                    }}
                  >
                    {ACTIVITIES.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Target fat %
                  <input
                    type="number"
                    min={2}
                    max={70}
                    step={0.1}
                    value={targetFat}
                    onChange={(event) => setTargetFat(event.target.value)}
                    onBlur={() => void saveTargets({ fat: targetFat })}
                  />
                </label>
              </div>
              <label>
                Meals per day: {meals}
                <input
                  type="range"
                  min={1}
                  max={8}
                  step={1}
                  value={meals}
                  onChange={(event) => setMeals(Number(event.target.value))}
                  onPointerUp={(event) =>
                    void saveTargets({ meals: Number((event.target as HTMLInputElement).value) })
                  }
                />
              </label>
              </div>
              <p className="muted" style={{ margin: '0.45rem 0 0' }}>
                Each meal:{' '}
                {perMealCalories != null
                  ? `${perMealCalories} kcal · ${perMealProtein} g protein · ${perMealFiber} g fiber`
                  : '—'}
              </p>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
