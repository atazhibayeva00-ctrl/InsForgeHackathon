export interface Holding {
  ticker: string
  shares: number
  cost_basis: number
  current_price: number
  market_value: number
  weight_pct: number
  asset_class: string
}

export interface Trade {
  action: 'buy' | 'sell' | 'hold'
  ticker: string
  shares: number
  rationale: string
}

export interface Plan {
  message: string
  findings: string[]
  proposed_trades: Trade[]
  target_allocation: Record<string, number>
  questions_for_user: string[]
  needs_approval: boolean
  source?: string
  fallback_reason?: string
}

export type InitiativeType =
  | 'agent_initiative'
  | 'human_override'
  | 'waiting_for_user'
  | 'human_approve'
  | 'human_constraint'

export interface LogEntry {
  role: 'user' | 'agent'
  content: string
  initiative?: InitiativeType
}

export interface CollabMetrics {
  delivered: number
  task_performance: number
  collab_score: number
  plan_status: string
  constraints_respected: string[]
}

export interface InvestmentCycle {
  cycle_index: number
  approved_plan: Plan
  metrics: CollabMetrics
  portfolio_before: PortfolioContext
  portfolio_after: PortfolioContext
  applied_trades: Trade[]
  constraints: string[]
  approved_at: number
}

export interface PortfolioContext {
  total_value: number
  cash_balance: number
  summary: string
  flags: string[]
  allocation_by_ticker: Record<string, number>
  allocation_by_class: Record<string, number>
  holdings: Holding[]
}

export interface SessionState {
  session_id: string
  total_value: number
  cash_balance: number
  summary: string
  flags: string[]
  allocation_by_ticker: Record<string, number>
  allocation_by_class: Record<string, number>
  allocation_before?: Record<string, number> | null
  holdings: Holding[]
  user_goal: string
  constraints: string[]
  plan: Plan | null
  prior_plan: Plan | null
  approved: boolean
  collab_metrics: CollabMetrics
  plan_status: string
  cycle_index: number
  cycles: InvestmentCycle[]
  last_approved_plan: Plan | null
  log: LogEntry[]
}

export interface InitSessionResponse {
  message: string
  session_id: string
  user_id: string
  env_class: string
}

export interface CogymWsMessage {
  type:
    | 'start'
    | 'observation'
    | 'state'
    | 'team_member_action'
    | 'end'
  observation?: {
    portfolio?: PortfolioContext
    plan?: Plan | null
    plan_status?: string
    constraints?: string[]
    user_goal?: string
    cycles?: InvestmentCycle[]
    cycle_index?: number
    last_approved_plan?: Plan | null
  }
  chat_history?: Array<{ role: string; message: string; timestamp?: string }>
  info?: Record<string, unknown>
  result_dir?: string
}

export interface CogymResult {
  event_log: unknown[]
  task_performance: CollabMetrics | null
}

export const INVESTMENT_GOALS = [
  { id: 'balanced', label: 'Balanced growth', value: 'Balanced long-term growth with moderate risk' },
  { id: 'growth', label: 'Aggressive growth', value: 'Maximize long-term growth; higher risk tolerance' },
  { id: 'income', label: 'Income focus', value: 'Prioritize dividend income and capital preservation' },
  { id: 'preserve', label: 'Preserve capital', value: 'Protect capital with minimal volatility' },
] as const

function goalQuery(cash: number, userGoal?: string) {
  const params = new URLSearchParams({ cash_balance: String(cash) })
  if (userGoal) params.set('user_goal', userGoal)
  return params.toString()
}

function normalizeSession(raw: SessionState): SessionState {
  return {
    ...raw,
    prior_plan: raw.prior_plan ?? null,
    plan_status: raw.plan_status ?? (raw.approved ? 'approved' : 'none'),
    cycle_index: raw.cycle_index ?? 1,
    cycles: raw.cycles ?? [],
    last_approved_plan: raw.last_approved_plan ?? null,
    collab_metrics: raw.collab_metrics ?? {
      delivered: raw.approved ? 1 : 0,
      task_performance: 0,
      collab_score: 0,
      plan_status: raw.approved ? 'approved' : 'none',
      constraints_respected: raw.constraints ?? [],
    },
  }
}

async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || `Request failed: ${res.status}`)
  }
  return res.json()
}

async function postForm<T>(url: string, body: FormData): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    body,
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || `Request failed: ${res.status}`)
  }
  return res.json()
}

async function postSession(url: string, body: unknown = {}): Promise<SessionState> {
  const raw = await postJSON<SessionState>(url, body)
  return normalizeSession(raw)
}

export function loadSample(cash = 5000, userGoal?: string): Promise<SessionState> {
  return postSession(`/api/sample?${goalQuery(cash, userGoal)}`)
}

export function initSampleSession(
  cash = 5000,
  userGoal: string = INVESTMENT_GOALS[0].value,
  portfolioPreset?: 'complex',
): Promise<InitSessionResponse> {
  return postJSON('/api/init_env', {
    user_id: 'human',
    env_class: 'investment',
    env_args: {
      query: userGoal,
      cash_balance: cash,
      ...(portfolioPreset ? { portfolio_preset: portfolioPreset } : {}),
    },
  })
}

export function initComplexDemoSession(
  cash = 5000,
  userGoal: string = INVESTMENT_GOALS[0].value,
): Promise<InitSessionResponse> {
  return initSampleSession(cash, userGoal, 'complex')
}

