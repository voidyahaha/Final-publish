import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { addDoc, collection, serverTimestamp } from 'firebase/firestore'
import { db } from '../firebase'
import { useAuth } from '../hooks/useAuth'
import { useUpload } from '../hooks/useUpload'
import { useJobPolling } from '../hooks/useJob'
import { useAppStore } from '../store'
import { api } from '../services/api'
import FileUploader from '../components/upload/FileUploader'
import JobCard from '../components/jobs/JobCard'
import { Job } from '../types'
import toast from 'react-hot-toast'
import clsx from 'clsx'

const MODELS = [
  { id: 'htdemucs', label: 'HTDemucs (Fast & Recommended)', desc: 'Optimized high-speed AI separation on this device', recommended: true },
  { id: 'htdemucs_ft', label: 'HTDemucs FT (Ensemble)', desc: 'Deep ensemble of 4 models (Slower processing on CPU)' },
  { id: 'htdemucs_6s', label: 'HTDemucs 6-stem', desc: 'Adds dedicated piano and guitar stems' },
  { id: 'mdx_extra', label: 'MDX Extra', desc: 'Alternative model, different characteristics' },
]

const STEMS = [
  { id: 'vocals', icon: '🎤', label: 'Vocals', color: '#EC4899' },
  { id: 'drums', icon: '🥁', label: 'Drums', color: '#F59E0B' },
  { id: 'bass', icon: '🎸', label: 'Bass', color: '#06B6D4' },
  { id: 'other', icon: '🎹', label: 'Other', color: '#10B981' },
  { id: 'piano', icon: '🎹', label: 'Piano', color: '#A78BFA' },
  { id: 'guitar', icon: '🎸', label: 'Guitar', color: '#FB7185' },
  { id: 'instrumental', icon: '🎼', label: 'Instrumental', color: '#6366F1' },
]

