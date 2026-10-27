import { motion } from 'framer-motion'
import { useAuth } from '../hooks/useAuth'
import { useAppStore } from '../store'
import toast from 'react-hot-toast'

export default function Settings() {
  const { user, logout } = useAuth()
  const { jobs } = useAppStore()

  const stats = {
    total: jobs.length,
    completed: jobs.filter(j => j.status === 'completed').length,
    failed: jobs.filter(j => j.status === 'failed').length,
    separations: jobs.filter(j => j.type === 'separation').length,
    mixes: jobs.filter(j => j.type === 'vocal_mix').length,
  }

  return (
    <div className="space-y-8 max-w-2xl">
      <div>
        <h2 className="text-2xl font-black text-text-primary mb-1">Settings</h2>
        <p className="text-text-muted">Account, API configuration and preferences</p>
      </div>

      {/* Profile */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="card space-y-4">
        <h3 className="text-sm font-bold text-text-primary border-b border-border pb-3">Profile</h3>
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-full bg-gradient-primary flex items-center justify-center text-xl font-black text-white">
            {user?.displayName?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || '?'}
          </div>
          <div>
            <div className="font-bold text-text-primary">{user?.displayName || 'User'}</div>
            <div className="text-sm text-text-muted">{user?.email}</div>
            <div className="mt-1">
              <span className="badge bg-accent-primary/20 text-accent-primary text-xs capitalize">
                {user?.plan || 'Free'} Plan
              </span>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Stats */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }} className="card space-y-4">
        <h3 className="text-sm font-bold text-text-primary border-b border-border pb-3">Usage Statistics</h3>
        <div className="grid grid-cols-3 gap-3">
          {Object.entries(stats).map(([k, v]) => (
            <div key={k} className="text-center p-3 rounded-xl bg-bg-secondary border border-border">
              <div className="text-xl font-black text-text-primary">{v}</div>
              <div className="text-xs text-text-muted capitalize mt-0.5">{k}</div>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Firebase config */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="card space-y-4">
        <h3 className="text-sm font-bold text-text-primary border-b border-border pb-3">Firebase Configuration</h3>
        <div className="space-y-2">
          {[
            { label: 'Project ID', value: 'vocal-separater-5eb7c' },
            { label: 'Auth Domain', value: 'vocal-separater-5eb7c.firebaseapp.com' },
            { label: 'Storage Bucket', value: 'vocal-separater-5eb7c.firebasestorage.app' },
          ].map(row => (
            <div key={row.label} className="flex items-center justify-between py-2">
              <span className="text-xs text-text-muted">{row.label}</span>
              <span className="text-xs font-mono text-text-secondary bg-bg-hover px-2 py-1 rounded">{row.value}</span>
            </div>
          ))}
        </div>
        <div className="flex items-center gap-2 p-3 rounded-xl bg-green-500/10 border border-green-500/20">
          <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          <span className="text-xs text-green-400 font-medium">Firebase client configured</span>
        </div>
      </motion.div>

      {/* Backend config */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="card space-y-4">
        <h3 className="text-sm font-bold text-text-primary border-b border-border pb-3">Backend API</h3>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-text-muted">API URL</span>
            <span className="text-xs font-mono text-text-secondary bg-bg-hover px-2 py-1 rounded">
              {import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : 'same origin')}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-text-muted">AI Model</span>
            <span className="text-xs font-mono text-accent-primary bg-accent-primary/10 px-2 py-1 rounded">HTDemucs FT</span>
          </div>
        </div>
      </motion.div>

      {/* Danger zone */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="card border-red-500/20 space-y-4">
        <h3 className="text-sm font-bold text-red-400 border-b border-red-500/20 pb-3">Danger Zone</h3>
        <button
          onClick={logout}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition-all text-sm font-medium"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          Sign Out
        </button>
      </motion.div>
    </div>
  )
}