export async function uploadPortfolio(
  file: File,
  cash = 5000,
  userGoal?: string,
): Promise<SessionState> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`/api/upload?${goalQuery(cash, userGoal)}`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || `Upload failed: ${res.status}`)
  }
  return normalizeSession(await res.json())
}

export async function initUploadedSession(
  file: File,
  cash = 5000,
  userGoal: string = INVESTMENT_GOALS[0].value,
): Promise<InitSessionResponse> {
  const form = new FormData()
  form.append('user_id', 'human')
  form.append('env_class', 'investment')
  form.append(
    'env_args',
    JSON.stringify({
      query: userGoal,
      cash_balance: cash,
    }),
  )
  form.append('file', file)
  return postForm('/api/init_env', form)
}

export async function postCogymAction(
  session_id: string,
  user_id: string,
  action: string,
): Promise<void> {
  await postJSON(`/api/post_action/${session_id}/${user_id}`, { action })
}

export function getCogymResult(session_id: string): Promise<CogymResult> {
  return fetch(`/api/result/${session_id}`).then(async (res) => {
    if (!res.ok) {
      const detail = await res.text()
      throw new Error(detail || `Request failed: ${res.status}`)
    }
    return res.json()
  })
}

export function openCogymSocket(
  session_id: string,
  user_id: string,
  onMessage: (message: CogymWsMessage) => void,
  onError: (error: Event) => void,
): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const socket = new WebSocket(`${protocol}//${window.location.host}/ws/${session_id}/${user_id}`)

  socket.addEventListener('open', () => {
    socket.send(JSON.stringify({ type: 'request_state' }))
  })
  socket.addEventListener('message', (event) => {
    onMessage(JSON.parse(event.data) as CogymWsMessage)
  })
  socket.addEventListener('error', onError)

  return socket
}

export function sessionFromObservation(
  session_id: string,
  message: CogymWsMessage,
  previous?: SessionState | null,
): SessionState | null {
  const obs = message.observation
  const portfolio = obs?.portfolio
  if (!obs || !portfolio) return previous ?? null

  const plan = obs.plan ?? null
  const cycles = obs.cycles ?? previous?.cycles ?? []
  const planStatus = obs.plan_status ?? 'none'
  const approved = planStatus === 'cycle_complete' || planStatus === 'approved'
  const lastCycle = cycles.length > 0 ? cycles[cycles.length - 1] : undefined
  const cycleIndex = obs.cycle_index ?? previous?.cycle_index ?? 1
  const isNewCycle = previous ? cycleIndex !== previous.cycle_index : false
  const chatLog: LogEntry[] = (message.chat_history ?? []).map((entry) => ({
    role: entry.role.includes('agent') ? 'agent' : 'user',
    content: entry.message,
  }))

  const log = [...chatLog]
  if (plan?.message && !log.some((entry) => entry.content === plan.message)) {
    log.push({ role: 'agent', content: plan.message, initiative: 'agent_initiative' })
  }
  if (approved && !log.some((entry) => entry.content.includes('mock-applied'))) {
    log.push({
      role: 'user',
      content: `Cycle ${lastCycle?.cycle_index ?? obs.cycle_index ?? 1} approved and mock-applied.`,
      initiative: 'human_approve',
    })
  }

  return normalizeSession({
    session_id,
    total_value: portfolio.total_value,
    cash_balance: portfolio.cash_balance,
    summary: portfolio.summary,
    flags: portfolio.flags,
    allocation_by_ticker: portfolio.allocation_by_ticker,
    allocation_by_class: portfolio.allocation_by_class,
    allocation_before:
      isNewCycle || !previous?.allocation_before
        ? portfolio.allocation_by_class
        : previous.allocation_before,
    holdings: portfolio.holdings,
    user_goal: obs.user_goal ?? previous?.user_goal ?? INVESTMENT_GOALS[0].value,
    constraints: obs.constraints ?? [],
    plan,
    plan_status: planStatus,
    prior_plan:
      planStatus === 'rejected' && previous?.plan
        ? previous.plan
        : previous?.plan && plan && previous.plan.message !== plan.message
          ? previous.plan
          : previous?.prior_plan ?? null,
    approved,
    collab_metrics: {
      delivered: lastCycle?.metrics.delivered ?? (approved ? 1 : 0),
      task_performance:
        lastCycle?.metrics.task_performance ??
        (approved ? previous?.collab_metrics.task_performance ?? 0 : 0),
      collab_score:
        lastCycle?.metrics.collab_score ??
        (approved ? previous?.collab_metrics.collab_score ?? 0 : 0),
      plan_status: planStatus,
      constraints_respected: obs.constraints ?? [],
    },
    cycle_index: cycleIndex,
    cycles,
    last_approved_plan:
      obs.last_approved_plan ?? lastCycle?.approved_plan ?? previous?.last_approved_plan ?? null,
    log,
  })
}

export function addConstraint(
  session_id: string,
  constraint: string,
): Promise<SessionState> {
  return postSession('/api/constraint', { session_id, constraint })
}

export function propose(
  session_id: string,
  user_goal?: string,
): Promise<SessionState> {
  return postSession('/api/propose', { session_id, user_goal })
}

export function revise(
  session_id: string,
  feedback: string,
): Promise<SessionState> {
  return postSession('/api/revise', { session_id, feedback })
}

export function answerQuestion(
  session_id: string,
  question: string,
  answer: string,
): Promise<SessionState> {
  return postSession('/api/answer', { session_id, question, answer })
}

export function approve(session_id: string): Promise<SessionState> {
  return postSession('/api/approve', { session_id })
}

export function reject(session_id: string): Promise<SessionState> {
  return postSession('/api/reject', { session_id })
}
