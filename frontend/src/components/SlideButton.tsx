import { useCallback, useRef, useState } from 'react'
import {
  AnimatePresence,
  motion,
  useMotionValue,
  useSpring,
  useTransform,
  type PanInfo,
} from 'framer-motion'
import { Check, Loader2, SendHorizontal } from 'lucide-react'
import './SlideButton.css'

const DRAG_MAX = 188
const DRAG_THRESHOLD = 0.9

const SPRING = { type: 'spring', stiffness: 400, damping: 40, mass: 0.8 } as const

type Status = 'idle' | 'loading' | 'success'

interface SlideButtonProps {
  label?: string
  onComplete: () => void
}

export function SlideButton({ label = 'Slide to launch', onComplete }: SlideButtonProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [status, setStatus] = useState<Status>('idle')
  const firedRef = useRef(false)

  const dragX = useMotionValue(0)
  const springX = useSpring(dragX, SPRING)
  const dragProgress = useTransform(springX, [0, DRAG_MAX], [0, 1])
  const fillWidth = useTransform(springX, (x) => x + 44)
  const labelOpacity = useTransform(springX, [0, DRAG_MAX * 0.6], [1, 0])

  const completed = status !== 'idle'

  const finish = useCallback(() => {
    if (firedRef.current) return
    firedRef.current = true
    setStatus('loading')
    dragX.set(DRAG_MAX)
    // brief loading spinner -> success check -> launch
    window.setTimeout(() => setStatus('success'), 800)
    window.setTimeout(onComplete, 1400)
  }, [dragX, onComplete])

  const handleDragStart = useCallback(() => {
    if (completed) return
    setIsDragging(true)
  }, [completed])

  const handleDrag = (_e: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    if (completed) return
    const newX = Math.max(0, Math.min(info.offset.x, DRAG_MAX))
    dragX.set(newX)
  }

  const handleDragEnd = () => {
    if (completed) return
    setIsDragging(false)
    if (dragProgress.get() >= DRAG_THRESHOLD) {
      finish()
    } else {
      dragX.set(0)
    }
  }

  // Click fallback (accessibility / non-drag): tapping the track launches too.
  const handleClickFallback = () => {
    if (!completed && !isDragging) finish()
  }

  return (
    <div
      className="slide-btn"
      role="button"
      tabIndex={0}
      aria-label={label}
      onClick={handleClickFallback}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          finish()
        }
      }}
    >
      <motion.div className="slide-fill" style={{ width: completed ? '100%' : fillWidth }} />

      {!completed && (
        <motion.span className="slide-label" style={{ opacity: labelOpacity }}>
          {label}
        </motion.span>
      )}

      <AnimatePresence>
        {completed && (
          <motion.span
            className="slide-done"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            {status === 'loading' ? 'Launching…' : 'Ready'}
          </motion.span>
        )}
      </AnimatePresence>

      {!completed && (
        <motion.div
          className={`slide-handle${isDragging ? ' dragging' : ''}`}
          drag="x"
          dragConstraints={{ left: 0, right: DRAG_MAX }}
          dragElastic={0.04}
          dragMomentum={false}
          onDragStart={handleDragStart}
          onDrag={handleDrag}
          onDragEnd={handleDragEnd}
          style={{ x: springX }}
        >
          <SendHorizontal size={18} strokeWidth={2.5} />
        </motion.div>
      )}

      {completed && (
        <motion.div
          className={`slide-handle done-handle ${status}`}
          initial={{ scale: 0.6, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
        >
          {status === 'loading' ? (
            <Loader2 className="spin" size={18} strokeWidth={2.5} />
          ) : (
            <Check size={18} strokeWidth={3} />
          )}
        </motion.div>
      )}
    </div>
  )
}
