import * as React from 'react'
import { motion, type Variants } from 'framer-motion'
import { cn } from '../lib/utils'
import './AnimatedText.css'

interface AnimatedTextProps extends React.HTMLAttributes<HTMLDivElement> {
  text: string
  textClassName?: string
  underlineClassName?: string
  underlinePath?: string
  underlineHoverPath?: string
  underlineDuration?: number
}

const AnimatedText = React.forwardRef<HTMLDivElement, AnimatedTextProps>(
  (
    {
      text,
      textClassName,
      underlineClassName,
      underlinePath = 'M 0,10 Q 75,0 150,10 Q 225,20 300,10',
      underlineHoverPath = 'M 0,10 Q 75,20 150,10 Q 225,0 300,10',
      underlineDuration = 1.5,
      className,
      ...props
    },
    ref,
  ) => {
    const pathVariants: Variants = {
      hidden: {
        pathLength: 0,
        opacity: 0,
      },
      visible: {
        pathLength: 1,
        opacity: 1,
        transition: {
          pathLength: {
            duration: underlineDuration,
            ease: 'easeInOut',
            repeat: Infinity,
            repeatType: 'reverse',
            repeatDelay: 0.4,
          },
          opacity: { duration: 0.4 },
        },
      },
    }

    return (
      <div ref={ref} className={cn('animated-text', className)} {...props}>
        <div className="animated-text-inner">
          <motion.p
            className={cn('animated-text-content', textClassName)}
            initial={{ y: -20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.6 }}
            whileHover={{ scale: 1.02 }}
          >
            {text}
          </motion.p>

          <motion.svg
            width="100%"
            height="20"
            viewBox="0 0 300 20"
            preserveAspectRatio="none"
            className={cn('animated-text-underline', underlineClassName)}
          >
            <motion.path
              d={underlinePath}
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
              vectorEffect="non-scaling-stroke"
              fill="none"
              variants={pathVariants}
              initial="hidden"
              animate="visible"
              whileHover={{
                d: underlineHoverPath,
                transition: { duration: 0.8 },
              }}
            />
          </motion.svg>
        </div>
      </div>
    )
  },
)

AnimatedText.displayName = 'AnimatedText'

export { AnimatedText }
