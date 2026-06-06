import { useEffect, useRef } from 'react'
import './ParticleTextEffect.css'

interface Vector2D {
  x: number
  y: number
}

interface RGB {
  r: number
  g: number
  b: number
}

// white particles
const PALETTE: RGB[] = [{ r: 255, g: 255, b: 255 }]

class Particle {
  pos: Vector2D = { x: 0, y: 0 }
  vel: Vector2D = { x: 0, y: 0 }
  acc: Vector2D = { x: 0, y: 0 }
  target: Vector2D = { x: 0, y: 0 }

  closeEnoughTarget = 100
  maxSpeed = 1.0
  maxForce = 0.1
  particleSize = 10
  isKilled = false

  startColor: RGB = { r: 0, g: 0, b: 0 }
  targetColor: RGB = { r: 0, g: 0, b: 0 }
  colorWeight = 0
  colorBlendRate = 0.01

  move() {
    let proximityMult = 1
    const distance = Math.sqrt(
      Math.pow(this.pos.x - this.target.x, 2) + Math.pow(this.pos.y - this.target.y, 2),
    )

    if (distance < this.closeEnoughTarget) {
      proximityMult = distance / this.closeEnoughTarget
    }

    const towardsTarget = {
      x: this.target.x - this.pos.x,
      y: this.target.y - this.pos.y,
    }

    const magnitude = Math.sqrt(
      towardsTarget.x * towardsTarget.x + towardsTarget.y * towardsTarget.y,
    )
    if (magnitude > 0) {
      towardsTarget.x = (towardsTarget.x / magnitude) * this.maxSpeed * proximityMult
      towardsTarget.y = (towardsTarget.y / magnitude) * this.maxSpeed * proximityMult
    }

    const steer = {
      x: towardsTarget.x - this.vel.x,
      y: towardsTarget.y - this.vel.y,
    }

    const steerMagnitude = Math.sqrt(steer.x * steer.x + steer.y * steer.y)
    if (steerMagnitude > 0) {
      steer.x = (steer.x / steerMagnitude) * this.maxForce
      steer.y = (steer.y / steerMagnitude) * this.maxForce
    }

    this.acc.x += steer.x
    this.acc.y += steer.y

    this.vel.x += this.acc.x
    this.vel.y += this.acc.y
    this.pos.x += this.vel.x
    this.pos.y += this.vel.y
    this.acc.x = 0
    this.acc.y = 0
  }

  draw(ctx: CanvasRenderingContext2D, drawAsPoints: boolean) {
    if (this.colorWeight < 1.0) {
      this.colorWeight = Math.min(this.colorWeight + this.colorBlendRate, 1.0)
    }

    const currentColor = {
      r: Math.round(this.startColor.r + (this.targetColor.r - this.startColor.r) * this.colorWeight),
      g: Math.round(this.startColor.g + (this.targetColor.g - this.startColor.g) * this.colorWeight),
      b: Math.round(this.startColor.b + (this.targetColor.b - this.startColor.b) * this.colorWeight),
    }

    ctx.fillStyle = `rgb(${currentColor.r}, ${currentColor.g}, ${currentColor.b})`
    if (drawAsPoints) {
      ctx.fillRect(this.pos.x, this.pos.y, 2, 2)
    } else {
      ctx.beginPath()
      ctx.arc(this.pos.x, this.pos.y, this.particleSize / 2, 0, Math.PI * 2)
      ctx.fill()
    }
  }

  kill(width: number, height: number) {
    if (!this.isKilled) {
      const randomPos = generateRandomPos(width / 2, height / 2, (width + height) / 2)
      this.target.x = randomPos.x
      this.target.y = randomPos.y

      this.startColor = {
        r: this.startColor.r + (this.targetColor.r - this.startColor.r) * this.colorWeight,
        g: this.startColor.g + (this.targetColor.g - this.startColor.g) * this.colorWeight,
        b: this.startColor.b + (this.targetColor.b - this.startColor.b) * this.colorWeight,
      }
      this.targetColor = { r: 0, g: 0, b: 0 }
      this.colorWeight = 0

      this.isKilled = true
    }
  }
}

