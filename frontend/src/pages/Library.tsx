import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAppStore } from '../store'
import JobCard from '../components/jobs/JobCard'
import { Job, JobStatus } from '../types'
import clsx from 'clsx'

const FILTERS: { label: string; value: 'all' | JobStatus | 'separation' | 'vocal_mix' }[] = [
  { label: 'All', value: 'all' },
  { label: 'Active', value: 'processing' },
  { label: 'Completed', value: 'completed' },
  { label: 'Failed', value: 'failed' },
  { label: 'Separations', value: 'separation' },
  { label: 'Vocal Mixes', value: 'vocal_mix' },
]

export default function Library() {
  const { jobs } = useAppStore()
  const [filter, setFilter] = useState<string>('all')
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  const filtered = jobs.filter(j => {
    const matchSearch = !search || j.originalFileName.toLowerCase().includes(search.toLowerCase())
    if (!matchSearch) return false
    if (filter === 'all') return true
    if (filter === 'processing') return !['completed', 'failed', 'queued'].includes(j.status)
    if (filter === 'separation' || filter === 'vocal_mix') return j.type === filter
    return j.status === filter
  })

  return (
    <div className="space-y-6">
      {/* Header + search */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-black text-text-primary mb-1">My Library</h2>
          <p className="text-text-muted">{jobs.length} total jobs</p>
        </div>
        <div className="relative">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search jobs..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="input pl-9 w-64"
          />
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        {FILTERS.map(f => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={clsx(
              'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
              filter === f.value
                ? 'bg-accent-primary text-white'
                : 'bg-bg-hover border border-border text-text-muted hover:text-text-primary hover:border-border-light'
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Separations', value: jobs.filter(j=>j.type==='separation').length, color: '#6366F1' },
          { label: 'Vocal Mixes', value: jobs.filter(j=>j.type==='vocal_mix').length, color: '#EC4899' },
          { label: 'Completed', value: jobs.filter(j=>j.status==='completed').length, color: '#10B981' },
        ].map(s => (
          <div key={s.label} className="card text-center">
            <div className="text-2xl font-black" style={{ color: s.color }}>{s.value}</div>
            <div className="text-xs text-text-muted mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Jobs list */}
      {filtered.length > 0 ? (
        <div className="space-y-3">
          <AnimatePresence>
            {filtered.map(job => (
              <JobCard
                key={job.id}
                job={job}
                expanded={expandedJobId === job.id}
                onToggle={() => setExpandedJobId(expandedJobId === job.id ? null : job.id)}
              />
            ))}
          </AnimatePresence>
        </div>
      ) : (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center py-20"
        >
          <div className="text-5xl mb-4">📂</div>
          <p className="text-lg font-semibold text-text-secondary mb-2">No jobs found</p>
          <p className="text-sm text-text-muted">
            {search ? `No results for "${search}"` : 'Start by separating a song or mixing vocals'}
          </p>
        </motion.div>
      )}
    </div>
  )
}
