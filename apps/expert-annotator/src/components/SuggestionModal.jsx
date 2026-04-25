import { useState } from 'react'
import { supabase } from '../supabaseClient'
import { appendTestEvent, isTestModeEnabled } from '../utils/testMode'

const ATTACHMENT_BUCKET = 'suggestion-attachments'
const MAX_IMAGE_ATTACHMENTS = 5
const MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024
const ALLOWED_IMAGE_MIME_TYPES = new Set([
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/gif',
    'image/bmp',
    'image/tiff',
    'image/heic',
])

function sanitizeFileName(filename) {
    return String(filename || 'image')
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9._-]+/g, '-')
        .replace(/-+/g, '-')
}

function formatFileSize(bytes) {
    if (!Number.isFinite(bytes) || bytes <= 0) return '0 B'
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function SuggestionModal({
    user,
    reviewerProfile = null,
    onClose,
    testMode = false,
    persistInTestMode = false,
}) {
    const [message, setMessage] = useState('')
    const [sending, setSending] = useState(false)
    const [sent, setSent] = useState(false)
    const [selectedFiles, setSelectedFiles] = useState([])
    const [attachmentError, setAttachmentError] = useState('')

    const handlePickFiles = (event) => {
        const incomingFiles = Array.from(event.target.files || [])
        event.target.value = ''
        if (!incomingFiles.length) return

        const validatedFiles = []
        const nextErrors = []

        for (const file of incomingFiles) {
            const mimeType = String(file.type || '').toLowerCase()
            if (!ALLOWED_IMAGE_MIME_TYPES.has(mimeType)) {
                nextErrors.push(`${file.name} has an unsupported image type.`)
                continue
            }
            if (file.size > MAX_IMAGE_SIZE_BYTES) {
                nextErrors.push(`${file.name} exceeds 10 MB.`)
                continue
            }
            validatedFiles.push(file)
        }

        setSelectedFiles((previous) => {
            const combined = [...previous]
            for (const file of validatedFiles) {
                const exists = combined.some((candidate) =>
                    candidate.name === file.name
                    && candidate.size === file.size
                    && candidate.lastModified === file.lastModified
                )
                if (!exists) combined.push(file)
            }

            if (combined.length > MAX_IMAGE_ATTACHMENTS) {
                nextErrors.push(`You can attach up to ${MAX_IMAGE_ATTACHMENTS} images.`)
            }
            return combined.slice(0, MAX_IMAGE_ATTACHMENTS)
        })

        setAttachmentError(nextErrors.join(' '))
    }

    const removeSelectedFile = (targetIndex) => {
        setSelectedFiles((previous) => previous.filter((_, index) => index !== targetIndex))
    }

    const handleSubmit = async () => {
        if (!message.trim()) return
        setSending(true)
        setAttachmentError('')

        const useLocalOnlyMode = !persistInTestMode && (testMode || isTestModeEnabled())
        const uploadedStorageObjects = []

        try {
            const attachments = []
            if (useLocalOnlyMode) {
                for (const file of selectedFiles) {
                    attachments.push({
                        bucket: ATTACHMENT_BUCKET,
                        path: null,
                        file_name: file.name,
                        file_size: file.size,
                        mime_type: file.type || 'image/*',
                        uploaded_at: new Date().toISOString(),
                        uploaded_by_auth_user_id: user?.id || null,
                        local_only: true,
                    })
                }
            } else {
                for (let index = 0; index < selectedFiles.length; index += 1) {
                    const file = selectedFiles[index]
                    const storagePath = `${user?.id || 'anonymous'}/${Date.now()}-${index}-${sanitizeFileName(file.name)}`
                    const { error: uploadError } = await supabase.storage
                        .from(ATTACHMENT_BUCKET)
                        .upload(storagePath, file, {
                            upsert: false,
                            contentType: file.type || 'application/octet-stream',
                        })
                    if (uploadError) {
                        throw new Error(`Failed to upload ${file.name}: ${uploadError.message}`)
                    }

                    uploadedStorageObjects.push({ bucket: ATTACHMENT_BUCKET, path: storagePath })
                    attachments.push({
                        bucket: ATTACHMENT_BUCKET,
                        path: storagePath,
                        file_name: file.name,
                        file_size: file.size,
                        mime_type: file.type || 'image/*',
                        uploaded_at: new Date().toISOString(),
                        uploaded_by_auth_user_id: user?.id || null,
                    })
                }
            }

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
                attachments,
                context: {
                    source: 'annotator_suggestion_modal',
                    attachment_count: attachments.length,
                },
            }

            if (useLocalOnlyMode) {
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
            if (uploadedStorageObjects.length > 0) {
                const pathsByBucket = uploadedStorageObjects.reduce((accumulator, row) => {
                    if (!accumulator[row.bucket]) {
                        accumulator[row.bucket] = []
                    }
                    accumulator[row.bucket].push(row.path)
                    return accumulator
                }, {})

                await Promise.all(Object.entries(pathsByBucket).map(async ([bucket, paths]) => {
                    try {
                        await supabase.storage.from(bucket).remove(paths)
                    } catch (cleanupError) {
                        console.error('Attachment cleanup failed:', cleanupError)
                    }
                }))
            }
            setAttachmentError(`Failed to send suggestion: ${err.message}`)
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
                        <p>
                            Your suggestion has been recorded{selectedFiles.length ? ` with ${selectedFiles.length} image attachment${selectedFiles.length > 1 ? 's' : ''}` : ''}. We&apos;ll review it soon.
                        </p>
                    </>
                ) : (
                    <>
                        <h2>Send a Suggestion</h2>
                        <p>
                            What would you like to see changed or added? Your feedback helps us improve the tool.
                        </p>
                        {testMode && !persistInTestMode && (
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
                        <div className="suggestion-attachment-panel">
                            <label className="suggestion-attachment-picker">
                                <input
                                    type="file"
                                    accept="image/*"
                                    multiple
                                    onChange={handlePickFiles}
                                    disabled={sending}
                                />
                                <span>Add images</span>
                            </label>
                            <div className="suggestion-attachment-hint">
                                Up to {MAX_IMAGE_ATTACHMENTS} images, max 10 MB each.
                            </div>

                            {selectedFiles.length > 0 && (
                                <div className="suggestion-attachment-list">
                                    {selectedFiles.map((file, index) => (
                                        <div key={`${file.name}-${file.lastModified}-${index}`} className="suggestion-attachment-item">
                                            <div>
                                                <div className="suggestion-attachment-name">{file.name}</div>
                                                <div className="suggestion-attachment-meta">{formatFileSize(file.size)}</div>
                                            </div>
                                            <button
                                                className="btn btn-outline suggestion-attachment-remove"
                                                onClick={() => removeSelectedFile(index)}
                                                disabled={sending}
                                            >
                                                Remove
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            )}
                            {attachmentError && <div className="error-msg suggestion-attachment-error">{attachmentError}</div>}
                        </div>
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