function generateRandomPos(x: number, y: number, mag: number): Vector2D {
  const randomX = Math.random() * 1000
  const randomY = Math.random() * 500

  const direction = {
    x: randomX - x,
    y: randomY - y,
  }

  const magnitude = Math.sqrt(direction.x * direction.x + direction.y * direction.y)
  if (magnitude > 0) {
    direction.x = (direction.x / magnitude) * mag
    direction.y = (direction.y / magnitude) * mag
  }

  return {
    x: x + direction.x,
    y: y + direction.y,
  }
}

interface ParticleTextEffectProps {
  words?: string[]
  /** Visible CSS height of the effect, in px. */
  height?: number
}

const DEFAULT_WORDS = ['Your investment copilot.', 'You decide. It assists.']

export function ParticleTextEffect({
  words = DEFAULT_WORDS,
  height = 240,
}: ParticleTextEffectProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animationRef = useRef<number>(0)
  const particlesRef = useRef<Particle[]>([])
  const frameCountRef = useRef(0)
  const wordIndexRef = useRef(0)
  const mouseRef = useRef({ x: 0, y: 0, isPressed: false, isRightClick: false })

  const pixelSteps = 4
  const drawAsPoints = true

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const wrapper = canvas.parentElement
    if (!wrapper) return

    const dpr = Math.min(window.devicePixelRatio || 1, 2)

    function sizeCanvas() {
      if (!canvas || !wrapper) return
      const cssW = wrapper.clientWidth
      const cssH = height
      canvas.width = Math.floor(cssW * dpr)
      canvas.height = Math.floor(cssH * dpr)
      canvas.style.width = `${cssW}px`
      canvas.style.height = `${cssH}px`
    }

    function nextWord(word: string) {
      if (!canvas) return
      const offscreen = document.createElement('canvas')
      offscreen.width = canvas.width
      offscreen.height = canvas.height
      const offCtx = offscreen.getContext('2d')
      if (!offCtx) return

      // auto-fit the font so the phrase fills most of the width
      let fontSize = Math.floor(canvas.height * 0.6)
      const fontFor = (size: number) =>
        `bold ${size}px -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif`
      offCtx.font = fontFor(fontSize)
      while (offCtx.measureText(word).width > canvas.width * 0.9 && fontSize > 8) {
        fontSize -= 2
        offCtx.font = fontFor(fontSize)
      }
      offCtx.fillStyle = 'white'
      offCtx.textAlign = 'center'
      offCtx.textBaseline = 'middle'
      offCtx.fillText(word, canvas.width / 2, canvas.height / 2)

      const pixels = offCtx.getImageData(0, 0, canvas.width, canvas.height).data

      const newColor = PALETTE[Math.floor(Math.random() * PALETTE.length)]
      const particles = particlesRef.current
      let particleIndex = 0

      const coordsIndexes: number[] = []
      for (let i = 0; i < pixels.length; i += pixelSteps * 4) {
        coordsIndexes.push(i)
      }
      for (let i = coordsIndexes.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1))
        ;[coordsIndexes[i], coordsIndexes[j]] = [coordsIndexes[j], coordsIndexes[i]]
      }

      for (const pixelIndex of coordsIndexes) {
        const alpha = pixels[pixelIndex + 3]
        if (alpha > 0) {
          const x = (pixelIndex / 4) % canvas.width
          const y = Math.floor(pixelIndex / 4 / canvas.width)

          let particle: Particle
          if (particleIndex < particles.length) {
            particle = particles[particleIndex]
            particle.isKilled = false
            particleIndex++
          } else {
            particle = new Particle()
            const randomPos = generateRandomPos(
              canvas.width / 2,
              canvas.height / 2,
              (canvas.width + canvas.height) / 2,
            )
            particle.pos.x = randomPos.x
            particle.pos.y = randomPos.y
            particle.maxSpeed = Math.random() * 6 + 4
            particle.maxForce = particle.maxSpeed * 0.05
            particle.particleSize = Math.random() * 6 + 6
            particle.colorBlendRate = Math.random() * 0.0275 + 0.0025
            particles.push(particle)
          }

          particle.startColor = {
            r: particle.startColor.r + (particle.targetColor.r - particle.startColor.r) * particle.colorWeight,
            g: particle.startColor.g + (particle.targetColor.g - particle.startColor.g) * particle.colorWeight,
            b: particle.startColor.b + (particle.targetColor.b - particle.startColor.b) * particle.colorWeight,
          }
          particle.targetColor = newColor
          particle.colorWeight = 0
          particle.target.x = x
          particle.target.y = y
        }
      }

      for (let i = particleIndex; i < particles.length; i++) {
        particles[i].kill(canvas.width, canvas.height)
      }
    }

    function animate() {
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      const particles = particlesRef.current

      // motion-blur trail on the near-black page background
      ctx.fillStyle = 'rgba(0, 0, 0, 0.1)'
      ctx.fillRect(0, 0, canvas.width, canvas.height)

      for (let i = particles.length - 1; i >= 0; i--) {
        const particle = particles[i]
        particle.move()
        particle.draw(ctx, drawAsPoints)

        if (particle.isKilled) {
          if (
            particle.pos.x < 0 ||
            particle.pos.x > canvas.width ||
            particle.pos.y < 0 ||
            particle.pos.y > canvas.height
          ) {
            particles.splice(i, 1)
          }
        }
      }

      if (mouseRef.current.isPressed && mouseRef.current.isRightClick) {
        particles.forEach((particle) => {
          const distance = Math.sqrt(
            Math.pow(particle.pos.x - mouseRef.current.x, 2) +
              Math.pow(particle.pos.y - mouseRef.current.y, 2),
          )
          if (distance < 50) {
            particle.kill(canvas.width, canvas.height)
          }
        })
      }

      frameCountRef.current++
      if (frameCountRef.current % 240 === 0) {
        wordIndexRef.current = (wordIndexRef.current + 1) % words.length
        nextWord(words[wordIndexRef.current])
      }

      animationRef.current = requestAnimationFrame(animate)
    }

    sizeCanvas()
    nextWord(words[0])
    animate()

    function toCanvasCoords(e: MouseEvent) {
      if (!canvas) return { x: 0, y: 0 }
      const rect = canvas.getBoundingClientRect()
      const scaleX = canvas.width / rect.width
      const scaleY = canvas.height / rect.height
      return { x: (e.clientX - rect.left) * scaleX, y: (e.clientY - rect.top) * scaleY }
    }
    const handleMouseDown = (e: MouseEvent) => {
      mouseRef.current.isPressed = true
      mouseRef.current.isRightClick = e.button === 2
      const { x, y } = toCanvasCoords(e)
      mouseRef.current.x = x
      mouseRef.current.y = y
    }
    const handleMouseUp = () => {
      mouseRef.current.isPressed = false
      mouseRef.current.isRightClick = false
    }
    const handleMouseMove = (e: MouseEvent) => {
      const { x, y } = toCanvasCoords(e)
      mouseRef.current.x = x
      mouseRef.current.y = y
    }
    const handleContextMenu = (e: MouseEvent) => e.preventDefault()
    const handleResize = () => {
      sizeCanvas()
      particlesRef.current = []
      nextWord(words[wordIndexRef.current])
    }

    canvas.addEventListener('mousedown', handleMouseDown)
    canvas.addEventListener('mouseup', handleMouseUp)
    canvas.addEventListener('mousemove', handleMouseMove)
    canvas.addEventListener('contextmenu', handleContextMenu)
    window.addEventListener('resize', handleResize)

    return () => {
      cancelAnimationFrame(animationRef.current)
      canvas.removeEventListener('mousedown', handleMouseDown)
      canvas.removeEventListener('mouseup', handleMouseUp)
      canvas.removeEventListener('mousemove', handleMouseMove)
      canvas.removeEventListener('contextmenu', handleContextMenu)
      window.removeEventListener('resize', handleResize)
      particlesRef.current = []
      frameCountRef.current = 0
      wordIndexRef.current = 0
    }
  }, [words, height])

  return (
    <div className="particle-text" style={{ height }}>
      <canvas ref={canvasRef} className="particle-text-canvas" />
    </div>
  )
}
