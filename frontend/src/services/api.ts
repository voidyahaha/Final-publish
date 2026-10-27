import axios, { AxiosProgressEvent } from 'axios'
import { auth } from '../firebase'

// In production VITE_API_URL points at the persistent FastAPI service. During
// local Vite development the proxy keeps `/api` calls on the same origin.
const API_BASE = import.meta.env.VITE_API_URL || ''

const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
})

// Attach Firebase ID token or guest token to every request
apiClient.interceptors.request.use(async (config) => {
  const user = auth.currentUser
  if (user) {
    try {
      const token = await user.getIdToken()
      config.headers.Authorization = `Bearer ${token}`
    } catch {
    }
  } else {
    // Check if guest / demo user is in storage
    try {
      const stored = localStorage.getItem('stemai-app-storage')
      if (stored) {
        const parsed = JSON.parse(stored)
        if (parsed?.state?.user?.uid) {
          config.headers.Authorization = `Bearer guest-${parsed.state.user.uid}`
        }
      }
    } catch {}
  }
  return config
})

// Response interceptor for unified error handling
apiClient.interceptors.response.use(
  (res) => res,
  (err) => {
    const message =
      err.response?.data?.detail ||
      err.response?.data?.error ||
      err.message ||
      'An unexpected error occurred'
    return Promise.reject(new Error(message))
  }
)

export const api = {
  // ─── Upload ────────────────────────────────────────────────────────────────
  async uploadFile(
    file: File,
    userId: string,
    onProgress?: (pct: number, bytes: number, total: number) => void
  ) {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('user_id', userId)

    const res = await apiClient.post('/api/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 600000, // 10 min upload timeout
      onUploadProgress: (evt: AxiosProgressEvent) => {
        if (evt.total && onProgress) {
          const pct = Math.round((evt.loaded * 100) / evt.total)
          onProgress(pct, evt.loaded, evt.total)
        }
      },
    })
    return {
      storagePath: res.data.storage_path,
      downloadUrl: res.data.download_url,
      fileName: res.data.file_name,
      size: res.data.size,
    }
  },

  // ─── Separation ────────────────────────────────────────────────────────────
  async startSeparation(payload: {
    jobId: string
    userId: string
    storagePath: string
    model?: string
  }) {
    const res = await apiClient.post('/api/separate', {
      job_id: payload.jobId,
      user_id: payload.userId,
      storage_path: payload.storagePath,
      model: payload.model || 'htdemucs',
    })
    return res.data
  },

  async getJobStatus(jobId: string) {
    const res = await apiClient.get(`/api/jobs/${jobId}`)
    return res.data
  },

  async getUserJobs(userId: string) {
    const res = await apiClient.get(`/api/jobs/user/${userId}`)
    return res.data
  },

  async cancelJob(jobId: string) {
    const res = await apiClient.delete(`/api/jobs/${jobId}`)
    return res.data
  },

  async getJobDownloadUrl(jobId: string, asset: string) {
    const res = await apiClient.get(`/api/jobs/${jobId}/download/${encodeURIComponent(asset)}`)
    return res.data.downloadUrl as string
  },

  // ─── Vocal Mix ─────────────────────────────────────────────────────────────
  async startVocalMix(payload: {
    jobId: string
    userId: string
    vocalPath: string
    instrumentalPath: string
    vocalGain?: number
    instrumentalGain?: number
    timeStretch?: boolean
  }) {
    const res = await apiClient.post('/api/mix', {
      job_id: payload.jobId,
      user_id: payload.userId,
      vocal_path: payload.vocalPath,
      instrumental_path: payload.instrumentalPath,
      vocal_gain: payload.vocalGain ?? 0.85,
      instrumental_gain: payload.instrumentalGain ?? 1.0,
      time_stretch: payload.timeStretch ?? true,
    })
    return res.data
  },

  // ─── Analysis ──────────────────────────────────────────────────────────────
  async analyzeAudio(storagePath: string) {
    const res = await apiClient.post('/api/analyze', { storage_path: storagePath })
    return res.data
  },

  // ─── Health ────────────────────────────────────────────────────────────────
  async healthCheck() {
    const res = await apiClient.get('/api/health')
    return res.data
  },
}

export default apiClient
