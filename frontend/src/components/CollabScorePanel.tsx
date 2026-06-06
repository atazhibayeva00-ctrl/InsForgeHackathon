import type React from 'react'
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import type { CollabMetrics, InvestmentCycle } from '../api/client'
import './CollabScorePanel.css'

interface Props {
  metrics?: CollabMetrics | null
  cycles?: InvestmentCycle[]
  approved: boolean
}

function pct(v: number) {
  return `${Math.round(v * 100)}%`
}

const Strength = {
  None: 'none',
  Weak: 'weak',
  Moderate: 'moderate',
  Strong: 'strong',
} as const

type Strength = (typeof Strength)[keyof typeof Strength]

type Score = number | null

interface ScoreCardData {
  title: string
  description: string
  score: Score
  max: number
  actionLabel: string
}

type CounterContextType = {
  getNextIndex: () => number
}

const CounterContext = createContext<CounterContextType | undefined>(undefined)

const EMPTY_METRICS: CollabMetrics = {
  delivered: 0,
  task_performance: 0,
  collab_score: 0,
  plan_status: 'none',
  constraints_respected: [],
}

class ScoreUtils {
  static circumference(r: number): number {
    return 2 * Math.PI * r
  }

  static formatNumber(n: number) {
    return new Intl.NumberFormat('en-US').format(n)
  }

  static getStrength(score: Score, maxScore: number): Strength {
    if (score === null) return Strength.None
    const percent = score / maxScore
    if (percent >= 0.8) return Strength.Strong
    if (percent >= 0.4) return Strength.Moderate
    return Strength.Weak
  }

  static randomHash(length = 4): string {
    const chars = 'abcdef0123456789'
    const randomValues = crypto.getRandomValues(new Uint8Array(length))
    return [...randomValues].map((b) => chars[b % chars.length]).join('')
  }
}

function CounterProvider({ children }: { children: React.ReactNode }) {
  const counterRef = useRef(0)
  const getNextIndex = useCallback(() => counterRef.current++, [])
  return <CounterContext.Provider value={{ getNextIndex }}>{children}</CounterContext.Provider>
}

function useCounter() {
  const context = useContext(CounterContext)
  if (!context) throw new Error('useCounter must be used within a CounterProvider')
  return context.getNextIndex
}

function FinancialScoreCard({ children }: { children: React.ReactNode }) {
  const getNextIndex = useCounter()
  const indexRef = useRef<number | null>(null)
  const animationRef = useRef<number | null>(null)
  const [appearing, setAppearing] = useState(false)

  if (indexRef.current === null) {
    indexRef.current = getNextIndex()
  }

  useEffect(() => {
    const delay = 180 + indexRef.current! * 160
    animationRef.current = window.setTimeout(() => setAppearing(true), delay)
    return () => {
      if (animationRef.current !== null) window.clearTimeout(animationRef.current)
    }
  }, [])

  if (!appearing) return null

  return <article className="financial-score-card">{children}</article>
}

function FinancialScoreHeader({ title, strength }: { title: string; strength: Strength }) {
  return (
    <header className="financial-score-header">
      <h3>{title}</h3>
      {strength !== Strength.None && (
        <span className={`financial-score-badge ${strength}`}>{strength}</span>
      )}
    </header>
  )
}

function FinancialScoreHalfCircle({ value, max }: { value: Score; max: number }) {
  const strokeRef = useRef<SVGCircleElement>(null)
  const gradIdRef = useRef(`collab-grad-${ScoreUtils.randomHash()}`)
  const radius = 45
  const dist = ScoreUtils.circumference(radius)
  const distHalf = dist / 2
  const distFourth = distHalf / 2
  const strokeDasharray = `${distHalf} ${distHalf}`
  const strokeDashoffset = value !== null ? Math.min(value / max, 1) * -distHalf : -distFourth
  const strength = ScoreUtils.getStrength(value, max)
  const strengthColors: Record<Strength, string[]> = {
    none: ['hsl(220, 13%, 69%)', 'hsl(220, 9%, 46%)'],
    weak: ['hsl(0, 84%, 78%)', 'hsl(0, 84%, 56%)', 'hsl(0, 84%, 42%)'],
    moderate: ['hsl(38, 92%, 78%)', 'hsl(38, 92%, 58%)', 'hsl(38, 92%, 42%)'],
    strong: ['hsl(142, 71%, 78%)', 'hsl(142, 71%, 56%)', 'hsl(142, 71%, 38%)'],
  }
  const colorStops = strengthColors[strength]

  useEffect(() => {
    strokeRef.current?.animate(
      [
        { strokeDashoffset: '0', offset: 0 },
        { strokeDashoffset: '0', offset: 0.28 },
        { strokeDashoffset: strokeDashoffset.toString() },
      ],
      {
        duration: 1400,
        easing: 'cubic-bezier(0.65, 0, 0.35, 1)',
        fill: 'forwards',
      },
    )
  }, [strokeDashoffset, value, max])

  return (
    <svg className="financial-score-arc" viewBox="0 0 100 50" aria-hidden="true">
      <defs>
        <linearGradient id={gradIdRef.current} x1="0" y1="0" x2="1" y2="0">
          {colorStops.map((stop, i) => (
            <stop key={stop} offset={`${(100 / (colorStops.length - 1)) * i}%`} stopColor={stop} />
          ))}
        </linearGradient>
      </defs>
      <g fill="none" strokeWidth="10" transform="translate(50, 50.5)">
        <circle className="financial-score-arc-track" r={radius} />
        <circle
          ref={strokeRef}
          stroke={`url(#${gradIdRef.current})`}
          strokeDasharray={strokeDasharray}
          r={radius}
        />
      </g>
    </svg>
  )
}

