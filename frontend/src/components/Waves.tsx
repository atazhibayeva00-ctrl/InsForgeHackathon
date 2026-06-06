import { useEffect, useRef, type CSSProperties } from 'react'
import { createNoise2D } from 'simplex-noise'
import { cn } from '../lib/utils'
import './Waves.css'

interface Point {
  x: number
  y: number
  wave: { x: number; y: number }
  cursor: { x: number; y: number; vx: number; vy: number }
}

interface WavesProps {
  className?: string
  strokeColor?: string
  backgroundColor?: string
  /** Target frames per second (lower = lighter). */
  fps?: number
}

const X_GAP = 20
const Y_GAP = 16
const MAX_LINES = 90
const MAX_POINTS = 60
const CURSOR_RADIUS = 160

export function Waves({
  className = '',
  strokeColor = 'rgba(255, 255, 255, 0.35)',
  backgroundColor = '#000000',
  fps = 30,
}: WavesProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const mouseRef = useRef({ sx: -9999, sy: -9999 })
  const pathsRef = useRef<SVGPathElement[]>([])
  const linesRef = useRef<Point[][]>([])
  const noiseRef = useRef<((x: number, y: number) => number) | null>(null)
  const rafRef = useRef<number | null>(null)
  const boundingRef = useRef<DOMRect | null>(null)
  const runningRef = useRef(false)
  const lastFrameRef = useRef(0)

  useEffect(() => {
    const container = containerRef.current
    const svg = svgRef.current
    if (!container || !svg) return

    noiseRef.current = createNoise2D()
    const frameInterval = 1000 / fps

    const setSize = () => {
      if (!containerRef.current || !svgRef.current) return
      boundingRef.current = containerRef.current.getBoundingClientRect()
      const { width, height } = boundingRef.current
      svgRef.current.style.width = `${width}px`
      svgRef.current.style.height = `${height}px`
    }

    const setLines = () => {
      if (!svgRef.current || !boundingRef.current) return

      const { width, height } = boundingRef.current
      linesRef.current = []
      pathsRef.current.forEach((path) => path.remove())
      pathsRef.current = []

      const totalLines = Math.min(MAX_LINES, Math.ceil((width + 120) / X_GAP))
      const totalPoints = Math.min(MAX_POINTS, Math.ceil((height + 20) / Y_GAP))
      const xStart = (width - X_GAP * totalLines) / 2
      const yStart = (height - Y_GAP * totalPoints) / 2

      for (let i = 0; i < totalLines; i++) {
        const points: Point[] = []
        for (let j = 0; j < totalPoints; j++) {
          points.push({
            x: xStart + X_GAP * i,
            y: yStart + Y_GAP * j,
            wave: { x: 0, y: 0 },
            cursor: { x: 0, y: 0, vx: 0, vy: 0 },
          })
        }

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path')
        path.classList.add('waves-line')
        path.setAttribute('fill', 'none')
        path.setAttribute('stroke', strokeColor)
        path.setAttribute('stroke-width', '1')
        svgRef.current.appendChild(path)
        pathsRef.current.push(path)
        linesRef.current.push(points)
      }
    }

    const onMouseMove = (e: MouseEvent) => {
      if (!boundingRef.current || !runningRef.current) return
      const mouse = mouseRef.current
      mouse.sx = e.clientX - boundingRef.current.left
      mouse.sy = e.clientY - boundingRef.current.top
    }

    const movePoints = (time: number) => {
      const lines = linesRef.current
      const mouse = mouseRef.current
      const noise = noiseRef.current
      if (!noise) return

      const radiusSq = CURSOR_RADIUS * CURSOR_RADIUS

      for (const points of lines) {
        for (const p of points) {
          const move = noise((p.x + time * 0.006) * 0.003, (p.y + time * 0.002) * 0.002) * 6
          p.wave.x = Math.cos(move) * 10
          p.wave.y = Math.sin(move) * 5

          const dx = p.x - mouse.sx
          const dy = p.y - mouse.sy
          const distSq = dx * dx + dy * dy
          if (distSq < radiusSq && distSq > 1) {
            const d = Math.sqrt(distSq)
            const s = 1 - d / CURSOR_RADIUS
            const f = s * s * 0.35
            p.cursor.vx += (dx / d) * f
            p.cursor.vy += (dy / d) * f
          }

          p.cursor.vx += -p.cursor.x * 0.02
          p.cursor.vy += -p.cursor.y * 0.02
          p.cursor.vx *= 0.9
          p.cursor.vy *= 0.9
          p.cursor.x = Math.max(-30, Math.min(30, p.cursor.x + p.cursor.vx))
          p.cursor.y = Math.max(-30, Math.min(30, p.cursor.y + p.cursor.vy))
        }
      }
    }

    const drawLines = () => {
      const lines = linesRef.current
      const paths = pathsRef.current

      for (let lIndex = 0; lIndex < lines.length; lIndex++) {
        const points = lines[lIndex]
        const path = paths[lIndex]
        if (!points || points.length < 2 || !path) continue

        const p0 = points[0]
        let d = `M ${p0.x + p0.wave.x} ${p0.y + p0.wave.y}`

        for (let i = 1; i < points.length; i++) {
          const p = points[i]
          d += `L ${p.x + p.wave.x + p.cursor.x} ${p.y + p.wave.y + p.cursor.y}`
        }

        path.setAttribute('d', d)
      }
    }

    const tick = (time: number) => {
      rafRef.current = requestAnimationFrame(tick)
      if (!runningRef.current) return

      if (time - lastFrameRef.current < frameInterval) return
      lastFrameRef.current = time

      movePoints(time)
      drawLines()
    }

    const start = () => {
      if (runningRef.current) return
      runningRef.current = true
      lastFrameRef.current = 0
      rafRef.current = requestAnimationFrame(tick)
    }

    const stop = () => {
      runningRef.current = false
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
    }

    const onResize = () => {
      setSize()
      setLines()
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !document.hidden) start()
        else stop()
      },
      { threshold: 0 },
    )

    const onVisibility = () => {
      if (document.hidden) stop()
      else if (container.getBoundingClientRect().height > 0) start()
    }

    setSize()
    setLines()
    observer.observe(container)
    window.addEventListener('resize', onResize, { passive: true })
    window.addEventListener('mousemove', onMouseMove, { passive: true })
    document.addEventListener('visibilitychange', onVisibility)

    if (!document.hidden) start()

    return () => {
      stop()
      observer.disconnect()
      window.removeEventListener('resize', onResize)
      window.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('visibilitychange', onVisibility)
      pathsRef.current.forEach((path) => path.remove())
      pathsRef.current = []
      linesRef.current = []
    }
  }, [strokeColor, fps])

  const containerStyle: CSSProperties = { backgroundColor }

  return (
    <div ref={containerRef} className={cn('waves', className)} style={containerStyle}>
      <svg ref={svgRef} className="waves-svg" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" />
    </div>
  )
}
