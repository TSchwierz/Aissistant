import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useCallback, useEffect, useMemo, useState } from 'react';
import { CategoryScale, Chart as ChartJS, LinearScale, LineElement, PointElement, Tooltip, Legend, } from 'chart.js';
import { Line } from 'react-chartjs-2';
import { api, } from '../api';
import { getApiBase } from '../api';
import { themeChartColors } from '../theme';
ChartJS.register(CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend);
const HISTORY_RANGES = [
    { id: '12h', label: '12 hours', hours: 12 },
    { id: '24h', label: '24 hours', hours: 24 },
    { id: '7d', label: '7 days', hours: 24 * 7 },
    { id: '30d', label: '30 days', hours: 24 * 30 },
];
function decimate(rows, maxPoints) {
    if (rows.length <= maxPoints)
        return rows;
    const step = (rows.length - 1) / (maxPoints - 1);
    const picked = [];
    for (let index = 0; index < maxPoints; index += 1) {
        picked.push(rows[Math.round(index * step)]);
    }
    return picked;
}
function climateChartOptions() {
    const colors = themeChartColors();
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: colors.muted } } },
        scales: {
            x: {
                ticks: { color: colors.muted, maxTicksLimit: 8 },
                grid: { color: colors.grid },
            },
            y: {
                position: 'left',
                ticks: { color: colors.muted },
                grid: { color: colors.grid },
            },
            y1: {
                position: 'right',
                ticks: { color: colors.muted },
                grid: { drawOnChartArea: false },
            },
        },
    };
}
export function ClimatePanel() {
    const [section, setSection] = useState('now');
    const [historyRange, setHistoryRange] = useState('24h');
    const [current, setCurrent] = useState(null);
    const [rows, setRows] = useState([]);
    const [historyLoading, setHistoryLoading] = useState(false);
    const [outside, setOutside] = useState(null);
    const [settings, setSettings] = useState(null);
    const [error, setError] = useState(null);
    const [formError, setFormError] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [cur, out, cfg] = await Promise.all([
                api.climateCurrent(),
                api.climateOutside().catch(() => null),
                api.climateSettings().catch(() => null),
            ]);
            setCurrent(cur);
            setOutside(out);
            setSettings(cfg);
        }
        catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        }
        finally {
            setLoading(false);
        }
    }, []);
    useEffect(() => {
        void load();
    }, [load]);
    useEffect(() => {
        if (section !== 'history')
            return;
        const range = HISTORY_RANGES.find((item) => item.id === historyRange) ?? HISTORY_RANGES[1];
        let cancelled = false;
        setHistoryLoading(true);
        void (async () => {
            try {
                const from = new Date(Date.now() - range.hours * 60 * 60 * 1000).toISOString();
                const meas = await api.climateMeasurements(50_000, from);
                if (!cancelled) {
                    setRows(meas.measurements);
                    setError(null);
                }
            }
            catch (e) {
                if (!cancelled)
                    setError(e instanceof Error ? e.message : String(e));
            }
            finally {
                if (!cancelled)
                    setHistoryLoading(false);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [section, historyRange]);
    const chartRows = useMemo(() => decimate(rows, 800), [rows]);
    const chartData = useMemo(() => {
        const colors = themeChartColors();
        const span = chartRows.length > 1
            ? new Date(chartRows[chartRows.length - 1].ts).getTime() - new Date(chartRows[0].ts).getTime()
            : 0;
        const labels = chartRows.map((row) => {
            const when = new Date(row.ts);
            return span > 36 * 60 * 60 * 1000
                ? when.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
                : when.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        });
        return {
            labels,
            datasets: [
                {
                    label: 'Temp °C',
                    data: chartRows.map((r) => r.temperature_c),
                    borderColor: colors.accent,
                    backgroundColor: 'transparent',
                    tension: 0.25,
                    yAxisID: 'y',
                    fill: false,
                    pointRadius: chartRows.length > 120 ? 0 : 2,
                },
                {
                    label: 'Humidity %',
                    data: chartRows.map((r) => r.humidity_pct),
                    borderColor: colors.secondary,
                    backgroundColor: 'transparent',
                    tension: 0.25,
                    yAxisID: 'y1',
                },
            ],
        };
    }, [chartRows]);
    async function saveSettings(event) {
        event.preventDefault();
        if (!settings)
            return;
        setSaving(true);
        setFormError(null);
        try {
            const saved = await api.updateClimateSettings({
                humidity_min: Number(settings.humidity_min),
                humidity_max: Number(settings.humidity_max),
                temp_min: Number(settings.temp_min),
                temp_max: Number(settings.temp_max),
                sample_interval_seconds: Number(settings.sample_interval_seconds),
            });
            setSettings(saved);
        }
        catch (e) {
            setFormError(e instanceof Error ? e.message : String(e));
        }
        finally {
            setSaving(false);
        }
    }
    async function refreshOutside() {
        setFormError(null);
        try {
            setOutside(await api.refreshClimateOutside());
        }
        catch (e) {
            setFormError(e instanceof Error ? e.message : String(e));
        }
    }
    const m = current?.measurement;
    const reading = outside?.reading;
    const ventilation = outside?.comparison?.ventilation;
    const reports = outside?.provider_reports ?? [];
    return (_jsxs("section", { className: "panel", children: [_jsx("h2", { children: "Climate" }), _jsxs("p", { className: "lede", children: ["Studio Climate under ", _jsx("code", { children: "/climate" }), ". Full JSON also at", ' ', _jsx("a", { href: `${getApiBase()}/climate/current`, target: "_blank", rel: "noreferrer", children: "/climate/current" }), "."] }), _jsx("div", { className: "panel-actions", children: _jsx("button", { type: "button", className: "primary", onClick: () => void load(), children: "Refresh" }) }), loading && _jsx("p", { className: "muted", children: "Loading\u2026" }), error && _jsx("div", { className: "error-box", children: error }), current && !loading && (_jsxs(_Fragment, { children: [_jsxs("div", { className: "subnav", role: "tablist", "aria-label": "Climate sections", children: [_jsx("button", { type: "button", className: section === 'now' ? 'active' : undefined, onClick: () => setSection('now'), children: "Now" }), _jsx("button", { type: "button", className: section === 'history' ? 'active' : undefined, onClick: () => setSection('history'), children: "History" }), _jsx("button", { type: "button", className: section === 'outside' ? 'active' : undefined, onClick: () => setSection('outside'), children: "Outside" }), _jsx("button", { type: "button", className: section === 'settings' ? 'active' : undefined, onClick: () => setSection('settings'), children: "Settings" })] }), section === 'now' && (_jsxs(_Fragment, { children: [_jsxs("div", { className: "grid-2", children: [_jsxs("div", { className: "stat", children: [_jsx("div", { className: "label", children: "Indoor temp" }), _jsx("div", { className: "value", children: m ? `${m.temperature_c.toFixed(1)}°C` : '—' })] }), _jsxs("div", { className: "stat", children: [_jsx("div", { className: "label", children: "Indoor humidity" }), _jsx("div", { className: "value", children: m ? `${m.humidity_pct.toFixed(1)}%` : '—' })] }), _jsxs("div", { className: "stat", children: [_jsx("div", { className: "label", children: "Band status" }), _jsx("div", { className: "value", style: { fontSize: '1.05rem' }, children: current.status?.overall ?? '—' })] })] }), _jsxs("div", { className: "section-card", style: { marginTop: '0.85rem' }, children: [_jsx("h3", { children: "Humidity" }), _jsx("p", { style: { margin: 0 }, children: ventilation?.reason || 'No ventilation advice yet.' })] }), current.open_incident && (_jsxs("div", { className: "section-card", children: [_jsx("h3", { children: "Open incident" }), _jsxs("p", { style: { margin: 0 }, children: ["#", current.open_incident.id, " \u00B7 ", current.open_incident.metric, ' ', current.open_incident.direction] })] }))] })), section === 'history' && (_jsxs(_Fragment, { children: [_jsx("div", { className: "subnav", role: "group", "aria-label": "History range", children: HISTORY_RANGES.map((item) => (_jsx("button", { type: "button", className: historyRange === item.id ? 'active' : undefined, onClick: () => setHistoryRange(item.id), children: item.label }, item.id))) }), _jsx("div", { className: "chart-wrap", children: historyLoading && chartRows.length === 0 ? (_jsx("p", { className: "muted", children: "Loading\u2026" })) : chartRows.length > 0 ? (_jsx(Line, { data: chartData, options: climateChartOptions() })) : (_jsx("div", { className: "list-empty", children: "No indoor measurements in this range." })) })] })), section === 'outside' && (_jsxs(_Fragment, { children: [_jsx("div", { className: "grid-2", children: _jsxs("div", { className: "stat", children: [_jsx("div", { className: "label", children: "Outside" }), _jsx("div", { className: "value", style: { fontSize: '1.05rem' }, children: reading
                                                ? `${reading.temperature_c?.toFixed?.(1) ?? '—'}°C · ${reading.condition ?? '—'}`
                                                : '—' })] }) }), _jsxs("div", { className: "section-card", style: { marginTop: '0.85rem' }, children: [_jsxs("div", { className: "card-head", children: [_jsx("h3", { children: "Outside providers" }), _jsx("button", { type: "button", onClick: () => void refreshOutside(), children: "Refresh outside" })] }), reports.length === 0 && (_jsx("p", { className: "muted", style: { margin: 0 }, children: "No provider readings stored yet. The sampler polls Open-Meteo, OpenWeatherMap, and Bright Sky on its own; Refresh outside asks them now." })), _jsx("div", { className: "grid-2", children: reports.map((report) => (_jsxs("div", { children: [_jsx("strong", { children: report.name }), _jsx("div", { className: "muted", children: report.ok
                                                        ? `${report.temperature_c ?? '—'}°C · ${report.humidity_pct ?? '—'}% · ${report.condition ?? '—'}`
                                                        : report.error || 'unavailable' })] }, report.name))) })] }), formError && _jsx("div", { className: "error-box", children: formError })] })), section === 'settings' && settings && (_jsxs("form", { className: "topic-form", onSubmit: (event) => void saveSettings(event), children: [_jsx("h3", { children: "Bands and sample interval" }), _jsxs("div", { className: "time-row", children: [_jsxs("label", { children: ["Humidity min %", _jsx("input", { type: "number", step: "0.1", value: settings.humidity_min, onChange: (event) => setSettings({ ...settings, humidity_min: Number(event.target.value) }) })] }), _jsxs("label", { children: ["Humidity max %", _jsx("input", { type: "number", step: "0.1", value: settings.humidity_max, onChange: (event) => setSettings({ ...settings, humidity_max: Number(event.target.value) }) })] })] }), _jsxs("div", { className: "time-row", children: [_jsxs("label", { children: ["Temp min \u00B0C", _jsx("input", { type: "number", step: "0.1", value: settings.temp_min, onChange: (event) => setSettings({ ...settings, temp_min: Number(event.target.value) }) })] }), _jsxs("label", { children: ["Temp max \u00B0C", _jsx("input", { type: "number", step: "0.1", value: settings.temp_max, onChange: (event) => setSettings({ ...settings, temp_max: Number(event.target.value) }) })] })] }), _jsxs("label", { children: ["Sample every (seconds)", _jsx("input", { type: "number", min: 2, value: settings.sample_interval_seconds, onChange: (event) => setSettings({
                                            ...settings,
                                            sample_interval_seconds: Number(event.target.value),
                                        }) }), _jsx("span", { className: "hint", children: "Indoor temperature and humidity are recorded around the clock." })] }), formError && _jsx("div", { className: "error-box", children: formError }), _jsx("div", { className: "panel-actions", children: _jsx("button", { type: "submit", className: "primary", disabled: saving, children: saving ? 'Saving…' : 'Save bands' }) })] }))] }))] }));
}
