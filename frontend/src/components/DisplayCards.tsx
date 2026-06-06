import type { LucideIcon } from 'lucide-react'
import './DisplayCards.css'

export interface DisplayCardData {
  icon: LucideIcon
  title: string
  description: string
  meta: string
}

interface DisplayCardsProps {
  cards: DisplayCardData[]
}

export function DisplayCards({ cards }: DisplayCardsProps) {
  return (
    <div className="display-cards">
      {cards.map((card, i) => {
        const Icon = card.icon
        return (
          <div key={card.title} className="display-card" data-index={i}>
            <div className="display-card-head">
              <span className="display-card-chip">
                <Icon size={18} strokeWidth={2.2} />
              </span>
              <h3>{card.title}</h3>
            </div>
            <p className="display-card-desc">{card.description}</p>
            <p className="display-card-meta">{card.meta}</p>
          </div>
        )
      })}
    </div>
  )
}
