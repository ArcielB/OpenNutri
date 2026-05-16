import { useMemo, useState } from 'react'
import PdfViewer from '../components/PdfViewer'
import FoodItemForm from '../components/FoodItemForm'
import EvidenceStrip from '../components/EvidenceStrip'
import PayloadSummary from '../components/PayloadSummary'
import { buildEvidenceLocationsFromFoodItems } from '../utils/EvidenceLocations'
import {
  formatDate,
  formatDecisionLabel,
  formatStatusLabel,
  getStatusBadgeClass,
  isValidFoodItem,
} from '../utils/annotateHelpers'

export default function ApprovalView({
  pendingSubmissions,
  selectedSubmission,
  selectedPaper,
  reviewerById,
  pdfUrl,
  theme,
  allNutrients,
  allFoods,
  foodsLoaded,
  user,
  approvalFoodItems,
  approvalDecision,
  setApprovalDecision,
  approvalNote,
  setApprovalNote,
  canApprove,
  saving,
  setSelectedApprovalId,
  addApprovalFoodItem,
  removeApprovalFoodItem,
  updateApprovalFoodItem,
  handleApprovalPdfNutrientAdd,
  approveSelectedSubmission,
}) {
  const submitter = selectedSubmission ? reviewerById[selectedSubmission.reviewer_profile_id] : null
  const approvalHasFood = approvalFoodItems.filter(isValidFoodItem).length > 0
  const evidenceFoodItems = useMemo(
    () => approvalDecision === 'has_data' ? approvalFoodItems : [],
    [approvalDecision, approvalFoodItems]
  )
  const evidenceLocations = useMemo(
    () => buildEvidenceLocationsFromFoodItems(evidenceFoodItems),
    [evidenceFoodItems]
  )
  const [evidenceStatuses, setEvidenceStatuses] = useState({})
  const [activeEvidence, setActiveEvidence] = useState(null)
  const activeEvidenceId = evidenceLocations.some((location) => location.id === activeEvidence?.id)
    ? activeEvidence.id
    : null

  return (
    <div className="workspace conflict-workspace">
      <div className="conflict-sidebar">
        <div className="conflict-sidebar-header">
          <h2>Approval</h2>
          <p>{pendingSubmissions.length} pending</p>
        </div>
        <div className="conflict-list">
          {pendingSubmissions.length === 0 ? (
            <div className="empty-panel">No submissions are waiting for approval.</div>
          ) : pendingSubmissions.map((submission) => (
            <button
              key={submission.id}
              className={`conflict-list-item ${selectedSubmission?.id === submission.id ? 'active' : ''}`}
              onClick={() => setSelectedApprovalId(submission.id)}
            >
              <span>{formatDecisionLabel(submission.decision_kind)}</span>
              <strong>{reviewerById[submission.reviewer_profile_id]?.display_name || 'Labeler'}</strong>
              <small>Paper {submission.paper_id} · {formatDate(submission.submitted_at)}</small>
            </button>
          ))}
        </div>
      </div>

      <PdfViewer
        pdfUrl={pdfUrl}
        allNutrients={allNutrients}
        onAddNutrient={handleApprovalPdfNutrientAdd}
        theme={theme}
        evidenceLocations={evidenceLocations}
        activeEvidenceId={activeEvidenceId}
        activeEvidenceRequestId={activeEvidenceId ? activeEvidence?.requestId || null : null}
        onEvidenceStatusesChange={setEvidenceStatuses}
      />

      <div className="annotation-panel conflict-panel">
        {!selectedSubmission ? (
          <div className="annotation-scroll">
            <div className="empty-panel">Select a submission to review.</div>
          </div>
        ) : (
          <>
            <div className="conflict-header">
              <div>
                <h2>{selectedPaper?.title || `Paper ${selectedSubmission.paper_id}`}</h2>
                <p>{submitter?.display_name || submitter?.email || 'Unknown labeler'} submitted {formatDate(selectedSubmission.submitted_at)}</p>
              </div>
              <div className={`status-badge ${getStatusBadgeClass(selectedSubmission.status)}`}>
                {formatStatusLabel(selectedSubmission.status)}
              </div>
            </div>
            <EvidenceStrip
              locations={evidenceLocations}
              statuses={evidenceStatuses}
              selectedEvidenceId={activeEvidenceId}
              onSelect={(location) => setActiveEvidence({ id: location.id, requestId: Date.now() })}
            />

            <div className="annotation-scroll conflict-scroll">
              <div className="payload-grid">
                <PayloadSummary submission={selectedSubmission} reviewer={submitter} title="Original Submission" />
                <div className="payload-card">
                  <div className="payload-card-header">
                    <div>
                      <h3>Reviewer Final Payload</h3>
                      <p>{canApprove ? 'Edit before approving when needed.' : 'Read-only preview.'}</p>
                    </div>
                  </div>
                  <div
                    className="annotation-scroll"
                    style={{ maxHeight: 620, pointerEvents: canApprove ? 'auto' : 'none', opacity: canApprove ? 1 : 0.85 }}
                    aria-disabled={!canApprove}
                  >
                    <label className="form-group" style={{ display: 'block', marginBottom: 12 }}>
                      <span style={{ display: 'block', marginBottom: 6, color: 'var(--text-secondary)', fontSize: 13 }}>Decision</span>
                      <select
                        value={approvalDecision}
                        onChange={(event) => setApprovalDecision(event.target.value)}
                        disabled={!canApprove || saving}
                      >
                        <option value="has_data">Usable Data</option>
                        <option value="no_usable_data">No Usable Data</option>
                      </select>
                    </label>
                    {approvalDecision === 'has_data' ? (
                      <>
                        {approvalFoodItems.map((item, index) => (
                          <FoodItemForm
                            key={`${selectedSubmission.id}-${index}`}
                            index={index}
                            data={item}
                            onChange={(updated) => updateApprovalFoodItem(index, updated)}
                            onDelete={() => removeApprovalFoodItem(index)}
                            allNutrients={allNutrients}
                            allFoods={allFoods}
                            foodsLoaded={foodsLoaded}
                            userId={user.id}
                          />
                        ))}
                        {canApprove && (
                          <button className="add-food-btn" onClick={addApprovalFoodItem}>Add Food</button>
                        )}
                      </>
                    ) : (
                      <div className="empty-panel">The accepted final decision will be no usable data.</div>
                    )}
                    <label className="form-group" style={{ display: 'block', marginTop: 12 }}>
                      <span style={{ display: 'block', marginBottom: 6, color: 'var(--text-secondary)', fontSize: 13 }}>Approval note</span>
                      <textarea
                        value={approvalNote}
                        onChange={(event) => setApprovalNote(event.target.value)}
                        disabled={!canApprove || saving}
                        placeholder="Correction or approval note"
                      />
                    </label>
                  </div>
                </div>
              </div>
            </div>

            <div className="annotation-actions">
              <button
                className="btn btn-success"
                onClick={approveSelectedSubmission}
                disabled={!canApprove || saving || (approvalDecision === 'has_data' && !approvalHasFood)}
              >
                {saving ? 'Approving...' : 'Approve Final Payload'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
