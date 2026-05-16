import { useCallback, useState } from 'react'
import { supabase } from '../supabaseClient'
import { formatBytesLabel } from '../utils/annotateHelpers'

export default function SuggestionAttachmentsCell({ rowKey, attachments }) {
  const [expandedKey, setExpandedKey] = useState(null)
  const [resolvedUrls, setResolvedUrls] = useState({})
  const [loadingKeys, setLoadingKeys] = useState({})
  const [errorsByKey, setErrorsByKey] = useState({})

  const handleToggleAttachment = useCallback(async (attachment, index) => {
    const attachmentKey = `${rowKey}:${attachment.path || attachment.directUrl || index}`
    if (expandedKey === attachmentKey) {
      setExpandedKey(null)
      return
    }

    setExpandedKey(attachmentKey)
    if (resolvedUrls[attachmentKey] || loadingKeys[attachmentKey]) return

    if (attachment.directUrl) {
      setResolvedUrls((previous) => ({ ...previous, [attachmentKey]: attachment.directUrl }))
      return
    }
    if (!attachment.path) {
      setErrorsByKey((previous) => ({ ...previous, [attachmentKey]: 'Attachment path is missing.' }))
      return
    }

    setLoadingKeys((previous) => ({ ...previous, [attachmentKey]: true }))
    try {
      const { data, error } = await supabase.storage.from(attachment.bucket).createSignedUrl(attachment.path, 60 * 60)
      if (error) throw error
      if (!data?.signedUrl) {
        throw new Error('No URL returned')
      }
      setResolvedUrls((previous) => ({ ...previous, [attachmentKey]: data.signedUrl }))
      setErrorsByKey((previous) => ({ ...previous, [attachmentKey]: '' }))
    } catch (error) {
      console.error('Suggestion attachment URL resolution failed:', error)
      setErrorsByKey((previous) => ({ ...previous, [attachmentKey]: error.message || 'Unable to load attachment.' }))
    } finally {
      setLoadingKeys((previous) => ({ ...previous, [attachmentKey]: false }))
    }
  }, [expandedKey, loadingKeys, resolvedUrls, rowKey])

  if (!attachments.length) return '-'

  return (
    <div className="suggestion-review-attachments">
      {attachments.map((attachment, index) => {
        const attachmentKey = `${rowKey}:${attachment.path || attachment.directUrl || index}`
        const isExpanded = expandedKey === attachmentKey
        const resolvedUrl = resolvedUrls[attachmentKey] || null
        const loading = Boolean(loadingKeys[attachmentKey])
        const error = errorsByKey[attachmentKey]
        const downloadableUrl = resolvedUrl || attachment.directUrl || null
        return (
          <div key={attachmentKey} className="suggestion-review-attachment-item">
            <button className="nav-btn" onClick={() => handleToggleAttachment(attachment, index)}>
              {attachment.fileName} {formatBytesLabel(attachment.fileSize)}
            </button>
            {isExpanded && (
              <div className="suggestion-review-attachment-meta">
                {loading && <div className="suggestion-review-attachment-unavailable">Loading image preview...</div>}
                {!loading && error && <div className="suggestion-review-attachment-unavailable">{error}</div>}
                {!loading && !error && !downloadableUrl && (
                  <div className="suggestion-review-attachment-unavailable">Attachment URL is unavailable.</div>
                )}
                {!loading && !error && downloadableUrl && (
                  <>
                    <a href={downloadableUrl} target="_blank" rel="noreferrer">Open full image</a>
                    <img src={downloadableUrl} alt={attachment.fileName || 'Suggestion attachment'} className="suggestion-review-attachment-thumb" />
                  </>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
