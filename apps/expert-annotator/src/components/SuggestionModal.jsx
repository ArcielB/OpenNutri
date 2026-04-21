import { useState } from 'react'
import { supabase } from '../supabaseClient'
import { appendTestEvent, isTestModeEnabled } from '../utils/testMode'

export default function SuggestionModal({ user, reviewerProfile = null, onClose, testMode = false }) {
    const [message, setMessage] = useState('')
    const [sending, setSending] = useState(false)
    const [sent, setSent] = useState(false)

    const handleSubmit = async () => {
        if (!message.trim()) return
        setSending(true)

        try {
            const payload = {
                item_kind: 'suggestion_review',
                status: 'new',
                submitted_by_auth_user_id: user?.id || null,
                submitted_by_email: user?.email || null,
                submitted_by_name:
                    reviewerProfile?.display_name ||
                    user?.user_metadata?.full_name ||
                    user?.user_metadata?.name ||
                    null,
                suggestion_text: message.trim(),
                context: {
                    source: 'annotator_suggestion_modal',
                },
            }

            if (testMode || isTestModeEnabled()) {
                appendTestEvent({
                    type: 'suggestion_review_item',
                    ...payload,
                })
                setSent(true)
                setTimeout(() => onClose(), 1500)
                return
            }
            const { error } = await supabase.from('backlog_review_items').insert(payload)

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
                        <h2>Thanks!</h2>
                        <p>Your suggestion has been recorded. We&apos;ll review it soon.</p>
                    </>
                ) : (
                    <>
                        <h2>Send a Suggestion</h2>
                        <p>
                            What would you like to see changed or added? Your feedback helps us improve the tool.
                        </p>
                        {testMode && (
                            <div className="test-mode-note">
                                Test mode is active. Suggestions are stored locally and not sent to Supabase.
                            </div>
                        )}
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