export default function Separator() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [selectedModel, setSelectedModel] = useState('htdemucs')
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null)
  const [step, setStep] = useState<'upload' | 'processing' | 'done'>('upload')
  const [submitting, setSubmitting] = useState(false)

  const { user } = useAuth()
  const { uploading, uploadProgress, uploadedBytes, totalBytes, uploadFile, error: uploadError } = useUpload()
  const { jobs, addJob } = useAppStore()
  const { startPolling, stopPolling } = useJobPolling(activeJobId)

  const separationJobs = jobs.filter(j => j.type === 'separation')

  const handleFileSelect = useCallback((file: File) => {
    setSelectedFile(file)
  }, [])

  const handleSeparate = async () => {
    if (!selectedFile || !user || submitting) return

    try {
      setSubmitting(true)

      // 1. Upload file to backend / storage
      toast.loading('Uploading audio...', { id: 'sep-toast' })
      const uploadResult = await uploadFile(selectedFile, user.uid, 'originals')

      if (!uploadResult) {
        setStep('upload')
        toast.error('Upload failed', { id: 'sep-toast' })
        return
      }

      setStep('processing')
      toast.loading('Starting separation...', { id: 'sep-toast' })

      // 2. Create job in Firestore (with local fallback)
      let jobId = ''
      try {
        const jobRef = await addDoc(collection(db, 'jobs'), {
          userId: user.uid,
          type: 'separation',
          status: 'queued',
          progress: 0,
          statusMessage: 'Job queued for processing',
          originalFileName: selectedFile.name,
          originalStoragePath: uploadResult.storagePath,
          originalDownloadUrl: uploadResult.downloadUrl,
          stems: [],
          model: selectedModel,
          createdAt: serverTimestamp(),
          updatedAt: serverTimestamp(),
        })
        jobId = jobRef.id
      } catch {
        jobId = 'job_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9)
      }

      setActiveJobId(jobId)

      const newJob: Job = {
        id: jobId,
        userId: user.uid,
        type: 'separation',
        status: 'queued',
        progress: 0,
        statusMessage: 'Job queued',
        originalFileName: selectedFile.name,
        originalStoragePath: uploadResult.storagePath,
        originalDownloadUrl: uploadResult.downloadUrl,
        stems: [],
        createdAt: new Date(),
        updatedAt: new Date(),
      }

      addJob(newJob)
      setExpandedJobId(jobId)

      // 3. Trigger backend processing
      await api.startSeparation({
        jobId,
        userId: user.uid,
        storagePath: uploadResult.storagePath,
        model: selectedModel,
      })

      // 4. Poll for status
      startPolling(jobId)
      toast.success('Separation started! AI is processing your audio.', { id: 'sep-toast' })
      setStep('done')
      setSelectedFile(null)

    } catch (err: any) {
      toast.error(`Error: ${err.message}`, { id: 'sep-toast' })
      setStep('upload')
      stopPolling()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-black text-text-primary mb-1">AI Stem Separator</h2>
        <p className="text-text-muted">Upload a song and HTDemucs AI will isolate each instrument</p>
      </div>

      {/* Upload & Config */}
      <AnimatePresence mode="wait">
        {step !== 'processing' && (
          <motion.div
            key="upload-form"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="grid grid-cols-1 lg:grid-cols-3 gap-6"
          >
            {/* Upload zone */}
            <div className="lg:col-span-2 card space-y-6">
              <div>
                <h3 className="text-sm font-bold text-text-primary mb-4">Upload Audio</h3>
                <FileUploader
                  onFileSelect={handleFileSelect}
                  uploading={uploading}
                  progress={uploadProgress}
                  uploadedBytes={uploadedBytes}
                  totalBytes={totalBytes}
                  error={uploadError}
                  currentFile={selectedFile}
                  label="Drop your song here"
                  sublabel="MP3, WAV, FLAC, M4A up to 200MB"
                />
              </div>

              {/* Stems preview */}
              <div>
                <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Output Stems</h4>
                <div className="flex flex-wrap gap-2">
                  {STEMS.map(s => (
                    <div key={s.id} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium"
                      style={{ background: `${s.color}15`, border: `1px solid ${s.color}30`, color: s.color }}>
                      {s.icon} {s.label}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Model selection + CTA */}
            <div className="space-y-4">
              <div className="card">
                <h3 className="text-sm font-bold text-text-primary mb-4">AI Model</h3>
                <div className="space-y-2">
                  {MODELS.map(m => (
                    <button
                      key={m.id}
                      onClick={() => setSelectedModel(m.id)}
                      className={clsx(
                        'w-full p-3 rounded-xl border text-left transition-all',
                        selectedModel === m.id
                          ? 'border-accent-primary bg-accent-primary/10'
                          : 'border-border hover:border-border-light'
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-semibold text-text-primary">{m.label}</span>
                        {m.recommended && (
                          <span className="badge bg-accent-primary/20 text-accent-primary text-xs">Best</span>
                        )}
                      </div>
                      <p className="text-xs text-text-muted mt-0.5">{m.desc}</p>
                    </button>
                  ))}
                </div>
              </div>

              <button
                onClick={handleSeparate}
                disabled={!selectedFile || uploading || submitting || !user}
                className={clsx(
                  'w-full py-4 rounded-xl font-bold text-base transition-all',
                  selectedFile && user
                    ? 'btn-primary shadow-glow-md'
                    : 'bg-bg-hover border border-border text-text-muted cursor-not-allowed'
                )}
              >
                {uploading ? `⬆️ Uploading (${uploadProgress}%)...` : submitting ? '⚙️ Starting separation...' : '🔪 Separate Stems'}
              </button>

              <div className="text-xs text-text-muted text-center">
                Powered by HTDemucs • Best available AI model
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Jobs list */}
      {separationJobs.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-lg font-bold text-text-primary">Separation Jobs</h3>
          <AnimatePresence>
            {separationJobs.map(job => (
              <JobCard
                key={job.id}
                job={job}
                expanded={expandedJobId === job.id}
                onToggle={() => setExpandedJobId(expandedJobId === job.id ? null : job.id)}
              />
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  )
}
