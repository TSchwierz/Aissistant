import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { api, getApiBase, setApiBase } from '../api';
import { applyTheme, readThemeAccent, readThemeMode, writeThemeAccent, writeThemeMode, } from '../theme';
const MODES = [
    { id: 'system', label: 'System' },
    { id: 'dark', label: 'Dark' },
    { id: 'light', label: 'Light' },
];
const ACCENTS = [
    { id: 'teal', label: 'Teal' },
    { id: 'blue', label: 'Blue' },
    { id: 'amber', label: 'Amber' },
    { id: 'rose', label: 'Rose' },
];
export function SettingsPanel({ onReload }) {
    const [baseDraft, setBaseDraft] = useState(getApiBase);
    const [testBusy, setTestBusy] = useState(false);
    const [testMsg, setTestMsg] = useState('');
    const [testOk, setTestOk] = useState(false);
    const [backupBusy, setBackupBusy] = useState(false);
    const [backupMsg, setBackupMsg] = useState('');
    const [backupIsError, setBackupIsError] = useState(false);
    const [mode, setMode] = useState(readThemeMode);
    const [accent, setAccent] = useState(readThemeAccent);
    function saveUrl() {
        setApiBase(baseDraft);
        setBaseDraft(getApiBase());
        onReload();
    }
    async function testConnection() {
        setTestBusy(true);
        setTestMsg('');
        try {
            const health = await api.healthLiveness();
            setTestOk(true);
            setTestMsg(`ok · ${health.service ?? 'ok'} · ${getApiBase()}`);
        }
        catch (e) {
            setTestOk(false);
            setTestMsg(`error · ${e instanceof Error ? e.message : String(e)}`);
        }
        finally {
            setTestBusy(false);
        }
    }
    async function downloadBackup() {
        setBackupBusy(true);
        setBackupMsg('');
        setBackupIsError(false);
        try {
            await api.downloadBackup();
            setBackupMsg('Backup zip downloaded. Restore is manual — see Pi README.');
        }
        catch (e) {
            setBackupIsError(true);
            setBackupMsg(e instanceof Error ? e.message : String(e));
        }
        finally {
            setBackupBusy(false);
        }
    }
    function selectMode(next) {
        setMode(next);
        writeThemeMode(next);
        applyTheme(next, accent);
    }
    function selectAccent(next) {
        setAccent(next);
        writeThemeAccent(next);
        applyTheme(mode, next);
    }
    return (_jsxs("section", { className: "panel", children: [_jsx("h2", { children: "Settings" }), _jsx("p", { className: "lede", children: "Pi API address and appearance for this browser. Theme is not stored on the Pi." }), _jsx("h3", { className: "settings-heading", children: "Connection" }), _jsxs("form", { className: "settings-bar", onSubmit: (event) => {
                    event.preventDefault();
                    saveUrl();
                }, children: [_jsx("input", { "aria-label": "Pi API base URL", value: baseDraft, onChange: (event) => setBaseDraft(event.target.value), placeholder: "http://192.168.178.23:8741", inputMode: "url", spellCheck: false }), _jsx("button", { type: "submit", className: "primary", children: "Save URL" }), _jsx("button", { type: "button", disabled: testBusy, onClick: () => void testConnection(), children: testBusy ? 'Testing…' : 'Test' }), _jsx("button", { type: "button", disabled: backupBusy, onClick: () => void downloadBackup(), title: "Download SSOT databases as a zip (restore is manual)", children: backupBusy ? 'Backing up…' : 'Download backup' })] }), _jsxs("div", { className: "settings-msgs", "aria-live": "polite", children: [testMsg ? _jsx("p", { className: testOk ? 'settings-note ok' : 'error-box', children: testMsg }) : null, backupMsg ? (_jsx("p", { className: backupIsError ? 'error-box' : 'settings-note', children: backupMsg })) : null] }), _jsx("h3", { className: "settings-heading", children: "Appearance" }), _jsxs("div", { className: "settings-block", children: [_jsx("div", { className: "settings-label", id: "theme-mode-label", children: "Mode" }), _jsx("div", { className: "choice-row", role: "group", "aria-labelledby": "theme-mode-label", children: MODES.map((item) => (_jsx("button", { type: "button", className: mode === item.id ? 'primary' : undefined, "aria-pressed": mode === item.id, onClick: () => selectMode(item.id), children: item.label }, item.id))) })] }), _jsxs("div", { className: "settings-block", children: [_jsx("div", { className: "settings-label", id: "theme-accent-label", children: "Accent" }), _jsx("div", { className: "choice-row", role: "group", "aria-labelledby": "theme-accent-label", children: ACCENTS.map((item) => (_jsxs("button", { type: "button", className: accent === item.id ? 'primary' : undefined, "aria-pressed": accent === item.id, onClick: () => selectAccent(item.id), children: [_jsx("span", { className: `accent-dot accent-dot-${item.id}`, "aria-hidden": "true" }), item.label] }, item.id))) })] })] }));
}
