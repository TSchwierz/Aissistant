import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
function emptyDraft() {
    return {
        id: '',
        label: '',
        goal: '',
        feeds: '',
        schedule_enabled: true,
        schedule_hour: '5',
        schedule_minute: '30',
        schedule_days: [0, 1, 2, 3, 4, 5, 6],
    };
}
function draftFromTopic(topic) {
    return {
        id: topic.id,
        label: topic.label,
        goal: topic.goal,
        feeds: topic.feed_urls.join('\n'),
        schedule_enabled: topic.schedule_enabled,
        schedule_hour: String(topic.schedule_hour),
        schedule_minute: String(topic.schedule_minute),
        schedule_days: [...topic.schedule_days],
    };
}
function pad2(value) {
    return String(value).padStart(2, '0');
}
function formatSchedule(topic) {
    if (!topic.schedule_enabled)
        return 'Schedule off';
    const days = topic.schedule_days.length === 7
        ? 'every day'
        : topic.schedule_days.map((day) => DAY_LABELS[day] ?? String(day)).join(', ');
    return `${pad2(topic.schedule_hour)}:${pad2(topic.schedule_minute)} · ${days}`;
}
function parseFeeds(text) {
    const seen = new Set();
    const out = [];
    for (const raw of text.split(/\r?\n/)) {
        const url = raw.trim();
        if (!url || seen.has(url))
            continue;
        seen.add(url);
        out.push(url);
    }
    return out;
}
function toWrite(draft) {
    const hour = Number(draft.schedule_hour);
    const minute = Number(draft.schedule_minute);
    if (draft.schedule_hour.trim() === '' || !Number.isInteger(hour) || hour < 0 || hour > 23) {
        throw new Error('Hour must be 0–23');
    }
    if (draft.schedule_minute.trim() === '' || !Number.isInteger(minute) || minute < 0 || minute > 59) {
        throw new Error('Minute must be 0–59');
    }
    if (draft.schedule_days.length === 0) {
        throw new Error('Pick at least one day');
    }
    return {
        label: draft.label.trim(),
        goal: draft.goal.trim(),
        feed_urls: parseFeeds(draft.feeds),
        schedule_enabled: draft.schedule_enabled,
        schedule_hour: hour,
        schedule_minute: minute,
        schedule_days: [...draft.schedule_days].sort((a, b) => a - b),
    };
}
export function NewsPanel() {
    const [topics, setTopics] = useState([]);
    const [digests, setDigests] = useState([]);
    const [providers, setProviders] = useState([]);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(true);
    const [editor, setEditor] = useState(null);
    const [draft, setDraft] = useState(emptyDraft);
    const [formError, setFormError] = useState(null);
    const [saving, setSaving] = useState(false);
    const [section, setSection] = useState('topics');
    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [status, t] = await Promise.all([api.newsStatus(), api.newsTopics()]);
            setProviders(status.providers_configured);
            setTopics(t);
            try {
                setDigests(await api.newsLatest());
            }
            catch (e) {
                setDigests([]);
                setError(e instanceof Error ? e.message : String(e));
            }
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
    function openCreate() {
        setEditor('create');
        setDraft(emptyDraft());
        setFormError(null);
    }
    function openEdit(topic) {
        setEditor('edit');
        setDraft(draftFromTopic(topic));
        setFormError(null);
    }
    function closeEditor() {
        setEditor(null);
        setFormError(null);
    }
    function toggleDay(day) {
        setDraft((current) => {
            const has = current.schedule_days.includes(day);
            const schedule_days = has
                ? current.schedule_days.filter((value) => value !== day)
                : [...current.schedule_days, day].sort((a, b) => a - b);
            return { ...current, schedule_days };
        });
    }
    async function saveTopic() {
        setSaving(true);
        setFormError(null);
        try {
            const body = toWrite(draft);
            if (editor === 'create') {
                const id = draft.id.trim().toLowerCase();
                if (!id)
                    throw new Error('Id is required');
                await api.createNewsTopic({ id, ...body });
            }
            else if (editor === 'edit') {
                await api.updateNewsTopic(draft.id, body);
            }
            closeEditor();
            await load();
        }
        catch (e) {
            setFormError(e instanceof Error ? e.message : String(e));
        }
        finally {
            setSaving(false);
        }
    }
    return (_jsxs("section", { className: "panel", children: [_jsx("h2", { children: "News" }), _jsxs("p", { className: "lede", children: ["Topic digests from the Pi. AI keys stay on the server (", providers.length ? providers.join(' → ') : 'none configured — summarize skipped', ")."] }), _jsxs("div", { className: "panel-actions", children: [_jsx("button", { type: "button", className: "primary", onClick: openCreate, children: "New topic" }), _jsx("button", { type: "button", onClick: () => void load(), children: "Refresh" })] }), editor && (_jsxs("form", { className: "topic-form", onSubmit: (event) => {
                    event.preventDefault();
                    void saveTopic();
                }, children: [_jsx("h3", { children: editor === 'create' ? 'New topic' : `Edit ${draft.id}` }), _jsxs("label", { children: ["Id", _jsx("input", { value: draft.id, disabled: editor === 'edit', required: true, autoComplete: "off", spellCheck: false, placeholder: "politics", onChange: (event) => setDraft({ ...draft, id: event.target.value }) }), _jsx("span", { className: "hint", children: "Lowercase slug. Cannot be changed later." })] }), _jsxs("label", { children: ["Label", _jsx("input", { value: draft.label, required: true, maxLength: 120, onChange: (event) => setDraft({ ...draft, label: event.target.value }) })] }), _jsxs("label", { children: ["Goal", _jsx("textarea", { value: draft.goal, maxLength: 2000, rows: 3, placeholder: "Short English digest of what changed.", onChange: (event) => setDraft({ ...draft, goal: event.target.value }) })] }), _jsxs("label", { children: ["Feed URLs", _jsx("textarea", { value: draft.feeds, rows: 4, spellCheck: false, placeholder: 'https://example.com/rss\nmock://politics', onChange: (event) => setDraft({ ...draft, feeds: event.target.value }) }), _jsx("span", { className: "hint", children: "One URL per line. http(s) or mock://" })] }), _jsxs("label", { className: "check", children: [_jsx("input", { type: "checkbox", checked: draft.schedule_enabled, onChange: (event) => setDraft({ ...draft, schedule_enabled: event.target.checked }) }), "Run on a schedule"] }), _jsxs("div", { className: "time-row", children: [_jsxs("label", { children: ["Hour", _jsx("input", { type: "number", min: 0, max: 23, value: draft.schedule_hour, onChange: (event) => setDraft({ ...draft, schedule_hour: event.target.value }) })] }), _jsxs("label", { children: ["Minute", _jsx("input", { type: "number", min: 0, max: 59, value: draft.schedule_minute, onChange: (event) => setDraft({ ...draft, schedule_minute: event.target.value }) })] })] }), _jsxs("fieldset", { children: [_jsx("legend", { children: "Days" }), _jsx("div", { className: "tags", children: DAY_LABELS.map((label, day) => (_jsx("button", { type: "button", className: `chip ${draft.schedule_days.includes(day) ? 'active' : ''}`, onClick: () => toggleDay(day), children: label }, label))) })] }), formError && _jsx("div", { className: "error-box", children: formError }), _jsxs("div", { className: "panel-actions", children: [_jsx("button", { type: "submit", className: "primary", disabled: saving, children: saving ? 'Saving…' : editor === 'create' ? 'Create topic' : 'Save changes' }), _jsx("button", { type: "button", onClick: closeEditor, disabled: saving, children: "Cancel" })] })] })), loading && _jsx("p", { className: "muted", children: "Loading\u2026" }), error && _jsx("div", { className: "error-box", children: error }), !loading && (_jsxs(_Fragment, { children: [_jsxs("div", { className: "subnav", role: "tablist", "aria-label": "News sections", children: [_jsxs("button", { type: "button", className: section === 'topics' ? 'active' : undefined, onClick: () => setSection('topics'), children: ["Topics (", topics.length, ")"] }), _jsxs("button", { type: "button", className: section === 'digests' ? 'active' : undefined, onClick: () => setSection('digests'), children: ["Latest digests (", digests.length, ")"] })] }), section === 'topics' && (_jsxs(_Fragment, { children: [_jsxs("h3", { className: "muted", style: { fontSize: '0.85rem' }, children: ["Topics (", topics.length, ")"] }), topics.length === 0 && _jsx("div", { className: "list-empty", children: "No topics yet." }), topics.map((topic) => (_jsxs("div", { className: "section-card", children: [_jsxs("div", { className: "card-head", children: [_jsxs("h3", { children: [topic.label, " ", _jsxs("span", { className: "muted", children: ["(", topic.id, ")"] })] }), _jsx("button", { type: "button", onClick: () => openEdit(topic), children: "Edit" })] }), topic.goal && _jsx("p", { style: { margin: '0 0 0.35rem' }, children: topic.goal }), _jsxs("p", { className: "muted", style: { margin: 0 }, children: [formatSchedule(topic), topic.feed_urls.length
                                                ? ` · ${topic.feed_urls.length} feed${topic.feed_urls.length === 1 ? '' : 's'}`
                                                : ' · no feeds'] }), _jsxs("p", { className: "muted", style: { margin: '0.25rem 0 0' }, children: ["Last run: ", topic.last_run_status ?? '—', topic.last_run_at ? ` · ${topic.last_run_at}` : '', topic.last_error ? ` · ${topic.last_error}` : ''] })] }, topic.id)))] })), section === 'digests' && (_jsxs(_Fragment, { children: [_jsx("h3", { className: "muted", style: { fontSize: '0.85rem', marginTop: '1rem' }, children: "Latest digests" }), digests.length === 0 && _jsx("div", { className: "list-empty", children: "No digests for today yet." }), digests.map((digest) => (_jsxs("div", { className: "digest-card", children: [_jsxs("h3", { children: [digest.topic_label, ' ', _jsxs("span", { className: "muted", children: ["\u00B7 ", digest.status, digest.ai_provider ? ` · ${digest.ai_provider}` : ''] })] }), _jsx("p", { style: { margin: 0 }, children: digest.digest }), _jsxs("p", { className: "muted", style: { margin: '0.5rem 0 0', fontSize: '0.8rem' }, children: [digest.item_count, " items \u00B7 ", digest.generated_at] })] }, digest.id)))] }))] }))] }));
}
