export const THEME_MODE_KEY = 'pa_theme_mode'
export const THEME_ACCENT_KEY = 'pa_theme_accent'

export type ThemeMode = 'system' | 'dark' | 'light'
export type ThemeAccent = 'teal' | 'blue' | 'amber' | 'rose'

function stored(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    /* storage unavailable */
    return null
  }
}

function persist(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* storage unavailable */
  }
}

export function readThemeMode(): ThemeMode {
  const value = stored(THEME_MODE_KEY)
  if (value === 'system' || value === 'dark' || value === 'light') return value
  return 'dark'
}

export function readThemeAccent(): ThemeAccent {
  const value = stored(THEME_ACCENT_KEY)
  if (value === 'teal' || value === 'blue' || value === 'amber' || value === 'rose') return value
  return 'teal'
}

export function writeThemeMode(mode: ThemeMode): void {
  persist(THEME_MODE_KEY, mode)
}

export function writeThemeAccent(accent: ThemeAccent): void {
  persist(THEME_ACCENT_KEY, accent)
}

export function applyTheme(
  mode: ThemeMode = readThemeMode(),
  accent: ThemeAccent = readThemeAccent(),
): void {
  const root = document.documentElement
  root.dataset.theme = mode
  root.dataset.accent = accent
}

function channel(hex: string, shift: number): number {
  return (Number.parseInt(hex, 16) >> shift) & 255
}

function withAlpha(hex: string, alpha: number, fallback: string): string {
  const raw = hex.trim().replace('#', '')
  if (raw.length !== 6 || Number.isNaN(Number.parseInt(raw, 16))) return fallback
  return `rgba(${channel(raw, 16)},${channel(raw, 8)},${channel(raw, 0)},${alpha})`
}

/** Canvas colors from the active theme. Chart.js does not read CSS variables. */
export function themeChartColors(): {
  accent: string
  accentFill: string
  muted: string
  grid: string
  secondary: string
} {
  const root = getComputedStyle(document.documentElement)
  const accent = root.getPropertyValue('--accent').trim() || '#3db8a0'
  const muted = root.getPropertyValue('--text-muted').trim() || '#8b9aab'
  const border = root.getPropertyValue('--border').trim() || '#2a3544'
  return {
    accent,
    accentFill: withAlpha(accent, 0.15, 'rgba(61,184,160,0.15)'),
    muted,
    grid: withAlpha(border, 0.6, 'rgba(42,53,68,0.6)'),
    secondary: '#7aa2d6',
  }
}
