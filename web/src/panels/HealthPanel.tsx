import { useState } from 'react'
import { CaloriesTab } from './health/CaloriesTab'
import { ChartsTab } from './health/ChartsTab'
import { DashboardTab } from './health/DashboardTab'
import { MeasurementsTab } from './health/MeasurementsTab'
import { ProfileTab } from './health/ProfileTab'
import './health/health.css'

type Section = 'dashboard' | 'charts' | 'measurements' | 'calories' | 'profile'

const SECTIONS: { id: Section; label: string }[] = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'charts', label: 'Charts' },
  { id: 'measurements', label: 'Measurements' },
  { id: 'calories', label: 'Calories' },
  { id: 'profile', label: 'Profile and Targets' },
]

export function HealthPanel() {
  const [section, setSection] = useState<Section>('dashboard')

  return (
    <section className="panel">
      <h2>Health</h2>
      <div className="subnav" role="tablist" aria-label="Health sections">
        {SECTIONS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={section === item.id ? 'active' : undefined}
            onClick={() => setSection(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {section === 'dashboard' && <DashboardTab />}
      {section === 'charts' && <ChartsTab />}
      {section === 'measurements' && <MeasurementsTab />}
      {section === 'calories' && <CaloriesTab />}
      {section === 'profile' && <ProfileTab />}
    </section>
  )
}
