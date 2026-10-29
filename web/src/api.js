/** Pi LAN API client — no AI keys in the browser. */
const STORAGE_KEY = 'pa_api_base';
export function getApiBase() {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored)
        return stored.replace(/\/$/, '');
    return import.meta.env.VITE_PI_API_BASE?.replace(/\/$/, '')
        || 'http://192.168.178.23:8741';
}
export function setApiBase(url) {
    localStorage.setItem(STORAGE_KEY, url.trim().replace(/\/$/, ''));
}
async function readApiError(res) {
    const text = await res.text();
    try {
        const data = JSON.parse(text);
        if (typeof data.detail === 'string')
            return data.detail;
        if (Array.isArray(data.detail)) {
            const parts = data.detail.map((item) => {
                if (typeof item === 'string')
                    return item;
                if (item && typeof item === 'object' && 'msg' in item) {
                    const rec = item;
                    const loc = Array.isArray(rec.loc)
                        ? rec.loc.filter((part) => part !== 'body').join('.')
                        : '';
                    const msg = String(rec.msg);
                    return loc ? `${loc}: ${msg}` : msg;
                }
                return JSON.stringify(item);
            });
            if (parts.length)
                return parts.join('; ');
        }
    }
    catch {
        /* fall through to raw body */
    }
    return `HTTP ${res.status}: ${text.slice(0, 200)}`;
}
async function getJson(path) {
    const res = await fetch(`${getApiBase()}${path}`);
    if (!res.ok)
        throw new Error(await readApiError(res));
    return res.json();
}
async function sendJson(method, path, body) {
    const res = await fetch(`${getApiBase()}${path}`, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (!res.ok)
        throw new Error(await readApiError(res));
    return res.json();
}
export const api = {
    healthLiveness: () => getJson('/health'),
    morningBrief: (refresh = false) => getJson(`/briefing/morning${refresh ? '?refresh=1' : ''}`),
    calendarDay: (day, tag) => {
        const q = new URLSearchParams();
        if (tag)
            q.set('tag', tag);
        const qs = q.toString();
        return getJson(`/calendar/day/${day}${qs ? `?${qs}` : ''}`);
    },
    calendarMonth: (month, tag) => {
        const q = new URLSearchParams();
        if (tag)
            q.set('tag', tag);
        const qs = q.toString();
        return getJson(`/calendar/month/${month}${qs ? `?${qs}` : ''}`);
    },
    calendarWeeks: (from, tag, days = 14) => {
        const q = new URLSearchParams();
        if (from)
            q.set('from', from);
        if (tag)
            q.set('tag', tag);
        q.set('days', String(days));
        const qs = q.toString();
        return getJson(`/calendar/weeks${qs ? `?${qs}` : ''}`);
    },
    calendarTags: () => getJson('/calendar/tags'),
    setCalendarTagColor: (tag, color) => sendJson('PUT', '/calendar/tags', {
        tag,
        color,
    }),
    createCalendarEvent: (body) => sendJson('POST', '/calendar/events', body),
    updateCalendarEvent: (id, body) => sendJson('PUT', `/calendar/events/${encodeURIComponent(id)}`, body),
    deleteCalendarEvent: (id) => sendJson('DELETE', `/calendar/events/${encodeURIComponent(id)}`, {}),
    healthStats: () => getJson('/api/stats'),
    scaleStatus: () => getJson('/api/scale'),
    setScaleMode: (action) => sendJson('POST', '/api/scale/mode', {
        action,
    }),
    healthProfile: () => getJson('/api/profile'),
    updateHealthProfile: (body) => sendJson('PUT', '/api/profile', body),
    healthMeasurements: (limit = 500) => getJson(`/api/measurements?limit=${limit}`),
    updateMeasurement: (id, body) => sendJson('PUT', `/api/measurements/${id}`, body),
    deleteMeasurement: (id) => sendJson('DELETE', `/api/measurements/${id}`, {}),
    searchFoods: (q) => getJson(`/api/foods/search?q=${encodeURIComponent(q)}`),
    parseMeal: (text) => sendJson('POST', '/api/nutrition/parse', { text }),
    createMeal: (body) => sendJson('POST', '/api/meals', body),
    deleteMeal: (id) => sendJson('DELETE', `/api/meals/${id}`, {}),
    mealSummary: (day) => getJson(`/api/meals/summary?day=${encodeURIComponent(day)}`),
    climateCurrent: () => getJson('/climate/current'),
    climateMeasurements: (limit = 288, from) => {
        const params = new URLSearchParams({ limit: String(limit) });
        if (from)
            params.set('from', from);
        return getJson(`/climate/measurements?${params}`);
    },
    climateOutside: () => getJson('/climate/outside'),
    climateSettings: () => getJson('/climate/settings'),
    updateClimateSettings: (body) => sendJson('PUT', '/climate/settings', body),
    refreshClimateOutside: () => sendJson('POST', '/climate/outside/refresh', {}),
    climateStrategies: () => getJson('/climate/advisor/strategies'),
    newsStatus: () => getJson('/news/status'),
    newsTopics: () => getJson('/news/topics'),
    newsLatest: () => getJson('/news/digests/latest'),
    createNewsTopic: (body) => sendJson('POST', '/news/topics', body),
    updateNewsTopic: (id, body) => sendJson('PUT', `/news/topics/${encodeURIComponent(id)}`, body),
    /** Trigger browser download of SSOT zip (Phase 6 light backup). */
    downloadBackup: async () => {
        const res = await fetch(`${getApiBase()}/backup/export`);
        if (!res.ok) {
            const text = await res.text();
            throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
        }
        const blob = await res.blob();
        const cd = res.headers.get('Content-Disposition') || '';
        const match = /filename="?([^";]+)"?/i.exec(cd);
        const filename = match?.[1] || 'personal-aissistent-backup.zip';
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    },
};