function FinancialScoreDisplay({ value, max }: { value: Score; max: number }) {
  const hasValue = value !== null
  const digits = hasValue ? String(Math.floor(value)).split('') : []
  const label = hasValue ? `out of ${ScoreUtils.formatNumber(max)}` : 'No score'

  return (
    <div className="financial-score-display">
      <div className="financial-score-number">
        <span className="financial-score-ghost">0</span>
        <span className="financial-score-digits">
          {digits.map((digit, i) => (
            <span
              key={`${digit}-${i}`}
              className="financial-score-digit"
              style={{
                animationDelay: `${360 + i * 100}ms`,
                animationDuration: `${780 + i * 240}ms`,
              }}
            >
              {digit}
            </span>
          ))}
        </span>
      </div>
      <div className="financial-score-max">{label}</div>
    </div>
  )
}

function FinancialScore({ title, description, score, max, actionLabel }: ScoreCardData) {
  const strength = ScoreUtils.getStrength(score, max)

  return (
    <FinancialScoreCard>
      <FinancialScoreHeader title={title} strength={strength} />
      <div className="financial-score-meter">
        <FinancialScoreHalfCircle value={score} max={max} />
        <FinancialScoreDisplay value={score} max={max} />
      </div>
      <p className="financial-score-description">{description}</p>
      <button type="button" className="financial-score-button">
        {actionLabel}
      </button>
    </FinancialScoreCard>
  )
}

export function CollabScorePanel({ metrics, cycles = [], approved }: Props) {
  if (!approved) return null
  const m = metrics ?? EMPTY_METRICS
  const cards: ScoreCardData[] = [
    {
      title: 'Collaboration Score',
      description:
        'Measures how well the human-agent loop delivered a useful plan while preserving user control.',
      score: Math.round(m.collab_score * 100),
      max: 100,
      actionLabel: 'Review collaboration',
    },
    {
      title: 'Task Performance',
      description:
        'Tracks how much of the portfolio risk analysis was addressed by the approved proposal.',
      score: Math.round(m.task_performance * 100),
      max: 100,
      actionLabel: 'Inspect rationale',
    },
    {
      title: 'Session Delivery',
      description:
        'Confirms whether this review cycle produced an approved, mock-applied plan for the portfolio.',
      score: m.delivered ? 100 : null,
      max: 100,
      actionLabel: m.delivered ? 'Plan delivered' : 'Still in progress',
    },
  ]

  return (
    <section className="panel collab-score-panel">
      <header className="panel-header">
        <h2>Collaboration score</h2>
        <span className="collab-delivered-badge">
          {m.delivered ? 'Plan delivered' : 'In progress'}
        </span>
      </header>

      <CounterProvider>
        <div className="financial-score-grid">
          {cards.map((card) => (
            <FinancialScore key={card.title} {...card} />
          ))}
        </div>
      </CounterProvider>

      {(m.constraints_respected ?? []).length > 0 && (
        <div className="collab-constraints">
          <span className="collab-constraints-label">Constraints respected</span>
          <div className="collab-constraint-chips">
            {(m.constraints_respected ?? []).map((c) => (
              <span key={c} className="constraint-respected-chip">
                {c}
              </span>
            ))}
          </div>
        </div>
      )}

      {cycles.length > 0 && (
        <div className="collab-cycle-list">
          <span className="collab-constraints-label">Cycle history</span>
          {cycles.map((cycle) => (
            <div className="collab-cycle-row" key={cycle.cycle_index}>
              <span>Cycle {cycle.cycle_index}</span>
              <strong>{pct(cycle.metrics.collab_score)}</strong>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
