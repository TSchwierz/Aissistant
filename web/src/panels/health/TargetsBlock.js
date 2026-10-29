import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
export function TargetsBlock({ nutrition, meals, currentFatPct, }) {
    const perMealCalories = nutrition.target_calories != null ? Math.round(nutrition.target_calories / meals) : null;
    const perMealProtein = nutrition.protein_g != null ? (nutrition.protein_g / meals).toFixed(1) : null;
    const perMealFiber = nutrition.fiber_g != null ? (nutrition.fiber_g / meals).toFixed(1) : null;
    return (_jsxs(_Fragment, { children: [_jsx("div", { className: "label", children: "Daily targets" }), _jsxs("div", { className: "value", style: { fontSize: '1.05rem' }, children: [nutrition.target_calories != null ? `${nutrition.target_calories} kcal` : '—', nutrition.protein_g != null ? ` · ${nutrition.protein_g} g protein` : '', nutrition.fiber_g != null ? ` · ${nutrition.fiber_g} g fiber` : ''] }), _jsxs("p", { className: "muted", style: { margin: '0.35rem 0 0' }, children: [nutrition.bmr
                        ? `BMR ${Math.round(nutrition.bmr)} × ${nutrition.activity_factor}. Fiber is 14 g per 1,000 kcal.`
                        : 'A measurement with BMR is needed before calories can be calculated.', nutrition.target_fat_pct != null
                        ? ` Fat goal ${nutrition.target_fat_pct}%${currentFatPct != null ? ` (now ${currentFatPct.toFixed(1)}%)` : ''}.`
                        : ''] }), _jsxs("p", { className: "muted", style: { margin: '0.45rem 0 0' }, children: ["Each meal:", ' ', perMealCalories != null
                        ? `${perMealCalories} kcal · ${perMealProtein} g protein · ${perMealFiber} g fiber`
                        : '—'] })] }));
}
