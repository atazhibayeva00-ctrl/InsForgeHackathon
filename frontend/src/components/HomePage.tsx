import { useCallback, useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  BarChart3,
  CheckCircle2,
  GitMerge,
  MessageSquarePlus,
  MessagesSquare,
  Repeat2,
  SearchCheck,
  ShieldCheck,
  SlidersHorizontal,
  UploadCloud,
} from 'lucide-react'
import { ParticleTextEffect } from './ParticleTextEffect'
import { Typewriter } from './Typewriter'
import VaporizeTextCycle, { Tag } from './VaporizeTextCycle'
import { MagneticText } from './MagneticText'
import { TextDisperse } from './TextDisperse'
import { SlideButton } from './SlideButton'
import { ContainerScroll } from './ContainerScroll'
import { DisplayCards, type DisplayCardData } from './DisplayCards'
import { BGPattern } from './BGPattern'
import './HomePage.css'

interface Props {
  onLaunch: () => void
}

const features: DisplayCardData[] = [
  {
    icon: MessagesSquare,
    title: 'Shared workspace',
    description:
      'You and the agent work on the same portfolio — it explains findings and asks before acting.',
    meta: 'TRANSPARENT BY DESIGN',
  },
  {
    icon: GitMerge,
    title: 'You stay in control',
    description:
      'Approve, reject, or revise every proposal. Add constraints like “don’t sell my employer stock.”',
    meta: 'HUMAN-IN-THE-LOOP',
  },
  {
    icon: ShieldCheck,
    title: 'Controlled autonomy',
    description:
      'Nothing is executed until you sign off. The agent adapts to your feedback and trade-offs.',
    meta: 'NOTHING WITHOUT APPROVAL',
  },
]

const SESSION_STAGES = [
  {
    id: 'load',
    label: 'Load Portfolio',
    icon: UploadCloud,
    image:
      'https://images.unsplash.com/photo-1554224155-6726b3ff858f?q=80&w=1200&auto=format&fit=crop',
    description:
      'Start with the sample portfolio or upload your own CSV so the shared workspace has holdings, prices, cash, and allocation context.',
  },
  {
    id: 'analyze',
    label: 'Agent Analyzes',
    icon: SearchCheck,
    image:
      'https://images.unsplash.com/photo-1642790106117-e829e14a795f?q=80&w=1200&auto=format&fit=crop',
    description:
      'The agent scans concentration risk, defensive allocation, unrealized gains, and goal fit before it suggests any action.',
  },
  {
    id: 'propose',
    label: 'Plan Proposed',
    icon: MessageSquarePlus,
    image:
      'https://images.unsplash.com/photo-1551836022-d5d88e9218df?q=80&w=1200&auto=format&fit=crop',
    description:
      'You get a clear rebalance proposal with findings, trade rationales, target allocation, and questions that still need human judgment.',
  },
  {
    id: 'revise',
    label: 'You Revise',
    icon: SlidersHorizontal,
    image:
      'https://images.unsplash.com/photo-1556761175-b413da4baf72?q=80&w=1200&auto=format&fit=crop',
    description:
      'Add constraints like “cannot sell employer stock,” reject plans, or ask for changes while the agent adapts inside the same session.',
  },
  {
    id: 'approve',
    label: 'Approve Cycle',
    icon: CheckCircle2,
    image:
      'https://images.unsplash.com/photo-1551288049-bbda38a10ad5?q=80&w=1200&auto=format&fit=crop',
    description:
      'Nothing is final until you approve. Approved trades are mock-applied so the portfolio state moves forward transparently.',
  },
  {
    id: 'repeat',
    label: 'Repeat Review',
    icon: Repeat2,
    image:
      'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?q=80&w=1200&auto=format&fit=crop',
    description:
      'Start the next review cycle from the updated portfolio, letting the collaboration become a realistic ongoing planning loop.',
  },
  {
    id: 'dashboard',
    label: 'Track Dashboard',
    icon: BarChart3,
    image:
      'https://images.unsplash.com/photo-1460925895917-afdab827c52f?q=80&w=1200&auto=format&fit=crop',
    description:
      'Watch collaboration score trends and expected portfolio value so the session has a visible record of progress over time.',
  },
]

const AUTO_PLAY_INTERVAL = 3000
const ITEM_HEIGHT = 65

const wrap = (min: number, max: number, v: number) => {
  const rangeSize = max - min
  return ((((v - min) % rangeSize) + rangeSize) % rangeSize) + min
}

