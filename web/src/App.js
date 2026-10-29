import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useCallback, useEffect, useState } from 'react';
import { api, getApiBase } from './api';
import { BriefPanel } from './panels/BriefPanel';
import { CalendarPanel } from './panels/CalendarPanel';
import { ClimatePanel } from './panels/ClimatePanel';
import { HealthPanel } from './panels/HealthPanel';
import { NewsPanel } from './panels/NewsPanel';
import { SettingsPanel } from './panels/SettingsPanel';
import { applyTheme } from './theme';
import './App.css';
applyTheme();
const TABS = [
    { id: 'brief', label: 'Morning brief' },
    { id: 'calendar', label: 'Calendar' },
    { id: 'climate', label: 'Climate' },
    { id: 'health', label: 'Health' },
    { id: 'news', label: 'News' },
    { id: 'settings', label: 'Settings' },
];
export default function App() {
    const [tab, setTab] = useState('brief');
    const [conn, setConn] = useState('unknown');
    const [connDetail, setConnDetail] = useState('');
    const [reloadKey, setReloadKey] = useState(0);
    const [navOpen, setNavOpen] = useState(false);
    const probe = useCallback(async () => {
        try {
            const health = await api.healthLiveness();
            setConn('ok');
            setConnDetail(`${health.service ?? 'ok'} · ${getApiBase()}`);
        }
        catch (e) {
            setConn('err');
            setConnDetail(e instanceof Error ? e.message : String(e));
        }
    }, []);
    useEffect(() => {
        void probe();
    }, [probe, reloadKey]);
    useEffect(() => {
        applyTheme();
    }, []);
    useEffect(() => {
        if (!navOpen)
            return;
        function onKey(event) {
            if (event.key === 'Escape')
                setNavOpen(false);
        }
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [navOpen]);
    function selectTab(id) {
        setTab(id);
        setNavOpen(false);
    }
    return (_jsxs("div", { className: "app-frame", children: [_jsxs("aside", { id: "app-sidebar", className: navOpen ? 'sidebar open' : 'sidebar', children: [_jsxs("div", { className: "brand", children: [_jsx("h1", { children: "Personal AIssistent" }), _jsx("p", { children: "LAN web UI for the Pi SSOT." })] }), _jsx("nav", { className: "sidebar-nav", "aria-label": "Sections", children: TABS.map((item) => (_jsx("button", { type: "button", className: tab === item.id ? 'active' : undefined, "aria-current": tab === item.id ? 'page' : undefined, onClick: () => selectTab(item.id), children: item.label }, item.id))) }), _jsxs("div", { className: "sidebar-status", children: [_jsx("span", { className: `status-pill ${conn === 'ok' ? 'ok' : conn === 'err' ? 'err' : ''}`, title: connDetail || undefined, children: conn === 'unknown' ? '…' : conn === 'ok' ? 'connected' : 'offline' }), connDetail ? _jsx("p", { className: "sidebar-detail", children: connDetail }) : null] })] }), navOpen ? (_jsx("button", { type: "button", className: "sidebar-backdrop", "aria-label": "Close menu", onClick: () => setNavOpen(false) })) : null, _jsxs("div", { className: "app-main", children: [_jsx("button", { type: "button", className: "menu-toggle", "aria-expanded": navOpen, "aria-controls": "app-sidebar", onClick: () => setNavOpen((open) => !open), children: "Menu" }), _jsxs("main", { children: [tab === 'brief' && _jsx(BriefPanel, {}), tab === 'calendar' && _jsx(CalendarPanel, {}), tab === 'climate' && _jsx(ClimatePanel, {}), tab === 'health' && _jsx(HealthPanel, {}), tab === 'news' && _jsx(NewsPanel, {}), tab === 'settings' && (_jsx(SettingsPanel, { onReload: () => setReloadKey((key) => key + 1) }))] }, `${tab}-${reloadKey}`)] })] }));
}
