import { useState, useEffect } from 'react'
import { supabase } from './supabaseClient'
import Login from './pages/Login'
import ResetPassword from './pages/ResetPassword'
import Annotate from './pages/Annotate'
import { useTheme } from './hooks/useTheme'
import './index.css'

const AUTH_PORTAL_INTENT_KEY = 'opennutri-auth-portal-intent'

function resolveLoginMode(pathname) {
  return pathname === '/admin-login' ? 'admin' : 'regular'
}

function applyLoginRouteMode(mode) {
  if (typeof window === 'undefined') return
  const targetPath = mode === 'admin' ? '/admin-login' : '/login'
  if (window.location.pathname !== targetPath) {
    window.history.replaceState({}, '', targetPath)
  }
}

export default function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [isRecovery, setIsRecovery] = useState(false)
  const [loginMode, setLoginMode] = useState(() => (
    typeof window === 'undefined' ? 'regular' : resolveLoginMode(window.location.pathname)
  ))
  const { theme, toggleTheme, clearOverride } = useTheme()

  useEffect(() => {
    if (typeof window === 'undefined') return undefined
    const syncModeFromRoute = () => {
      setLoginMode(resolveLoginMode(window.location.pathname))
    }
    syncModeFromRoute()
    window.addEventListener('popstate', syncModeFromRoute)
    return () => window.removeEventListener('popstate', syncModeFromRoute)
  }, [])

  useEffect(() => {
    const isRecoveryUrl = () => {
      if (typeof window === 'undefined') return false
      const hash = window.location.hash || ''
      const search = window.location.search || ''
      const path = window.location.pathname || ''
      return (
        hash.includes('type=recovery') ||
        search.includes('type=recovery') ||
        search.includes('reset=1') ||
        path.startsWith('/reset')
      )
    }

    // Check for existing session
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      const nextUser = session?.user ?? null
      if (nextUser && !isRecoveryUrl()) {
        const intentMode = typeof window !== 'undefined' ? window.sessionStorage.getItem(AUTH_PORTAL_INTENT_KEY) : null
        const modeToValidate = intentMode === 'admin' || intentMode === 'regular' ? intentMode : loginMode
        const { data, error } = await supabase.rpc('sync_reviewer_profile')
        if (error) {
          await supabase.auth.signOut()
          setUser(null)
          setLoading(false)
          return
        }
        const profile = Array.isArray(data) ? data[0] : data
        const isAdminUser = Boolean(profile?.cockpit_access || profile?.can_approve_labels)
        const expectedMode = isAdminUser ? 'admin' : 'regular'
        if (modeToValidate !== expectedMode) {
          await supabase.auth.signOut()
          setUser(null)
          applyLoginRouteMode(expectedMode)
          setLoginMode(expectedMode)
          setLoading(false)
          return
        }
        if (typeof window !== 'undefined') {
          window.sessionStorage.removeItem(AUTH_PORTAL_INTENT_KEY)
        }
      }
      setUser(nextUser)
      if (isRecoveryUrl()) {
        setIsRecovery(true)
      }
      if (!nextUser) {
        clearOverride()
        if (typeof window !== 'undefined') {
          sessionStorage.removeItem('opennutri-theme')
        }
      }
      setLoading(false)
    })

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, session) => {
        const nextUser = session?.user ?? null
        setUser(nextUser)
        if (event === 'PASSWORD_RECOVERY') {
          setIsRecovery(true)
        }
        if (event === 'SIGNED_OUT') {
          setIsRecovery(false)
        }
        if (!nextUser) {
          clearOverride()
          if (typeof window !== 'undefined') {
            sessionStorage.removeItem('opennutri-theme')
          }
        }
      }
    )

    return () => subscription.unsubscribe()
  }, [clearOverride, loginMode])

  useEffect(() => {
    if (typeof window === 'undefined' || !user || isRecovery) return
    if (window.location.pathname === '/login' || window.location.pathname === '/admin-login') {
      window.history.replaceState({}, '', '/')
    }
  }, [isRecovery, user])

  const handleLogout = async () => {
    await supabase.auth.signOut()
    setUser(null)
    clearOverride()
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem('opennutri-theme')
      window.sessionStorage.removeItem(AUTH_PORTAL_INTENT_KEY)
    }
  }

  if (loading) {
    return (
      <div className="login-page">
        <div style={{ color: 'var(--text-muted)', fontSize: '14px' }}>
          Loading...
        </div>
      </div>
    )
  }

  if (isRecovery) {
    return <ResetPassword onDone={() => setIsRecovery(false)} />
  }

  if (!user) {
    return (
      <Login
        mode={loginMode}
        onLogin={setUser}
        onSwitchMode={(nextMode) => {
          applyLoginRouteMode(nextMode)
          setLoginMode(nextMode)
        }}
      />
    )
  }

  return <Annotate user={user} onLogout={handleLogout} theme={theme} toggleTheme={toggleTheme} />
}
