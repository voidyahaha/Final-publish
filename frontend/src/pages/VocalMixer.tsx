import { useState, useCallback, useRef } from 'react'
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

export default function VocalMixer() {
  const [vocalFile, setVocalFile] = useState<File | null>(null)
  const [instrumentalFile, setInstrumentalFile] = useState<File | null>(null)
  const [vocalGain, setVocalGain] = useState(0.85)
  const [instrumentalGain, setInstrumentalGain] = useState(1.0)
  const [timeStretch, setTimeStretch] = useState(true)
  const [recording, setRecording] = useState(false)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null)

  const { user } = useAuth()
  const {
    uploading: uploadingVocal, uploadProgress: vocalProgress,
    uploadFile: uploadVocal, error: vocalError
  } = useUpload()
  const {
    uploading: uploadingInst, uploadProgress: instProgress,
    uploadFile: uploadInst, error: instError
  } = useUpload()

  const { jobs, addJob } = useAppStore()
  const { startPolling } = useJobPolling(activeJobId)

  const mixJobs = jobs.filter(j => j.type === 'vocal_mix')

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      chunksRef.current = []

      mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      mr.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        setRecordedBlob(blob)
        const file = new File([blob], `recording-${Date.now()}.webm`, { type: 'audio/webm' })
        setVocalFile(file)
        stream.getTracks().forEach(t => t.stop())
        toast.success('Recording saved!')
      }

      mr.start()
      mediaRecorderRef.current = mr
      setRecording(true)
    } catch (e: any) {
      toast.error('Microphone access denied: ' + e.message)
    }
  }

  const stopRecording = () => {
    mediaRecorderRef.current?.stop()
    setRecording(false)
  }

  const handleMix = async () => {
    if ((!vocalFile && !recordedBlob) || !instrumentalFile || !user || submitting) return

    try {
      setSubmitting(true)
      toast.loading('Uploading vocal...', { id: 'mix-toast' })
      const vocalResult = await uploadVocal(vocalFile || new File([recordedBlob!], 'recording.webm'), user.uid, 'vocals')
      if (!vocalResult) { toast.error('Vocal upload failed', { id: 'mix-toast' }); return }

      toast.loading('Uploading instrumental...', { id: 'mix-toast' })
      const instResult = await uploadInst(instrumentalFile, user.uid, 'instrumentals')
      if (!instResult) { toast.error('Instrumental upload failed', { id: 'mix-toast' }); return }

      toast.loading('Starting mix...', { id: 'mix-toast' })

      const jobRef = await addDoc(collection(db, 'jobs'), {
        userId: user.uid,
        type: 'vocal_mix',
        status: 'queued',
        progress: 0,
        statusMessage: 'Mix queued',
        originalFileName: vocalFile?.name || 'recording.webm',
        originalStoragePath: vocalResult.storagePath,
        vocalStoragePath: vocalResult.storagePath,
        instrumentalStoragePath: instResult.storagePath,
        vocalGain,
        instrumentalGain,
        timeStretch,
        stems: [],
        createdAt: serverTimestamp(),
        updatedAt: serverTimestamp(),
      })

      const jobId = jobRef.id
      setActiveJobId(jobId)

      const newJob: Job = {
        id: jobId, userId: user.uid, type: 'vocal_mix',
        status: 'queued', progress: 0, statusMessage: 'Mix queued',
        originalFileName: vocalFile?.name || 'recording.webm',
        originalStoragePath: vocalResult.storagePath,
        vocalStoragePath: vocalResult.storagePath,
        instrumentalStoragePath: instResult.storagePath,
        stems: [], createdAt: new Date(), updatedAt: new Date(),
      }
      addJob(newJob)
      setExpandedJobId(jobId)

      await api.startVocalMix({
        jobId,
        userId: user.uid,
        vocalPath: vocalResult.storagePath,
        instrumentalPath: instResult.storagePath,
        vocalGain,
        instrumentalGain,
        timeStretch,
      })

      startPolling(jobId)
      toast.success('Mixing started! AI is aligning and mixing.', { id: 'mix-toast' })
      setVocalFile(null)
      setInstrumentalFile(null)
      setRecordedBlob(null)

    } catch (err: any) {
      toast.error(`Error: ${err.message}`, { id: 'mix-toast' })
    } finally {
      setSubmitting(false)
    }
  }

  const canMix = (vocalFile || recordedBlob) && instrumentalFile && !uploadingVocal && !uploadingInst && !submitting

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-black text-text-primary mb-1">Vocal Mixer</h2>
        <p className="text-text-muted">Upload or record your vocals and mix with any instrumental using AI beat alignment</p>
      </div>

      {/* How it works */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { step: '1', icon: '🎤', label: 'Upload/Record Vocals', color: '#EC4899' },
          { step: '2', icon: '🧠', label: 'AI Analyzes & Aligns BPM', color: '#8B5CF6' },
          { step: '3', icon: '🎛️', label: 'Mix & Download', color: '#10B981' },
        ].map(s => (
          <div key={s.step} className="card text-center">
            <div className="w-10 h-10 rounded-full mx-auto mb-3 flex items-center justify-center text-xl"
              style={{ background: `${s.color}20`, border: `1px solid ${s.color}30` }}>
              {s.icon}
            </div>
            <div className="text-xs font-bold text-text-primary">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Upload panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Vocals */}
        <div className="card space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-text-primary">🎤 Your Vocals</h3>
            <button
              onClick={recording ? stopRecording : startRecording}
              className={clsx(
                'flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                recording
                  ? 'bg-red-500/20 border border-red-500/40 text-red-400 animate-pulse'
                  : 'bg-accent-pink/10 border border-accent-pink/30 text-accent-pink hover:bg-accent-pink/20'
              )}
            >
              {recording ? (
                <><div className="w-2 h-2 rounded-full bg-red-400 animate-pulse" /> Stop Recording</>
              ) : (
                <><svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                </svg> Record</>
              )}
            </button>
          </div>

          {recording && (
            <div className="flex items-center justify-center gap-1 py-4">
              {[1,2,3,4,5,6,7,8].map(i => (
                <div key={i} className="w-1 rounded-full bg-red-400"
                  style={{ height: `${Math.random() * 32 + 8}px`, animation: `waveformPulse 0.8s ease-in-out ${i*0.08}s infinite` }} />
              ))}
            </div>
          )}

          <FileUploader
            onFileSelect={setVocalFile}
            uploading={uploadingVocal}
            progress={vocalProgress}
            error={vocalError}
            currentFile={vocalFile}
            label="Drop vocal audio here"
            sublabel="MP3, WAV, M4A, WebM"
          />

          <div>
            <div className="flex justify-between text-xs text-text-muted mb-1">
              <span>Vocal Volume</span>
              <span>{Math.round(vocalGain * 100)}%</span>
            </div>
            <input type="range" min={0} max={1.5} step={0.05} value={vocalGain}
              onChange={e => setVocalGain(parseFloat(e.target.value))} className="w-full" />
          </div>
        </div>

        {/* Instrumental */}
        <div className="card space-y-4">
          <h3 className="text-sm font-bold text-text-primary">🎼 Instrumental</h3>
          <FileUploader
            onFileSelect={setInstrumentalFile}
            uploading={uploadingInst}
            progress={instProgress}
            error={instError}
            currentFile={instrumentalFile}
            label="Drop instrumental here"
            sublabel="MP3, WAV, FLAC, M4A"
          />

          <div>
            <div className="flex justify-between text-xs text-text-muted mb-1">
              <span>Instrumental Volume</span>
              <span>{Math.round(instrumentalGain * 100)}%</span>
            </div>
            <input type="range" min={0} max={1.5} step={0.05} value={instrumentalGain}
              onChange={e => setInstrumentalGain(parseFloat(e.target.value))} className="w-full" />
          </div>

          <label className="flex items-center gap-3 cursor-pointer">
            <div
              onClick={() => setTimeStretch(!timeStretch)}
              className={clsx(
                'relative w-10 h-5 rounded-full transition-all',
                timeStretch ? 'bg-accent-primary' : 'bg-bg-hover border border-border'
              )}
            >
              <div className={clsx(
                'absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all',
                timeStretch ? 'left-5' : 'left-0.5'
              )} />
            </div>
            <div>
              <div className="text-sm font-medium text-text-primary">AI Beat Alignment</div>
              <div className="text-xs text-text-muted">Auto time-stretch vocals to match BPM</div>
            </div>
          </label>
        </div>
      </div>

      <button
        onClick={handleMix}
        disabled={!canMix}
        className={clsx(
          'w-full py-4 rounded-xl font-bold text-base transition-all',
          canMix ? 'btn-primary shadow-glow-md' : 'bg-bg-hover border border-border text-text-muted cursor-not-allowed'
        )}
      >
        🎛️ Mix & Synchronize
      </button>

      {/* Mix jobs */}
      {mixJobs.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-lg font-bold text-text-primary">Mix Jobs</h3>
          <AnimatePresence>
            {mixJobs.map(job => (
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
