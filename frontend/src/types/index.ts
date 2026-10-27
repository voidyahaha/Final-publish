// Job status flow: queued → uploading → processing → separating → mixing → completed | failed

export type JobStatus =
  | 'queued'
  | 'uploading'
  | 'processing'
  | 'separating'
  | 'mixing'
  | 'completed'
  | 'failed'

export type JobType = 'separation' | 'vocal_mix'

export type StemType = 'vocals' | 'drums' | 'bass' | 'other' | 'instrumental' | 'piano' | 'guitar'

export interface StemFile {
  stem: StemType
  storagePath: string
  downloadUrl: string
  duration: number
  sampleRate: number
  sizeBytes?: number
  sizBytes?: number
}

export interface Job {
  id: string
  userId: string
  type: JobType
  status: JobStatus
  progress: number
  statusMessage: string
  originalFileName: string
  originalStoragePath: string
  originalDownloadUrl?: string
  stems: StemFile[]
  mixedTrackPath?: string
  mixedTrackUrl?: string
  bpm?: number
  key?: string
  duration?: number
  error?: string
  createdAt: Date
  updatedAt: Date
  completedAt?: Date
  // Vocal mix specific
  vocalStoragePath?: string
  instrumentalStoragePath?: string
  instrumentalDownloadUrl?: string
  vocalBpm?: number
  instrumentalBpm?: number
}

export interface User {
  uid: string
  email: string | null
  displayName: string | null
  photoURL: string | null
  createdAt: Date
  totalJobs: number
  totalProcessingTime: number
  plan: 'free' | 'pro'
}

export interface AudioAnalysis {
  bpm: number
  key: string
  duration: number
  sampleRate: number
  loudness: number
  onsets: number[]
  beats: number[]
}

export interface UploadProgress {
  phase: 'uploading' | 'processing'
  percent: number
  bytesTransferred?: number
  totalBytes?: number
  message: string
}

export interface ApiResponse<T = unknown> {
  success: boolean
  data?: T
  error?: string
  message?: string
}

export interface SeparationRequest {
  jobId: string
  userId: string
  storagePath: string
  model: string
}

export interface MixRequest {
  jobId: string
  userId: string
  vocalPath: string
  instrumentalPath: string
  vocalGain?: number
  instrumentalGain?: number
  timeStretch?: boolean
}

export interface NavItem {
  id: string
  label: string
  icon: string
  path: string
  badge?: string | number
}
