import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api';
import { errorMessage, pair } from './shared';
import { TargetsBlock } from './TargetsBlock';
export function DashboardTab() {
    const [stats, setStats] = useState(null);
    const [profile, setProfile] = useState(null);
    const [scale, setScale] = useState(null);
    const [mode, setMode] = useState('auto');
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState(false);
    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [s, p, scan] = await Promise.all([
                api.healthStats(),
                api.healthProfile(),
                api.scaleStatus().catch(() => null),
            ]);
            setStats(s);
            setProfile(p);
            setMode(scan?.mode || 'auto');
            setScale(scan
                ? `${scan.mode || 'auto'} · ${scan.window} · ${scan.phase}${scan.detail ? ` — ${scan.detail}` : ''}`
                : null);
        }
        catch (e) {
            setError(errorMessage(e));
        }
        finally {
            setLoading(false);
        }
    }, []);
    const refreshScale = useCallback(async () => {
        const scan = await api.scaleStatus().catch(() => null);
        if (!scan)
            return;
        setMode(scan.mode || 'auto');
        setScale(`${scan.mode || 'auto'} · ${scan.window} · ${scan.phase}${scan.detail ? ` — ${scan.detail}` : ''}`);
    }, []);
    useEffect(() => {
        void load();
    }, [load]);
    useEffect(() => {
        const timer = window.setInterval(() => {
            void refreshScale();
        }, 3000);
        return () => window.clearInterval(timer);
    }, [refreshScale]);
    useEffect(() => {
        if (!scale || !/Stored|recorded/i.test(scale))
            return;
        let cancelled = false;
        void api.healthStats().then((next) => {
            if (!cancelled)
                setStats(next);
        }).catch(() => undefined);
        return () => {
            cancelled = true;
        };
    }, [scale]);
    async function setScan(action) {
        setBusy(true);
        setError(null);
        try {
            const scan = await api.setScaleMode(action);
            setMode(scan.mode || action);
            await load();
        }
        catch (e) {
            setError(errorMessage(e));
        }
        finally {
            setBusy(false);
        }
    }
    const latest = stats?.latest;
    const nutrition = stats?.nutrition ?? profile?.nutrition;
    const meals = profile?.meals_per_day || nutrition?.meals_per_day || 3;
    return (_jsxs(_Fragment, { children: [_jsx("p", { className: "lede", children: "The Pi records the scale over Bluetooth from 06:00 to 12:00, then stops once today's measurement is stored. Height, age, and sex stay on the health dashboard." }), _jsxs("div", { className: "panel-actions", children: [_jsx("button", { type: "button", className: "primary", onClick: () => void load(), children: "Refresh" }), _jsx("button", { type: "button", disabled: busy || mode === 'on', onClick: () => void setScan('start'), children: "Start scan" }), _jsx("button", { type: "button", disabled: busy || mode === 'off', onClick: () => void setScan('stop'), children: "Stop scan" }), _jsx("button", { type: "button", disabled: busy || mode === 'auto', onClick: () => void setScan('auto'), children: "Use schedule" })] }), loading && _jsx("p", { className: "muted", children: "Loading\u2026" }), error && _jsx("div", { className: "error-box", children: error }), stats && profile && !loading && (_jsxs("div", { className: "grid-2", children: [_jsxs("div", { className: "stat", children: [_jsx("div", { className: "label", children: "Latest weight" }), _jsx("div", { className: "value", children: stats.latest ? `${stats.latest.weight_kg.toFixed(1)} kg` : '—' })] }), _jsxs("div", { className: "stat", children: [_jsx("div", { className: "label", children: "7d average" }), _jsx("div", { className: "value", children: stats.avg_weight_7d != null ? `${stats.avg_weight_7d.toFixed(1)} kg` : '—' })] }), _jsxs("div", { className: "stat", children: [_jsx("div", { className: "label", children: "Measurements" }), _jsx("div", { className: "value", children: stats.count })] }), scale && (_jsxs("div", { className: "stat", children: [_jsx("div", { className: "label", children: "Scale listener" }), _jsx("div", { className: "value", style: { fontSize: '1.05rem' }, children: scale })] })), _jsxs("div", { className: "stat", children: [_jsx("div", { className: "label", children: "Profile" }), _jsxs("div", { className: "value", style: { fontSize: '1.05rem' }, children: [profile.name || '—', " \u00B7 ", profile.is_complete ? 'complete' : 'incomplete'] })] }), latest?.bmi != null && (_jsxs("div", { className: "stat", children: [_jsx("div", { className: "label", children: "BMI" }), _jsx("div", { className: "value", children: latest.bmi.toFixed(1) })] })), latest && (latest.body_fat_pct != null || latest.body_fat_kg != null) && (_jsxs("div", { className: "stat", children: [_jsx("div", { className: "label", children: "Body fat" }), _jsx("div", { className: "value", style: { fontSize: '1.05rem' }, children: pair(latest.body_fat_pct, latest.body_fat_kg) })] })), latest && (latest.muscle_pct != null || latest.muscle_mass_kg != null) && (_jsxs("div", { className: "stat", children: [_jsx("div", { className: "label", children: "Muscle" }), _jsx("div", { className: "value", style: { fontSize: '1.05rem' }, children: pair(latest.muscle_pct, latest.muscle_mass_kg) })] })), latest && (latest.water_pct != null || latest.water_kg != null) && (_jsxs("div", { className: "stat", children: [_jsx("div", { className: "label", children: "Water" }), _jsx("div", { className: "value", style: { fontSize: '1.05rem' }, children: pair(latest.water_pct, latest.water_kg) })] })), latest && (latest.bone_pct != null || latest.bone_mass_kg != null) && (_jsxs("div", { className: "stat", children: [_jsx("div", { className: "label", children: "Bone" }), _jsx("div", { className: "value", style: { fontSize: '1.05rem' }, children: pair(latest.bone_pct, latest.bone_mass_kg) })] })), nutrition && (_jsx("div", { className: "stat", style: { gridColumn: '1 / -1' }, children: _jsx(TargetsBlock, { nutrition: nutrition, meals: meals, currentFatPct: latest?.body_fat_pct }) }))] }))] }));
}
