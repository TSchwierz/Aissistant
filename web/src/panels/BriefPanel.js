import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
export function BriefPanel() {
    const [brief, setBrief] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(true);
    const load = useCallback(async (refresh = false) => {
        setLoading(true);
        setError(null);
        try {
            setBrief(await api.morningBrief(refresh));
        }
        catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        }
        finally {
            setLoading(false);
        }
    }, []);
    useEffect(() => {
        void load(false);
    }, [load]);
    return (_jsxs("section", { className: "panel", children: [_jsx("h2", { children: "Morning brief" }), _jsx("p", { className: "lede", children: "Pi-composed English script and sections. TTS stays on the phone." }), _jsx("div", { className: "panel-actions", children: _jsx("button", { type: "button", className: "primary", onClick: () => void load(true), children: "Refresh" }) }), loading && _jsx("p", { className: "muted", children: "Loading\u2026" }), error && _jsx("div", { className: "error-box", children: error }), brief && !loading && (_jsxs(_Fragment, { children: [_jsxs("div", { className: "grid-2", style: { marginBottom: '0.85rem' }, children: [_jsxs("div", { className: "stat", children: [_jsx("div", { className: "label", children: "Date" }), _jsx("div", { className: "value", style: { fontSize: '1.05rem' }, children: brief.meta.date })] }), _jsxs("div", { className: "stat", children: [_jsx("div", { className: "label", children: "Sections" }), _jsx("div", { className: "value", style: { fontSize: '1.05rem' }, children: brief.meta.sections_present.join(', ') || '—' })] })] }), brief.meta.empty_reason && (_jsxs("p", { className: "muted", children: ["Empty reason: ", brief.meta.empty_reason] })), _jsx("h3", { className: "muted", style: { fontSize: '0.85rem', marginBottom: '0.35rem' }, children: "Script" }), _jsx("div", { className: "script-box", children: brief.script || '—' }), brief.sections.map((s) => (_jsxs("div", { className: "section-card", children: [_jsx("h3", { children: s.title }), _jsx("p", { style: { margin: 0 }, children: s.body })] }, s.id)))] }))] }));
}
