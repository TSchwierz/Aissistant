import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useCallback, useEffect, useMemo, useState } from 'react';
import { addDays, addHours, addMonths, eachDayOfInterval, endOfMonth, endOfWeek, format, parse, startOfMonth, startOfWeek, } from 'date-fns';
import { api } from '../api';
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const TAG_PALETTE = ['#5b8def', '#3d9b8f', '#d4a056', '#c46b6b', '#9b7ed4', '#6bcb8a', '#e07a5f', '#4ea8de'];
function hashColor(name) {
    let hash = 0;
    for (let i = 0; i < name.length; i += 1)
        hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
    return TAG_PALETTE[hash % TAG_PALETTE.length];
}
function colorFor(tag, colors) {
    const assigned = Object.entries(colors).find(([name]) => name.toLowerCase() === tag.toLowerCase());
    return assigned?.[1] || hashColor(tag);
}
function defaultTimedEnd(start) {
    if (start.length < 16)
        return '';
    const parsed = parse(start.slice(0, 16), "yyyy-MM-dd'T'HH:mm", new Date());
    if (Number.isNaN(parsed.getTime()))
        return '';
    return format(addHours(parsed, 1), "yyyy-MM-dd'T'HH:mm");
}
function eventDayKey(ev) {
    return ev.start.slice(0, 10);
}
function toLocalInput(iso) {
    if (!iso)
        return '';
    const noZone = iso.replace(/Z$/, '').replace(/[+-]\d{2}:\d{2}$/, '');
    return noZone.slice(0, 16);
}
function emptyDraft() {
    const start = new Date();
    start.setMinutes(0, 0, 0);
    start.setHours(start.getHours() + 1);
    const startValue = format(start, "yyyy-MM-dd'T'HH:mm");
    return {
        id: '',
        title: '',
        allDay: false,
        start: startValue,
        end: defaultTimedEnd(startValue),
        location: '',
        notes: '',
        tags: '',
        repeat: '',
        repeatUntil: '',
        repeatWeekdays: [],
    };
}
function draftFromEvent(event) {
    const anchorStart = event.series_start || event.start;
    const anchorEnd = event.repeat ? event.series_end : event.end;
    return {
        id: event.series_id || event.id.split('~')[0],
        title: event.title,
        allDay: event.all_day,
        start: event.all_day ? anchorStart.slice(0, 10) : toLocalInput(anchorStart),
        end: event.all_day
            ? anchorEnd
                ? anchorEnd.slice(0, 10)
                : ''
            : toLocalInput(anchorEnd),
        location: event.location ?? '',
        notes: event.notes ?? '',
        tags: event.tags.join(', '),
        repeat: event.repeat === 'weekly' || event.repeat === 'biweekly' || event.repeat === 'monthly'
            ? event.repeat
            : '',
        repeatUntil: event.repeat_until ?? '',
        repeatWeekdays: event.repeat_weekdays ?? [],
    };
}
function repeatLabel(ev) {
    if (!ev.repeat)
        return '';
    const days = (ev.repeat_weekdays ?? []).map((day) => WEEKDAYS[day]).filter(Boolean);
    if (ev.repeat === 'monthly' && days.length)
        return `first ${days.join(' + ')} each month`;
    if (ev.repeat === 'monthly')
        return 'monthly';
    const freq = ev.repeat === 'biweekly' ? 'every 2 weeks' : 'weekly';
    return days.length > 1 ? `${freq} · ${days.join(' + ')}` : freq;
}
function eventClock(ev) {
    if (ev.all_day)
        return '';
    const match = /T(\d{2}:\d{2})/.exec(ev.start);
    return match ? match[1] : '';
}
function eventLabel(ev) {
    const clock = eventClock(ev);
    return clock ? `${clock} ${ev.title}` : ev.title;
}
function wallMinutes(iso) {
    const match = /T(\d{2}):(\d{2})/.exec(iso);
    if (!match)
        return 0;
    return Number(match[1]) * 60 + Number(match[2]);
}
function isUpcoming(ev, now = Date.now()) {
    const end = ev.end || ev.start;
    const parsed = Date.parse(end);
    return Number.isNaN(parsed) ? true : parsed >= now;
}
const HOUR_PX = 42;
function daySegment(ev, dayKey) {
    if (ev.all_day)
        return null;
    const startDay = eventDayKey(ev);
    const endDay = (ev.end || ev.start).slice(0, 10);
    const startMin = wallMinutes(ev.start);
    let endMin = ev.end ? wallMinutes(ev.end) : startMin + 60;
    if (endDay === startDay && endMin <= startMin)
        endMin = startMin + 60;
    if (dayKey === startDay && dayKey === endDay)
        return { startMin, endMin };
    if (dayKey === startDay && endDay > startDay)
        return { startMin, endMin: 24 * 60 };
    if (dayKey > startDay && dayKey < endDay)
        return { startMin: 0, endMin: 24 * 60 };
    if (dayKey === endDay && endDay > startDay)
        return { startMin: 0, endMin: Math.max(endMin, 15) };
    return null;
}
function parseTags(text) {
    const seen = new Set();
    const out = [];
    for (const raw of text.split(',')) {
        const tag = raw.trim();
        if (!tag || seen.has(tag.toLowerCase()))
            continue;
        seen.add(tag.toLowerCase());
        out.push(tag);
    }
    return out;
}
function toApiStamp(value, allDay) {
    if (allDay)
        return `${value.slice(0, 10)}T00:00:00`;
    return value.length === 16 ? `${value}:00` : value;
}
function toWrite(draft, mode) {
    const title = draft.title.trim();
    if (!title)
        throw new Error('Title is required');
    if (!draft.start)
        throw new Error('Start is required');
    const start = toApiStamp(draft.start, draft.allDay);
    const end = draft.end.trim() ? toApiStamp(draft.end, draft.allDay) : null;
    const location = draft.location.trim();
    const notes = draft.notes.trim();
    return {
        title,
        start,
        end,
        all_day: draft.allDay,
        location: location || null,
        notes: notes || null,
        tags: parseTags(draft.tags),
        clear_end: mode === 'edit' && !end,
        clear_location: mode === 'edit' && !location,
        clear_notes: mode === 'edit' && !notes,
        repeat: draft.repeat || null,
        repeat_until: draft.repeat ? draft.repeatUntil || null : null,
        repeat_weekdays: draft.repeat ? draft.repeatWeekdays : [],
        clear_repeat: mode === 'edit' && !draft.repeat,
        clear_repeat_until: mode === 'edit' && !draft.repeatUntil,
    };
}
export function CalendarPanel() {
    const [mode, setMode] = useState('fortnight');
    const [upcomingOnly, setUpcomingOnly] = useState(false);
    const [tag, setTag] = useState('');
    const [tags, setTags] = useState([]);
    const [tagColors, setTagColors] = useState({});
    const [list, setList] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(true);
    const [cursor, setCursor] = useState(() => new Date());
    const [editor, setEditor] = useState(null);
    const [draft, setDraft] = useState(emptyDraft);
    const [formError, setFormError] = useState(null);
    const [saving, setSaving] = useState(false);
    const monthKey = format(cursor, 'yyyy-MM');
    const todayKey = format(new Date(), 'yyyy-MM-dd');
    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const tagArg = tag || undefined;
            const span = mode === 'week' ? 7 : 14;
            const fromDate = mode === 'week' || mode === 'fortnight'
                ? startOfWeek(cursor, { weekStartsOn: 1 })
                : cursor;
            const [tagList, events] = await Promise.all([
                api.calendarTags(),
                mode === 'month'
                    ? api.calendarMonth(monthKey, tagArg)
                    : api.calendarWeeks(format(fromDate, 'yyyy-MM-dd'), tagArg, span),
            ]);
            setTags(tagList.tags);
            setTagColors(tagList.colors ?? {});
            setList(events);
        }
        catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        }
        finally {
            setLoading(false);
        }
    }, [mode, monthKey, tag, cursor]);
    useEffect(() => {
        void load();
    }, [load]);
    const byDay = useMemo(() => {
        const map = new Map();
        for (const ev of list?.events ?? []) {
            const key = eventDayKey(ev);
            const arr = map.get(key) ?? [];
            arr.push(ev);
            map.set(key, arr);
        }
        return map;
    }, [list]);
    const monthCells = useMemo(() => {
        const start = startOfWeek(startOfMonth(cursor), { weekStartsOn: 1 });
        const end = endOfWeek(endOfMonth(cursor), { weekStartsOn: 1 });
        return eachDayOfInterval({ start, end });
    }, [cursor]);
    const rasterDays = useMemo(() => {
        const start = startOfWeek(cursor, { weekStartsOn: 1 });
        const count = mode === 'week' ? 6 : 13;
        return eachDayOfInterval({ start, end: addDays(start, count) });
    }, [cursor, mode]);
    const visibleEvents = useMemo(() => {
        const events = list?.events ?? [];
        if (mode === 'simple' && upcomingOnly)
            return events.filter((ev) => isUpcoming(ev));
        return events;
    }, [list, mode, upcomingOnly]);
    const todayInView = list != null &&
        todayKey >= list.range_start.slice(0, 10) &&
        todayKey < list.range_end.slice(0, 10);
    function openCreate() {
        setEditor('create');
        setDraft(emptyDraft());
        setFormError(null);
    }
    function openCreateAt(day, hour) {
        const start = new Date(day);
        start.setHours(hour, 0, 0, 0);
        const startValue = format(start, "yyyy-MM-dd'T'HH:mm");
        setEditor('create');
        setDraft({ ...emptyDraft(), start: startValue, end: defaultTimedEnd(startValue) });
        setFormError(null);
    }
    function eventStyle(ev) {
        const tag = ev.tags[0];
        if (!tag)
            return undefined;
        const color = colorFor(tag, tagColors);
        return {
            borderColor: color,
            background: `color-mix(in srgb, ${color} 32%, transparent)`,
        };
    }
    async function saveTagColor(name, color) {
        setTagColors((current) => ({ ...current, [name]: color }));
        try {
            const saved = await api.setCalendarTagColor(name, color);
            setTagColors(saved.colors ?? {});
            setTags(saved.tags);
        }
        catch (e) {
            setFormError(e instanceof Error ? e.message : String(e));
        }
    }
    function shift(direction) {
        if (mode === 'month')
            setCursor(addMonths(cursor, direction));
        else if (mode === 'week')
            setCursor(addDays(cursor, direction * 7));
        else
            setCursor(addDays(cursor, direction * 14));
    }
    function openEdit(event) {
        setEditor('edit');
        setDraft(draftFromEvent(event));
        setFormError(null);
    }
    async function saveEvent() {
        setSaving(true);
        setFormError(null);
        try {
            const body = toWrite(draft, editor === 'edit' ? 'edit' : 'create');
            if (editor === 'edit')
                await api.updateCalendarEvent(draft.id, body);
            else
                await api.createCalendarEvent(body);
            setEditor(null);
            await load();
        }
        catch (e) {
            setFormError(e instanceof Error ? e.message : String(e));
        }
        finally {
            setSaving(false);
        }
    }
    async function removeEvent() {
        if (!draft.id)
            return;
        if (!window.confirm(`Delete “${draft.title}”?`))
            return;
        setSaving(true);
        setFormError(null);
        try {
            await api.deleteCalendarEvent(draft.id);
            setEditor(null);
            await load();
        }
        catch (e) {
            setFormError(e instanceof Error ? e.message : String(e));
        }
        finally {
            setSaving(false);
        }
    }
    return (_jsxs("section", { className: "panel", children: [_jsx("h2", { children: "Calendar" }), _jsx("p", { className: "lede", children: "Personal events on the Pi (Europe/Berlin). No M365." }), _jsxs("div", { className: "panel-actions", children: [_jsx("button", { type: "button", className: "primary", onClick: openCreate, children: "New event" }), _jsx("button", { type: "button", className: mode === 'week' ? 'primary' : undefined, onClick: () => setMode('week'), children: "Week" }), _jsx("button", { type: "button", className: mode === 'fortnight' ? 'primary' : undefined, onClick: () => setMode('fortnight'), children: "2 weeks" }), _jsx("button", { type: "button", className: mode === 'simple' ? 'primary' : undefined, onClick: () => setMode('simple'), children: "Simplified" }), _jsx("button", { type: "button", className: mode === 'month' ? 'primary' : undefined, onClick: () => setMode('month'), children: "Month" }), mode === 'simple' && (_jsxs("label", { className: "check", style: { display: 'flex', alignItems: 'center', gap: '0.4rem' }, children: [_jsx("input", { type: "checkbox", checked: upcomingOnly, onChange: (event) => setUpcomingOnly(event.target.checked) }), "Only upcoming"] })), _jsx("button", { type: "button", onClick: () => shift(-1), children: "\u2190" }), _jsx("button", { type: "button", onClick: () => setCursor(new Date()), children: "Today" }), _jsx("button", { type: "button", onClick: () => shift(1), children: "\u2192" }), _jsx("button", { type: "button", onClick: () => void load(), children: "Reload" })] }), editor && (_jsxs("form", { className: "topic-form", onSubmit: (event) => {
                    event.preventDefault();
                    void saveEvent();
                }, children: [_jsx("h3", { children: editor === 'create' ? 'New event' : 'Edit event' }), _jsxs("label", { children: ["Title", _jsx("input", { value: draft.title, required: true, maxLength: 300, onChange: (event) => setDraft({ ...draft, title: event.target.value }) })] }), _jsxs("label", { className: "check", children: [_jsx("input", { type: "checkbox", checked: draft.allDay, onChange: (event) => {
                                    const allDay = event.target.checked;
                                    setDraft((current) => ({
                                        ...current,
                                        allDay,
                                        start: allDay
                                            ? current.start.slice(0, 10)
                                            : current.start.length === 10
                                                ? `${current.start}T09:00`
                                                : current.start,
                                        end: !current.end
                                            ? ''
                                            : allDay
                                                ? current.end.slice(0, 10)
                                                : current.end.length === 10
                                                    ? `${current.end}T10:00`
                                                    : current.end,
                                    }));
                                } }), "All day"] }), _jsxs("div", { className: "time-row", children: [_jsxs("label", { children: ["Repeat", _jsxs("select", { value: draft.repeat, onChange: (event) => setDraft({
                                            ...draft,
                                            repeat: event.target.value,
                                        }), children: [_jsx("option", { value: "", children: "Does not repeat" }), _jsx("option", { value: "weekly", children: "Every week" }), _jsx("option", { value: "biweekly", children: "Every two weeks" }), _jsx("option", { value: "monthly", children: "Every month" })] })] }), _jsxs("label", { children: ["Repeat until", _jsx("input", { type: "date", value: draft.repeatUntil, disabled: !draft.repeat, onChange: (event) => setDraft({ ...draft, repeatUntil: event.target.value }) })] })] }), draft.repeat && (_jsxs("fieldset", { children: [_jsx("legend", { children: "Days" }), _jsx("div", { className: "weekday-row", children: WEEKDAYS.map((label, day) => (_jsx("button", { type: "button", className: draft.repeatWeekdays.includes(day) ? 'primary' : undefined, onClick: () => setDraft((current) => {
                                        const selected = current.repeatWeekdays.includes(day)
                                            ? current.repeatWeekdays.filter((value) => value !== day)
                                            : [...current.repeatWeekdays, day].sort((a, b) => a - b);
                                        return { ...current, repeatWeekdays: selected };
                                    }), children: label }, label))) }), _jsx("span", { className: "hint", children: draft.repeat === 'monthly'
                                    ? 'Selected days repeat in the first week of each month. Leave them empty to repeat on the same date.'
                                    : 'Select every day this should occur. Leave them empty to follow the start day only.' })] })), _jsxs("div", { className: "time-row", children: [_jsxs("label", { children: ["Start", _jsx("input", { type: draft.allDay ? 'date' : 'datetime-local', required: true, value: draft.allDay ? draft.start.slice(0, 10) : draft.start, onChange: (event) => {
                                            const start = event.target.value;
                                            setDraft((current) => {
                                                const previousDefault = defaultTimedEnd(current.start);
                                                const keepAutoEnd = !current.allDay && (current.end === '' || current.end === previousDefault);
                                                return {
                                                    ...current,
                                                    start,
                                                    end: keepAutoEnd ? defaultTimedEnd(start) : current.end,
                                                };
                                            });
                                        } })] }), _jsxs("label", { children: ["End", _jsx("input", { type: draft.allDay ? 'date' : 'datetime-local', value: draft.allDay ? draft.end.slice(0, 10) : draft.end, onChange: (event) => setDraft({ ...draft, end: event.target.value }) })] })] }), _jsxs("label", { children: ["Location", _jsx("input", { value: draft.location, maxLength: 500, onChange: (event) => setDraft({ ...draft, location: event.target.value }) })] }), _jsxs("label", { children: ["Notes", _jsx("textarea", { rows: 3, maxLength: 4000, value: draft.notes, onChange: (event) => setDraft({ ...draft, notes: event.target.value }) })] }), _jsxs("label", { children: ["Tags", _jsx("input", { value: draft.tags, placeholder: "health, work", onChange: (event) => setDraft({ ...draft, tags: event.target.value }) }), _jsx("span", { className: "hint", children: "Comma-separated. Times are stored in the Pi timezone." })] }), parseTags(draft.tags).length > 0 && (_jsx("div", { className: "weekday-row", children: parseTags(draft.tags).map((name) => (_jsxs("label", { className: "tag-chip", children: [name, _jsx("input", { type: "color", "aria-label": `Colour for ${name}`, value: colorFor(name, tagColors), onChange: (event) => void saveTagColor(name, event.target.value) })] }, name))) })), formError && _jsx("div", { className: "error-box", children: formError }), _jsxs("div", { className: "panel-actions", children: [_jsx("button", { type: "submit", className: "primary", disabled: saving, children: saving ? 'Saving…' : editor === 'create' ? 'Create event' : 'Save changes' }), editor === 'edit' && (_jsx("button", { type: "button", onClick: () => void removeEvent(), disabled: saving, children: "Delete" })), _jsx("button", { type: "button", onClick: () => setEditor(null), disabled: saving, children: "Cancel" })] })] })), _jsxs("div", { className: "tags", style: { marginBottom: '0.85rem' }, children: [_jsx("button", { type: "button", className: `chip ${tag === '' ? 'active' : ''}`, onClick: () => setTag(''), children: "All tags" }), tags.map((t) => (_jsxs("span", { className: "tag-chip", children: [_jsx("button", { type: "button", className: `chip ${tag === t ? 'active' : ''}`, style: { borderColor: colorFor(t, tagColors) }, onClick: () => setTag(t), children: t }), _jsx("input", { type: "color", "aria-label": `Colour for ${t}`, value: colorFor(t, tagColors), onChange: (event) => void saveTagColor(t, event.target.value) })] }, t)))] }), loading && _jsx("p", { className: "muted", children: "Loading\u2026" }), error && _jsx("div", { className: "error-box", children: error }), list && !loading && (_jsxs(_Fragment, { children: [_jsxs("p", { className: "muted", children: [list.count, " event(s) \u00B7 ", list.range_start.slice(0, 10), " \u2192 ", list.range_end.slice(0, 10)] }), mode === 'month' ? (_jsxs("div", { className: "month-grid", children: [['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d) => (_jsx("div", { className: "dow", children: d }, d))), monthCells.map((day) => {
                                const key = format(day, 'yyyy-MM-dd');
                                const events = byDay.get(key) ?? [];
                                const inMonth = day.getMonth() === cursor.getMonth();
                                return (_jsxs("div", { className: `month-cell ${inMonth ? '' : 'outside'} ${key === todayKey ? 'today' : ''}`, onClick: () => openCreateAt(day, 9), children: [_jsx("div", { className: "daynum", children: format(day, 'd') }), _jsx("ul", { children: events.slice(0, 4).map((ev) => (_jsx("li", { children: _jsx("button", { type: "button", className: "linkish", style: eventStyle(ev), onClick: (event) => {
                                                        event.stopPropagation();
                                                        openEdit(ev);
                                                    }, children: eventLabel(ev) }) }, ev.id))) })] }, key));
                            })] })) : mode === 'week' || mode === 'fortnight' ? (_jsxs("div", { className: "raster", children: [_jsxs("div", { className: "raster-head", style: { gridTemplateColumns: `52px repeat(${rasterDays.length}, minmax(0, 1fr))` }, children: [_jsx("div", {}), rasterDays.map((day) => (_jsx("div", { className: format(day, 'yyyy-MM-dd') === todayKey ? 'today' : undefined, children: format(day, 'EEE d') }, format(day, 'yyyy-MM-dd'))))] }), _jsxs("div", { className: "raster-allday", style: { gridTemplateColumns: `52px repeat(${rasterDays.length}, minmax(0, 1fr))` }, children: [_jsx("div", { className: "raster-label", children: "all day" }), rasterDays.map((day) => {
                                        const key = format(day, 'yyyy-MM-dd');
                                        const events = (byDay.get(key) ?? []).filter((ev) => ev.all_day);
                                        return (_jsx("div", { className: key === todayKey ? 'today' : undefined, children: events.map((ev) => (_jsx("button", { type: "button", className: "raster-event static", style: eventStyle(ev), onClick: () => openEdit(ev), children: ev.title }, ev.id))) }, key));
                                    })] }), _jsx("div", { className: "raster-scroll", children: _jsxs("div", { className: "raster-body", style: { gridTemplateColumns: `52px repeat(${rasterDays.length}, minmax(0, 1fr))` }, children: [_jsx("div", { children: Array.from({ length: 24 }, (_, hour) => (_jsxs("div", { className: "raster-label", style: { height: HOUR_PX }, children: [String(hour).padStart(2, '0'), ":00"] }, hour))) }), rasterDays.map((day) => {
                                            const key = format(day, 'yyyy-MM-dd');
                                            const events = (byDay.get(key) ?? []).filter((ev) => !ev.all_day);
                                            return (_jsxs("div", { className: key === todayKey ? 'raster-col today' : 'raster-col', children: [Array.from({ length: 24 }, (_, hour) => (_jsx("button", { type: "button", className: "raster-slot", style: { height: HOUR_PX }, "aria-label": `New event ${key} ${hour}:00`, onClick: () => openCreateAt(day, hour) }, hour))), events.map((ev) => {
                                                        const segment = daySegment(ev, key);
                                                        if (!segment)
                                                            return null;
                                                        const top = (segment.startMin / (24 * 60)) * 24 * HOUR_PX;
                                                        const height = Math.max(18, ((segment.endMin - segment.startMin) / (24 * 60)) * 24 * HOUR_PX);
                                                        return (_jsx("button", { type: "button", className: "raster-event", style: { top, height, ...eventStyle(ev) }, onClick: () => openEdit(ev), children: eventLabel(ev) }, ev.id));
                                                    })] }, key));
                                        })] }) })] })) : (_jsxs(_Fragment, { children: [visibleEvents.length === 0 && !todayInView && (_jsx("div", { className: "list-empty", children: "No events in this window." })), todayInView && visibleEvents.every((ev) => eventDayKey(ev) !== todayKey) && (_jsxs("div", { className: "event-row today", children: [_jsxs("div", { className: "when", children: [format(new Date(), 'EEE d MMM'), " \u00B7 today"] }), _jsx("div", { className: "muted", children: "No events" })] })), visibleEvents.map((ev) => (_jsxs("div", { className: eventDayKey(ev) === todayKey ? 'event-row today' : 'event-row', style: eventDayKey(ev) === todayKey
                                    ? {
                                        ...eventStyle(ev),
                                        background: 'color-mix(in srgb, var(--accent) 28%, var(--bg-elevated))',
                                    }
                                    : eventStyle(ev), children: [_jsxs("div", { className: "card-head", children: [_jsxs("div", { children: [_jsxs("div", { className: "when", children: [ev.all_day ? `${eventDayKey(ev)} · all day` : ev.start, eventDayKey(ev) === todayKey ? ' · today' : '', ev.repeat ? ` · ${repeatLabel(ev)}` : ''] }), _jsx("strong", { children: ev.title })] }), _jsx("button", { type: "button", onClick: () => openEdit(ev), children: "Edit" })] }), _jsx("div", { className: "muted", children: [ev.location, ev.tags?.join(', ')].filter(Boolean).join(' · ') || '—' })] }, ev.id)))] }))] }))] }));
}
