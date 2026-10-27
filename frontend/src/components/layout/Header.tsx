import { useLocation } from 'react-router-dom'
import { useAppStore } from '../../store'

const pageTitles: Record<string, { title: string; subtitle: string }> = {
  '/': { title: 'Overview', subtitle: 'AI Music Separation Platform' },
  '/separator': { title: 'Stem Separator', subtitle: 'Split audio into isolated tracks using HTDemucs AI' },
  '/mixer': { title: 'Vocal Mixer', subtitle: 'Record or upload vocals and blend with any instrumental' },
  '/library': { title: 'My Library', subtitle: 'All your processed tracks and stems' },
  '/analyzer': { title: 'AI Analyzer', subtitle: 'Deep analysis of tempo, key, beats and structure' },
  '/settings': { title: 'Settings', subtitle: 'Configure your account and API connections' },
}

export default function Header() {
  const location = useLocation()
  const { jobs } = useAppStore()
  const page = pageTitles[location.pathname] || { title: 'StemAI', subtitle: '' }
  const activeJobs = jobs.filter(j => !['completed','failed'].includes(j.status))

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-border bg-bg-secondary/80 backdrop-blur-sm sticky top-0 z-20">
      <div>
        <h1 className="text-lg font-bold text-text-primary">{page.title}</h1>
        <p className="text-xs text-text-muted">{page.subtitle}</p>
      </div>

      <div className="flex items-center gap-3">
        {/* Status indicator */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-bg-hover border border-border">
          <div className="w-2 h-2 rounded-full bg-accent-green animate-pulse" />
          <span className="text-xs text-text-secondary">
            {activeJobs.length > 0 ? `${activeJobs.length} job${activeJobs.length > 1 ? 's' : ''} running` : 'Ready'}
          </span>
        </div>

        {/* Model badge */}
        <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-primary/10 border border-accent-primary/20">
          <svg className="w-3.5 h-3.5 text-accent-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <span className="text-xs font-medium text-accent-primary">HTDemucs</span>
        </div>
      </div>
    </header>
  )
}
