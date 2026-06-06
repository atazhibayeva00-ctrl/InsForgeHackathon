import { AllocationChart } from './AllocationChart'
import './AllocationCompare.css'

interface Props {
  before: Record<string, number>
  proposed: Record<string, number>
  approved?: boolean
}

function formatPct(v: number) {
  return `${v.toFixed(1)}%`
}

function deltaRows(
  before: Record<string, number>,
  proposed: Record<string, number>,
) {
  const keys = new Set([...Object.keys(before), ...Object.keys(proposed)])
  return [...keys]
    .map((key) => {
      const b = before[key] ?? 0
      const p = proposed[key] ?? 0
      return { key, before: b, proposed: p, delta: p - b }
    })
    .filter((r) => Math.abs(r.before) > 0.01 || Math.abs(r.proposed) > 0.01)
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
}

export function AllocationCompare({ before, proposed, approved }: Props) {
  const rows = deltaRows(before, proposed)
  const stageLabel = approved ? 'Approved' : 'Proposed'

  return (
    <section className="panel allocation-compare">
      <header className="panel-header">
        <h2>Allocation comparison</h2>
        <span className="compare-stage-badge">{stageLabel}</span>
      </header>

      <p className="compare-description">
        Side-by-side view of your portfolio at proposal time (left) and the projected
        mix after the agent&apos;s trades (right) by asset class. The table below
        shows how each slice would shift if you {approved ? 'approved' : 'approve'}{' '}
        the plan.
      </p>

      <div className="compare-charts">
        <div className="compare-chart-card">
          <h3>Before</h3>
          <AllocationChart data={before} title="" />
        </div>
        <div className="compare-arrow" aria-hidden>
          →
        </div>
        <div className="compare-chart-card">
          <h3>{stageLabel}</h3>
          <AllocationChart data={proposed} title="" />
        </div>
      </div>

      <div className="compare-delta-table">
        <div className="compare-delta-head">
          <span>Asset class</span>
          <span>Before</span>
          <span>{stageLabel}</span>
          <span>Change</span>
        </div>
        {rows.map((row) => (
          <div key={row.key} className="compare-delta-row">
            <span className="compare-delta-key">{row.key}</span>
            <span>{formatPct(row.before)}</span>
            <span>{formatPct(row.proposed)}</span>
            <span
              className={
                row.delta > 0.05
                  ? 'delta-up'
                  : row.delta < -0.05
                    ? 'delta-down'
                    : 'delta-flat'
              }
            >
              {row.delta >= 0 ? '+' : ''}
              {formatPct(row.delta)}
            </span>
          </div>
        ))}
      </div>
    </section>
  )
}
