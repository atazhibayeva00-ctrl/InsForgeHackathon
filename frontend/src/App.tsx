import { useEffect, useRef, useState } from 'react'
import './App.css'
import { Gauge, Home, LineChart } from 'lucide-react'
import {
  INVESTMENT_GOALS,
  initSampleSession,
  initUploadedSession,
  getCogymResult,
  openCogymSocket,
  postCogymAction,
  sessionFromObservation,
  type SessionState,
  type InitSessionResponse,
} from './api/client'
import { PortfolioPanel } from './components/PortfolioPanel'
import { ProposalPanel } from './components/ProposalPanel'
import { CollaborationLog } from './components/CollaborationLog'
import { GoalWizard } from './components/GoalWizard'
import { AllocationCompare } from './components/AllocationCompare'
import { CollabScorePanel } from './components/CollabScorePanel'
import { NavBar, type NavItem } from './components/NavBar'
import { HomePage } from './components/HomePage'
import { DottedSurface } from './components/DottedSurface'
import { DownloadButton } from './components/DownloadButton'
import { PortfolioFileUpload } from './components/PortfolioFileUpload'
import { DashboardPanel } from './components/DashboardPanel'
import { TextScramble } from './components/TextScramble'

const NAV_ITEMS: NavItem[] = [
  { name: 'Home', id: 'home', icon: Home },
  { name: 'Copilot', id: 'app', icon: LineChart },
  { name: 'Dashboard', id: 'dashboard', icon: Gauge },
]

