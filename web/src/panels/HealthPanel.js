import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { CaloriesTab } from './health/CaloriesTab';
import { ChartsTab } from './health/ChartsTab';
import { DashboardTab } from './health/DashboardTab';
import { MeasurementsTab } from './health/MeasurementsTab';
import { ProfileTab } from './health/ProfileTab';
import './health/health.css';
const SECTIONS = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'charts', label: 'Charts' },
    { id: 'measurements', label: 'Measurements' },
    { id: 'calories', label: 'Calories' },
    { id: 'profile', label: 'Profile and Targets' },
];
export function HealthPanel() {
    const [section, setSection] = useState('dashboard');
    return (_jsxs("section", { className: "panel", children: [_jsx("h2", { children: "Health" }), _jsx("div", { className: "subnav", role: "tablist", "aria-label": "Health sections", children: SECTIONS.map((item) => (_jsx("button", { type: "button", className: section === item.id ? 'active' : undefined, onClick: () => setSection(item.id), children: item.label }, item.id))) }), section === 'dashboard' && _jsx(DashboardTab, {}), section === 'charts' && _jsx(ChartsTab, {}), section === 'measurements' && _jsx(MeasurementsTab, {}), section === 'calories' && _jsx(CaloriesTab, {}), section === 'profile' && _jsx(ProfileTab, {})] }));
}
