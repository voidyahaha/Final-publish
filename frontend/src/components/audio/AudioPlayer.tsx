import { useEffect, useRef, useState } from 'react'
import WaveSurfer from 'wavesurfer.js'
import clsx from 'clsx'
import { formatDuration } from '../../services/storage'
import { resolveAudioUrl } from '../../services/api'

interface AudioPlayerProps {
  url: string
  title?: string
  subtitle?: string
  color?: string
  compact?: boolean
}

export default function AudioPlayer({
  url: rawUrl,
  title,
  subtitle,
  color = '#6366F1',
  compact = false,
}: AudioPlayerProps) {
  const url = resolveAudioUrl(rawUrl)
  const containerRef = useRef<HTMLDivElement>(null)
  const wavesurferRef = useRef<WaveSurfer | null>(null)
  const [playing, setPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolume] = useState(0.8)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: '#1E293B',
      progressColor: color,
      cursorColor: color,
      barWidth: 2,
      barRadius: 2,
      barGap: 1,
      height: compact ? 40 : 64,
      normalize: true,
      interact: true,
    })

    ws.on('ready', () => {
      setDuration(ws.getDuration())
      setLoading(false)
    })

    ws.on('timeupdate', (t) => setCurrentTime(t))
    ws.on('play', () => setPlaying(true))
    ws.on('pause', () => setPlaying(false))
    ws.on('finish', () => setPlaying(false))
    ws.on('error', (e) => {
      setError('Failed to load audio')
      setLoading(false)
    })

    ws.load(url)
    ws.setVolume(volume)
    wavesurferRef.current = ws

    return () => ws.destroy()
  }, [url, color, compact])

  const togglePlay = () => {
    wavesurferRef.current?.playPause()
  }

  const handleVolumeChange = (val: number) => {
    setVolume(val)
    wavesurferRef.current?.setVolume(val)
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-sm text-red-400">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        {error}
      </div>
    )
  }

  return (
    <div className={clsx('bg-bg-secondary border border-border rounded-xl p-4 space-y-3', compact && 'space-y-2')}>
      {(title || subtitle) && !compact && (
        <div className="flex items-center justify-between">
          <div>
            {title && <div className="text-sm font-semibold text-text-primary">{title}</div>}
            {subtitle && <div className="text-xs text-text-muted">{subtitle}</div>}
          </div>
          <a
            href={url}
            download={title || 'audio'}
            className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-bg-hover transition-all"
            title="Download"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          </a>
        </div>
      )}

      {/* Waveform */}
      <div className="relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-bg-secondary rounded">
            <div className="flex gap-1 items-end h-8">
              {[1,2,3,4,5].map(i => (
                <div
                  key={i}
                  className="w-1.5 rounded-full"
                  style={{
                    background: color,
                    animation: `waveformPulse 1.2s ease-in-out ${i * 0.12}s infinite`,
                    height: `${8 + i * 4}px`
                  }}
                />
              ))}
            </div>
          </div>
        )}
        <div ref={containerRef} />
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3">
        <button
          onClick={togglePlay}
          disabled={loading}
          className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 transition-all"
          style={{ background: `${color}20`, border: `1px solid ${color}40` }}
        >
          {playing ? (
            <svg className="w-4 h-4" style={{ color }} fill="currentColor" viewBox="0 0 24 24">
              <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
            </svg>
          ) : (
            <svg className="w-4 h-4 ml-0.5" style={{ color }} fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z"/>
            </svg>
          )}
        </button>

        <div className="flex-1 min-w-0">
          <div className="flex justify-between text-xs text-text-muted mb-1">
            <span>{formatDuration(currentTime)}</span>
            <span>{formatDuration(duration)}</span>
          </div>
        </div>

        {!compact && (
          <div className="flex items-center gap-2 flex-shrink-0">
            <svg className="w-3.5 h-3.5 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072M12 6v12m0 0a7 7 0 01-4.95-11.95M12 18a7 7 0 004.95-11.95" />
            </svg>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={volume}
              onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
              className="w-16"
            />
          </div>
        )}
      </div>
    </div>
  )
}