export function HomePage({ onLaunch }: Props) {
  return (
    <div className="home">
      <BGPattern variant="grid" fill="rgba(129, 140, 248, 0.12)" size={28} mask="fade-edges" />
      <motion.div
        className="hero"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <h1 className="visually-hidden">Your investment copilot. You decide. It assists.</h1>
        <ParticleTextEffect
          words={['Your investment copilot.', 'You decide. It assists.']}
          height={360}
        />
        <div className="eyebrow-disperse-wrap">
          <TextDisperse className="text-disperse-eyebrow text-disperse-eyebrow-main">
            Human–Agent Collaboration
          </TextDisperse>
          <TextDisperse className="text-disperse-eyebrow text-disperse-eyebrow-sub">
            Inspired by Collaborative Gym
          </TextDisperse>
          <p className="research-context">
            This demo is built on top of the Stanford Collaborative Gym research paper and adapts its
            human-agent collaboration loop for personal investing.
          </p>
          <a
            className="cta-secondary research-link"
            href="https://arxiv.org/abs/2412.15701"
            target="_blank"
            rel="noreferrer"
          >
            View the research
          </a>
          <div className="hero-vapor">
            <VaporizeTextCycle
              texts={[
                'Most robo-advisors trade in a black box.',
                'This agent analyzes your portfolio.',
                'It proposes changes with clear reasoning.',
                'And waits for your approval — you decide.',
              ]}
              font={{
                fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                fontSize: '38px',
                fontWeight: 600,
              }}
              color="rgb(203, 213, 225)"
              spread={5}
              density={6}
              animation={{ vaporizeDuration: 2, fadeInDuration: 1, waitDuration: 1 }}
              direction="left-to-right"
              alignment="center"
              tag={Tag.P}
            />
          </div>
        </div>
      </motion.div>

      <ContainerScroll
        titleComponent={
          <div className="scroll-title">
            <p className="scroll-eyebrow">A preview of the workspace</p>
            <MagneticText
              className="magnetic-text-scroll"
              text="See every move before it happens"
              hoverText="Full transparency"
            />
          </div>
        }
      >
        <CopilotMock />
      </ContainerScroll>

      <div className="feature-section">
        <h2 className="section-heading">
          <Typewriter text="Built around you" speed={90} loop delay={2000} />
        </h2>
        <p className="section-sub">
          A collaborative loop where the agent proposes and you stay the decision-maker.
        </p>
        <DisplayCards cards={features} />
      </div>

      <div className="how">
        <MagneticText
          className="magnetic-text-how"
          text="How a session works"
          hoverText="Follow the loop"
        />
        <SessionStageCarousel />
      </div>

      <div className="post-how-launch">
        <p className="launch-eyebrow">Ready to step into the shared workspace?</p>
        <h2 className="launch-typewriter">
          <Typewriter text="Launch the copilot" speed={90} loop delay={2000} />
        </h2>
        <SlideButton label="Slide to launch" onComplete={onLaunch} />
      </div>
    </div>
  )
}

