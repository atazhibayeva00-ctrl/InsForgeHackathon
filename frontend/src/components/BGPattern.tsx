import type { ComponentProps, CSSProperties } from 'react'
import { cn } from '../lib/utils'
import './BGPattern.css'

type BGVariantType =
  | 'dots'
  | 'diagonal-stripes'
  | 'grid'
  | 'horizontal-lines'
  | 'vertical-lines'
  | 'checkerboard'

type BGMaskType =
  | 'fade-center'
  | 'fade-edges'
  | 'fade-top'
  | 'fade-bottom'
  | 'fade-left'
  | 'fade-right'
  | 'fade-x'
  | 'fade-y'
  | 'none'

type BGPatternProps = ComponentProps<'div'> & {
  variant?: BGVariantType
  mask?: BGMaskType
  size?: number
  fill?: string
}

const maskClassMap: Record<BGMaskType, string> = {
  'fade-edges': 'bg-pattern-mask-fade-edges',
  'fade-center': 'bg-pattern-mask-fade-center',
  'fade-top': 'bg-pattern-mask-fade-top',
  'fade-bottom': 'bg-pattern-mask-fade-bottom',
  'fade-left': 'bg-pattern-mask-fade-left',
  'fade-right': 'bg-pattern-mask-fade-right',
  'fade-x': 'bg-pattern-mask-fade-x',
  'fade-y': 'bg-pattern-mask-fade-y',
  none: '',
}

function getBgImage(variant: BGVariantType, fill: string, size: number) {
  switch (variant) {
    case 'dots':
      return `radial-gradient(${fill} 1px, transparent 1px)`
    case 'grid':
      return `linear-gradient(to right, ${fill} 1px, transparent 1px), linear-gradient(to bottom, ${fill} 1px, transparent 1px)`
    case 'diagonal-stripes':
      return `repeating-linear-gradient(45deg, ${fill}, ${fill} 1px, transparent 1px, transparent ${size}px)`
    case 'horizontal-lines':
      return `linear-gradient(to bottom, ${fill} 1px, transparent 1px)`
    case 'vertical-lines':
      return `linear-gradient(to right, ${fill} 1px, transparent 1px)`
    case 'checkerboard':
      return `linear-gradient(45deg, ${fill} 25%, transparent 25%), linear-gradient(-45deg, ${fill} 25%, transparent 25%), linear-gradient(45deg, transparent 75%, ${fill} 75%), linear-gradient(-45deg, transparent 75%, ${fill} 75%)`
    default:
      return undefined
  }
}

export function BGPattern({
  variant = 'grid',
  mask = 'none',
  size = 24,
  fill = '#252525',
  className,
  style,
  ...props
}: BGPatternProps) {
  const bgSize = `${size}px ${size}px`
  const backgroundImage = getBgImage(variant, fill, size)

  const patternStyle: CSSProperties = {
    backgroundImage,
    backgroundSize: bgSize,
    ...style,
  }

  return (
    <div
      className={cn('bg-pattern', maskClassMap[mask], className)}
      style={patternStyle}
      aria-hidden="true"
      {...props}
    />
  )
}

BGPattern.displayName = 'BGPattern'
