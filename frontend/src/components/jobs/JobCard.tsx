import { motion, AnimatePresence } from 'framer-motion'
import { Job, JobStatus, StemFile } from '../../types'
import AudioPlayer from '../audio/AudioPlayer'
import clsx from 'clsx'
import { formatFileSize, formatDuration } from '../../services/storage'
import { resolveAudioUrl } from '../../services/api'
import { formatDistanceToNow } from 'date-fns'

const STATUS_CONFIG: Record<JobStatus, { label: string; color: string; bg: string; icon: string }> = {
  queued: { label: 'Queued', color: '#94A3B8', bg: 'rgba(148,163,184,0.1)', icon: '⏳' },
  uploading: { label: 'Uploading', color: '#F59E0B', bg: 'rgba(245,158,11,0.1)', icon: '⬆️' },
  processing: { label: 'Processing', color: '#06B6D4', bg: 'rgba(6,182,212,0.1)', icon: '⚙️' },
  separating: { label: 'Separating', color: '#8B5CF6', bg: 'rgba(139,92,246,0.1)', icon: '🎵' },
  mixing: { label: 'Mixing', color: '#EC4899', bg: 'rgba(236,72,153,0.1)', icon: '🎛️' },
  completed: { label: 'Completed', color: '#10B981', bg: 'rgba(16,185,129,0.1)', icon: '✅' },
  failed: { label: 'Failed', color: '#EF4444', bg: 'rgba(239,68,68,0.1)', icon: '❌' },
}

const STEM_COLORS: Record<string, string> = {
  vocals: '#EC4899',
  drums: '#F59E0B',
  bass: '#06B6D4',
  other: '#10B981',
  piano: '#A78BFA',
  guitar: '#FB7185',
  instrumental: '#6366F1',
}

const STEM_ICONS: Record<string, string> = {
  vocals: '🎤',
  drums: '🥁',
  bass: '🎸',
  other: '🎹',
  piano: '🎹',
  guitar: '🎸',
  instrumental: '🎼',
}

interface JobCardProps {
  job: Job
  expanded?: boolean
  onToggle?: () => void
  onDelete?: (id: string) => void
}

export default function JobCard({ job, expanded = false, onToggle, onDelete }: JobCardProps) {
  const config = STATUS_CONFIG[job.status]
  const isActive = !['completed', 'failed'].includes(job.status)

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="card-hover cursor-pointer"
      onClick={onToggle}
    >
      {/* Header */}
      <div className="flex items-start gap-4">
        {/* Icon */}
        <div className={clsx(
          'w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 text-lg'
        )} style={{ background: config.bg, border: `1px solid ${config.color}30` }}>
          {config.icon}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-text-primary truncate">{job.originalFileName}</span>
            <span className="badge text-xs" style={{ color: config.color, background: config.bg }}>
              {config.label}
            </span>
            <span className="badge bg-bg-hover text-text-muted text-xs capitalize">
              {job.type === 'separation' ? '🔪 Separation' : '🎤 Vocal Mix'}
            </span>
          </div>

          <div className="flex items-center gap-3 mt-1 text-xs text-text-muted">
            <span>{formatDistanceToNow(job.createdAt, { addSuffix: true })}</span>
            {job.bpm && <span>♩ {job.bpm} BPM</span>}
            {job.duration && <span>⏱ {formatDuration(job.duration)}</span>}
          </div>

          {/* Progress bar for active jobs */}
          {isActive && (
            <div className="mt-2 space-y-1">
              <div className="progress-bar">
                <motion.div
                  className="progress-fill"
                  animate={{ width: `${job.progress}%` }}
                  transition={{ duration: 0.5 }}
                />
              </div>
              <div className="flex justify-between text-xs text-text-muted">
                <span>{job.statusMessage || config.label}</span>
                <span>{job.progress}%</span>
              </div>
            </div>
          )}

          {/* Error */}
          {job.status === 'failed' && job.error && (
            <div className="mt-2 text-xs text-red-400 bg-red-500/10 rounded-lg px-3 py-1.5 border border-red-500/20">
              {job.error}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 flex-shrink-0">
          {onDelete && (
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(job.id) }}
              className="p-1.5 rounded-lg text-text-muted hover:text-red-400 hover:bg-red-500/10 transition-all"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          )}
          <button
            onClick={(e) => { e.stopPropagation(); onToggle?.() }}
            className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-bg-hover transition-all"
          >
            <svg className={clsx('w-4 h-4 transition-transform', expanded && 'rotate-180')} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>
      </div>

      {/* Expanded: Stems */}
      <AnimatePresence>
        {expanded && job.status === 'completed' && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-4 pt-4 border-t border-border space-y-3"
            onClick={(e) => e.stopPropagation()}
          >
            {job.stems.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider">Separated Stems</h4>
                {job.stems.map((stem) => (
                  <StemRow key={stem.stem} stem={stem} />
                ))}
              </div>
            )}
            {job.mixedTrackUrl && (
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider">Mixed Track</h4>
                <AudioPlayer url={resolveAudioUrl(job.mixedTrackUrl)} title="Final Mix" color="#EC4899" />
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

function StemRow({ stem }: { stem: StemFile }) {
  const color = STEM_COLORS[stem.stem] || '#6366F1'
  const icon = STEM_ICONS[stem.stem] || '🎵'
  const audioUrl = resolveAudioUrl(stem.downloadUrl)

  return (
    <div className="stem-card">
      <div className="flex items-center gap-3">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center text-sm"
          style={{ background: `${color}20`, border: `1px solid ${color}30` }}
        >
          {icon}
        </div>
        <div>
          <div className="text-sm font-medium text-text-primary capitalize">{stem.stem}</div>
          {stem.duration && <div className="text-xs text-text-muted">{formatDuration(stem.duration)}</div>}
        </div>
      </div>
      <div className="flex items-center gap-2">
        {audioUrl && (
          <>
            <AudioPlayer url={audioUrl} color={color} compact />
            <a
              href={audioUrl}
              download={`${stem.stem}.mp3`}
              className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-bg-hover transition-all"
              onClick={(e) => e.stopPropagation()}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
            </a>
          </>
        )}
      </div>
    </div>
  )
}
