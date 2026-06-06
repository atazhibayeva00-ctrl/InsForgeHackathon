import { useCallback, useEffect, useRef, useState } from 'react'
import './TetrisLoading.css'

const TETRIS_PIECES = [
  { shape: [[1, 1, 1, 1]] },
  { shape: [[1, 1], [1, 1]] },
  { shape: [[0, 1, 0], [1, 1, 1]] },
  { shape: [[1, 0], [1, 0], [1, 1]] },
  { shape: [[0, 1, 1], [1, 1, 0]] },
  { shape: [[1, 1, 0], [0, 1, 1]] },
  { shape: [[0, 1], [0, 1], [1, 1]] },
]

interface Cell {
  filled: boolean
  clearing?: boolean
}

interface FallingPiece {
  shape: number[][]
  x: number
  y: number
}

interface TetrisLoadingProps {
  size?: 'sm' | 'md' | 'lg'
  speed?: 'slow' | 'normal' | 'fast'
  showLoadingText?: boolean
  loadingText?: string
}

const SIZE_CONFIG = {
  sm: { cellSize: 6, gridWidth: 8, gridHeight: 12 },
  md: { cellSize: 8, gridWidth: 10, gridHeight: 14 },
  lg: { cellSize: 10, gridWidth: 10, gridHeight: 16 },
}

const SPEED_CONFIG = {
  slow: 150,
  normal: 80,
  fast: 40,
}

function emptyGrid(width: number, height: number): Cell[][] {
  return Array.from({ length: height }, () =>
    Array.from({ length: width }, () => ({ filled: false })),
  )
}

