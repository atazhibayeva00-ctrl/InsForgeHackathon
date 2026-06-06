import { type ElementType, type JSX, useEffect, useMemo, useRef, useState } from 'react'
import { motion, type MotionProps } from 'framer-motion'

type TextScrambleProps = {
  children: string
  duration?: number
  speed?: number
  characterSet?: string
  as?: ElementType
  className?: string
  trigger?: boolean
  onScrambleComplete?: () => void
} & MotionProps

const defaultChars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'

export function TextScramble({
  children,
  duration = 0.8,
  speed = 0.04,
  characterSet = defaultChars,
  className,
  as: Component = 'p',
  trigger = true,
  onScrambleComplete,
  ...props
}: TextScrambleProps) {
  const MotionComponent = useMemo(
    () => motion.create(Component as keyof JSX.IntrinsicElements),
    [Component],
  )
  const [displayText, setDisplayText] = useState(children)
  const isAnimatingRef = useRef(false)

  useEffect(() => {
    setDisplayText(children)
  }, [children])

  useEffect(() => {
    if (!trigger || isAnimatingRef.current) return

    isAnimatingRef.current = true
    const steps = duration / speed
    let step = 0

    const interval = window.setInterval(() => {
      let scrambled = ''
      const progress = step / steps

      for (let i = 0; i < children.length; i += 1) {
        if (children[i] === ' ') {
          scrambled += ' '
          continue
        }

        scrambled +=
          progress * children.length > i
            ? children[i]
            : characterSet[Math.floor(Math.random() * characterSet.length)]
      }

      setDisplayText(scrambled)
      step += 1

      if (step > steps) {
        window.clearInterval(interval)
        setDisplayText(children)
        isAnimatingRef.current = false
        onScrambleComplete?.()
      }
    }, speed * 1000)

    return () => {
      window.clearInterval(interval)
      isAnimatingRef.current = false
    }
  }, [characterSet, children, duration, onScrambleComplete, speed, trigger])

  return (
    <MotionComponent className={className} {...props}>
      {displayText}
    </MotionComponent>
  )
}
