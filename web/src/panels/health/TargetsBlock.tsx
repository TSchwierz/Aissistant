import type { NutritionTarget } from '../../api'

export function TargetsBlock({
  nutrition,
  meals,
  currentFatPct,
}: {
  nutrition: NutritionTarget
  meals: number
  currentFatPct?: number | null
}) {
  const perMealCalories =
    nutrition.target_calories != null ? Math.round(nutrition.target_calories / meals) : null
  const perMealProtein =
    nutrition.protein_g != null ? (nutrition.protein_g / meals).toFixed(1) : null
  const perMealFiber = nutrition.fiber_g != null ? (nutrition.fiber_g / meals).toFixed(1) : null

  return (
    <>
      <div className="label">Daily targets</div>
      <div className="value" style={{ fontSize: '1.05rem' }}>
        {nutrition.target_calories != null ? `${nutrition.target_calories} kcal` : '—'}
        {nutrition.protein_g != null ? ` · ${nutrition.protein_g} g protein` : ''}
        {nutrition.fiber_g != null ? ` · ${nutrition.fiber_g} g fiber` : ''}
      </div>
      <p className="muted" style={{ margin: '0.35rem 0 0' }}>
        {nutrition.bmr
          ? `BMR ${Math.round(nutrition.bmr)} × ${nutrition.activity_factor}. Fiber is 14 g per 1,000 kcal.`
          : 'A measurement with BMR is needed before calories can be calculated.'}
        {nutrition.target_fat_pct != null
          ? ` Fat goal ${nutrition.target_fat_pct}%${
              currentFatPct != null ? ` (now ${currentFatPct.toFixed(1)}%)` : ''
            }.`
          : ''}
      </p>
      <p className="muted" style={{ margin: '0.45rem 0 0' }}>
        Each meal:{' '}
        {perMealCalories != null
          ? `${perMealCalories} kcal · ${perMealProtein} g protein · ${perMealFiber} g fiber`
          : '—'}
      </p>
    </>
  )
}
