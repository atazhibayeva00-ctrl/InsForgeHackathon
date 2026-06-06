import { useState, type ComponentProps, type ReactNode } from 'react'
import { motion } from 'framer-motion'
import { cn } from '../lib/utils'
import './TextDisperse.css'

interface Transform {
  x: number
  y: number
  rotationZ: number
}

const transforms: Transform[] = [
  { x: -0.8, y: -0.6, rotationZ: -29 },
  { x: -0.2, y: -0.4, rotationZ: -6 },
  { x: -0.05, y: 0.1, rotationZ: 12 },
  { x: -0.05, y: -0.1, rotationZ: -9 },
  { x: -0.1, y: 0.55, rotationZ: 3 },
  { x: 0, y: -0.1, rotationZ: 9 },
  { x: 0, y: 0.15, rotationZ: -12 },
  { x: 0, y: 0.15, rotationZ: -17 },
  { x: 0, y: -0.65, rotationZ: 9 },
  { x: 0.1, y: 0.4, rotationZ: 12 },
  { x: 0, y: -0.15, rotationZ: -9 },
  { x: 0.2, y: 0.15, rotationZ: 12 },
  { x: 0.8, y: 0.6, rotationZ: 20 },
]

type TextDisperseProps = Omit<ComponentProps<'div'>, 'children' | 'onMouseEnter' | 'onMouseLeave'> & {
  children: string
  onHover?: (isActive: boolean) => void
}

export function TextDisperse({
  children,
  onHover,
  className,
  ...props
}: TextDisperseProps) {
  const [isAnimated, setIsAnimated] = useState(false)

  const splitChars = (text: string): ReactNode[] => {
    return text.split('').map((char, i) => {
      const t = transforms[i % transforms.length]
      return (
        <motion.span
          key={`${char}-${i}`}
          custom={i}
          className="text-disperse-char"
          variants={{
            open: {
              x: `${t.x}em`,
              y: `${t.y}em`,
              rotateZ: t.rotationZ,
              transition: { duration: 0.75, ease: [0.33, 1, 0.68, 1] },
              zIndex: 1,
            },
            closed: {
              x: 0,
              y: 0,
              rotateZ: 0,
              transition: { duration: 0.75, ease: [0.33, 1, 0.68, 1] },
              zIndex: 0,
            },
          }}
          animate={isAnimated ? 'open' : 'closed'}
        >
          {char === ' ' ? '\u00A0' : char}
        </motion.span>
      )
    })
  }

  return (
    <div
      className={cn('text-disperse', className)}
      onMouseEnter={() => {
        onHover?.(true)
        setIsAnimated(true)
      }}
      onMouseLeave={() => {
        onHover?.(false)
        setIsAnimated(false)
      }}
      {...props}
    >
      {splitChars(children)}
    </div>
  )
}
