import type { InitiativeType, LogEntry } from '../api/client'
import { InitiativeMeter } from './InitiativeMeter'

const INITIATIVE_LABELS: Record<InitiativeType, string> = {
  agent_initiative: 'Agent',
  human_override: 'Override',
  waiting_for_user: 'Waiting',
  human_approve: 'Approved',
  human_constraint: 'Constraint',
}

interface Props {
  log: LogEntry[]
}

export function CollaborationLog({ log }: Props) {
  if (log.length === 0) return null
  return (
    <div className="panel log-panel">
      <h2>Collaboration log</h2>
      <InitiativeMeter log={log} />
      <div className="log">
        {log.map((entry, i) => (
          <div key={i} className={`log-entry ${entry.role}`}>
            <span className="log-role">{entry.role === 'user' ? 'You' : 'Agent'}</span>
            {entry.initiative && (
              <span className={`initiative-badge initiative-${entry.initiative}`}>
                {INITIATIVE_LABELS[entry.initiative]}
              </span>
            )}
            <span className="log-content">{entry.content}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
