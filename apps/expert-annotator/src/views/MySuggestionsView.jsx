import SuggestionAttachmentsCell from '../components/SuggestionAttachmentsCell'
import {
  formatDate,
  formatStatusLabel,
  getStatusBadgeClass,
  normalizeSuggestionAttachments,
} from '../utils/annotateHelpers'

export default function MySuggestionsView({ suggestionItems, loading, onRefresh }) {
  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <div>
          <h2>My Suggestions</h2>
          <p>Track the review status of suggestions you submitted.</p>
        </div>
        <button className="btn btn-outline" onClick={onRefresh} disabled={loading}>
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>
      <div className="dashboard-card dashboard-card-table">
        <div className="table-scroll">
          <table className="dashboard-table">
            <thead>
              <tr>
                <th>Submitted</th>
                <th>Type</th>
                <th>Status</th>
                <th>Message</th>
                <th>Attachments</th>
                <th>Reviewed</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan="6">Loading your suggestions...</td></tr>
              ) : suggestionItems.length === 0 ? (
                <tr><td colSpan="6">You have not submitted any suggestions yet.</td></tr>
              ) : suggestionItems.map((item) => {
                const attachments = normalizeSuggestionAttachments(item.attachments)
                return (
                  <tr key={item.id}>
                    <td>{formatDate(item.created_at)}</td>
                    <td>{item.context?.request_kind === 'general_queue_help_request' ? 'Help Request' : 'Suggestion'}</td>
                    <td><span className={`status-badge ${getStatusBadgeClass(item.status)}`}>{formatStatusLabel(item.status)}</span></td>
                    <td>{item.suggestion_text}</td>
                    <td><SuggestionAttachmentsCell rowKey={`self:${item.id}`} attachments={attachments} /></td>
                    <td>{formatDate(item.reviewed_at)}</td>
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
