export const THEME_MODE_KEY = 'pa_theme_mode';
export const THEME_ACCENT_KEY = 'pa_theme_accent';
function stored(key) {
    try {
        return localStorage.getItem(key);
    }
    catch {
        /* storage unavailable */
        return null;
    }
}
function persist(key, value) {
    try {
        localStorage.setItem(key, value);
    }
    catch {
        /* storage unavailable */
    }
}
export function readThemeMode() {
    const value = stored(THEME_MODE_KEY);
    if (value === 'system' || value === 'dark' || value === 'light')
        return value;
    return 'dark';
}
export function readThemeAccent() {
    const value = stored(THEME_ACCENT_KEY);
    if (value === 'teal' || value === 'blue' || value === 'amber' || value === 'rose')
        return value;
    return 'teal';
}
export function writeThemeMode(mode) {
    persist(THEME_MODE_KEY, mode);
}
export function writeThemeAccent(accent) {
    persist(THEME_ACCENT_KEY, accent);
}
export function applyTheme(mode = readThemeMode(), accent = readThemeAccent()) {
    const root = document.documentElement;
    root.dataset.theme = mode;
    root.dataset.accent = accent;
}
function channel(hex, shift) {
    return (Number.parseInt(hex, 16) >> shift) & 255;
}
function withAlpha(hex, alpha, fallback) {
    const raw = hex.trim().replace('#', '');
    if (raw.length !== 6 || Number.isNaN(Number.parseInt(raw, 16)))
        return fallback;
    return `rgba(${channel(raw, 16)},${channel(raw, 8)},${channel(raw, 0)},${alpha})`;
}
/** Canvas colors from the active theme. Chart.js does not read CSS variables. */
export function themeChartColors() {
    const root = getComputedStyle(document.documentElement);
    const accent = root.getPropertyValue('--accent').trim() || '#3db8a0';
    const muted = root.getPropertyValue('--text-muted').trim() || '#8b9aab';
    const border = root.getPropertyValue('--border').trim() || '#2a3544';
    return {
        accent,
        accentFill: withAlpha(accent, 0.15, 'rgba(61,184,160,0.15)'),
        muted,
        grid: withAlpha(border, 0.6, 'rgba(42,53,68,0.6)'),
        secondary: '#7aa2d6',
    };
}
