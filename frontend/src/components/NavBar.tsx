import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import type { LucideIcon } from 'lucide-react'
import { cn } from '../lib/utils'
import './NavBar.css'

export interface NavItem {
  name: string
  id: string
  icon: LucideIcon
}

interface NavBarProps {
  items: NavItem[]
  active: string
  onChange: (id: string) => void
  className?: string
  /** When true, the bar stays hidden until the user scrolls down. */
  revealOnScroll?: boolean
}

export function NavBar({ items, active, onChange, className, revealOnScroll }: NavBarProps) {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    if (!revealOnScroll) return
    const onScroll = () => setScrolled(window.scrollY > 80)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [revealOnScroll])

  const hidden = revealOnScroll && !scrolled

  return (
    <div
      className={cn(
        'navbar',
        revealOnScroll && 'navbar-animated',
        hidden && 'navbar-hidden',
        className,
      )}
    >
      <div className="navbar-pill">
        {items.map((item) => {
          const Icon = item.icon
          const isActive = active === item.id
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onChange(item.id)}
              className={cn('nav-item', isActive && 'nav-item-active')}
            >
              <span className="nav-label">{item.name}</span>
              <span className="nav-icon">
                <Icon size={18} strokeWidth={2.5} />
              </span>
              {isActive && (
                <motion.div
                  layoutId="lamp"
                  className="nav-lamp"
                  initial={false}
                  transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                >
                  <div className="lamp-bar">
                    <div className="lamp-glow lamp-glow-1" />
                    <div className="lamp-glow lamp-glow-2" />
                    <div className="lamp-glow lamp-glow-3" />
                  </div>
                </motion.div>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
