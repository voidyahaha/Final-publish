import { Routes, Route, Navigate } from 'react-router-dom'
import { useEffect } from 'react'
import Layout from './components/layout/Layout'
import AuthPage from './pages/Auth'
import Dashboard from './pages/Dashboard'
import Separator from './pages/Separator'
import VocalMixer from './pages/VocalMixer'
import Library from './pages/Library'
import Analyzer from './pages/Analyzer'
import Settings from './pages/Settings'
import { useAuth } from './hooks/useAuth'
import { useJobs } from './hooks/useJob'

function AppRoutes() {
  const { user, loading } = useAuth()
  useJobs(user?.uid)

  if (loading) {
    return (
      <div className="min-h-screen bg-bg-primary flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="flex gap-1.5 justify-center items-end h-10">
            {[1,2,3,4,5].map(i => (
              <div key={i} className="w-2 rounded-full bg-accent-primary"
                style={{ height: `${8 + i * 6}px`, animation: `waveformPulse 1.2s ease-in-out ${i * 0.12}s infinite` }} />
            ))}
          </div>
          <p className="text-text-muted text-sm">Loading StemAI...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return (
      <Routes>
        <Route path="/auth" element={<AuthPage />} />
        <Route path="*" element={<Navigate to="/auth" replace />} />
      </Routes>
    )
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/separator" element={<Separator />} />
        <Route path="/mixer" element={<VocalMixer />} />
        <Route path="/library" element={<Library />} />
        <Route path="/analyzer" element={<Analyzer />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
      <Route path="/auth" element={<Navigate to="/" replace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return <AppRoutes />
}
