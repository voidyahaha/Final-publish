import { motion } from 'framer-motion'
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useAppStore } from '../store'
import { useAuth } from '../hooks/useAuth'
import { formatDistanceToNow } from 'date-fns'
import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts'

const features = [
  { icon: '🔪', title: 'Stem Separator', desc: 'HTDemucs AI splits vocals, drums, bass & more', path: '/separator', color: '#6366F1' },
  { icon: '🎤', title: 'Vocal Mixer', desc: 'Add your voice to any instrumental with AI alignment', path: '/mixer', color: '#EC4899' },
  { icon: '📊', title: 'AI Analyzer', desc: 'BPM, key, beats and structure analysis', path: '/analyzer', color: '#06B6D4' },
  { icon: '📚', title: 'My Library', desc: 'Browse all your processed tracks and stems', path: '/library', color: '#10B981' },
]

export default function Dashboard() {
  const { jobs } = useAppStore()
  const { user } = useAuth()

  const completed = jobs.filter(j => j.status === 'completed').length
  const active = jobs.filter(j => !['completed','failed'].includes(j.status)).length
  const recent = jobs.slice(0, 3)
  const activity = useMemo(() => {
    const today = new Date()
    return Array.from({ length: 7 }, (_, index) => {
      const date = new Date(today)
      date.setHours(0, 0, 0, 0)
      date.setDate(today.getDate() - (6 - index))
      const next = new Date(date)
      next.setDate(date.getDate() + 1)
      return {
        name: date.toLocaleDateString(undefined, { weekday: 'short' }),
        jobs: jobs.filter(job => job.createdAt >= date && job.createdAt < next).length,
      }
    })
  }, [jobs])

  const greet = () => {
    const h = new Date().getHours()
    if (h < 12) return 'Good morning'
    if (h < 17) return 'Good afternoon'
    return 'Good evening'
  }

  return (
    <div className="space-y-8">
      {/* Hero greeting */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-accent-primary/20 via-accent-secondary/10 to-bg-card border border-accent-primary/20 p-8"
      >
        <div className="absolute inset-0 bg-glow-primary opacity-30" />
        <div className="relative z-10">
          <h1 className="text-3xl font-black text-text-primary mb-2">
            {greet()}, {user?.displayName?.split(' ')[0] || 'there'} 👋
          </h1>
          <p className="text-text-secondary text-lg max-w-lg">
            Separate stems, mix vocals, and analyze music with state-of-the-art AI.
          </p>
          <div className="flex gap-3 mt-6">
            <Link to="/separator" className="btn-primary">
              🔪 Separate a Song
            </Link>
            <Link to="/mixer" className="btn-secondary">
              🎤 Mix Vocals
            </Link>
          </div>
        </div>

        {/* Decorative waveform */}
        <div className="absolute right-8 top-1/2 -translate-y-1/2 flex gap-1 items-end h-16 opacity-20">
          {Array.from({ length: 20 }).map((_, i) => (
            <div
              key={i}
              className="w-1.5 rounded-full bg-accent-primary"
              style={{ height: `${Math.sin(i * 0.5) * 40 + 20}px` }}
            />
          ))}
        </div>
      </motion.div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Jobs', value: jobs.length, icon: '📋', color: '#6366F1' },
          { label: 'Completed', value: completed, icon: '✅', color: '#10B981' },
          { label: 'Processing', value: active, icon: '⚙️', color: '#F59E0B' },
          { label: 'Plan', value: user?.plan?.toUpperCase() || 'FREE', icon: '⭐', color: '#EC4899' },
        ].map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className="card"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-2xl">{stat.icon}</span>
              <div className="w-2 h-2 rounded-full" style={{ background: stat.color }} />
            </div>
            <div className="text-2xl font-black text-text-primary">{stat.value}</div>
            <div className="text-xs text-text-muted mt-1">{stat.label}</div>
          </motion.div>
        ))}
      </div>

      {/* Features grid */}
      <div>
        <h2 className="text-lg font-bold text-text-primary mb-4">Quick Start</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {features.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 + i * 0.05 }}
            >
              <Link
                to={f.path}
                className="card-hover flex items-center gap-4 group no-underline"
              >
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl flex-shrink-0"
                  style={{ background: `${f.color}20`, border: `1px solid ${f.color}30` }}
                >
                  {f.icon}
                </div>
                <div className="flex-1">
                  <div className="text-sm font-bold text-text-primary group-hover:text-white">{f.title}</div>
                  <div className="text-xs text-text-muted">{f.desc}</div>
                </div>
                <svg className="w-4 h-4 text-text-muted group-hover:text-text-primary transition-all group-hover:translate-x-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </Link>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Activity chart */}
      <div className="card">
        <h3 className="text-sm font-bold text-text-primary mb-4">Processing Activity</h3>
        <ResponsiveContainer width="100%" height={120}>
          <AreaChart data={activity}>
            <defs>
              <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#6366F1" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#6366F1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="name" tick={{ fill: '#475569', fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis hide />
            <Tooltip
              contentStyle={{ background: '#0F1724', border: '1px solid #1E293B', borderRadius: '8px', fontSize: '12px' }}
              labelStyle={{ color: '#94A3B8' }}
            />
            <Area type="monotone" dataKey="jobs" stroke="#6366F1" fill="url(#grad)" strokeWidth={2} dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Recent jobs */}
      {recent.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-text-primary">Recent Jobs</h2>
            <Link to="/library" className="text-sm text-accent-primary hover:underline">View all</Link>
          </div>
          <div className="space-y-3">
            {recent.map((job) => (
              <div key={job.id} className="card flex items-center gap-4">
                <span className="text-xl">{job.type === 'separation' ? '🔪' : '🎤'}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-text-primary truncate">{job.originalFileName}</div>
                  <div className="text-xs text-text-muted">{formatDistanceToNow(job.createdAt, { addSuffix: true })}</div>
                </div>
                <span className={`badge text-xs ${job.status === 'completed' ? 'bg-green-500/10 text-green-400' : job.status === 'failed' ? 'bg-red-500/10 text-red-400' : 'bg-yellow-500/10 text-yellow-400'}`}>
                  {job.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {jobs.length === 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center py-16 text-text-muted"
        >
          <div className="text-5xl mb-4">🎵</div>
          <p className="text-lg font-semibold text-text-secondary">No jobs yet</p>
          <p className="text-sm mb-6">Upload a song to get started</p>
          <Link to="/separator" className="btn-primary">Start Separating</Link>
        </motion.div>
      )}
    </div>
  )
}
