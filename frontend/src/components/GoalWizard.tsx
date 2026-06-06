import { INVESTMENT_GOALS } from '../api/client'
import './GoalWizard.css'

interface Props {
  value: string
  onChange: (goal: string) => void
  disabled?: boolean
}

export function GoalWizard({ value, onChange, disabled }: Props) {
  return (
    <div className="goal-wizard">
      <span className="goal-wizard-label">Investment goal</span>
      <div className="goal-wizard-options">
        {INVESTMENT_GOALS.map((g) => (
          <button
            key={g.id}
            type="button"
            className={`goal-chip${value === g.value ? ' goal-chip-active' : ''}`}
            disabled={disabled}
            onClick={() => onChange(g.value)}
          >
            {g.label}
          </button>
        ))}
      </div>
    </div>
  )
}
