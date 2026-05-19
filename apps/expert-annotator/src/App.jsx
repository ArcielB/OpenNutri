import { useState, useEffect } from 'react'
import { supabase } from './supabaseClient'
import Login from './pages/Login'
import ResetPassword from './pages/ResetPassword'
import Annotate from './pages/Annotate'
import { useTheme } from './hooks/useTheme'
import './index.css'

export default function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [isRecovery, setIsRecovery] = useState(false)
  const { theme, toggleTheme, clearOverride } = useTheme()

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
    supabase.auth.getSession().then(({ data: { session } }) => {
      const nextUser = session?.user ?? null
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
  }, [])

  const handleLogout = async () => {
    await supabase.auth.signOut()
    setUser(null)
    clearOverride()
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem('opennutri-theme')
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
    return <Login onLogin={setUser} />
  }

  return <Annotate user={user} onLogout={handleLogout} theme={theme} toggleTheme={toggleTheme} />
}