function App() {
  const [view, setView] = useState('home')
  const [state, setState] = useState<SessionState | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [cash, setCash] = useState(5000)
  const [constraint, setConstraint] = useState('')
  const [userGoal, setUserGoal] = useState<string>(INVESTMENT_GOALS[0].value)
  const [userId, setUserId] = useState('human')
  const [agentStatus, setAgentStatus] = useState<string | null>(null)
  const socketRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    return () => socketRef.current?.close()
  }, [])

  const connectSessionSocket = (session: InitSessionResponse) => {
    socketRef.current?.close()
    setUserId(session.user_id)
    socketRef.current = openCogymSocket(
      session.session_id,
      session.user_id,
      (message) => {
        if (message.type === 'observation' || message.type === 'state') {
          setState((prev) =>
            sessionFromObservation(session.session_id, message, prev),
          )
          const status = message.observation?.plan_status
          if (
            status === 'proposed' ||
            status === 'cycle_complete' ||
            status === 'approved' ||
            status === 'rejected'
          ) {
            setBusy(false)
            setAgentStatus(null)
          }
        }
        if (message.type === 'end') {
          setBusy(false)
          setAgentStatus(null)
          hydrateCollabMetrics(session.session_id)
        }
      },
      () => {
        setError('WebSocket connection failed')
        setBusy(false)
      },
    )
  }

  const startDistributedSession = async (fn: () => Promise<InitSessionResponse>) => {
    setBusy(true)
    setError(null)
    setState(null)
    setAgentStatus('Starting collaborative session…')
    try {
      const session = await fn()
      connectSessionSocket(session)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
      setBusy(false)
      setAgentStatus(null)
    }
  }

  const sendAction = async (action: string) => {
    if (!sid) return
    setBusy(true)
    setError(null)
    setAgentStatus(action === 'ANALYZE_PORTFOLIO()' ? 'Agent is analyzing the portfolio…' : 'Sending action…')
    try {
      await postCogymAction(sid, userId, action)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
      setBusy(false)
      setAgentStatus(null)
    }
  }

  const approveCycle = async () => {
    if (!sid) return
    setBusy(true)
    setError(null)
    setAgentStatus('Approving plan and mock-applying trades…')
    try {
      await postCogymAction(sid, userId, 'APPROVE_PLAN()')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
      setBusy(false)
      setAgentStatus(null)
    }
  }

  const startNextCycle = async () => {
    if (!sid) return
    setBusy(true)
    setError(null)
    setAgentStatus('Starting the next portfolio review cycle…')
    try {
      await postCogymAction(sid, userId, 'START_NEXT_CYCLE()')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
      setBusy(false)
      setAgentStatus(null)
    }
  }

  const endSession = async () => {
    if (!sid) return
    setBusy(true)
    setError(null)
    setAgentStatus('Ending session and calculating final metrics…')
    try {
      await postCogymAction(sid, userId, 'FINISH()')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
      setBusy(false)
      setAgentStatus(null)
    }
  }

  const hydrateCollabMetrics = async (sessionId: string) => {
    try {
      const result = await getCogymResult(sessionId)
      if (!result.task_performance) return
      const metrics = result.task_performance
      setState((prev) =>
        prev
          ? {
              ...prev,
              approved: metrics.plan_status === 'approved',
              collab_metrics: metrics,
            }
          : prev,
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load collaboration metrics')
    }
  }

  const reviseWithFeedback = async (feedback: string) => {
    if (!sid) return
    setBusy(true)
    setError(null)
    setAgentStatus('Agent is revising the plan with your feedback…')
    try {
      await postCogymAction(sid, userId, `SEND_TEAMMATE_MESSAGE(message=${feedback})`)
      await postCogymAction(sid, userId, 'REJECT_PLAN()')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
      setBusy(false)
      setAgentStatus(null)
    }
  }

  const answerQuestion = async (question: string, answer: string) => {
    await reviseWithFeedback(`Answer to "${question}": ${answer}`)
  }

  const addStandingConstraint = async (value: string) => {
    if (!sid) return
    setBusy(true)
    setError(null)
    setAgentStatus('Agent is updating the plan with your constraint…')
    try {
      await postCogymAction(sid, userId, `ADD_CONSTRAINT(constraint=${value})`)
      if (state?.plan && !state.approved) {
        await postCogymAction(sid, userId, 'REJECT_PLAN()')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
      setBusy(false)
      setAgentStatus(null)
    } finally {
      setConstraint('')
    }
  }

  const sid = state?.session_id

  return (
    <div className="page">
      <NavBar
        items={NAV_ITEMS}
        active={view}
        onChange={setView}
        revealOnScroll={view === 'home'}
      />

      {view === 'home' && <HomePage onLaunch={() => setView('app')} />}

      {view === 'dashboard' && (
        <div className="app">
          <DottedSurface />
          <DashboardPanel state={state} />
        </div>
      )}

      {view === 'app' && (
        <div className="app">
          <DottedSurface />
          <header className="topbar">
            <div>
              <TextScramble as="h1" duration={1.2} speed={0.035} trigger={view === 'app'}>
                Collaborative Investment Copilot
              </TextScramble>
              <p className="subtitle">
                Human-in-the-loop portfolio assistant — the agent proposes, you decide.
                Inspired by{' '}
                <a href="https://github.com/SALT-NLP/collaborative-gym" target="_blank">
                  Collaborative Gym
                </a>
                .
              </p>
            </div>
          </header>

          <div className="setup-bar">
            <GoalWizard
              value={userGoal}
              onChange={setUserGoal}
              disabled={busy}
            />

            <DownloadButton
              label="Load sample portfolio"
              disabled={busy}
              onDownload={() =>
                startDistributedSession(() => initSampleSession(cash, userGoal))
              }
            />

            <PortfolioFileUpload
              disabled={busy}
              onUpload={(f) =>
                startDistributedSession(() => initUploadedSession(f, cash, userGoal))
              }
            />

            <label className="cash">
              Cash $
              <input
                type="number"
                value={cash}
                min={0}
                step={500}
                onChange={(e) => setCash(Number(e.target.value))}
              />
            </label>

            {sid && (
              <div className="constraint-add">
                <input
                  type="text"
                  placeholder="Standing constraint (e.g. Cannot sell AAPL)"
                  value={constraint}
                  onChange={(e) => setConstraint(e.target.value)}
                />
                <button
                  className="btn"
                  disabled={busy || !constraint.trim()}
                  onClick={() => {
                    addStandingConstraint(constraint.trim())
                  }}
                >
                  Add
                </button>
              </div>
            )}
          </div>

          {state && state.constraints.length > 0 && (
            <div className="constraints-bar">
              <span className="muted">Constraints:</span>
              {state.constraints.map((c, i) => (
                <span className="chip" key={i}>
                  {c}
                </span>
              ))}
            </div>
          )}

          {error && <div className="error">{error}</div>}

          {!state && (
            <div className="welcome">
              <p>
                Load the sample portfolio or upload a CSV with columns{' '}
                <code>ticker, shares, current_price</code> (optional:{' '}
                <code>cost_basis, asset_class</code>) to begin.
              </p>
            </div>
          )}

          {state && state.plan && (
            <AllocationCompare
              before={state.allocation_before ?? state.allocation_by_class}
              proposed={state.plan.target_allocation}
              approved={state.approved}
            />
          )}

          {state && state.approved && (
            <CollabScorePanel
              metrics={state.collab_metrics}
              cycles={state.cycles}
              approved={state.approved}
            />
          )}

          {state && (
            <main className="grid">
              <PortfolioPanel state={state} />
              <ProposalPanel
                state={state}
                busy={busy}
                agentStatus={agentStatus}
                onPropose={() => sendAction('ANALYZE_PORTFOLIO()')}
                onRevise={reviseWithFeedback}
                onAnswer={answerQuestion}
                onApprove={approveCycle}
                onReject={() => sendAction('REJECT_PLAN()')}
                onStartNextCycle={startNextCycle}
                onEndSession={endSession}
              />
            </main>
          )}

          {state && <CollaborationLog log={state.log} />}
        </div>
      )}
    </div>
  )
}

export default App
