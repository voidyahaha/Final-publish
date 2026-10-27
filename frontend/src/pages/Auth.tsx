import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useAuth } from '../hooks/useAuth'
import clsx from 'clsx'

type AuthMode = 'signin' | 'signup' | 'reset'

export default function AuthPage() {
  const [mode, setMode] = useState<AuthMode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { signInEmail, signUpEmail, signInGoogle, signInGuest, resetPassword, authError, setAuthError, user, loading } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (user && !loading) navigate('/')
  }, [user, loading, navigate])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)
    try {
      if (mode === 'signin') {
        await signInEmail(email, password)
      } else if (mode === 'signup') {
        await signUpEmail(email, password, displayName)
      } else {
        await resetPassword(email)
        setMode('signin')
      }
    } catch {
      // error is shown via toast and authError
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleGoogle = async () => {
    setIsSubmitting(true)
    try {
      await signInGoogle()
    } catch {
      // handled
    } finally {
      setIsSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-bg-primary flex items-center justify-center">
        <div className="flex gap-1 items-end h-8">
          {[1,2,3,4,5].map(i => (
            <div key={i} className="w-1.5 rounded-full bg-accent-primary"
              style={{ height: `${8 + i * 4}px`, animation: `waveformPulse 1.2s ease-in-out ${i*0.12}s infinite` }} />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-bg-primary flex">
      {/* Left: Branding */}
      <div className="hidden lg:flex flex-col flex-1 bg-bg-secondary border-r border-border p-12 relative overflow-hidden">
        <div className="absolute inset-0 bg-glow-primary opacity-50" />
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-16">
            <div className="w-10 h-10 rounded-xl bg-gradient-primary flex items-center justify-center shadow-glow-md">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2z" />
              </svg>
            </div>
            <span className="text-2xl font-black gradient-text">StemAI</span>
          </div>

          <h2 className="text-4xl font-black text-text-primary mb-4 leading-tight">
            Separate any song<br />
            <span className="gradient-text">with AI precision</span>
          </h2>
          <p className="text-text-secondary text-lg mb-12 max-w-sm">
            Powered by HTDemucs — state-of-the-art AI for professional-grade stem separation.
          </p>

          {[
            { icon: '🎤', label: 'Vocals', desc: 'Crystal-clear vocal isolation' },
            { icon: '🥁', label: 'Drums', desc: 'Full drum track extraction' },
            { icon: '🎸', label: 'Bass', desc: 'Deep bass stem separation' },
            { icon: '🎹', label: 'Other', desc: 'All remaining instruments' },
          ].map((item) => (
            <div key={item.label} className="flex items-center gap-3 mb-4 p-3 rounded-xl bg-bg-hover border border-border">
              <span className="text-2xl">{item.icon}</span>
              <div>
                <div className="text-sm font-semibold text-text-primary">{item.label}</div>
                <div className="text-xs text-text-muted">{item.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Right: Auth form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-md"
        >
          {/* Logo mobile */}
          <div className="flex items-center gap-2 mb-8 lg:hidden">
            <div className="w-8 h-8 rounded-lg bg-gradient-primary flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2z" />
              </svg>
            </div>
            <span className="font-black text-xl gradient-text">StemAI</span>
          </div>

          <h1 className="text-2xl font-black text-text-primary mb-1">
            {mode === 'signin' ? 'Welcome back' : mode === 'signup' ? 'Create account' : 'Reset password'}
          </h1>
          <p className="text-text-muted text-sm mb-8">
            {mode === 'signin' ? 'Sign in to your StemAI account' : mode === 'signup' ? 'Start separating music with AI' : 'Enter your email to reset password'}
          </p>

          {/* Google & Guest */}
          {mode !== 'reset' && (
            <>
              <button
                onClick={handleGoogle}
                disabled={isSubmitting}
                className="w-full flex items-center justify-center gap-3 py-3 px-4 rounded-xl bg-bg-card border border-border hover:border-border-light transition-all font-medium text-sm mb-2"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Continue with Google
              </button>

              <button
                type="button"
                onClick={() => signInGuest()}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-accent-primary/10 border border-accent-primary/30 hover:bg-accent-primary/20 text-accent-primary transition-all font-medium text-xs mb-4"
              >
                ⚡ Instant Guest Access (No Sign In Needed)
              </button>

              <div className="flex items-center gap-3 mb-4">
                <div className="flex-1 h-px bg-border" />
                <span className="text-xs text-text-muted">or continue with email</span>
                <div className="flex-1 h-px bg-border" />
              </div>
            </>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'signup' && (
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1.5">Full name</label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => { setDisplayName(e.target.value); setAuthError(null) }}
                  className="input"
                  placeholder="Your name"
                  required
                  autoComplete="name"
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1.5">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => { setEmail(e.target.value); setAuthError(null) }}
                className="input"
                placeholder="you@example.com"
                required
                autoComplete="email"
              />
            </div>

            {mode !== 'reset' && (
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1.5">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setAuthError(null) }}
                  className="input"
                  placeholder={mode === 'signup' ? 'At least 6 characters' : 'Your password'}
                  required
                  minLength={mode === 'signup' ? 6 : undefined}
                  autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                />
              </div>
            )}

            {authError && (
              <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-3">
                {authError}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="btn-primary w-full py-3 flex items-center justify-center gap-2"
            >
              {isSubmitting ? (
                <>
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Processing...
                </>
              ) : mode === 'signin' ? 'Sign In' : mode === 'signup' ? 'Create Account' : 'Send Reset Email'}
            </button>
          </form>

          {/* Mode switcher */}
          <div className="mt-6 text-center text-sm">
            {mode === 'signin' ? (
              <span className="text-text-muted">
                No account?{' '}
                <button onClick={() => { setMode('signup'); setAuthError(null) }} className="text-accent-primary hover:underline font-medium">
                  Create one
                </button>
                {' · '}
                <button onClick={() => { setMode('reset'); setAuthError(null) }} className="text-text-muted hover:text-text-secondary">
                  Forgot password?
                </button>
              </span>
            ) : mode === 'signup' ? (
              <span className="text-text-muted">
                Already have an account?{' '}
                <button onClick={() => { setMode('signin'); setAuthError(null) }} className="text-accent-primary hover:underline font-medium">
                  Sign in
                </button>
              </span>
            ) : (
              <button onClick={() => { setMode('signin'); setAuthError(null) }} className="text-accent-primary hover:underline font-medium">
                Back to sign in
              </button>
            )}
          </div>
        </motion.div>
      </div>
    </div>
  )
}
