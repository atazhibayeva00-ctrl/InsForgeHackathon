import type { InitiativeType, LogEntry } from '../api/client'
import './InitiativeMeter.css'

const INITIATIVE_META: Record<
  InitiativeType,
  { label: string; color: string; description: string }
> = {
  agent_initiative: {
    label: 'Agent',
    color: '#818cf8',
    description: 'Agent proposed or revised a plan',
  },
  human_override: {
    label: 'You',
    color: '#fbbf24',
    description: 'You steered the plan (feedback, reject, constraint)',
  },
  waiting_for_user: {
    label: 'Waiting',
    color: '#94a3b8',
    description: 'Agent paused for your input',
  },
  human_approve: {
    label: 'Approved',
    color: '#4ade80',
    description: 'You approved the final plan',
  },
  human_constraint: {
    label: 'Constraint',
    color: '#f472b6',
    description: 'You added a guardrail',
  },
}

function countByInitiative(log: LogEntry[]) {
  const counts: Partial<Record<InitiativeType, number>> = {}
  for (const entry of log) {
    if (entry.initiative) {
      counts[entry.initiative] = (counts[entry.initiative] ?? 0) + 1
    }
  }
  return counts
}

interface Props {
  log: LogEntry[]
}

export function InitiativeMeter({ log }: Props) {
  const counts = countByInitiative(log)
  const tagged = Object.values(counts).reduce((a, b) => a + (b ?? 0), 0)
  if (tagged === 0) return null

  const agentCount =
    (counts.agent_initiative ?? 0) + (counts.waiting_for_user ?? 0)
  const humanCount =
    (counts.human_override ?? 0) +
    (counts.human_approve ?? 0) +
    (counts.human_constraint ?? 0)
  const total = agentCount + humanCount || 1
  const agentPct = Math.round((agentCount / total) * 100)
  const humanPct = 100 - agentPct

  return (
    <div className="initiative-meter">
      <div className="initiative-meter-header">
        <span className="initiative-meter-title">Initiative balance</span>
        <span className="initiative-meter-sub">
          Agent {agentPct}% · You {humanPct}%
        </span>
      </div>

      <div className="initiative-meter-bar" role="img" aria-label={`Agent ${agentPct}%, You ${humanPct}%`}>
        <div
          className="initiative-segment initiative-agent"
          style={{ width: `${agentPct}%` }}
        />
        <div
          className="initiative-segment initiative-human"
          style={{ width: `${humanPct}%` }}
        />
      </div>

      <div className="initiative-legend">
        {(Object.keys(INITIATIVE_META) as InitiativeType[])
          .filter((k) => (counts[k] ?? 0) > 0)
          .map((k) => {
            const meta = INITIATIVE_META[k]
            return (
              <div key={k} className="initiative-legend-item" title={meta.description}>
                <span
                  className="initiative-dot"
                  style={{ background: meta.color }}
                />
                <span className="initiative-legend-label">{meta.label}</span>
                <span className="initiative-legend-count">{counts[k]}</span>
              </div>
            )
          })}
      </div>
    </div>
  )
}
