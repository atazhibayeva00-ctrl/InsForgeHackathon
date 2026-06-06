import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { SessionState } from '../api/client'
import './DashboardPanel.css'

interface Props {
  state: SessionState | null
}

function expectedAnnualReturn(allocation: Record<string, number>) {
  const assumptions: Record<string, number> = {
    stock: 0.07,
    etf: 0.065,
    bond: 0.03,
    cash: 0.01,
    unknown: 0.04,
  }

  return (
    Object.entries(allocation).reduce((acc, [assetClass, pct]) => {
      return acc + (pct / 100) * (assumptions[assetClass] ?? assumptions.unknown)
    }, 0) || 0.04
  )
}

function formatCurrency(value: number) {
  return `$${Math.round(value).toLocaleString()}`
}

function numericValue(value: unknown) {
  return typeof value === 'number' ? value : Number(value ?? 0)
}

export function DashboardPanel({ state }: Props) {
  if (!state) {
    return (
      <section className="dashboard-empty panel">
        <h2>Dashboard</h2>
        <p className="muted">Start a session to see collaboration score and portfolio projections.</p>
      </section>
    )
  }

  const scoreData =
    state.cycles.length > 0
      ? state.cycles.map((cycle) => ({
          cycle: `Cycle ${cycle.cycle_index}`,
          collabScore: Math.round(cycle.metrics.collab_score * 100),
          taskPerformance: Math.round(cycle.metrics.task_performance * 100),
        }))
      : [{ cycle: 'Current', collabScore: Math.round(state.collab_metrics.collab_score * 100), taskPerformance: Math.round(state.collab_metrics.task_performance * 100) }]

  const annualReturn = expectedAnnualReturn(state.allocation_by_class)
  const projectionData = Array.from({ length: 6 }, (_, year) => ({
    year: year === 0 ? 'Now' : `Y${year}`,
    value: Math.round(state.total_value * (1 + annualReturn) ** year),
  }))

  return (
    <section className="dashboard">
      <div className="dashboard-hero panel">
        <div>
          <p className="dashboard-eyebrow">Recurring review dashboard</p>
          <h2>Portfolio collaboration over time</h2>
          <p className="muted">
            Track each approved cycle and a simple expected-value projection based on the current mock-applied allocation.
          </p>
        </div>
        <div className="dashboard-stat">
          <span className="dashboard-stat-label">Current value</span>
          <strong>{formatCurrency(state.total_value)}</strong>
          <span>{(annualReturn * 100).toFixed(1)}% assumed annual return</span>
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="panel dashboard-chart-card">
          <h3>Collaboration score by cycle</h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={scoreData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.2)" />
              <XAxis dataKey="cycle" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
              <Tooltip
                formatter={(value) => `${numericValue(value)}%`}
                contentStyle={{ background: '#111827', border: '1px solid #374151', color: '#e5e7eb' }}
              />
              <Line type="monotone" dataKey="collabScore" name="Collab score" stroke="#818cf8" strokeWidth={3} dot />
              <Line type="monotone" dataKey="taskPerformance" name="Task performance" stroke="#34d399" strokeWidth={2} dot />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="panel dashboard-chart-card">
          <h3>Expected portfolio value</h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={projectionData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.2)" />
              <XAxis dataKey="year" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" tickFormatter={(v) => `$${Math.round(Number(v) / 1000)}k`} />
              <Tooltip
                formatter={(value) => formatCurrency(numericValue(value))}
                contentStyle={{ background: '#111827', border: '1px solid #374151', color: '#e5e7eb' }}
              />
              <Line type="monotone" dataKey="value" name="Projected value" stroke="#fbbf24" strokeWidth={3} dot />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="panel dashboard-cycle-list">
        <h3>Approved cycles</h3>
        {state.cycles.length === 0 ? (
          <p className="muted">No approved cycles yet.</p>
        ) : (
          state.cycles.map((cycle) => (
            <div className="dashboard-cycle" key={cycle.cycle_index}>
              <div>
                <strong>Cycle {cycle.cycle_index}</strong>
                <p className="muted">
                  {cycle.applied_trades.length} mock trade{cycle.applied_trades.length === 1 ? '' : 's'} applied
                </p>
              </div>
              <span>{Math.round(cycle.metrics.collab_score * 100)}%</span>
            </div>
          ))
        )}
      </div>
    </section>
  )
}
