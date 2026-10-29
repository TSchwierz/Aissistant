import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../api';
import { errorMessage, formatWhen } from './shared';
function Amount({ pct, kg }) {
    if (pct == null && kg == null)
        return _jsx("span", { children: "\u2014" });
    return (_jsxs("span", { className: "health-pair", children: [_jsx("span", { children: pct == null ? '—' : `${pct.toFixed(1)}%` }), _jsx("span", { className: "muted", children: kg == null ? '—' : `${kg.toFixed(1)} kg` })] }));
}
export function MeasurementsTab() {
    const [rows, setRows] = useState([]);
    const [drafts, setDrafts] = useState({});
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(true);
    const [busyId, setBusyId] = useState(null);
    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            setRows(await api.healthMeasurements());
            setDrafts({});
        }
        catch (e) {
            setError(errorMessage(e));
        }
        finally {
            setLoading(false);
        }
    }, []);
    useEffect(() => {
        void load();
    }, [load]);
    const sorted = useMemo(() => [...rows].sort((a, b) => new Date(b.measured_at).getTime() - new Date(a.measured_at).getTime()), [rows]);
    function clearDraft(id) {
        setDrafts((prev) => {
            if (!(id in prev))
                return prev;
            const next = { ...prev };
            delete next[id];
            return next;
        });
    }
    async function saveWeight(row) {
        const text = (drafts[row.id] ?? String(row.weight_kg)).trim();
        const weight = Number(text);
        if (!text || !Number.isFinite(weight) || weight <= 0) {
            setError('Enter a weight in kg');
            return;
        }
        setBusyId(row.id);
        setError(null);
        try {
            await api.updateMeasurement(row.id, { weight_kg: weight });
            clearDraft(row.id);
            await load();
        }
        catch (e) {
            setError(errorMessage(e));
        }
        finally {
            setBusyId(null);
        }
    }
    async function remove(id) {
        setBusyId(id);
        setError(null);
        try {
            await api.deleteMeasurement(id);
            clearDraft(id);
            await load();
        }
        catch (e) {
            setError(errorMessage(e));
        }
        finally {
            setBusyId(null);
        }
    }
    return (_jsxs(_Fragment, { children: [_jsx("div", { className: "panel-actions", children: _jsx("button", { type: "button", className: "primary", onClick: () => void load(), children: "Refresh" }) }), loading && _jsx("p", { className: "muted", children: "Loading\u2026" }), error && _jsx("div", { className: "error-box", children: error }), !loading && sorted.length === 0 && !error && (_jsx("div", { className: "list-empty", children: "No measurements yet." })), sorted.length > 0 && (_jsxs("div", { className: "health-scroll", children: [_jsxs("div", { className: "health-head", children: [_jsx("span", { children: "Time" }), _jsx("span", { children: "Weight" }), _jsx("span", { children: "Body fat" }), _jsx("span", { children: "Muscle" }), _jsx("span", { children: "Water" }), _jsx("span", {})] }), sorted.map((row) => (_jsxs("div", { className: "health-row", children: [_jsx("span", { children: formatWhen(row.measured_at) }), _jsxs("div", { className: "health-weight", children: [_jsx("input", { type: "number", min: 0, step: "0.1", "aria-label": `Weight on ${formatWhen(row.measured_at)}`, value: drafts[row.id] ?? String(row.weight_kg), disabled: busyId === row.id, onChange: (event) => setDrafts((prev) => ({ ...prev, [row.id]: event.target.value })), onKeyDown: (event) => {
                                            if (event.key === 'Enter')
                                                void saveWeight(row);
                                        } }), _jsx("span", { className: "muted", children: "kg" })] }), _jsx(Amount, { pct: row.body_fat_pct, kg: row.body_fat_kg }), _jsx(Amount, { pct: row.muscle_pct, kg: row.muscle_mass_kg }), _jsx(Amount, { pct: row.water_pct, kg: row.water_kg }), _jsxs("div", { className: "health-row-actions", children: [_jsx("button", { type: "button", className: "health-btn", disabled: busyId === row.id, onClick: () => void saveWeight(row), children: "Save" }), _jsx("button", { type: "button", className: "health-btn", disabled: busyId === row.id, onClick: () => void remove(row.id), children: "Delete" })] })] }, row.id)))] }))] }));
}
