export const ACTIVITIES = [
    { id: 'sedentary', label: 'Sedentary' },
    { id: 'light', label: 'Light' },
    { id: 'moderate', label: 'Moderate' },
    { id: 'active', label: 'Active' },
    { id: 'very_active', label: 'Very active' },
];
export function pair(pct, kg) {
    if (pct == null && kg == null)
        return '—';
    const left = pct == null ? '—' : `${pct.toFixed(1)}%`;
    const right = kg == null ? '—' : `${kg.toFixed(1)} kg`;
    return `${left} · ${right}`;
}
export function formatWhen(iso) {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime()))
        return iso;
    return date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
}
export function errorMessage(error) {
    return error instanceof Error ? error.message : String(error);
}
