import { useState } from 'react'
import { supabase } from '../supabaseClient'

const AUTH_PORTAL_INTENT_KEY = 'opennutri-auth-portal-intent'

export default function Login({ onLogin, mode = 'regular', onSwitchMode }) {
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)
    const [resetSent, setResetSent] = useState(false)
    const isAdminMode = mode === 'admin'
    const oppositeMode = isAdminMode ? 'regular' : 'admin'

    const handleLogin = async (e) => {
        e.preventDefault()
        setLoading(true)
        setError(null)

        try {
            const { data, error: authError } = await supabase.auth.signInWithPassword({
                email,
                password,
            })

            if (authError) throw authError
            const { data: profileData, error: profileError } = await supabase.rpc('sync_reviewer_profile')
            if (profileError) throw profileError
            const profile = Array.isArray(profileData) ? profileData[0] : profileData
            const isAdminUser = Boolean(profile?.cockpit_access || profile?.can_approve_labels)
            if (isAdminMode !== isAdminUser) {
                await supabase.auth.signOut()
                throw new Error(
                    isAdminMode
                        ? 'This account is not an admin account. Please use the regular login page.'
                        : 'This account is an admin account. Please use the admin login page.'
                )
            }
            if (typeof window !== 'undefined') {
                window.sessionStorage.removeItem(AUTH_PORTAL_INTENT_KEY)
            }
            onLogin(data.user)
        } catch (err) {
            setError(err.message || 'Login failed. Please check your credentials.')
        } finally {
            setLoading(false)
        }
    }

    const handleGoogleLogin = async () => {
        setLoading(true)
        setError(null)

        try {
            const targetRedirect = `${window.location.origin}${isAdminMode ? '/admin-login' : '/login'}`
            if (typeof window !== 'undefined') {
                window.sessionStorage.setItem(AUTH_PORTAL_INTENT_KEY, mode)
            }
            const { data, error: authError } = await supabase.auth.signInWithOAuth({
                provider: 'google',
                options: {
                    redirectTo: targetRedirect,
                    skipBrowserRedirect: true,
                },
            })

            if (authError) throw authError
            if (!data?.url) throw new Error('Google login failed: missing authorization URL.')

            const authUrl = new URL(data.url)
            authUrl.searchParams.set('redirect_to', targetRedirect)
            window.location.assign(authUrl.toString())
        } catch (err) {
            if (typeof window !== 'undefined') {
                window.sessionStorage.removeItem(AUTH_PORTAL_INTENT_KEY)
            }
            setError(err.message || 'Google login failed.')
            setLoading(false)
        }
    }

    const handleForgotPassword = async () => {
        if (!email) {
            setError('Please enter your email first, then click "Forgot password?"')
            return
        }
        setLoading(true)
        setError(null)

        try {
            const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, {
                redirectTo: `${window.location.origin}/reset`,
            })
            if (resetError) throw resetError
            setResetSent(true)
        } catch (err) {
            setError(err.message || 'Failed to send reset email.')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="login-page">
            <div className="login-card">
                <span className="logo" aria-hidden="true">ON</span>
                <h1>{isAdminMode ? 'OpenNutri Admin' : 'OpenNutri Annotator'}</h1>
                <p className="subtitle">{isAdminMode ? 'Admin and approval workspace' : 'Food composition data labeling workspace'}</p>

                {error && <div className="error-msg">{error}</div>}
                {resetSent && (
                    <div className="error-msg" style={{ background: 'rgba(34,197,94,0.1)', borderColor: 'rgba(34,197,94,0.3)', color: '#86efac' }}>
                        Password reset email sent! Check your inbox.
                    </div>
                )}

                <button
                    type="button"
                    className="btn btn-google"
                    onClick={handleGoogleLogin}
                    disabled={loading}
                >
                    <svg width="18" height="18" viewBox="0 0 24 24">
                        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
                        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                    </svg>
                    {isAdminMode ? 'Admin sign in with Google' : 'Sign in with Google'}
                </button>

                <div className="divider">
                    <span>or</span>
                </div>

                <form onSubmit={handleLogin}>
                    <div className="form-group">
                        <label>Email</label>
                        <input
                            type="email"
                            placeholder="annotator@opennutri.com"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                        />
                    </div>
                    <div className="form-group">
                        <label>Password</label>
                        <input
                            type="password"
                            placeholder="Enter your password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                        />
                    </div>
                    <button
                        type="submit"
                        className="btn btn-primary"
                        disabled={loading}
                    >
                        {loading ? 'Signing In...' : 'Sign In'}
                    </button>
                </form>
                <div className="login-mode-switch">
                    <button
                        type="button"
                        className="btn btn-outline"
                        onClick={() => onSwitchMode?.(oppositeMode)}
                        disabled={loading}
                    >
                        {isAdminMode ? 'Go to regular login' : 'Go to admin login'}
                    </button>
                </div>

                <div className="forgot-password">
                    <a onClick={handleForgotPassword}>Forgot password?</a>
                </div>
            </div>
        </div>
    )
}
