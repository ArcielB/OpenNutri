import {
  countCorrectionItems,
  formatDate,
  formatDecisionLabel,
  formatStatusLabel,
  getPayloadRowCount,
  getStatusBadgeClass,
} from '../utils/annotateHelpers'

export default function DashboardView({ cockpitData, reviewerById, paperById, onRefresh }) {
  const submissionById = Object.fromEntries((cockpitData.labelSubmissions || []).map((row) => [row.id, row]))
  const metricsByReviewer = {}

  for (const profile of cockpitData.reviewerProfiles || []) {
    metricsByReviewer[profile.id] = {
      id: profile.id,
      display_name: profile.display_name || profile.email,
      submitted: 0,
      pending: 0,
      accepted: 0,
      corrected: 0,
      superseded: 0,
      correction_items: 0,
    }
  }

  for (const submission of cockpitData.labelSubmissions || []) {
    if (!metricsByReviewer[submission.reviewer_profile_id]) {
      metricsByReviewer[submission.reviewer_profile_id] = {
        id: submission.reviewer_profile_id,
        display_name: reviewerById[submission.reviewer_profile_id]?.display_name || 'Unknown',
        submitted: 0,
        pending: 0,
        accepted: 0,
        corrected: 0,
        superseded: 0,
        correction_items: 0,
      }
    }
    const metric = metricsByReviewer[submission.reviewer_profile_id]
    metric.submitted += 1
    if (submission.status === 'pending_approval') metric.pending += 1
    if (submission.status === 'superseded') metric.superseded += 1
    if (submission.status === 'accepted') metric.accepted += 1
  }

  for (const approval of cockpitData.labelApprovals || []) {
    const submission = submissionById[approval.label_submission_id]
    const metric = submission ? metricsByReviewer[submission.reviewer_profile_id] : null
    if (!metric) continue
    const correctionItems = countCorrectionItems(approval.correction_diff_json)
    metric.correction_items += correctionItems
    if (correctionItems > 0) metric.corrected += 1
  }

  const metrics = Object.values(metricsByReviewer).sort((left, right) => left.display_name.localeCompare(right.display_name))
  const approvalBySubmissionId = Object.fromEntries((cockpitData.labelApprovals || []).map((row) => [row.label_submission_id, row]))

  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <div>
          <h2>Labeler Dashboard</h2>
          <p>Submission ownership, approval outcomes, and correction history.</p>
        </div>
        <button className="btn btn-outline" onClick={onRefresh}>Refresh</button>
      </div>

      <div className="dashboard-grid dashboard-grid-summary">
        <div className="dashboard-card">
          <div className="dashboard-card-label">General Submissions</div>
          <div className="dashboard-card-value">{cockpitData.labelSubmissions.length}</div>
        </div>
        <div className="dashboard-card">
          <div className="dashboard-card-label">Pending Approval</div>
          <div className="dashboard-card-value">{cockpitData.labelSubmissions.filter((row) => row.status === 'pending_approval').length}</div>
        </div>
        <div className="dashboard-card">
          <div className="dashboard-card-label">Approved Outcomes</div>
          <div className="dashboard-card-value">{cockpitData.labelApprovals.length}</div>
        </div>
        <div className="dashboard-card">
          <div className="dashboard-card-label">Resolved Papers</div>
          <div className="dashboard-card-value">{cockpitData.outcomes.length}</div>
        </div>
      </div>

      <div className="dashboard-card dashboard-card-table">
        <div className="dashboard-card-title">Performance By Labeler</div>
        <div className="table-scroll">
          <table className="dashboard-table">
            <thead>
              <tr>
                <th>Labeler</th>
                <th>Submitted</th>
                <th>Pending</th>
                <th>Accepted</th>
                <th>Corrected</th>
                <th>Superseded</th>
                <th>Correction Items</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((row) => (
                <tr key={row.id}>
                  <td>{row.display_name}</td>
                  <td>{row.submitted}</td>
                  <td>{row.pending}</td>
                  <td>{row.accepted}</td>
                  <td>{row.corrected}</td>
                  <td>{row.superseded}</td>
                  <td>{row.correction_items}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="dashboard-card dashboard-card-table">
        <div className="dashboard-card-title">Submission Detail</div>
        <div className="table-scroll">
          <table className="dashboard-table">
            <thead>
              <tr>
                <th>Paper</th>
                <th>Labeler</th>
                <th>Submitted</th>
                <th>Status</th>
                <th>Original</th>
                <th>Final</th>
                <th>Mistake Detail</th>
              </tr>
            </thead>
            <tbody>
              {cockpitData.labelSubmissions.length === 0 ? (
                <tr><td colSpan="7">No general submissions yet.</td></tr>
              ) : cockpitData.labelSubmissions.map((submission) => {
                const approval = approvalBySubmissionId[submission.id]
                const diff = approval?.correction_diff_json || {}
                const paper = paperById[submission.paper_id]
                return (
                  <tr key={submission.id}>
                    <td className="table-title-cell">
                      <div className="table-primary-line">{paper?.title || paper?.filename || `Paper ${submission.paper_id}`}</div>
                      <div className="table-secondary-line">Paper {submission.paper_id}</div>
                    </td>
                    <td>{reviewerById[submission.reviewer_profile_id]?.display_name || reviewerById[submission.reviewer_profile_id]?.email || 'Unknown'}</td>
                    <td>{formatDate(submission.submitted_at)}</td>
                    <td><span className={`status-badge ${getStatusBadgeClass(submission.status)}`}>{formatStatusLabel(submission.status)}</span></td>
                    <td>{formatDecisionLabel(submission.decision_kind)} · {getPayloadRowCount(submission.payload_json)} rows</td>
                    <td>{approval ? `${formatDecisionLabel(approval.decision_kind)} · ${getPayloadRowCount(approval.payload_json)} rows` : '-'}</td>
                    <td>
                      {approval ? (
                        <div className="table-cell-stack">
                          <span>{countCorrectionItems(diff)} correction items</span>
                          {diff.decision_changed && <span className="table-secondary-line">Decision changed</span>}
                          {!!approval.approval_note && <span className="table-secondary-line">{approval.approval_note}</span>}
                        </div>
                      ) : '-'}
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
