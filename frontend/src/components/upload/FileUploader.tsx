import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { motion, AnimatePresence } from 'framer-motion'
import clsx from 'clsx'
import { formatFileSize } from '../../services/storage'

interface FileUploaderProps {
  onFileSelect: (file: File) => void
  uploading?: boolean
  progress?: number
  uploadedBytes?: number
  totalBytes?: number
  accept?: Record<string, string[]>
  maxSize?: number
  label?: string
  sublabel?: string
  error?: string | null
  currentFile?: File | null
}

const DEFAULT_ACCEPT = {
  'audio/mpeg': ['.mp3'],
  'audio/wav': ['.wav'],
  'audio/flac': ['.flac'],
  'audio/mp4': ['.m4a', '.mp4'],
  'audio/aac': ['.aac'],
  'audio/ogg': ['.ogg'],
  'audio/x-wav': ['.wav'],
  'audio/x-flac': ['.flac'],
  'audio/webm': ['.webm'],
}

export default function FileUploader({
  onFileSelect,
  uploading = false,
  progress = 0,
  uploadedBytes = 0,
  totalBytes = 0,
  accept = DEFAULT_ACCEPT,
  maxSize = 200 * 1024 * 1024,
  label = 'Drop your audio file here',
  sublabel = 'MP3, WAV, FLAC, M4A up to 200MB',
  error,
  currentFile,
}: FileUploaderProps) {
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles[0]) {
        onFileSelect(acceptedFiles[0])
      }
    },
    [onFileSelect]
  )

  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    onDrop,
    accept,
    maxSize,
    maxFiles: 1,
    disabled: uploading,
  })

  const dropError =
    fileRejections[0]?.errors[0]?.message ||
    (fileRejections[0]?.errors[0]?.code === 'file-too-large' ? 'File is too large (max 200MB)' : null)

  return (
    <div className="w-full">
      <div
        {...getRootProps()}
        className={clsx(
          'relative border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-300',
          isDragActive
            ? 'border-accent-primary bg-accent-primary/5 dropzone-active'
            : uploading
            ? 'border-border cursor-not-allowed'
            : 'border-border hover:border-border-light hover:bg-bg-hover'
        )}
      >
        <input {...getInputProps()} />

        <AnimatePresence mode="wait">
          {uploading ? (
            <motion.div
              key="uploading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="space-y-4"
            >
              <div className="flex justify-center">
                <div className="relative w-16 h-16">
                  <svg className="w-16 h-16 -rotate-90" viewBox="0 0 64 64">
                    <circle cx="32" cy="32" r="28" fill="none" stroke="#1E293B" strokeWidth="4" />
                    <circle
                      cx="32" cy="32" r="28"
                      fill="none"
                      stroke="#6366F1"
                      strokeWidth="4"
                      strokeLinecap="round"
                      strokeDasharray={`${2 * Math.PI * 28}`}
                      strokeDashoffset={`${2 * Math.PI * 28 * (1 - progress / 100)}`}
                      className="transition-all duration-300"
                    />
                  </svg>
                  <span className="absolute inset-0 flex items-center justify-center text-sm font-bold text-accent-primary">
                    {progress}%
                  </span>
                </div>
              </div>
              <div>
                <p className="text-sm font-semibold text-text-primary">Uploading...</p>
                {totalBytes > 0 && (
                  <p className="text-xs text-text-muted mt-1">
                    {formatFileSize(uploadedBytes)} / {formatFileSize(totalBytes)}
                  </p>
                )}
              </div>
            </motion.div>
          ) : currentFile ? (
            <motion.div
              key="file"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              className="space-y-3"
            >
              <div className="w-12 h-12 mx-auto rounded-xl bg-accent-green/20 border border-accent-green/30 flex items-center justify-center">
                <svg className="w-6 h-6 text-accent-green" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-text-primary truncate">{currentFile.name}</p>
                <p className="text-xs text-text-muted">{formatFileSize(currentFile.size)}</p>
              </div>
              <p className="text-xs text-accent-primary">Click or drop to change file</p>
            </motion.div>
          ) : (
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="space-y-4"
            >
              <div className={clsx(
                'w-14 h-14 mx-auto rounded-2xl border-2 border-dashed flex items-center justify-center transition-all',
                isDragActive ? 'border-accent-primary bg-accent-primary/10 scale-110' : 'border-border'
              )}>
                <svg className={clsx('w-6 h-6 transition-colors', isDragActive ? 'text-accent-primary' : 'text-text-muted')} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-text-primary">{label}</p>
                <p className="text-xs text-text-muted mt-1">{sublabel}</p>
              </div>
              <span className="inline-block px-4 py-1.5 rounded-lg bg-bg-hover border border-border text-xs text-text-secondary hover:border-accent-primary transition-all">
                {isDragActive ? 'Release to upload' : 'Browse files'}
              </span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Errors */}
      <AnimatePresence>
        {(error || dropError) && (
          <motion.div
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            className="mt-2 flex items-center gap-2 text-xs text-red-400 px-1"
          >
            <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {error || dropError}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
