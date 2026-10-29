import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useCallback, useEffect, useMemo, useState } from 'react';
import { BarElement, CategoryScale, Chart as ChartJS, LinearScale, LineElement, PointElement, Tooltip, Legend, Filler, } from 'chart.js';
import { Bar, Line } from 'react-chartjs-2';
import { api } from '../../api';
import { themeChartColors } from '../../theme';
import { errorMessage, formatWhen } from './shared';
ChartJS.register(CategoryScale, LinearScale, LineElement, PointElement, BarElement, Tooltip, Legend, Filler);
const RANGES = [
    { id: 30, label: '30 days' },
    { id: 90, label: '90 days' },
    { id: 365, label: '365 days' },
    { id: 'all', label: 'All' },
];
const SERIES = {
    weight: '#3b82c4',
    fat: '#e07a2f',
    muscle: '#2f9d6c',
    other: '#8b97a6',
};
function withinRange(iso, range) {
    if (range === 'all')
        return true;
    const time = new Date(iso).getTime();
    if (Number.isNaN(time))
        return false;
    return time >= Date.now() - range * 24 * 60 * 60 * 1000;
}
function axisLabel(iso, range) {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime()))
        return iso;
    const day = date.toLocaleDateString([], {
        month: 'short',
        day: 'numeric',
        ...(range === 365 || range === 'all' ? { year: '2-digit' } : {}),
    });
    if (range !== 30)
        return day;
    const time = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return [day, time];
}
function finiteOrNull(value) {
    return value == null || !Number.isFinite(value) ? null : value;
}
function percentOf(part, weight) {
    const value = finiteOrNull(part);
    if (value == null || weight <= 0)
        return null;
    return (value / weight) * 100;
}
/** Fat and muscle as shares of body weight, plus the remainder so the stack is 100%. */
function compositionOf(row) {
    const weight = row.weight_kg;
    if (!Number.isFinite(weight) || weight <= 0)
        return null;
    const fat = finiteOrNull(row.body_fat_pct) ?? percentOf(row.body_fat_kg, weight);
    const muscle = finiteOrNull(row.muscle_pct) ?? percentOf(row.muscle_mass_kg, weight);
    if (fat == null || muscle == null)
        return null;
    const fatPct = Math.max(0, fat);
    const musclePct = Math.max(0, muscle);
    const total = fatPct + musclePct;
    if (total <= 0)
        return null;
    if (total > 100) {
        return { fat: (fatPct / total) * 100, muscle: (musclePct / total) * 100, other: 0 };
    }
    return { fat: fatPct, muscle: musclePct, other: 100 - total };
}
function categoryAxis(muted, grid) {
    return {
        offset: true,
        ticks: {
            color: muted,
            maxRotation: 0,
            minRotation: 0,
            autoSkip: true,
            autoSkipPadding: 18,
            maxTicksLimit: 8,
            padding: 8,
        },
        grid: { color: grid, drawTicks: false },
    };
}
function legend(muted) {
    return {
        position: 'bottom',
        labels: {
            color: muted,
            boxWidth: 12,
            boxHeight: 12,
            padding: 16,
        },
    };
}
export function ChartsTab() {
    const [rows, setRows] = useState([]);
    const [range, setRange] = useState(30);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(true);
    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            setRows(await api.healthMeasurements(5000));
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
    const points = useMemo(() => {
        return rows
            .filter((row) => withinRange(row.measured_at, range))
            .sort((a, b) => new Date(a.measured_at).getTime() - new Date(b.measured_at).getTime());
    }, [rows, range]);
    const labels = useMemo(() => points.map((row) => axisLabel(row.measured_at, range)), [points, range]);
    const shares = useMemo(() => points.map(compositionOf), [points]);
    const hasComposition = shares.some((share) => share != null);
    const tooltipTitle = useCallback((items) => {
        const iso = points[items[0]?.dataIndex ?? -1]?.measured_at;
        return iso ? formatWhen(iso) : '';
    }, [points]);
    const absoluteData = useMemo(() => {
        const pointRadius = points.length > 80 ? 0 : 3;
        const series = (label, color, data) => ({
            label,
            data,
            borderColor: color,
            backgroundColor: color,
            pointBackgroundColor: color,
            pointBorderWidth: 0,
            pointRadius,
            pointHoverRadius: 5,
            borderWidth: 2,
            tension: 0.25,
            spanGaps: false,
        });
        return {
            labels,
            datasets: [
                series('Weight', SERIES.weight, points.map((row) => finiteOrNull(row.weight_kg))),
                series('Body fat', SERIES.fat, points.map((row) => finiteOrNull(row.body_fat_kg))),
                series('Muscle', SERIES.muscle, points.map((row) => finiteOrNull(row.muscle_mass_kg))),
            ],
        };
    }, [labels, points]);
    const absoluteOptions = useMemo(() => {
        const colors = themeChartColors();
        return {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: legend(colors.muted),
                tooltip: {
                    callbacks: {
                        title: tooltipTitle,
                        label: (item) => {
                            const y = item.parsed.y;
                            if (y == null || Number.isNaN(y))
                                return item.dataset.label ?? '';
                            return `${item.dataset.label}: ${y.toFixed(1)} kg`;
                        },
                    },
                },
            },
            scales: {
                x: categoryAxis(colors.muted, colors.grid),
                y: {
                    title: { display: true, text: 'kg', color: colors.muted, font: { size: 12 } },
                    ticks: { color: colors.muted, padding: 6 },
                    grid: { color: colors.grid },
                    grace: '8%',
                },
            },
        };
    }, [tooltipTitle]);
    const shareData = useMemo(() => {
        const band = (label, color, data) => ({
            label,
            data,
            backgroundColor: color,
            borderColor: color,
            borderWidth: 0,
            stack: 'composition',
            maxBarThickness: 36,
        });
        return {
            labels,
            datasets: [
                band('Body fat', SERIES.fat, shares.map((share) => share?.fat ?? null)),
                band('Muscle', SERIES.muscle, shares.map((share) => share?.muscle ?? null)),
                band('Other', SERIES.other, shares.map((share) => share?.other ?? null)),
            ],
        };
    }, [labels, shares]);
    const shareOptions = useMemo(() => {
        const colors = themeChartColors();
        return {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: legend(colors.muted),
                tooltip: {
                    callbacks: {
                        title: tooltipTitle,
                        label: (item) => {
                            const y = item.parsed.y;
                            if (y == null || Number.isNaN(y))
                                return item.dataset.label ?? '';
                            return `${item.dataset.label}: ${y.toFixed(1)}%`;
                        },
                    },
                },
            },
            scales: {
                x: { ...categoryAxis(colors.muted, colors.grid), stacked: true },
                y: {
                    stacked: true,
                    min: 0,
                    max: 100,
                    title: { display: true, text: '%', color: colors.muted, font: { size: 12 } },
                    ticks: { color: colors.muted, stepSize: 20, padding: 6 },
                    grid: { color: colors.grid },
                },
            },
        };
    }, [tooltipTitle]);
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "panel-actions", children: [RANGES.map((item) => (_jsx("button", { type: "button", className: range === item.id ? 'primary' : undefined, onClick: () => setRange(item.id), children: item.label }, item.id))), _jsx("button", { type: "button", onClick: () => void load(), children: "Refresh" })] }), loading && _jsx("p", { className: "muted", children: "Loading\u2026" }), error && _jsx("div", { className: "error-box", children: error }), !loading && !error && points.length === 0 && (_jsx("div", { className: "list-empty", children: "No measurements in this range." })), !loading && points.length > 0 && (_jsxs("div", { className: "health-charts", children: [_jsxs("section", { className: "health-chart", "aria-label": "Absolute values", children: [_jsx("h3", { children: "Absolute values" }), _jsx("div", { className: "chart-wrap", children: _jsx(Line, { data: absoluteData, options: absoluteOptions }) })] }), _jsxs("section", { className: "health-chart", "aria-label": "Composition", children: [_jsx("h3", { children: "Composition" }), hasComposition ? (_jsx("div", { className: "chart-wrap", children: _jsx(Bar, { data: shareData, options: shareOptions }) })) : (_jsx("div", { className: "list-empty", children: "No body-fat or muscle percentages in this range." }))] })] }))] }));
}
