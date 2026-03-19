import { useState, useEffect } from 'react'
import { supabase } from '../supabaseClient'

export default function ResetPassword({ onDone }) {
    const [password, setPassword] = useState('')
    const [confirm, setConfirm] = useState('')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)
    const [success, setSuccess] = useState(false)
    const [sessionChecked, setSessionChecked] = useState(false)
    const [hasSession, setHasSession] = useState(false)

    useEffect(() => {
        // Clear any existing error when user edits fields
        if (hasSession && error && (password || confirm)) {
            setError(null)
        }
    }, [password, confirm])

    useEffect(() => {
        let cancelled = false

        const initSession = async () => {
            if (typeof window !== 'undefined') {
                const hashParams = new URLSearchParams(window.location.hash.replace('#', ''))
                const accessToken = hashParams.get('access_token')
                const refreshToken = hashParams.get('refresh_token')
                if (accessToken && refreshToken) {
                    const { error: setSessionError } = await supabase.auth.setSession({
                        access_token: accessToken,
                        refresh_token: refreshToken,
                    })
                    if (!cancelled && !setSessionError) {
                        setHasSession(true)
                        setSessionChecked(true)
                        return
                    }
                }
            }

            const { data: { session } } = await supabase.auth.getSession()
            if (cancelled) return
            if (!session) {
                setError('Recovery link is invalid or expired. Please request a new reset email.')
            } else {
                setHasSession(true)
            }
            setSessionChecked(true)
        }

        initSession()
        return () => { cancelled = true }
    }, [])

    const cleanUrl = () => {
        if (typeof window === 'undefined') return
        const path = window.location.pathname === '/reset' ? '/' : window.location.pathname
        window.history.replaceState(null, '', path)
    }

    const handleSubmit = async (e) => {
        e.preventDefault()
        if (!password || !confirm) {
            setError('Please fill out both password fields.')
            return
        }
        if (password !== confirm) {
            setError('Passwords do not match.')
            return
        }
        if (password.length < 8) {
            setError('Password must be at least 8 characters.')
            return
        }

        setLoading(true)
        setError(null)
        try {
            const { error: updateError } = await supabase.auth.updateUser({ password })
            if (updateError) throw updateError
            setSuccess(true)
        } catch (err) {
            setError(err.message || 'Failed to update password.')
        } finally {
            setLoading(false)
        }
    }

    const handleReturnToLogin = async () => {
        await supabase.auth.signOut()
        cleanUrl()
        onDone()
    }

    return (
        <div className="login-page">
            <div className="login-card">
                <span className="logo">🔐</span>
                <h1>Reset your password</h1>
                <p className="subtitle">Create a new password for your account</p>

                {error && <div className="error-msg">{error}</div>}
                {success && (
                    <div className="error-msg" style={{ background: 'rgba(34,197,94,0.1)', borderColor: 'rgba(34,197,94,0.3)', color: '#86efac' }}>
                        Password updated. You can now sign in.
                    </div>
                )}

                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label>New password</label>
                        <input
                            type="password"
                            placeholder="Enter a new password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                        />
                    </div>
                    <div className="form-group">
                        <label>Confirm password</label>
                        <input
                            type="password"
                            placeholder="Re-enter your new password"
                            value={confirm}
                            onChange={(e) => setConfirm(e.target.value)}
                            required
                        />
                    </div>
                    <button
                        type="submit"
                        className="btn btn-primary"
                        disabled={loading || success || !sessionChecked || !hasSession}
                    >
                        {loading ? 'Updating...' : 'Update Password'}
                    </button>
                </form>

                <div className="forgot-password" style={{ marginTop: '18px' }}>
                    <a onClick={handleReturnToLogin}>Return to sign in</a>
                </div>
            </div>
        </div>
    )
}