export function TetrisLoading({
  size = 'sm',
  speed = 'normal',
  showLoadingText = true,
  loadingText = 'Loading...',
}: TetrisLoadingProps) {
  const config = SIZE_CONFIG[size]
  const fallSpeed = SPEED_CONFIG[speed]
  const [grid, setGrid] = useState<Cell[][]>(() =>
    emptyGrid(config.gridWidth, config.gridHeight),
  )
  const [fallingPiece, setFallingPiece] = useState<FallingPiece | null>(null)
  const [isClearing, setIsClearing] = useState(false)
  const frameRef = useRef<number | null>(null)
  const lastUpdateRef = useRef(0)

  const rotateShape = useCallback((shape: number[][]): number[][] => {
    const rows = shape.length
    const cols = shape[0].length
    const rotated = Array.from({ length: cols }, () => Array(rows).fill(0))

    for (let row = 0; row < rows; row += 1) {
      for (let col = 0; col < cols; col += 1) {
        rotated[col][rows - 1 - row] = shape[row][col]
      }
    }

    return rotated
  }, [])

  const createNewPiece = useCallback((): FallingPiece => {
    const pieceData = TETRIS_PIECES[Math.floor(Math.random() * TETRIS_PIECES.length)]
    let shape = pieceData.shape
    const rotations = Math.floor(Math.random() * 4)

    for (let i = 0; i < rotations; i += 1) {
      shape = rotateShape(shape)
    }

    const maxX = config.gridWidth - shape[0].length
    return {
      shape,
      x: Math.floor(Math.random() * (maxX + 1)),
      y: -shape.length,
    }
  }, [config.gridWidth, rotateShape])

  const canPlacePiece = useCallback(
    (piece: FallingPiece, newX: number, newY: number) => {
      for (let row = 0; row < piece.shape.length; row += 1) {
        for (let col = 0; col < piece.shape[row].length; col += 1) {
          if (!piece.shape[row][col]) continue

          const gridX = newX + col
          const gridY = newY + row

          if (gridX < 0 || gridX >= config.gridWidth || gridY >= config.gridHeight) {
            return false
          }
          if (gridY >= 0 && grid[gridY][gridX].filled) {
            return false
          }
        }
      }
      return true
    },
    [config.gridHeight, config.gridWidth, grid],
  )

  const placePiece = useCallback(
    (piece: FallingPiece) => {
      setGrid((prevGrid) => {
        const newGrid = prevGrid.map((row) => row.map((cell) => ({ ...cell })))

        for (let row = 0; row < piece.shape.length; row += 1) {
          for (let col = 0; col < piece.shape[row].length; col += 1) {
            if (!piece.shape[row][col]) continue

            const gridX = piece.x + col
            const gridY = piece.y + row
            if (
              gridY >= 0 &&
              gridY < config.gridHeight &&
              gridX >= 0 &&
              gridX < config.gridWidth
            ) {
              newGrid[gridY][gridX] = { filled: true }
            }
          }
        }

        return newGrid
      })
    },
    [config.gridHeight, config.gridWidth],
  )

  const clearFullLines = useCallback(() => {
    setGrid((prevGrid) => {
      const linesToClear = prevGrid
        .map((row, index) => (row.every((cell) => cell.filled) ? index : -1))
        .filter((index) => index !== -1)

      if (linesToClear.length === 0) return prevGrid

      setIsClearing(true)
      const markedGrid = prevGrid.map((row, rowIndex) =>
        linesToClear.includes(rowIndex)
          ? row.map((cell) => ({ ...cell, clearing: true }))
          : row,
      )

      window.setTimeout(() => {
        setGrid((currentGrid) => {
          const filteredGrid = currentGrid.filter(
            (_, index) => !linesToClear.includes(index),
          )
          setIsClearing(false)
          return [
            ...emptyGrid(config.gridWidth, linesToClear.length),
            ...filteredGrid,
          ]
        })
      }, 200)

      return markedGrid
    })
  }, [config.gridWidth])

  const checkAndReset = useCallback(() => {
    const topRows = grid.slice(0, 4)
    const needsReset = topRows.some(
      (row) => row.filter((cell) => cell.filled).length > config.gridWidth * 0.7,
    )

    if (!needsReset) return false

    setIsClearing(true)
    window.setTimeout(() => {
      setGrid(emptyGrid(config.gridWidth, config.gridHeight))
      setFallingPiece(null)
      setIsClearing(false)
    }, 500)
    return true
  }, [config.gridHeight, config.gridWidth, grid])

  useEffect(() => {
    const gameLoop = (timestamp: number) => {
      if (timestamp - lastUpdateRef.current >= fallSpeed) {
        lastUpdateRef.current = timestamp

        if (!isClearing && !checkAndReset()) {
          setFallingPiece((prevPiece) => {
            if (!prevPiece) return createNewPiece()

            const newY = prevPiece.y + 1
            if (canPlacePiece(prevPiece, prevPiece.x, newY)) {
              return { ...prevPiece, y: newY }
            }

            placePiece(prevPiece)
            window.setTimeout(clearFullLines, 50)
            return createNewPiece()
          })
        }
      }

      frameRef.current = requestAnimationFrame(gameLoop)
    }

    frameRef.current = requestAnimationFrame(gameLoop)
    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current)
    }
  }, [
    canPlacePiece,
    checkAndReset,
    clearFullLines,
    createNewPiece,
    fallSpeed,
    isClearing,
    placePiece,
  ])

  const displayGrid = grid.map((row) => row.map((cell) => ({ ...cell })))
  if (fallingPiece && !isClearing) {
    for (let row = 0; row < fallingPiece.shape.length; row += 1) {
      for (let col = 0; col < fallingPiece.shape[row].length; col += 1) {
        if (!fallingPiece.shape[row][col]) continue

        const gridX = fallingPiece.x + col
        const gridY = fallingPiece.y + row
        if (
          gridY >= 0 &&
          gridY < config.gridHeight &&
          gridX >= 0 &&
          gridX < config.gridWidth
        ) {
          displayGrid[gridY][gridX] = { filled: true }
        }
      }
    }
  }

  return (
    <div className="tetris-loading">
      <div
        className="tetris-board"
        style={
          {
            '--tetris-cell-size': `${config.cellSize}px`,
          } as React.CSSProperties
        }
        aria-hidden="true"
      >
        {displayGrid.map((row, rowIndex) => (
          <div className="tetris-row" key={rowIndex}>
            {row.map((cell, colIndex) => (
              <div
                className={[
                  'tetris-cell',
                  cell.filled ? 'tetris-cell-filled' : '',
                  cell.clearing ? 'tetris-cell-clearing' : '',
                ].join(' ')}
                key={`${rowIndex}-${colIndex}`}
              />
            ))}
          </div>
        ))}
      </div>

      {showLoadingText && <p className="tetris-loading-text">{loadingText}</p>}
    </div>
  )
}
