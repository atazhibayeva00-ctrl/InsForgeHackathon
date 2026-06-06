import type { Plan } from '../api/client'
import './PlanRevisionDiff.css'

interface Props {
  prior: Plan
  current: Plan
}

function tradeKey(t: { action: string; ticker: string; shares: number }) {
  return `${t.action}:${t.ticker}:${t.shares}`
}

export function PlanRevisionDiff({ prior, current }: Props) {
  const priorTrades = new Map(
    prior.proposed_trades.map((t) => [tradeKey(t), t]),
  )
  const currentTrades = new Map(
    current.proposed_trades.map((t) => [tradeKey(t), t]),
  )

  const removed = prior.proposed_trades.filter((t) => !currentTrades.has(tradeKey(t)))
  const added = current.proposed_trades.filter((t) => !priorTrades.has(tradeKey(t)))
  const kept = current.proposed_trades.filter((t) => priorTrades.has(tradeKey(t)))

  const allocKeys = new Set([
    ...Object.keys(prior.target_allocation),
    ...Object.keys(current.target_allocation),
  ])
  const allocChanges = [...allocKeys]
    .map((k) => ({
      key: k,
      before: prior.target_allocation[k] ?? 0,
      after: current.target_allocation[k] ?? 0,
      delta: (current.target_allocation[k] ?? 0) - (prior.target_allocation[k] ?? 0),
    }))
    .filter((r) => Math.abs(r.delta) > 0.05)
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))

  return (
    <div className="plan-revision-diff">
      <h3 className="revision-title">Plan revision</h3>
      <p className="revision-sub">
        Changes after your feedback — {added.length} added, {removed.length}{' '}
        removed, {kept.length} unchanged.
      </p>

      {allocChanges.length > 0 && (
        <div className="revision-block">
          <h4>Target allocation shifts</h4>
          <ul>
            {allocChanges.map((r) => (
              <li key={r.key}>
                <span className="revision-key">{r.key}</span>
                <span>
                  {r.before.toFixed(1)}% → {r.after.toFixed(1)}%
                </span>
                <span className={r.delta > 0 ? 'delta-up' : 'delta-down'}>
                  ({r.delta >= 0 ? '+' : ''}
                  {r.delta.toFixed(1)}%)
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {removed.length > 0 && (
        <div className="revision-block">
          <h4>Removed trades</h4>
          <ul>
            {removed.map((t) => (
              <li key={tradeKey(t)} className="trade-removed">
                {t.action.toUpperCase()} {t.shares} {t.ticker}
              </li>
            ))}
          </ul>
        </div>
      )}

      {added.length > 0 && (
        <div className="revision-block">
          <h4>New trades</h4>
          <ul>
            {added.map((t) => (
              <li key={tradeKey(t)} className="trade-added">
                {t.action.toUpperCase()} {t.shares} {t.ticker}
                <span className="trade-rationale">{t.rationale}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
