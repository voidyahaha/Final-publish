import { useState } from 'react'
import { motion } from 'framer-motion'
import { useAuth } from '../hooks/useAuth'
import { useUpload } from '../hooks/useUpload'
import { api } from '../services/api'
import { useAppStore } from '../store'
import FileUploader from '../components/upload/FileUploader'
import toast from 'react-hot-toast'

interface AnalysisResult {
  bpm: number
  key: string
  duration: number
  loudness: number
  sampleRate: number
  beats: number[]
  onsets: number[]
}

export default function Analyzer() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState<AnalysisResult | null>(null)

  const { user } = useAuth()
  const { uploading, uploadProgress, uploadFile, error: uploadError } = useUpload()

  const handleAnalyze = async () => {
    if (!selectedFile || !user) return
    setAnalyzing(true)
    try {
      toast.loading('Uploading for analysis...', { id: 'analyze' })
      const uploaded = await uploadFile(selectedFile, user.uid, 'originals')
      if (!uploaded) { toast.error('Upload failed', { id: 'analyze' }); return }

      toast.loading('Analyzing audio...', { id: 'analyze' })

      const data = await api.analyzeAudio(uploaded.storagePath)
      setResult(data.analysis)
      toast.success('Analysis complete!', { id: 'analyze' })
    } catch (e: any) {
      toast.error('Analysis failed: ' + e.message, { id: 'analyze' })
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-black text-text-primary mb-1">AI Audio Analyzer</h2>
        <p className="text-text-muted">Deep analysis of tempo, key, beats, and audio characteristics</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card space-y-4">
          <h3 className="text-sm font-bold text-text-primary">Upload Audio for Analysis</h3>
          <FileUploader
            onFileSelect={setSelectedFile}
            uploading={uploading}
            progress={uploadProgress}
            error={uploadError}
            currentFile={selectedFile}
            label="Drop audio file here"
            sublabel="Any supported audio format"
          />
          <button
            onClick={handleAnalyze}
            disabled={!selectedFile || uploading || analyzing}
            className="btn-primary w-full py-3"
          >
            {analyzing ? '🧠 Analyzing...' : '📊 Analyze Audio'}
          </button>
        </div>

        {result && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="card space-y-4"
          >
            <h3 className="text-sm font-bold text-text-primary">Analysis Results</h3>
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'BPM', value: result.bpm?.toFixed(1), icon: '♩', color: '#6366F1' },
                { label: 'Key', value: result.key || 'Unknown', icon: '🎵', color: '#EC4899' },
                { label: 'Duration', value: `${Math.floor(result.duration/60)}:${Math.floor(result.duration%60).toString().padStart(2,'0')}`, icon: '⏱', color: '#10B981' },
                { label: 'Loudness', value: `${result.loudness?.toFixed(1)} dB`, icon: '🔊', color: '#F59E0B' },
                { label: 'Sample Rate', value: `${result.sampleRate} Hz`, icon: '📡', color: '#06B6D4' },
                { label: 'Beats Found', value: result.beats?.length || 0, icon: '🥁', color: '#8B5CF6' },
              ].map(stat => (
                <div key={stat.label} className="p-3 rounded-xl bg-bg-secondary border border-border">
                  <div className="text-lg font-black" style={{ color: stat.color }}>{stat.icon} {stat.value}</div>
                  <div className="text-xs text-text-muted">{stat.label}</div>
                </div>
              ))}
            </div>

            {result.beats?.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-text-muted mb-2 uppercase tracking-wider">Beat Grid Preview</div>
                <div className="flex gap-0.5 h-8 items-end overflow-hidden rounded">
                  {result.beats.slice(0, 60).map((_, i) => (
                    <div key={i} className="flex-1 min-w-0 rounded-t"
                      style={{ background: `rgba(99,102,241,${0.3 + (i % 4 === 0 ? 0.7 : 0.2)})`, height: i % 4 === 0 ? '100%' : '50%' }} />
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}
      </div>

      {/* Feature overview */}
      {!result && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { icon: '♩', title: 'BPM Detection', desc: 'Accurate tempo using librosa beat tracking', color: '#6366F1' },
            { icon: '🎵', title: 'Key Detection', desc: 'Musical key and scale identification', color: '#EC4899' },
            { icon: '🥁', title: 'Beat Grid', desc: 'Beat and onset timestamps', color: '#F59E0B' },
            { icon: '📊', title: 'Loudness', desc: 'RMS and LUFS analysis', color: '#10B981' },
          ].map(f => (
            <div key={f.title} className="card text-center">
              <div className="text-3xl mb-3">{f.icon}</div>
              <div className="text-sm font-bold text-text-primary mb-1">{f.title}</div>
              <div className="text-xs text-text-muted">{f.desc}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
