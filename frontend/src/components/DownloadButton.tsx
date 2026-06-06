import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '../lib/utils'
import './DownloadButton.css'

interface DownloadButtonProps {
  onDownload?: () => void | Promise<void>
  disabled?: boolean
  label?: string
}

export function DownloadButton({
  onDownload,
  disabled = false,
  label = 'Load sample portfolio',
}: DownloadButtonProps) {
  const [isDownloading, setIsDownloading] = useState(false)

  const handleDownloadClick = async () => {
    if (isDownloading || disabled) return

    setIsDownloading(true)
    const animation = new Promise<void>((resolve) => setTimeout(resolve, 3500))

    try {
      await Promise.all([Promise.resolve(onDownload?.()), animation])
    } finally {
      setIsDownloading(false)
    }
  }

  return (
    <div className="download-btn-wrap">
      <motion.button
        type="button"
        onClick={handleDownloadClick}
        disabled={disabled || isDownloading}
        className={cn('download-btn', isDownloading && 'download-btn-loading')}
        animate={{
          width: isDownloading ? 56 : 288,
        }}
        transition={{ duration: 0.4, ease: 'easeInOut' }}
        style={{ minWidth: isDownloading ? 56 : 288, height: 56 }}
      >
        <AnimatePresence>
          {isDownloading && (
            <motion.div
              className="download-btn-orbit"
              initial={{ opacity: 1 }}
              animate={{
                rotate: 360,
                x: [0, 27, 0, -27, 0],
                y: [0, -27, 0, 27, 0],
              }}
              exit={{ opacity: 0 }}
              transition={{
                duration: 3,
                ease: 'easeInOut',
                times: [0, 0.25, 0.5, 0.75, 1],
              }}
            />
          )}
        </AnimatePresence>

        <motion.div
          className="download-btn-circle"
          animate={
            isDownloading
              ? {
                  rotate: 180,
                  scale: [0.95, 1, 0.95],
                }
              : {}
          }
          transition={{
            duration: isDownloading ? 1 : 0.4,
            times: isDownloading ? [0, 0.7, 1] : undefined,
          }}
        >
          <motion.div
            className="download-btn-fill"
            initial={{ height: '0%' }}
            animate={isDownloading ? { height: '100%' } : { height: '0%' }}
            transition={{ duration: 3, ease: 'easeInOut' }}
          />

          <motion.svg
            className="download-btn-icon"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            initial={{ opacity: 1 }}
            animate={{ opacity: isDownloading ? 0 : 1 }}
            transition={{ duration: 0.2 }}
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M12 19V5m0 14-4-4m4 4 4-4"
            />
          </motion.svg>

          <motion.div
            className="download-btn-dot"
            initial={{ opacity: 0 }}
            animate={{ opacity: isDownloading ? 1 : 0 }}
            transition={{ duration: 0.2 }}
          />
        </motion.div>

        <AnimatePresence>
          {!isDownloading && (
            <motion.span
              className="download-btn-label"
              initial={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
            >
              {label}
            </motion.span>
          )}
        </AnimatePresence>
      </motion.button>
    </div>
  )
}
