import { useRef, useState } from 'react'
import { FileSpreadsheet } from 'lucide-react'
import { cn } from '../lib/utils'
import './PortfolioFileUpload.css'

interface PortfolioFileUploadProps {
  onUpload: (file: File) => void | Promise<void>
  disabled?: boolean
  accept?: string
  className?: string
}

export function PortfolioFileUpload({
  onUpload,
  disabled = false,
  accept = '.csv',
  className,
}: PortfolioFileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)

  const openPicker = () => {
    if (disabled) return
    inputRef.current?.click()
  }

  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = e.target.files?.[0]
    if (!picked) return
    setFile(picked)
    await onUpload(picked)
  }

  const handleRemove = () => {
    setFile(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div className={cn('portfolio-upload', className)}>
      <div className="portfolio-upload-row">
        <div className="portfolio-upload-preview">
          {file ? (
            <FileSpreadsheet className="portfolio-upload-icon portfolio-upload-icon-active" />
          ) : (
            <FileSpreadsheet className="portfolio-upload-icon" />
          )}
        </div>

        <button
          type="button"
          className="portfolio-upload-trigger"
          onClick={openPicker}
          disabled={disabled}
        >
          {file ? 'Change file' : 'Upload CSV'}
        </button>
      </div>

      {file && (
        <div className="portfolio-upload-meta">
          <span className="portfolio-upload-name">{file.name}</span>
          <button
            type="button"
            className="portfolio-upload-remove"
            onClick={handleRemove}
            disabled={disabled}
          >
            Remove
          </button>
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="portfolio-upload-input"
        onChange={handleChange}
        disabled={disabled}
        tabIndex={-1}
      />
    </div>
  )
}
