import {
  ref,
  uploadBytesResumable,
  getDownloadURL,
  UploadTask,
} from 'firebase/storage'
import { storage } from '../firebase'

export interface StorageUploadResult {
  storagePath: string
  downloadUrl: string
  fileName: string
  size: number
}

export function uploadAudioToStorage(
  file: File,
  userId: string,
  folder: 'originals' | 'vocals' | 'instrumentals',
  onProgress?: (pct: number, bytesTransferred: number, totalBytes: number) => void,
  onError?: (error: Error) => void,
  onComplete?: (result: StorageUploadResult) => void
): UploadTask {
  const timestamp = Date.now()
  const sanitizedName = file.name.replace(/[^a-zA-Z0-9._-]/g, '_')
  const storagePath = `users/${userId}/${folder}/${timestamp}_${sanitizedName}`
  const storageRef = ref(storage, storagePath)

  const uploadTask = uploadBytesResumable(storageRef, file, {
    contentType: file.type || 'audio/mpeg',
  })

  uploadTask.on(
    'state_changed',
    (snapshot: any) => {
      const pct = Math.round(
        (snapshot.bytesTransferred / snapshot.totalBytes) * 100
      )
      onProgress?.(pct, snapshot.bytesTransferred, snapshot.totalBytes)
    },
    (error: any) => {
      onError?.(new Error(error.message))
    },
    async () => {
      try {
        const downloadUrl = await getDownloadURL(uploadTask.snapshot.ref)
        onComplete?.({
          storagePath,
          downloadUrl,
          fileName: file.name,
          size: file.size,
        })
      } catch (e) {
        onError?.(e as Error)
      }
    }
  )

  return uploadTask
}

export async function getFileDownloadUrl(storagePath: string): Promise<string> {
  if (
    storagePath.startsWith('blob:') ||
    storagePath.startsWith('http://') ||
    storagePath.startsWith('https://')
  ) {
    return storagePath
  }
  if (storagePath.startsWith('/api/') || storagePath.startsWith('api/')) {
    const base = import.meta.env.VITE_API_URL || ''
    return base ? `${base.replace(/\/$/, '')}/${storagePath.replace(/^\//, '')}` : storagePath
  }
  try {
    const storageRef = ref(storage, storagePath)
    return await getDownloadURL(storageRef)
  } catch {
    const base = import.meta.env.VITE_API_URL || ''
    return base ? `${base.replace(/\/$/, '')}/api/files/${storagePath}` : `/api/files/${storagePath}`
  }
}

export function validateAudioFile(file: File): { valid: boolean; error?: string } {
  const MAX_SIZE = 200 * 1024 * 1024 // 200 MB
  const ALLOWED_TYPES = [
    'audio/mpeg',
    'audio/mp3',
    'audio/wav',
    'audio/wave',
    'audio/x-wav',
    'audio/flac',
    'audio/x-flac',
    'audio/mp4',
    'audio/m4a',
    'audio/aac',
    'audio/ogg',
    'audio/webm',
    'audio/x-m4a',
    'video/mp4', // some m4a files have this type
  ]
  const ALLOWED_EXTENSIONS = ['.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.webm']

  if (file.size > MAX_SIZE) {
    return { valid: false, error: `File too large. Max size is 200MB. Your file: ${(file.size / 1024 / 1024).toFixed(1)}MB` }
  }

  const ext = '.' + file.name.split('.').pop()?.toLowerCase()
  const hasValidType = ALLOWED_TYPES.includes(file.type)
  const hasValidExt = ALLOWED_EXTENSIONS.includes(ext)

  if (!hasValidType && !hasValidExt) {
    return {
      valid: false,
      error: `Unsupported file type: ${file.type || ext}. Supported: MP3, WAV, FLAC, M4A, AAC, OGG`,
    }
  }

  return { valid: true }
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}
