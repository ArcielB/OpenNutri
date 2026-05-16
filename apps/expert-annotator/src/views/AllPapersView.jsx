import { Fragment, useState } from 'react'
import AiDetailPanel from '../components/AiDetailPanel'
import {
  buildLatestAiExtractionMaps,
  formatDate,
  formatDecisionLabel,
  formatRouteDestinationLabel,
  formatRoutingStatusLabel,
  formatStatusLabel,
  getAiDecisionKind,
  groupRowsByPaperId,
  shouldShowPaperInUsefulOverview,
} from '../utils/annotateHelpers'

export default function AllPapersView({ cockpitData, reviewerById, onRefresh }) {
  const [expandedAiPaperId, setExpandedAiPaperId] = useState(null)
  const submissionsByPaperId = groupRowsByPaperId(cockpitData.labelSubmissions)
  const approvalsByPaperId = Object.fromEntries((cockpitData.labelApprovals || []).map((row) => [row.paper_id, row]))
  const outcomeByPaperId = Object.fromEntries((cockpitData.outcomes || []).map((row) => [row.paper_id, row]))
  const latestAiExtractionById = Object.fromEntries((cockpitData.aiExtractions || []).map((row) => [row.id, row]))
  const { byPaperId: latestAiExtractionByPaperId } = buildLatestAiExtractionMaps(cockpitData.aiExtractions || [])
  const rows = (cockpitData.papers || [])
    .map((paper) => ({
      paper,
      submissions: submissionsByPaperId[paper.id] || [],
      approval: approvalsByPaperId[paper.id] || null,
      outcome: outcomeByPaperId[paper.id] || null,
      latestAiExtraction: latestAiExtractionById[paper.latest_ai_extraction_id] || latestAiExtractionByPaperId[paper.id] || null,
    }))
    .filter(shouldShowPaperInUsefulOverview)

  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <div>
          <h2>Useful Papers</h2>
          <p>Useful paper state under the general queue and approval workflow.</p>
        </div>
        <button className="btn btn-outline" onClick={onRefresh}>Refresh</button>
      </div>
      <div className="dashboard-card dashboard-card-table">
        <div className="dashboard-card-title">Useful Paper Workflow Overview</div>
        <div className="table-scroll">
          <table className="dashboard-table">
            <thead>
              <tr>
                <th>Paper</th>
                <th>Routing</th>
                <th>Latest AI</th>
                <th>Submissions</th>
                <th>Approval</th>
                <th>Final Outcome</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr><td colSpan="6">No useful papers found.</td></tr>
              ) : rows.map(({ paper, submissions, approval, outcome, latestAiExtraction }) => {
                const aiExpanded = Boolean(latestAiExtraction && expandedAiPaperId === paper.id)
                return (
                  <Fragment key={paper.id}>
                    <tr>
                      <td className="table-title-cell">
                        <div className="table-primary-line">{paper.title || paper.filename || `Paper ${paper.id}`}</div>
                        <div className="table-secondary-line">
                          Paper {paper.id}
                          {paper.workflow_language && ` · ${paper.workflow_language.toUpperCase()}`}
                          {paper.doi && ` · DOI: ${paper.doi}`}
                        </div>
                      </td>
                      <td>
                        <div className="table-cell-stack">
                          <div className="table-detail-line">
                            <span>{formatRoutingStatusLabel(paper.routing_status)}</span>
                            <span className={`status-badge ${paper.route_destination === 'finalized' ? 'status-done' : paper.route_destination === 'blocked' ? 'status-skipped' : 'status-pending'}`}>
                              {formatRouteDestinationLabel(paper.route_destination)}
                            </span>
                          </div>
                          <span className="table-secondary-line">{paper.routing_bucket || '-'}</span>
                        </div>
                      </td>
                      <td>
                        {latestAiExtraction ? (
                          <div className="table-cell-stack">
                            <div className="table-detail-line">
                              <span>{formatDecisionLabel(getAiDecisionKind(latestAiExtraction))}</span>
                              <span className={`status-badge ${latestAiExtraction.audit_sampled ? 'status-draft' : 'status-pending'}`}>
                                {latestAiExtraction.audit_sampled ? 'AUDIT' : 'LIVE'}
                              </span>
                            </div>
                            <span className="table-secondary-line">
                              conf {latestAiExtraction.overall_confidence == null ? '-' : Number(latestAiExtraction.overall_confidence).toFixed(2)}
                              {' · '}
                              {formatRouteDestinationLabel(latestAiExtraction.route_destination)}
                            </span>
                            <button
                              className="nav-btn ai-detail-toggle"
                              onClick={() => setExpandedAiPaperId(aiExpanded ? null : paper.id)}
                            >
                              {aiExpanded ? 'Hide Details' : 'Details'}
                            </button>
                          </div>
                        ) : (
                          <span className="table-secondary-line">No AI extraction yet.</span>
                        )}
                      </td>
                      <td>
                        {submissions.length === 0 ? '-' : (
                          <div className="table-cell-stack">
                            {submissions.map((submission) => (
                              <span key={submission.id}>
                                {reviewerById[submission.reviewer_profile_id]?.display_name || 'Labeler'} · {formatStatusLabel(submission.status)}
                              </span>
                            ))}
                          </div>
                        )}
                      </td>
                      <td>{approval ? `${formatDecisionLabel(approval.decision_kind)} · ${formatDate(approval.approved_at)}` : '-'}</td>
                      <td>{outcome ? `${formatDecisionLabel(outcome.decision_kind)} · ${outcome.resolution_source}` : 'Pending'}</td>
                    </tr>
                    {aiExpanded && (
                      <tr className="ai-detail-row">
                        <td colSpan="6">
                          <AiDetailPanel extraction={latestAiExtraction} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
