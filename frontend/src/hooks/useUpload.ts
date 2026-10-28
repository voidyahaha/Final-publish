import { useState, useCallback, useRef } from 'react'
import { validateAudioFile } from '../services/storage'
import { api } from '../services/api'
import { useAppStore } from '../store'
import toast from 'react-hot-toast'

export interface UseUploadReturn {
  uploading: boolean
  uploadProgress: number
  uploadedBytes: number
  totalBytes: number
  uploadFile: (
    file: File,
    userId: string,
    folder?: 'originals' | 'vocals' | 'instrumentals'
  ) => Promise<{ storagePath: string; downloadUrl: string; fileName: string; size: number } | null>
  cancelUpload: () => void
  error: string | null
}

export function useUpload(): UseUploadReturn {
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadedBytes, setUploadedBytes] = useState(0)
  const [totalBytes, setTotalBytes] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const taskRef = useRef<any>(null)

  const cancelUpload = useCallback(() => {
    if (taskRef.current) {
      taskRef.current.cancel()
      taskRef.current = null
      setUploading(false)
      setUploadProgress(0)
      toast('Upload cancelled', { icon: '⏹️' })
    }
  }, [])

  const uploadFile = useCallback(
    async (
      file: File,
      userId: string,
      folder: 'originals' | 'vocals' | 'instrumentals' = 'originals'
    ) => {
      const validation = validateAudioFile(file)
      if (!validation.valid) {
        setError(validation.error || 'Invalid file')
        toast.error(validation.error || 'Invalid file')
        return null
      }

      setError(null)
      setUploading(true)
      setUploadProgress(0)

      try {
        const result = await api.uploadFile(file, userId, folder, (pct, bytes, total) => {
          setUploadProgress(pct)
          setUploadedBytes(bytes)
          setTotalBytes(total)
        })
        setUploading(false)
        setUploadProgress(100)
        return result
      } catch (err: any) {
        setError(err.message || 'Upload failed')
        setUploading(false)
        toast.error(`Upload failed: ${err.message || 'Network error'}`)
        return null
      }
    },
    []
  )

  return {
    uploading,
    uploadProgress,
    uploadedBytes,
    totalBytes,
    uploadFile,
    cancelUpload,
    error,
  }
}
