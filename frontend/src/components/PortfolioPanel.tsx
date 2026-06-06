import type { SessionState } from '../api/client'
import { AllocationChart } from './AllocationChart'

interface Props {
  state: SessionState
}

export function PortfolioPanel({ state }: Props) {
  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Portfolio</h2>
        <span className="badge">
          ${state.total_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
        </span>
      </div>
      <p className="muted">{state.summary}</p>

      <table className="holdings">
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Shares</th>
            <th>Price</th>
            <th>Value</th>
            <th>Weight</th>
            <th>Class</th>
          </tr>
        </thead>
        <tbody>
          {state.holdings.map((h) => (
            <tr key={h.ticker}>
              <td className="ticker">{h.ticker}</td>
              <td>{h.shares}</td>
              <td>${h.current_price.toLocaleString()}</td>
              <td>${h.market_value.toLocaleString()}</td>
              <td>
                <span className={h.weight_pct >= 40 ? 'weight hot' : 'weight'}>
                  {h.weight_pct.toFixed(1)}%
                </span>
              </td>
              <td className="muted">{h.asset_class}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <AllocationChart data={state.allocation_by_ticker} title="Current allocation" />

      {state.flags.length > 0 && (
        <div className="flags">
          <h3>Risk flags</h3>
          {state.flags.map((f, i) => (
            <div className="flag" key={i}>
              {f}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
