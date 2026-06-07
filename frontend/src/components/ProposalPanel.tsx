import { useState } from 'react'
import type { SessionState } from '../api/client'
import { PlanRevisionDiff } from './PlanRevisionDiff'
import { TetrisLoading } from './TetrisLoading'
import './AgentQuestions.css'

interface Props {
  state: SessionState
  busy: boolean
  agentStatus?: string | null
  onPropose: () => void
  onRevise: (feedback: string) => void
  onAnswer: (question: string, answer: string) => void
  onApprove: () => void
  onReject: () => void
  onStartNextCycle: () => void
  onEndSession: () => void
}

export function ProposalPanel({
  state,
  busy,
  agentStatus,
  onPropose,
  onRevise,
  onAnswer,
  onApprove,
  onReject,
  onStartNextCycle,
  onEndSession,
}: Props) {
  const [feedback, setFeedback] = useState('')
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const plan = state.plan
  const hasActiveSession = Boolean(state.session_id)
  const isCycleComplete = state.plan_status === 'cycle_complete'
  const isEmptyState = !plan && !isCycleComplete

  const emptyLoadingMessage = (() => {
    if (!isEmptyState) return null
    if (busy && agentStatus) return agentStatus
    if (busy) return 'Agent is analyzing the portfolio…'
    if (hasActiveSession) return 'Agent is preparing a plan…'
    return null
  })()

  const panelLoadingMessage =
    !isEmptyState && busy && agentStatus ? agentStatus : null

  const submitRevise = () => {
    if (!feedback.trim()) return
    onRevise(feedback.trim())
    setFeedback('')
  }

  const submitAnswer = (question: string) => {
    const answer = answers[question]?.trim()
    if (!answer) return
    onAnswer(question, answer)
    setAnswers((prev) => {
      const next = { ...prev }
      delete next[question]
      return next
    })
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Agent proposal</h2>
        {plan?.source && (
          <span className={`badge ${plan.source === 'llm' ? 'badge-ai' : 'badge-rule'}`}>
            {plan.source === 'llm' ? 'LLM agent' : 'rule-based'}
          </span>
        )}
      </div>

      {state.user_goal && (
        <p className="goal-context muted">
          Goal: <span>{state.user_goal}</span>
        </p>
      )}

      {panelLoadingMessage && (
        <div className="agent-progress" role="status" aria-live="polite">
          <TetrisLoading
            size="sm"
            speed="normal"
            loadingText={panelLoadingMessage}
          />
        </div>
      )}

      {isCycleComplete && (
        <div className="approved">
          <div className="approved-banner">
            Cycle {state.cycle_index} approved and mock-applied. Your portfolio has been updated for the next review.
          </div>
          {state.last_approved_plan && (
            <div className="agent-message">{state.last_approved_plan.message}</div>
          )}
          <div className="btn-row cycle-actions">
            <button className="btn primary" disabled={busy} onClick={onStartNextCycle}>
              Start next review
            </button>
            <button className="btn" disabled={busy} onClick={onEndSession}>
              End session
            </button>
          </div>
        </div>
      )}

      {isEmptyState && (
        <div className="empty">
          {emptyLoadingMessage ? (
            <div className="agent-progress empty-loading" role="status" aria-live="polite">
              <TetrisLoading
                size="sm"
                speed="normal"
                loadingText={emptyLoadingMessage}
              />
            </div>
          ) : (
            <>
              <p className="muted">
                The agent will analyze your portfolio and propose a plan. You stay in
                control — approve, reject, or revise before anything is final.
              </p>
              <button className="btn primary" disabled={busy} onClick={onPropose}>
                Analyze & propose plan
              </button>
            </>
          )}
        </div>
      )}

      {plan && !isCycleComplete && (
        <>
          {plan.source === 'fallback' && plan.fallback_reason && (
            <p className="fallback-hint muted">
              LLM unavailable ({plan.fallback_reason}). Showing rule-based plan instead.
            </p>
          )}
          <div className="agent-message">{plan.message}</div>

          {state.prior_plan && (
            <PlanRevisionDiff prior={state.prior_plan} current={plan} />
          )}

          {plan.findings.length > 0 && (
            <div className="block">
              <h3>Findings</h3>
              <ul>
                {plan.findings.map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
              </ul>
            </div>
          )}

          {plan.proposed_trades.length > 0 && (
            <div className="block">
              <h3>Proposed trades — pending your approval</h3>
              <table className="trades">
                <thead>
                  <tr>
                    <th>Action</th>
                    <th>Ticker</th>
                    <th>Shares</th>
                    <th>Rationale</th>
                  </tr>
                </thead>
                <tbody>
                  {plan.proposed_trades.map((t, i) => (
                    <tr key={i}>
                      <td>
                        <span className={`action ${t.action}`}>{t.action}</span>
                      </td>
                      <td className="ticker">{t.ticker}</td>
                      <td>{t.shares}</td>
                      <td className="muted">{t.rationale}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {plan.questions_for_user.length > 0 && !state.approved && (
            <div className="block agent-questions">
              <h3>Answer agent questions</h3>
              <p className="muted agent-questions-hint">
                Your answers steer the next revision — the agent will incorporate them
                before you approve.
              </p>
              {plan.questions_for_user.map((q, i) => (
                <div key={i} className="agent-question-card">
                  <p className="agent-question-text">{q}</p>
                  <textarea
                    placeholder="Your answer…"
                    value={answers[q] ?? ''}
                    onChange={(e) =>
                      setAnswers((prev) => ({ ...prev, [q]: e.target.value }))
                    }
                    rows={2}
                  />
                  <button
                    className="btn"
                    disabled={busy || !answers[q]?.trim()}
                    onClick={() => submitAnswer(q)}
                  >
                    Submit answer
                  </button>
                </div>
              ))}
            </div>
          )}

          {!state.approved && (
            <div className="block control">
              <h3>Your turn — stay in control</h3>
              <textarea
                placeholder="e.g. Don't sell AAPL — it's my employer stock."
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                rows={2}
              />
              <div className="btn-row">
                <button className="btn" disabled={busy || !feedback.trim()} onClick={submitRevise}>
                  Revise with feedback
                </button>
                <button className="btn approve" disabled={busy} onClick={onApprove}>
                  Approve plan
                </button>
                <button className="btn reject" disabled={busy} onClick={onReject}>
                  Reject
                </button>
              </div>
            </div>
          )}

          {state.approved && (
            <div className="approved">
              <div className="approved-banner">
                Cycle approved. Mock trades are being applied to the portfolio.
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
