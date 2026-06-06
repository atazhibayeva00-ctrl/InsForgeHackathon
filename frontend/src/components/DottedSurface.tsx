import type { ComponentProps } from 'react'
import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { cn } from '../lib/utils'
import './DottedSurface.css'

type DottedSurfaceProps = Omit<ComponentProps<'div'>, 'ref'>

export function DottedSurface({ className, ...props }: DottedSurfaceProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const sceneRef = useRef<{
    scene: THREE.Scene
    camera: THREE.PerspectiveCamera
    renderer: THREE.WebGLRenderer
    geometry: THREE.BufferGeometry
    material: THREE.PointsMaterial
    animationId: number
  } | null>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const SEPARATION = 150
    const AMOUNTX = 40
    const AMOUNTY = 60
    let running = true
    let count = 0

    const scene = new THREE.Scene()
    scene.fog = new THREE.Fog(0x05080f, 2000, 10000)

    const camera = new THREE.PerspectiveCamera(
      60,
      window.innerWidth / window.innerHeight,
      1,
      10000,
    )
    camera.position.set(0, 355, 1220)

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
    renderer.setSize(window.innerWidth, window.innerHeight)
    renderer.setClearColor(0x05080f, 0)
    container.appendChild(renderer.domElement)

    const positions: number[] = []
    const colors: number[] = []

    const geometry = new THREE.BufferGeometry()

    for (let ix = 0; ix < AMOUNTX; ix++) {
      for (let iy = 0; iy < AMOUNTY; iy++) {
        const x = ix * SEPARATION - (AMOUNTX * SEPARATION) / 2
        const y = 0
        const z = iy * SEPARATION - (AMOUNTY * SEPARATION) / 2

        positions.push(x, y, z)
        // dark theme: soft indigo dots
        colors.push(0.55, 0.58, 0.85)
      }
    }

    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3))

    const material = new THREE.PointsMaterial({
      size: 8,
      vertexColors: true,
      transparent: true,
      opacity: 0.75,
      sizeAttenuation: true,
    })

    const points = new THREE.Points(geometry, material)
    scene.add(points)

    let animationId = 0

    const animate = () => {
      if (!running) return
      animationId = requestAnimationFrame(animate)

      const positionAttribute = geometry.attributes.position
      const positionArray = positionAttribute.array as Float32Array

      let i = 0
      for (let ix = 0; ix < AMOUNTX; ix++) {
        for (let iy = 0; iy < AMOUNTY; iy++) {
          const index = i * 3
          positionArray[index + 1] =
            Math.sin((ix + count) * 0.3) * 50 + Math.sin((iy + count) * 0.5) * 50
          i++
        }
      }

      positionAttribute.needsUpdate = true
      renderer.render(scene, camera)
      count += 0.1
    }

    const handleResize = () => {
      camera.aspect = window.innerWidth / window.innerHeight
      camera.updateProjectionMatrix()
      renderer.setSize(window.innerWidth, window.innerHeight)
    }

    const onVisibility = () => {
      if (document.hidden) {
        running = false
        cancelAnimationFrame(animationId)
      } else {
        running = true
        animate()
      }
    }

    window.addEventListener('resize', handleResize)
    document.addEventListener('visibilitychange', onVisibility)
    animate()

    sceneRef.current = {
      scene,
      camera,
      renderer,
      geometry,
      material,
      animationId,
    }

    return () => {
      running = false
      window.removeEventListener('resize', handleResize)
      document.removeEventListener('visibilitychange', onVisibility)
      cancelAnimationFrame(animationId)

      geometry.dispose()
      material.dispose()
      renderer.dispose()

      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement)
      }

      sceneRef.current = null
    }
  }, [])

  return (
    <div
      ref={containerRef}
      className={cn('dotted-surface', className)}
      aria-hidden="true"
      {...props}
    />
  )
}
