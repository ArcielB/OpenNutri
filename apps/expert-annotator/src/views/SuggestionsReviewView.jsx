import SuggestionAttachmentsCell from '../components/SuggestionAttachmentsCell'
import {
  SUGGESTION_REVIEW_STATUSES,
  formatStatusLabel,
  getStatusBadgeClass,
  normalizeSuggestionAttachments,
} from '../utils/annotateHelpers'

export default function SuggestionsReviewView({ suggestionItems, onRefresh, onSaveReview, savingSuggestionId }) {
  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <div>
          <h2>Suggestions</h2>
          <p>Incoming suggestions and help requests.</p>
        </div>
        <button className="btn btn-outline" onClick={onRefresh}>Refresh</button>
      </div>
      <div className="dashboard-card dashboard-card-table">
        <div className="table-scroll">
          <table className="dashboard-table">
            <thead>
              <tr>
                <th>Item</th>
                <th>Submitted By</th>
                <th>Status</th>
                <th>Text</th>
                <th>Attachments</th>
                <th>Update</th>
              </tr>
            </thead>
            <tbody>
              {suggestionItems.length === 0 ? (
                <tr><td colSpan="6">No suggestions or help requests.</td></tr>
              ) : suggestionItems.map((item) => {
                const attachments = normalizeSuggestionAttachments(item.attachments)
                return (
                  <tr key={item.id}>
                    <td>{item.context?.request_kind === 'general_queue_help_request' ? 'Help Request' : item.item_kind}</td>
                    <td>{item.submitted_by_name || item.submitted_by_email || '-'}</td>
                    <td><span className={`status-badge ${getStatusBadgeClass(item.status)}`}>{formatStatusLabel(item.status)}</span></td>
                    <td>{item.suggestion_text}</td>
                    <td>
                      <SuggestionAttachmentsCell rowKey={`admin:${item.id}`} attachments={attachments} />
                    </td>
                    <td>
                      <select
                        className="suggestion-status-select"
                        value={item.status || 'new'}
                        disabled={savingSuggestionId === item.id}
                        onChange={(event) => onSaveReview(item.id, { status: event.target.value })}
                      >
                        {SUGGESTION_REVIEW_STATUSES.map((status) => (
                          <option key={status} value={status}>{formatStatusLabel(status)}</option>
                        ))}
                      </select>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
