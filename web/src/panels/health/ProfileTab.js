import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api';
import { ACTIVITIES, errorMessage } from './shared';
import { TargetsBlock } from './TargetsBlock';
function applyNumbers(next) {
    return {
        name: next.name ?? '',
        height: next.height_cm != null ? String(next.height_cm) : '',
        age: next.age != null ? String(next.age) : '',
        sex: next.sex === 'male' || next.sex === 'female' ? next.sex : '',
        activity: next.activity_level || 'moderate',
        targetFat: next.target_fat_pct != null ? String(next.target_fat_pct) : '',
        meals: next.meals_per_day || next.nutrition?.meals_per_day || 3,
    };
}
function readOptionalNumber(text, label) {
    const trimmed = text.trim();
    if (!trimmed)
        return null;
    const value = Number(trimmed);
    if (!Number.isFinite(value))
        throw new Error(`${label} must be a number`);
    return value;
}
function readOptionalInt(text, label) {
    const value = readOptionalNumber(text, label);
    if (value == null)
        return null;
    if (!Number.isInteger(value))
        throw new Error(`${label} must be a whole number`);
    return value;
}
export function ProfileTab() {
    const [profile, setProfile] = useState(null);
    const [stats, setStats] = useState(null);
    const [name, setName] = useState('');
    const [height, setHeight] = useState('');
    const [age, setAge] = useState('');
    const [sex, setSex] = useState('');
    const [activity, setActivity] = useState('moderate');
    const [targetFat, setTargetFat] = useState('');
    const [meals, setMeals] = useState(3);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const fill = useCallback((next) => {
        const form = applyNumbers(next);
        setName(form.name);
        setHeight(form.height);
        setAge(form.age);
        setSex(form.sex);
        setActivity(form.activity);
        setTargetFat(form.targetFat);
        setMeals(form.meals);
    }, []);
    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [nextProfile, nextStats] = await Promise.all([
                api.healthProfile(),
                api.healthStats().catch(() => null),
            ]);
            setProfile(nextProfile);
            setStats(nextStats);
            fill(nextProfile);
        }
        catch (e) {
            setError(errorMessage(e));
        }
        finally {
            setLoading(false);
        }
    }, [fill]);
    useEffect(() => {
        void load();
    }, [load]);
    async function save() {
        setSaving(true);
        setError(null);
        try {
            const saved = await api.updateHealthProfile({
                name: name.trim(),
                height_cm: readOptionalNumber(height, 'Height'),
                age: readOptionalInt(age, 'Age'),
                sex: sex === 'male' || sex === 'female' ? sex : null,
                activity_level: activity,
                target_fat_pct: readOptionalNumber(targetFat, 'Target fat'),
                meals_per_day: meals,
            });
            setProfile(saved);
            fill(saved);
        }
        catch (e) {
            setError(errorMessage(e));
        }
        finally {
            setSaving(false);
        }
    }
    const nutrition = profile?.nutrition ?? stats?.nutrition;
    const currentFat = stats?.latest?.body_fat_pct;
    return (_jsxs(_Fragment, { children: [loading && _jsx("p", { className: "muted", children: "Loading\u2026" }), error && _jsx("div", { className: "error-box", children: error }), profile && !loading && (_jsxs(_Fragment, { children: [_jsxs("form", { className: "topic-form", onSubmit: (event) => {
                            event.preventDefault();
                            void save();
                        }, children: [_jsx("h3", { children: "Profile and targets" }), _jsxs("div", { className: "time-row", children: [_jsxs("label", { children: ["Name", _jsx("input", { value: name, onChange: (event) => setName(event.target.value) })] }), _jsxs("label", { children: ["Height cm", _jsx("input", { type: "number", min: 1, max: 299, step: "0.1", value: height, onChange: (event) => setHeight(event.target.value) })] })] }), _jsxs("div", { className: "time-row", children: [_jsxs("label", { children: ["Age", _jsx("input", { type: "number", min: 1, max: 120, step: 1, value: age, onChange: (event) => setAge(event.target.value) })] }), _jsxs("label", { children: ["Sex", _jsxs("select", { value: sex, onChange: (event) => setSex(event.target.value), children: [_jsx("option", { value: "", children: "Not set" }), _jsx("option", { value: "male", children: "Male" }), _jsx("option", { value: "female", children: "Female" })] })] })] }), _jsxs("div", { className: "time-row", children: [_jsxs("label", { children: ["Activity", _jsx("select", { value: activity, onChange: (event) => setActivity(event.target.value), children: ACTIVITIES.map((item) => (_jsx("option", { value: item.id, children: item.label }, item.id))) })] }), _jsxs("label", { children: ["Target fat %", _jsx("input", { type: "number", min: 2, max: 70, step: 0.1, value: targetFat, onChange: (event) => setTargetFat(event.target.value) })] })] }), _jsxs("label", { children: ["Meals per day: ", meals, _jsx("input", { type: "range", min: 1, max: 8, step: 1, value: meals, onChange: (event) => setMeals(Number(event.target.value)) })] }), _jsx("div", { className: "panel-actions", children: _jsx("button", { type: "submit", className: "primary", disabled: saving, children: saving ? 'Saving…' : 'Save' }) })] }), nutrition && (_jsx("div", { className: "stat", children: _jsx(TargetsBlock, { nutrition: nutrition, meals: meals, currentFatPct: currentFat }) }))] }))] }));
}
