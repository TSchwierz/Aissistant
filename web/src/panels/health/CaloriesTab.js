import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { api } from '../../api';
import { errorMessage, formatWhen } from './shared';
let rowSeq = 0;
function nextKey() {
    rowSeq += 1;
    return `food-${rowSeq}`;
}
function todayLocal() {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${now.getFullYear()}-${month}-${day}`;
}
function formatMacro(value) {
    if (value == null || !Number.isFinite(value))
        return '—';
    const rounded = Math.round(value * 10) / 10;
    return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
}
function formatAgainst(value, target, unit) {
    const suffix = unit ? ` ${unit}` : '';
    if (target == null)
        return `${formatMacro(value)}${suffix}`;
    return `${formatMacro(value)} / ${formatMacro(target)}${suffix}`;
}
function roundMacro(value) {
    return Math.round(value * 100) / 100;
}
function scaleTo(item, newGrams) {
    if (!(item.grams > 0))
        return { ...item, grams: newGrams };
    const ratio = newGrams / item.grams;
    return {
        ...item,
        grams: newGrams,
        kcal: item.kcal * ratio,
        protein_g: item.protein_g * ratio,
        carbs_g: item.carbs_g * ratio,
        fat_g: item.fat_g * ratio,
        fiber_g: item.fiber_g * ratio,
    };
}
function toRow(item) {
    return { key: nextKey(), gramsText: String(item.grams), item };
}
function hitToItem(hit) {
    return {
        name: hit.name,
        grams: 100,
        kcal: hit.kcal_100g,
        protein_g: hit.protein_100g,
        carbs_g: hit.carbs_100g,
        fat_g: hit.fat_100g,
        fiber_g: hit.fiber_100g,
        source: hit.source,
        source_id: hit.source_id ?? null,
    };
}
function itemFromRow(row) {
    const name = row.item.name.trim();
    if (!name)
        return null;
    const grams = Number(row.gramsText);
    if (!Number.isFinite(grams) || grams <= 0)
        return null;
    const scaled = grams === row.item.grams ? row.item : scaleTo(row.item, grams);
    return {
        ...(scaled.id != null ? { id: scaled.id } : {}),
        name,
        grams: roundMacro(scaled.grams),
        kcal: roundMacro(scaled.kcal),
        protein_g: roundMacro(scaled.protein_g),
        carbs_g: roundMacro(scaled.carbs_g),
        fat_g: roundMacro(scaled.fat_g),
        fiber_g: roundMacro(scaled.fiber_g),
        source: scaled.source || 'manual',
        source_id: scaled.source_id ?? null,
    };
}
export function CaloriesTab() {
    const [day, setDay] = useState(todayLocal);
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [note, setNote] = useState('');
    const [proposal, setProposal] = useState([]);
    const [proposed, setProposed] = useState(false);
    const [proposing, setProposing] = useState(false);
    const [query, setQuery] = useState('');
    const [hits, setHits] = useState([]);
    const [searched, setSearched] = useState(false);
    const [searching, setSearching] = useState(false);
    const [saving, setSaving] = useState(false);
    const [deletingId, setDeletingId] = useState(null);
    const [reloadToken, setReloadToken] = useState(0);
    const [loadedDay, setLoadedDay] = useState(null);
    useEffect(() => {
        let cancel = false;
        setLoading(true);
        setError(null);
        api
            .mealSummary(day)
            .then((data) => {
            if (cancel)
                return;
            setSummary(data);
            setLoadedDay(day);
        })
            .catch((e) => {
            if (!cancel)
                setError(errorMessage(e));
        })
            .finally(() => {
            if (!cancel)
                setLoading(false);
        });
        return () => {
            cancel = true;
        };
    }, [day, reloadToken]);
    function updateRow(key, next) {
        setProposal((rows) => rows.map((row) => (row.key === key ? next : row)));
    }
    async function propose() {
        if (!note.trim()) {
            setError('Describe a meal first.');
            return;
        }
        setProposing(true);
        setError(null);
        try {
            const parsed = await api.parseMeal(note);
            setProposal((parsed.items ?? []).map(toRow));
            setProposed(true);
        }
        catch (e) {
            setError(errorMessage(e));
        }
        finally {
            setProposing(false);
        }
    }
    async function runSearch() {
        const q = query.trim();
        if (!q) {
            setHits([]);
            setSearched(false);
            return;
        }
        setSearching(true);
        setError(null);
        try {
            const result = await api.searchFoods(q);
            setHits(result.foods ?? []);
            setSearched(true);
        }
        catch (e) {
            setError(errorMessage(e));
        }
        finally {
            setSearching(false);
        }
    }
    function addHit(hit) {
        setProposal((rows) => [...rows, toRow(hitToItem(hit))]);
        setProposed(true);
    }
    async function saveMeal() {
        if (proposal.length === 0) {
            setError('Add at least one food.');
            return;
        }
        const items = [];
        for (const row of proposal) {
            const item = itemFromRow(row);
            if (!item) {
                setError('Each food needs a name and grams greater than 0.');
                return;
            }
            items.push(item);
        }
        setSaving(true);
        setError(null);
        try {
            await api.createMeal({
                eaten_at: `${day}T12:00:00`,
                note,
                source: 'text',
                items,
            });
            setProposal([]);
            setNote('');
            setProposed(false);
            setReloadToken((token) => token + 1);
        }
        catch (e) {
            setError(errorMessage(e));
        }
        finally {
            setSaving(false);
        }
    }
    async function removeMeal(id) {
        setDeletingId(id);
        setError(null);
        try {
            await api.deleteMeal(id);
            setReloadToken((token) => token + 1);
        }
        catch (e) {
            setError(errorMessage(e));
        }
        finally {
            setDeletingId(null);
        }
    }
    const shown = loadedDay === day ? summary : null;
    const targets = shown?.targets;
    return (_jsxs(_Fragment, { children: [_jsx("div", { className: "topic-form", children: _jsxs("label", { children: ["Day", _jsx("input", { type: "date", value: day, onChange: (event) => {
                                const next = event.target.value;
                                if (!next || next === day)
                                    return;
                                setLoading(true);
                                setError(null);
                                setDay(next);
                            } })] }) }), loading && _jsx("p", { className: "muted", children: "Loading\u2026" }), error && _jsx("div", { className: "error-box", children: error }), shown && (_jsxs(_Fragment, { children: [_jsxs("div", { className: "grid-2", children: [_jsxs("div", { className: "stat", children: [_jsx("div", { className: "label", children: "Calories" }), _jsx("div", { className: "value", style: { fontSize: '1.05rem' }, children: formatAgainst(shown.totals.kcal, targets?.target_calories, 'kcal') })] }), _jsxs("div", { className: "stat", children: [_jsx("div", { className: "label", children: "Protein" }), _jsx("div", { className: "value", style: { fontSize: '1.05rem' }, children: formatAgainst(shown.totals.protein_g, targets?.protein_g, 'g') })] }), _jsxs("div", { className: "stat", children: [_jsx("div", { className: "label", children: "Fiber" }), _jsx("div", { className: "value", style: { fontSize: '1.05rem' }, children: formatAgainst(shown.totals.fiber_g, targets?.fiber_g, 'g') })] }), _jsxs("div", { className: "stat", children: [_jsx("div", { className: "label", children: "Carbs" }), _jsx("div", { className: "value", style: { fontSize: '1.05rem' }, children: formatAgainst(shown.totals.carbs_g, null, 'g') })] }), _jsxs("div", { className: "stat", children: [_jsx("div", { className: "label", children: "Fat" }), _jsx("div", { className: "value", style: { fontSize: '1.05rem' }, children: formatAgainst(shown.totals.fat_g, null, 'g') })] })] }), _jsx("h3", { className: "muted", style: { fontSize: '0.85rem' }, children: "Meals" }), shown.meals.length === 0 && _jsx("div", { className: "list-empty", children: "No meals logged for this day." }), shown.meals.map((meal) => (_jsxs("div", { className: "section-card", children: [_jsxs("div", { className: "card-head", children: [_jsxs("div", { children: [_jsxs("h3", { children: [formatWhen(meal.eaten_at), meal.note ? ` · ${meal.note}` : ''] }), _jsx("div", { className: "muted", children: meal.source })] }), _jsx("button", { type: "button", disabled: deletingId === meal.id, onClick: () => void removeMeal(meal.id), children: "Delete meal" })] }), meal.items.length === 0 ? (_jsx("p", { className: "muted", style: { margin: '0.45rem 0 0' }, children: "No items." })) : (_jsx("ul", { className: "meal-items", children: meal.items.map((item, index) => (_jsxs("li", { children: [item.name, " \u00B7 ", formatMacro(item.grams), " g \u00B7 ", formatMacro(item.kcal), " kcal \u00B7", ' ', formatMacro(item.protein_g), " g protein \u00B7 ", formatMacro(item.carbs_g), " g carbs \u00B7", ' ', formatMacro(item.fat_g), " g fat \u00B7 ", formatMacro(item.fiber_g), " g fiber"] }, item.id ?? `${meal.id}-${index}`))) }))] }, meal.id)))] })), _jsxs("div", { className: "topic-form", children: [_jsx("h3", { children: "Log a meal" }), _jsxs("label", { children: ["Describe the meal", _jsx("textarea", { rows: 3, placeholder: "Two slices of bread and a banana", value: note, onChange: (event) => setNote(event.target.value) })] }), _jsx("div", { className: "panel-actions", children: _jsx("button", { type: "button", onClick: () => void propose(), disabled: proposing, children: proposing ? 'Proposing…' : 'Propose foods' }) }), proposing && _jsx("p", { className: "muted", children: "Proposing foods\u2026" }), proposed && proposal.length === 0 && !proposing && (_jsx("p", { className: "muted", children: "No foods proposed." })), proposal.map((row) => (_jsxs("div", { className: "proposal-row", children: [_jsxs("label", { children: ["Name", _jsx("input", { value: row.item.name, onChange: (event) => updateRow(row.key, {
                                            ...row,
                                            item: { ...row.item, name: event.target.value },
                                        }) })] }), _jsxs("label", { children: ["Grams", _jsx("input", { type: "number", min: 0, step: "any", value: row.gramsText, onChange: (event) => {
                                            const text = event.target.value;
                                            const trimmed = text.trim();
                                            const newGrams = Number(trimmed);
                                            if (trimmed === '' || !Number.isFinite(newGrams) || newGrams === 0) {
                                                updateRow(row.key, { ...row, gramsText: text });
                                                return;
                                            }
                                            updateRow(row.key, {
                                                ...row,
                                                gramsText: text,
                                                item: newGrams === row.item.grams ? row.item : scaleTo(row.item, newGrams),
                                            });
                                        } })] }), _jsx("div", { className: "proposal-remove", children: _jsx("button", { type: "button", className: "health-btn", onClick: () => setProposal((rows) => rows.filter((item) => item.key !== row.key)), children: "Remove" }) }), _jsxs("p", { className: "proposal-macros", children: [formatMacro(row.item.kcal), " kcal \u00B7 ", formatMacro(row.item.protein_g), " g protein \u00B7", ' ', formatMacro(row.item.carbs_g), " g carbs \u00B7 ", formatMacro(row.item.fat_g), " g fat \u00B7", ' ', formatMacro(row.item.fiber_g), " g fiber"] })] }, row.key))), _jsxs("div", { className: "health-search", children: [_jsxs("label", { children: ["Search foods", _jsx("input", { value: query, placeholder: "Food name", onChange: (event) => setQuery(event.target.value), onKeyDown: (event) => {
                                            if (event.key === 'Enter') {
                                                event.preventDefault();
                                                void runSearch();
                                            }
                                        } })] }), _jsx("button", { type: "button", className: "health-btn", onClick: () => void runSearch(), disabled: searching, children: "Search" })] }), searching && _jsx("p", { className: "muted", children: "Searching\u2026" }), searched && !searching && hits.length === 0 && (_jsx("p", { className: "muted", children: "No matching foods." })), hits.length > 0 && (_jsx("div", { className: "health-hits", children: hits.map((hit, index) => (_jsxs("button", { type: "button", className: "health-btn", onClick: () => addHit(hit), children: [hit.name, " \u00B7 ", formatMacro(hit.kcal_100g), " kcal/100 g \u00B7 ", formatMacro(hit.protein_100g), " g protein \u00B7 ", hit.source] }, `${hit.source}-${hit.source_id ?? hit.name}-${index}`))) })), _jsx("div", { className: "panel-actions", children: _jsx("button", { type: "button", className: "primary", disabled: saving || proposal.length === 0, onClick: () => void saveMeal(), children: saving ? 'Saving…' : 'Save meal' }) })] })] }));
}
