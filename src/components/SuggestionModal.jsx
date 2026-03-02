import { useState } from 'react'
import { supabase } from '../supabaseClient'

export default function SuggestionModal({ user, onClose }) {
    const [message, setMessage] = useState('')
    const [sending, setSending] = useState(false)
    const [sent, setSent] = useState(false)

    const handleSubmit = async () => {
        if (!message.trim()) return
        setSending(true)

        try {
            const { error } = await supabase.from('suggestions').insert({
                user_id: user?.id,
                user_email: user?.email,
                message: message.trim(),
            })

            if (error) throw error
            setSent(true)
            setTimeout(() => onClose(), 1500)
        } catch (err) {
            alert('Failed to send: ' + err.message)
        } finally {
            setSending(false)
        }
    }

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-card" onClick={(e) => e.stopPropagation()}>
                {sent ? (
                    <>
                        <h2>✅ Thank you!</h2>
                        <p>Your suggestion has been recorded. We&apos;ll review it soon.</p>
                    </>
                ) : (
                    <>
                        <h2>💡 Send a Suggestion</h2>
                        <p>
                            What would you like to see changed or added? Your feedback helps us improve the tool.
                        </p>
                        <textarea
                            placeholder="e.g. It would be nice if I could zoom into the PDF by scrolling..."
                            value={message}
                            onChange={(e) => setMessage(e.target.value)}
                            autoFocus
                        />
                        <div className="modal-actions">
                            <button className="btn btn-outline" onClick={onClose}>Cancel</button>
                            <button
                                className="btn btn-primary"
                                onClick={handleSubmit}
                                disabled={sending || !message.trim()}
                                style={{ width: 'auto' }}
                            >
                                {sending ? 'Sending...' : 'Send Suggestion'}
                            </button>
                        </div>
                    </>
                )}
            </div>
        </div>
    )
}
