import { useCallback, useEffect, useState } from 'react'
import { api, type HealthProfile, type HealthStats, type NutritionTarget } from '../../api'
import { ACTIVITIES, errorMessage } from './shared'
import { TargetsBlock } from './TargetsBlock'

function applyNumbers(next: HealthProfile) {
  return {
    name: next.name ?? '',
    height: next.height_cm != null ? String(next.height_cm) : '',
    age: next.age != null ? String(next.age) : '',
    sex: next.sex === 'male' || next.sex === 'female' ? next.sex : '',
    activity: next.activity_level || 'moderate',
    targetFat: next.target_fat_pct != null ? String(next.target_fat_pct) : '',
    meals: next.meals_per_day || next.nutrition?.meals_per_day || 3,
  }
}

function readOptionalNumber(text: string, label: string): number | null {
  const trimmed = text.trim()
  if (!trimmed) return null
  const value = Number(trimmed)
  if (!Number.isFinite(value)) throw new Error(`${label} must be a number`)
  return value
}

function readOptionalInt(text: string, label: string): number | null {
  const value = readOptionalNumber(text, label)
  if (value == null) return null
  if (!Number.isInteger(value)) throw new Error(`${label} must be a whole number`)
  return value
}

export function ProfileTab() {
  const [profile, setProfile] = useState<HealthProfile | null>(null)
  const [stats, setStats] = useState<HealthStats | null>(null)
  const [name, setName] = useState('')
  const [height, setHeight] = useState('')
  const [age, setAge] = useState('')
  const [sex, setSex] = useState('')
  const [activity, setActivity] = useState('moderate')
  const [targetFat, setTargetFat] = useState('')
  const [meals, setMeals] = useState(3)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const fill = useCallback((next: HealthProfile) => {
    const form = applyNumbers(next)
    setName(form.name)
    setHeight(form.height)
    setAge(form.age)
    setSex(form.sex)
    setActivity(form.activity)
    setTargetFat(form.targetFat)
    setMeals(form.meals)
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [nextProfile, nextStats] = await Promise.all([
        api.healthProfile(),
        api.healthStats().catch(() => null),
      ])
      setProfile(nextProfile)
      setStats(nextStats)
      fill(nextProfile)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setLoading(false)
    }
  }, [fill])

  useEffect(() => {
    void load()
  }, [load])

  async function save() {
    setSaving(true)
    setError(null)
    try {
      const saved = await api.updateHealthProfile({
        name: name.trim(),
        height_cm: readOptionalNumber(height, 'Height'),
        age: readOptionalInt(age, 'Age'),
        sex: sex === 'male' || sex === 'female' ? sex : null,
        activity_level: activity,
        target_fat_pct: readOptionalNumber(targetFat, 'Target fat'),
        meals_per_day: meals,
      })
      setProfile(saved)
      fill(saved)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setSaving(false)
    }
  }

  const nutrition: NutritionTarget | null | undefined = profile?.nutrition ?? stats?.nutrition
  const currentFat = stats?.latest?.body_fat_pct

  return (
    <>
      {loading && <p className="muted">Loading…</p>}
      {error && <div className="error-box">{error}</div>}
      {profile && !loading && (
        <>
          <form
            className="topic-form"
            onSubmit={(event) => {
              event.preventDefault()
              void save()
            }}
          >
            <h3>Profile and targets</h3>
            <div className="time-row">
              <label>
                Name
                <input value={name} onChange={(event) => setName(event.target.value)} />
              </label>
              <label>
                Height cm
                <input
                  type="number"
                  min={1}
                  max={299}
                  step="0.1"
                  value={height}
                  onChange={(event) => setHeight(event.target.value)}
                />
              </label>
            </div>
            <div className="time-row">
              <label>
                Age
                <input
                  type="number"
                  min={1}
                  max={120}
                  step={1}
                  value={age}
                  onChange={(event) => setAge(event.target.value)}
                />
              </label>
              <label>
                Sex
                <select value={sex} onChange={(event) => setSex(event.target.value)}>
                  <option value="">Not set</option>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                </select>
              </label>
            </div>
            <div className="time-row">
              <label>
                Activity
                <select value={activity} onChange={(event) => setActivity(event.target.value)}>
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
              />
            </label>
            <div className="panel-actions">
              <button type="submit" className="primary" disabled={saving}>
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </form>
          {nutrition && (
            <div className="stat">
              <TargetsBlock nutrition={nutrition} meals={meals} currentFatPct={currentFat} />
            </div>
          )}
        </>
      )}
    </>
  )
}