function SessionStageCarousel() {
  const [step, setStep] = useState(0)
  const [isPaused, setIsPaused] = useState(false)

  const currentIndex = ((step % SESSION_STAGES.length) + SESSION_STAGES.length) % SESSION_STAGES.length
  const nextStep = useCallback(() => setStep((prev) => prev + 1), [])

  const handleChipClick = (index: number) => {
    const diff = (index - currentIndex + SESSION_STAGES.length) % SESSION_STAGES.length
    if (diff > 0) setStep((s) => s + diff)
  }

  useEffect(() => {
    if (isPaused) return
    const interval = window.setInterval(nextStep, AUTO_PLAY_INTERVAL)
    return () => window.clearInterval(interval)
  }, [isPaused, nextStep])

  const getCardStatus = (index: number) => {
    const diff = index - currentIndex
    const len = SESSION_STAGES.length
    let normalizedDiff = diff

    if (diff > len / 2) normalizedDiff -= len
    if (diff < -len / 2) normalizedDiff += len

    if (normalizedDiff === 0) return 'active'
    if (normalizedDiff === -1) return 'prev'
    if (normalizedDiff === 1) return 'next'
    return 'hidden'
  }

  return (
    <div className="session-carousel">
      <div className="session-carousel-shell">
        <div className="session-stage-list">
          <div className="session-stage-fade top" />
          <div className="session-stage-fade bottom" />
          <div className="session-stage-track">
            {SESSION_STAGES.map((stage, index) => {
              const Icon = stage.icon
              const isActive = index === currentIndex
              const distance = index - currentIndex
              const wrappedDistance = wrap(
                -(SESSION_STAGES.length / 2),
                SESSION_STAGES.length / 2,
                distance,
              )

              return (
                <motion.div
                  key={stage.id}
                  style={{ height: ITEM_HEIGHT, width: 'fit-content' }}
                  animate={{
                    y: wrappedDistance * ITEM_HEIGHT,
                    opacity: 1 - Math.abs(wrappedDistance) * 0.25,
                  }}
                  transition={{
                    type: 'spring',
                    stiffness: 90,
                    damping: 22,
                    mass: 1,
                  }}
                  className="session-stage-chip-wrap"
                >
                  <button
                    type="button"
                    onClick={() => handleChipClick(index)}
                    onMouseEnter={() => setIsPaused(true)}
                    onMouseLeave={() => setIsPaused(false)}
                    className={isActive ? 'session-stage-chip active' : 'session-stage-chip'}
                  >
                    <span className="session-stage-icon">
                      <Icon size={18} strokeWidth={2.2} />
                    </span>
                    <span>{stage.label}</span>
                  </button>
                </motion.div>
              )
            })}
          </div>
        </div>

        <div className="session-card-area">
          <div className="session-card-stack">
            {SESSION_STAGES.map((stage, index) => {
              const status = getCardStatus(index)
              const isActive = status === 'active'
              const isPrev = status === 'prev'
              const isNext = status === 'next'

              return (
                <motion.div
                  key={stage.id}
                  initial={false}
                  animate={{
                    x: isActive ? 0 : isPrev ? -94 : isNext ? 94 : 0,
                    scale: isActive ? 1 : isPrev || isNext ? 0.86 : 0.7,
                    opacity: isActive ? 1 : isPrev || isNext ? 0.36 : 0,
                    rotate: isPrev ? -3 : isNext ? 3 : 0,
                    zIndex: isActive ? 20 : isPrev || isNext ? 10 : 0,
                    pointerEvents: isActive ? 'auto' : 'none',
                  }}
                  transition={{
                    type: 'spring',
                    stiffness: 260,
                    damping: 25,
                    mass: 0.8,
                  }}
                  className="session-card"
                >
                  <img
                    src={stage.image}
                    alt={stage.label}
                    className={isActive ? 'session-card-image active' : 'session-card-image'}
                  />

                  <AnimatePresence>
                    {isActive && (
                      <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 10 }}
                        className="session-card-copy"
                      >
                        <div className="session-card-pill">
                          {index + 1} / {SESSION_STAGES.length} · {stage.label}
                        </div>
                        <p>{stage.description}</p>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <div className={isActive ? 'session-live active' : 'session-live'}>
                    <span />
                    <strong>Live Session</strong>
                  </div>
                </motion.div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

/** Styled, static mock of the copilot UI shown inside the 3D scroll card. */
function CopilotMock() {
  return (
    <div className="copilot-mock">
      <div className="mock-topbar">
        <span className="mock-dot" />
        <span className="mock-dot" />
        <span className="mock-dot" />
        <span className="mock-title">Collaborative Investment Copilot</span>
      </div>
      <div className="mock-body">
        <div className="mock-panel">
          <div className="mock-panel-head">Portfolio</div>
          <div className="mock-row">
            <span>NVDA</span>
            <span className="mock-hot">32%</span>
          </div>
          <div className="mock-row">
            <span>AAPL</span>
            <span className="mock-hot">24%</span>
          </div>
          <div className="mock-row">
            <span>VOO</span>
            <span>18%</span>
          </div>
          <div className="mock-row">
            <span>Cash</span>
            <span>9%</span>
          </div>
          <div className="mock-flag">⚠ Concentration risk: NVDA + AAPL = 56%</div>
        </div>
        <div className="mock-panel">
          <div className="mock-panel-head">Agent proposal</div>
          <p className="mock-msg">
            I’d trim NVDA and AAPL to reduce single-stock risk and rotate into a
            diversified index. Approve to continue?
          </p>
          <div className="mock-trade sell">SELL · NVDA · −12%</div>
          <div className="mock-trade sell">SELL · AAPL · −8%</div>
          <div className="mock-trade buy">BUY · VOO · +20%</div>
          <div className="mock-actions">
            <span className="mock-btn approve">Approve</span>
            <span className="mock-btn revise">Revise</span>
            <span className="mock-btn reject">Reject</span>
          </div>
        </div>
      </div>
    </div>
  )
}
