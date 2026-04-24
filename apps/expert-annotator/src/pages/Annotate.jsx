import { Fragment, useCallback, useEffect, useRef, useState } from 'react'
import { supabase } from '../supabaseClient'
import PdfViewer from '../components/PdfViewer'
import FoodItemForm from '../components/FoodItemForm'
import SuggestionModal from '../components/SuggestionModal'
import { appendTestEvent, isTestModeEnabled, setTestModeEnabled } from '../utils/testMode'

function parseUnitFromDescription(desc) {
  if (!desc) return 'G'
  const match = desc.match(/^Unit:\s*(\S+)/)
  return match ? match[1].replace(/\.$/, '') : 'G'
}

function createEmptyFoodItem() {
  return {
    food_name: '',
    food_fdc_id: null,
    is_custom_food: false,
    nutrients: [],
  }
}

function isValidFoodItem(item) {
  return Boolean((item?.food_name || '').trim() || item?.food_fdc_id)
}

function normalizeFoodItem(item) {
  return {
    ...item,
    food_name: (item?.food_name || '').trim(),
  }
}

const OPEN_STATUSES = new Set(['assigned', 'draft'])
const FINAL_STATUSES = new Set(['submitted', 'conflict', 'resolved', 'cancelled'])
const SUGGESTION_REVIEW_STATUSES = ['new', 'triaged', 'planned', 'dismissed', 'done']
const SUPPORTED_WORKFLOW_LANGUAGES = ['en', 'tr']
const LIVE_TRAINING_SLOT_STATUSES = new Set(['pending', 'submitted', 'conflict'])
const EMPTY_COCKPIT_DATA = {
  reviewerProfiles: [],
  reviewerSlots: [],
  slotMembers: [],
  slotAssignments: [],
  userAssignments: [],
  submissions: [],
  outcomes: [],
  conflicts: [],
  papers: [],
  aiExtractions: [],
  routingStageConfigs: [],
  searchHits: [],
  suggestionReviewItems: [],
}

function buildSlotMembersByProfile(rows) {
  return (rows || []).reduce((accumulator, row) => {
    if (!row?.reviewer_profile_id) return accumulator
    if (!accumulator[row.reviewer_profile_id]) {
      accumulator[row.reviewer_profile_id] = []
    }
    accumulator[row.reviewer_profile_id].push(row)
    return accumulator
  }, {})
}

function createReviewerDraft(profile = null, slotMembers = []) {
  const shadowSlots = (slotMembers || [])
    .filter((row) => row?.member_role === 'shadow' && row?.active !== false)
    .map((row) => row.slot_key)
    .filter(Boolean)
    .sort()

  return {
    email: profile?.email || '',
    display_name: profile?.display_name || '',
    active: profile?.active ?? true,
    can_review_en: profile?.can_review_en ?? true,
    can_review_tr: profile?.can_review_tr ?? true,
    tester_access: profile?.tester_access ?? false,
    official_slot: profile?.official_slot || '',
    shadow_slots: shadowSlots,
    cockpit_access: profile?.cockpit_access ?? false,
    priority_weight_en: profile?.priority_weight_en ?? 1,
    priority_weight_tr: profile?.priority_weight_tr ?? 1,
    notes: profile?.notes || '',
  }
}

function createEmptyReviewerDraft() {
  return createReviewerDraft()
}

function toggleShadowSlot(shadowSlots, slotKey) {
  if (!slotKey) return shadowSlots || []
  if ((shadowSlots || []).includes(slotKey)) {
    return shadowSlots.filter((value) => value !== slotKey)
  }
  return [...(shadowSlots || []), slotKey].sort()
}

function buildReviewerAdminPayload(draft) {
  return {
    p_email: (draft?.email || '').trim().toLowerCase(),
    p_display_name: (draft?.display_name || '').trim(),
    p_active: Boolean(draft?.active),
    p_can_review_en: Boolean(draft?.can_review_en),
    p_can_review_tr: Boolean(draft?.can_review_tr),
    p_tester_access: Boolean(draft?.tester_access),
    p_official_slot: draft?.official_slot || null,
    p_shadow_slots: [...new Set((draft?.shadow_slots || []).filter(Boolean))].sort(),
    p_cockpit_access: Boolean(draft?.cockpit_access),
    p_priority_weight_en: Number(draft?.priority_weight_en ?? 1) || 1,
    p_priority_weight_tr: Number(draft?.priority_weight_tr ?? 1) || 1,
    p_notes: (draft?.notes || '').trim() || null,
  }
}

function describeMemberships(draft, reviewerSlots) {
  const labels = []
  if (draft?.official_slot) {
    labels.push(`official:${draft.official_slot}`)
  }
  for (const slotKey of draft?.shadow_slots || []) {
    labels.push(`shadow:${slotKey}`)
  }
  if (!labels.length) return 'No active slot membership.'
  const slotLabelByKey = Object.fromEntries((reviewerSlots || []).map((slot) => [slot.slot_key, slot.display_name || slot.slot_key]))
  return labels
    .map((value) => {
      const [kind, slotKey] = value.split(':')
      return `${kind === 'official' ? 'Official' : 'Shadow'} ${slotLabelByKey[slotKey] || slotKey}`
    })
    .join(' · ')
}

function sortAssignments(assignments) {
  const statusRank = {
    assigned: 0,
    draft: 1,
    submitted: 2,
    conflict: 3,
    resolved: 4,
    cancelled: 5,
  }
  return [...assignments].sort((a, b) => {
    const rankDiff = (statusRank[a.status] ?? 99) - (statusRank[b.status] ?? 99)
    if (rankDiff !== 0) return rankDiff
    return new Date(a.assigned_at || 0).getTime() - new Date(b.assigned_at || 0).getTime()
  })
}

function getStatusBadgeClass(status) {
  if (status === 'draft') return 'status-draft'
  if (status === 'submitted' || status === 'resolved') return 'status-done'
  if (status === 'conflict') return 'status-conflict'
  if (status === 'cancelled') return 'status-skipped'
  return 'status-pending'
}

function formatStatusLabel(status) {
  switch (status) {
    case 'assigned':
      return 'Assigned'
    case 'draft':
      return 'Draft'
    case 'submitted':
      return 'Submitted'
    case 'conflict':
      return 'Conflict'
    case 'resolved':
      return 'Resolved'
    case 'cancelled':
      return 'Cancelled'
    default:
      return status || 'Unknown'
  }
}

function formatDecisionLabel(decisionKind) {
  return decisionKind === 'has_data' ? 'Usable Data' : 'No Usable Data'
}

function formatRoutingStatusLabel(status) {
  switch (status) {
    case 'queued_for_ai':
      return 'Queued For AI'
    case 'ai_processing':
      return 'AI Processing'
    case 'ai_failed':
      return 'AI Failed'
    case 'human_review_ready':
      return 'Human Review Ready'
    case 'ai_finalized_has_data':
      return 'AI Finalized: Has Data'
    case 'ai_finalized_no_usable_data':
      return 'AI Finalized: No Data'
    default:
      return status || 'Unknown'
  }
}

function formatRouteDestinationLabel(destination) {
  switch (destination) {
    case 'human_review':
      return 'Human Review'
    case 'finalized':
      return 'Finalized'
    case 'blocked':
      return 'Blocked'
    default:
      return destination || 'Unknown'
  }
}

function formatSuggestionReviewStatus(status) {
  switch (status) {
    case 'new':
      return 'New'
    case 'triaged':
      return 'Triaged'
    case 'planned':
      return 'Planned'
    case 'dismissed':
      return 'Dismissed'
    case 'done':
      return 'Done'
    default:
      return status || 'Unknown'
  }
}

function getPublicPdfUrl(filename) {
  if (!filename) return null
  return supabase.storage.from('papers').getPublicUrl(filename).data.publicUrl
}

function pickDefaultAssignment(assignments, previousId = null) {
  if (!assignments.length) return null
  if (previousId && assignments.some((assignment) => assignment.id === previousId)) {
    return previousId
  }
  const firstOpen = assignments.find((assignment) => OPEN_STATUSES.has(assignment.status))
  return firstOpen?.id || assignments[0].id
}

function nextOpenAssignmentId(assignments, currentId) {
  const currentIndex = assignments.findIndex((assignment) => assignment.id === currentId)
  for (let index = currentIndex + 1; index < assignments.length; index += 1) {
    if (OPEN_STATUSES.has(assignments[index].status)) return assignments[index].id
  }
  for (let index = 0; index < currentIndex; index += 1) {
    if (OPEN_STATUSES.has(assignments[index].status)) return assignments[index].id
  }
  return pickDefaultAssignment(assignments, currentId)
}

function buildPaperMap(rows) {
  return Object.fromEntries((rows || []).map((row) => [row.id, row]))
}

function buildReviewerMap(rows) {
  return Object.fromEntries((rows || []).map((row) => [row.id, row]))
}

function normalizeWorkflowLanguage(value) {
  const normalized = String(value || '').trim().toLowerCase()
  return SUPPORTED_WORKFLOW_LANGUAGES.includes(normalized) ? normalized : null
}

function interleaveRows(primaryRows, secondaryRows) {
  const result = []
  const maxLength = Math.max(primaryRows.length, secondaryRows.length)
  for (let index = 0; index < maxLength; index += 1) {
    if (primaryRows[index]) result.push(primaryRows[index])
    if (secondaryRows[index]) result.push(secondaryRows[index])
  }
  return result
}

function compareTrainingPapers(left, right) {
  const leftTime = new Date(left.representativeSlot?.assigned_at || left.paper?.created_at || 0).getTime()
  const rightTime = new Date(right.representativeSlot?.assigned_at || right.paper?.created_at || 0).getTime()
  if (rightTime !== leftTime) return rightTime - leftTime
  return (right.paper?.id || 0) - (left.paper?.id || 0)
}

function pickTrainingRepresentativeSlot(slotAssignments) {
  const statusRank = {
    conflict: 0,
    submitted: 1,
    pending: 2,
    resolved: 3,
    cancelled: 4,
  }

  return [...(slotAssignments || [])].sort((left, right) => {
    const rankDiff = (statusRank[left?.status] ?? 99) - (statusRank[right?.status] ?? 99)
    if (rankDiff !== 0) return rankDiff
    const leftTime = new Date(left?.assigned_at || left?.created_at || 0).getTime()
    const rightTime = new Date(right?.assigned_at || right?.created_at || 0).getTime()
    if (rightTime !== leftTime) return rightTime - leftTime
    return String(left?.slot_key || '').localeCompare(String(right?.slot_key || ''))
  })[0] || null
}

function buildVirtualQueueItem({ paper, reviewerProfileId, assignmentIdPrefix, representativeSlot = null, isTraining = false }) {
  return {
    id: `${assignmentIdPrefix}:${paper.id}`,
    paper_id: paper.id,
    reviewer_profile_id: reviewerProfileId,
    workflow_language: normalizeWorkflowLanguage(paper.workflow_language),
    status: 'assigned',
    assigned_at: representativeSlot?.assigned_at || paper.created_at || null,
    paper_slot_assignment_id: representativeSlot?.id || null,
    latest_submission_id: null,
    is_virtual: true,
    is_training: isTraining,
    paper,
    slot_assignment: representativeSlot,
    outcome: null,
  }
}

function buildGenericTesterAssignments(papers, reviewerProfileId) {
  const orderedPapers = [...(papers || [])].sort((left, right) => {
    const leftLanguage = normalizeWorkflowLanguage(left?.workflow_language)
    const rightLanguage = normalizeWorkflowLanguage(right?.workflow_language)
    if (leftLanguage !== rightLanguage) {
      if (leftLanguage === 'en') return -1
      if (rightLanguage === 'en') return 1
      if (leftLanguage === 'tr') return -1
      if (rightLanguage === 'tr') return 1
    }
    return (right?.id || 0) - (left?.id || 0)
  })

  return orderedPapers.map((paper) => buildVirtualQueueItem({
    paper,
    reviewerProfileId,
    assignmentIdPrefix: 'tester',
  }))
}

function buildDeveloperTrainingAssignments({ papers, slotAssignments, reviewerProfileId }) {
  const slotAssignmentsByPaperId = groupRowsByPaperId(slotAssignments)
  const rankedPapers = (papers || [])
    .filter((paper) => normalizeWorkflowLanguage(paper?.workflow_language))
    .map((paper) => {
      const paperSlotAssignments = slotAssignmentsByPaperId[paper.id] || []
      const liveSlotAssignments = paperSlotAssignments.filter((assignment) =>
        LIVE_TRAINING_SLOT_STATUSES.has(String(assignment?.status || '').trim().toLowerCase())
      )

      return {
        paper,
        language: normalizeWorkflowLanguage(paper.workflow_language),
        hasLiveSlotAssignments: liveSlotAssignments.length > 0,
        representativeSlot: pickTrainingRepresentativeSlot(liveSlotAssignments.length ? liveSlotAssignments : paperSlotAssignments),
      }
    })

  const liveEn = rankedPapers
    .filter((row) => row.hasLiveSlotAssignments && row.language === 'en')
    .sort(compareTrainingPapers)
  const liveTr = rankedPapers
    .filter((row) => row.hasLiveSlotAssignments && row.language === 'tr')
    .sort(compareTrainingPapers)
  const backlogEn = rankedPapers
    .filter((row) => !row.hasLiveSlotAssignments && row.language === 'en')
    .sort(compareTrainingPapers)
  const backlogTr = rankedPapers
    .filter((row) => !row.hasLiveSlotAssignments && row.language === 'tr')
    .sort(compareTrainingPapers)

  return [...interleaveRows(liveEn, liveTr), ...interleaveRows(backlogEn, backlogTr)].map((row) =>
    buildVirtualQueueItem({
      paper: row.paper,
      reviewerProfileId,
      assignmentIdPrefix: 'training',
      representativeSlot: row.representativeSlot,
      isTraining: true,
    })
  )
}

function computeReviewerMetrics(cockpitData) {
  const reviewerById = buildReviewerMap(cockpitData.reviewerProfiles)
  const outcomeByPaperId = Object.fromEntries((cockpitData.outcomes || []).map((row) => [row.paper_id, row]))
  const submissionsById = Object.fromEntries((cockpitData.submissions || []).map((row) => [row.id, row]))
  const metrics = (cockpitData.reviewerProfiles || []).map((profile) => ({
    ...profile,
    open: 0,
    draft: 0,
    submitted: 0,
    conflict: 0,
    resolved: 0,
    accuracyNumerator: 0,
    accuracyDenominator: 0,
  }))
  const metricsById = Object.fromEntries(metrics.map((row) => [row.id, row]))

  for (const assignment of cockpitData.userAssignments || []) {
    const metric = metricsById[assignment.reviewer_profile_id]
    if (!metric) continue
    metric[assignment.status] = (metric[assignment.status] || 0) + 1
    if (OPEN_STATUSES.has(assignment.status)) {
      metric.open += 1
    }
    const submission = submissionsById[assignment.latest_submission_id]
    const outcome = outcomeByPaperId[assignment.paper_id]
    if (!submission || !outcome) continue
    metric.accuracyDenominator += 1
    if (submission.payload_hash === outcome.payload_hash) {
      metric.accuracyNumerator += 1
    }
  }

  return metrics.map((row) => ({
    ...row,
    accuracy:
      row.accuracyDenominator > 0
        ? Math.round((row.accuracyNumerator / row.accuracyDenominator) * 100)
        : null,
    reviewer: reviewerById[row.id] || row,
  }))
}

function computeSourceBreakdown(cockpitData) {
  const outcomeByPaperId = Object.fromEntries((cockpitData.outcomes || []).map((row) => [row.paper_id, row]))
  const aggregate = new Map()

  for (const hit of cockpitData.searchHits || []) {
    const outcome = outcomeByPaperId[hit.paper_id]
    if (!outcome) continue
    const key = `${hit.source || 'unknown'}|${hit.template_id || 'unknown'}|${hit.source_term || ''}`
    if (!aggregate.has(key)) {
      aggregate.set(key, {
        source: hit.source || 'unknown',
        template_id: hit.template_id || 'unknown',
        source_term: hit.source_term || '',
        positive: 0,
        negative: 0,
      })
    }
    const row = aggregate.get(key)
    if (outcome.decision_kind === 'has_data') row.positive += 1
    if (outcome.decision_kind === 'no_usable_data') row.negative += 1
  }

  return [...aggregate.values()]
    .sort((a, b) => (b.positive - a.positive) || (a.negative - b.negative) || a.source.localeCompare(b.source))
    .slice(0, 10)
}

function computeRoutingCounts(papers) {
  const counts = {
    queued_for_ai: 0,
    ai_processing: 0,
    ai_failed: 0,
    human_review_ready: 0,
    ai_finalized_has_data: 0,
    ai_finalized_no_usable_data: 0,
  }

  for (const paper of papers || []) {
    const status = String(paper?.routing_status || '').trim().toLowerCase()
    if (status in counts) {
      counts[status] += 1
    }
  }

  return counts
}

function countPayloadRows(payload) {
  const foodItems = Array.isArray(payload?.food_items) ? payload.food_items : []
  return foodItems.reduce((total, item) => total + (Array.isArray(item?.nutrients) ? item.nutrients.length : 0), 0)
}

function normalizeForStableJson(value) {
  if (Array.isArray(value)) {
    return value.map(normalizeForStableJson)
  }
  if (value && typeof value === 'object') {
    return Object.keys(value).sort().reduce((accumulator, key) => {
      accumulator[key] = normalizeForStableJson(value[key])
      return accumulator
    }, {})
  }
  return value
}

function stableJson(value) {
  return JSON.stringify(normalizeForStableJson(value ?? null))
}

function getAiDecisionKind(extraction) {
  const decisionKind = extraction?.normalized_payload_json?.decision_kind
  if (decisionKind) return decisionKind
  return extraction?.is_useful ? 'has_data' : 'no_usable_data'
}

function getAiComparisonStatus(extraction, outcome) {
  if (!extraction || !outcome) return null
  const truthSource = String(outcome.truth_source_kind || 'human_review').trim().toLowerCase()
  if (truthSource === 'ai_model') return null

  const aiPayload = extraction.normalized_payload_json || null
  const outcomePayload = outcome.payload_json || null
  if (aiPayload && outcomePayload && stableJson(aiPayload) === stableJson(outcomePayload)) {
    return { label: 'Exact DB Payload Match', badgeClass: 'status-done' }
  }
  if (getAiDecisionKind(extraction) === outcome.decision_kind) {
    return { label: 'Decision-Only Match', badgeClass: 'status-draft' }
  }
  return { label: 'Mismatch', badgeClass: 'status-conflict' }
}

function getNormalizationSummary(extraction) {
  const rawSummary = extraction?.raw_data?.normalization_summary || {}
  const payload = extraction?.normalized_payload_json || {}
  const accepted = Number(rawSummary.accepted_row_count ?? countPayloadRows(payload)) || 0
  const input = Number(rawSummary.input_row_count ?? extraction?.raw_data?.parsed_result?.data?.length ?? accepted) || 0
  return {
    accepted_row_count: accepted,
    rejected_row_count: Number(rawSummary.rejected_row_count ?? Math.max(0, input - accepted)) || 0,
    unmapped_food_count: Number(rawSummary.unmapped_food_count ?? 0) || 0,
    unmapped_nutrient_count: Number(rawSummary.unmapped_nutrient_count ?? 0) || 0,
    input_row_count: input,
    rejection_reasons: rawSummary.rejection_reasons || {},
  }
}

function getAiRawMetadata(extraction) {
  const rawData = extraction?.raw_data || {}
  return {
    extraction_id: extraction?.id || null,
    stage_key: extraction?.stage_key || null,
    prompt_version: extraction?.prompt_version || null,
    model_name: extraction?.model_name || null,
    input_hash: extraction?.input_hash || null,
    status: extraction?.status || null,
    route_destination: extraction?.route_destination || null,
    audit_sampled: Boolean(extraction?.audit_sampled),
    finalized_without_human: Boolean(extraction?.finalized_without_human),
    positive_threshold_snapshot: extraction?.positive_threshold_snapshot ?? null,
    negative_threshold_snapshot: extraction?.negative_threshold_snapshot ?? null,
    parsed_data_rows: Array.isArray(rawData?.parsed_result?.data) ? rawData.parsed_result.data.length : null,
    raw_response_chars: typeof rawData?.raw_response_text === 'string' ? rawData.raw_response_text.length : null,
    created_at: extraction?.created_at || null,
  }
}

function groupRowsByPaperId(rows) {
  return (rows || []).reduce((accumulator, row) => {
    if (!row?.paper_id) return accumulator
    if (!accumulator[row.paper_id]) {
      accumulator[row.paper_id] = []
    }
    accumulator[row.paper_id].push(row)
    return accumulator
  }, {})
}

function QueueView({
  assignments,
  currentAssignment,
  currentPaperIndex,
  pdfUrl,
  theme,
  allNutrients,
  foodItems,
  allFoods,
  foodsLoaded,
  user,
  queueStats,
  isEditable,
  saving,
  showPaperList,
  setShowPaperList,
  paperListRef,
  setSelectedAssignmentId,
  addFoodItem,
  removeFoodItem,
  updateFoodItem,
  handlePdfNutrientAdd,
  handleGlobalNoData,
  saveAnnotation,
  getStatusBadgeClass,
  formatStatusLabel,
  formatDecisionLabel,
}) {
  return (
    <div className="workspace">
      <PdfViewer
        pdfUrl={pdfUrl}
        allNutrients={allNutrients}
        onAddNutrient={handlePdfNutrientAdd}
        theme={theme}
      />

      <div className="annotation-panel">
        <div className="queue-assignment-header">
          {currentAssignment ? (
            <>
              <div className="queue-assignment-toolbar">
                <div className="queue-toolbar-group">
                  <div className="paper-list-toggle" ref={paperListRef}>
                    <button className="nav-btn" onClick={() => setShowPaperList((open) => !open)}>
                      {currentPaperIndex >= 0 ? `Assignment ${currentPaperIndex + 1}/${assignments.length}` : 'Queue'} ▾
                    </button>
                    {showPaperList && (
                      <div className="paper-list-dropdown">
                        {assignments.map((assignment, index) => (
                          <div
                            key={assignment.id}
                            className={`paper-list-item ${assignment.id === currentAssignment.id ? 'active' : ''}`}
                            onClick={() => {
                              setSelectedAssignmentId(assignment.id)
                              setShowPaperList(false)
                            }}
                          >
                            <span className="paper-id">{index + 1}</span>
                            <span className="paper-title">{assignment.paper?.title || assignment.paper?.filename || `Paper ${assignment.paper_id}`}</span>
                            <span className={`status-badge ${getStatusBadgeClass(assignment.status)}`}>{formatStatusLabel(assignment.status)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="queue-mini-stats">
                    <span className={`status-badge ${getStatusBadgeClass(currentAssignment.status)}`}>
                      {formatStatusLabel(currentAssignment.status)}
                    </span>
                    <span className="status-badge status-pending">{queueStats.open} open</span>
                    <span className="status-badge status-draft">{queueStats.conflict} conflict</span>
                    <span className="status-badge status-done">{queueStats.resolved} resolved</span>
                    {!!queueStats.cancelled && <span className="status-badge status-skipped">{queueStats.cancelled} cancelled</span>}
                  </div>
                </div>

                <div className="queue-nav-buttons">
                  <button
                    className="nav-btn"
                    disabled={currentPaperIndex <= 0}
                    onClick={() => setSelectedAssignmentId(assignments[Math.max(currentPaperIndex - 1, 0)]?.id || null)}
                  >
                    ← Prev
                  </button>
                  <button
                    className="nav-btn"
                    disabled={currentPaperIndex < 0 || currentPaperIndex >= assignments.length - 1}
                    onClick={() => setSelectedAssignmentId(assignments[Math.min(currentPaperIndex + 1, assignments.length - 1)]?.id || null)}
                  >
                    Next →
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="empty-panel">No assigned papers yet. Run the refill job to top the queue back up.</div>
          )}
        </div>

        <div className="annotation-scroll">
          {!currentAssignment ? (
            <div className="empty-panel">Your queue is empty.</div>
          ) : (
            <>
              {currentAssignment.is_training && (
                <div className="outcome-banner">
                  Developer training mode is read-only for annotation and admin actions. Suggestions still sync to the live review queue.
                </div>
              )}
              {!isEditable && (
                <div className="review-lock-banner">
                  This assignment is finalized. You can inspect it here, but new edits will not be saved.
                </div>
              )}
              {currentAssignment.outcome && (
                <div className="outcome-banner">
                  Final paper outcome: {formatDecisionLabel(currentAssignment.outcome.decision_kind)}
                </div>
              )}

              {foodItems.map((item, index) => (
                <FoodItemForm
                  key={`${currentAssignment.id}-${index}`}
                  index={index}
                  data={item}
                  onChange={(updated) => updateFoodItem(index, updated)}
                  onDelete={() => removeFoodItem(index)}
                  allNutrients={allNutrients}
                  allFoods={allFoods}
                  foodsLoaded={foodsLoaded}
                  userId={user.id}
                />
              ))}

              {isEditable && (
                <button className="add-food-btn" onClick={addFoodItem}>
                  + Add Another Food Item
                </button>
              )}
            </>
          )}
        </div>

        <div className="annotation-actions">
          <div className="action-row">
            <button
              className="btn btn-danger btn-global-skip"
              onClick={handleGlobalNoData}
              disabled={saving || !isEditable}
            >
              🛑 Definitely No Data
            </button>
          </div>
          <div className="action-row">
            <button
              className="btn btn-skip"
              onClick={() => saveAnnotation(false, 'skipped')}
              disabled={saving || !isEditable}
            >
              ⊘ No Usable Data
            </button>
            <button
              className="btn btn-outline"
              onClick={() => saveAnnotation(true, 'draft')}
              disabled={saving || !isEditable}
            >
              Save Draft
            </button>
          </div>
          <button
            className="btn btn-success"
            onClick={() => saveAnnotation(true, 'done')}
            disabled={saving || !isEditable}
            style={{ width: '100%' }}
          >
            {saving ? 'Saving...' : 'Submit Final Extraction'}
          </button>
        </div>
      </div>
    </div>
  )
}

function PayloadSummary({ submission, reviewer, highlighted, onResolve }) {
  const payload = submission?.payload_json || null
  const foodItems = Array.isArray(payload?.food_items) ? payload.food_items : []

  return (
    <div className={`payload-card ${highlighted ? 'payload-card-highlighted' : ''}`}>
      <div className="payload-card-header">
        <div>
          <h3>{reviewer?.display_name || reviewer?.email || 'Unknown Reviewer'}</h3>
          <p>{formatDecisionLabel(submission?.decision_kind)}</p>
        </div>
        {onResolve && (
          <button className="btn btn-primary payload-resolve-btn" onClick={onResolve}>
            Choose This
          </button>
        )}
      </div>
      <div className="payload-meta">
        <span className="status-badge status-pending">{submission?.submitted_at ? new Date(submission.submitted_at).toLocaleString() : 'No timestamp'}</span>
        <span className="status-badge status-draft">{foodItems.length} foods</span>
      </div>
      <div className="payload-scroll">
        {foodItems.length === 0 ? (
          <div className="empty-panel">No extracted foods stored in this submission.</div>
        ) : (
          foodItems.map((foodItem, index) => (
            <div key={`${submission?.id || 'submission'}-${index}`} className="payload-food-block">
              <div className="payload-food-title">
                {foodItem.food_name || 'Unnamed food'}
                {foodItem.food_fdc_id && <span className="payload-food-id">{foodItem.food_fdc_id}</span>}
              </div>
              <div className="payload-nutrients">
                {(foodItem.nutrients || []).length === 0 ? (
                  <span className="payload-empty-line">No nutrient rows.</span>
                ) : (
                  (foodItem.nutrients || []).map((nutrient, nutrientIndex) => (
                    <div key={`${index}-${nutrientIndex}`} className="payload-nutrient-row">
                      <span>{nutrient.nutrient_name || 'Unnamed nutrient'}</span>
                      <span>{nutrient.value ?? '—'} {nutrient.unit || ''}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function ReviewerEditor({
  title,
  subtitle,
  draft,
  reviewerSlots,
  authLinked,
  saving,
  isNew,
  onChange,
  onToggleShadowSlot,
  onSave,
  onReset,
}) {
  return (
    <div className={`reviewer-admin-card ${isNew ? 'reviewer-admin-card-new' : ''}`}>
      <div className="reviewer-admin-header">
        <div>
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>
        <div className="reviewer-admin-badges">
          <span className={`status-badge ${draft.active ? 'status-done' : 'status-skipped'}`}>
            {draft.active ? 'Active' : 'Inactive'}
          </span>
          {!isNew && (
            <span className={`status-badge ${authLinked ? 'status-pending' : 'status-draft'}`}>
              {authLinked ? 'Auth linked' : 'Awaiting first login'}
            </span>
          )}
        </div>
      </div>

      <div className="reviewer-admin-grid">
        <label className="form-group">
          <span>Email</span>
          <input
            value={draft.email}
            onChange={(event) => onChange('email', event.target.value)}
            placeholder="reviewer@example.com"
            readOnly={!isNew}
          />
        </label>

        <label className="form-group">
          <span>Display name</span>
          <input
            value={draft.display_name}
            onChange={(event) => onChange('display_name', event.target.value)}
            placeholder="Reviewer name"
          />
        </label>

        <label className="form-group">
          <span>Official slot</span>
          <select
            value={draft.official_slot}
            onChange={(event) => onChange('official_slot', event.target.value)}
          >
            <option value="">No official slot</option>
            {(reviewerSlots || []).map((slot) => (
              <option key={slot.slot_key} value={slot.slot_key}>
                {slot.display_name || slot.slot_key}
              </option>
            ))}
          </select>
        </label>

        <label className="form-group">
          <span>Notes</span>
          <textarea
            value={draft.notes}
            onChange={(event) => onChange('notes', event.target.value)}
            placeholder="Optional reviewer note"
            rows={2}
          />
        </label>
      </div>

      <div className="reviewer-toggle-row">
        <label className="reviewer-toggle">
          <input
            type="checkbox"
            checked={draft.active}
            onChange={(event) => onChange('active', event.target.checked)}
          />
          <span>Active</span>
        </label>
        <label className="reviewer-toggle">
          <input
            type="checkbox"
            checked={draft.can_review_en}
            onChange={(event) => onChange('can_review_en', event.target.checked)}
          />
          <span>English</span>
        </label>
        <label className="reviewer-toggle">
          <input
            type="checkbox"
            checked={draft.can_review_tr}
            onChange={(event) => onChange('can_review_tr', event.target.checked)}
          />
          <span>Turkish</span>
        </label>
        <label className="reviewer-toggle">
          <input
            type="checkbox"
            checked={draft.tester_access}
            onChange={(event) => onChange('tester_access', event.target.checked)}
          />
          <span>Tester (read-only)</span>
        </label>
        <label className="reviewer-toggle">
          <input
            type="checkbox"
            checked={draft.cockpit_access}
            onChange={(event) => onChange('cockpit_access', event.target.checked)}
          />
          <span>Cockpit</span>
        </label>
      </div>

      <div className="reviewer-shadow-block">
        <div className="reviewer-shadow-header">
          <strong>Shadow memberships</strong>
          <span>{describeMemberships(draft, reviewerSlots)}</span>
        </div>
        <div className="reviewer-shadow-slots">
          {(reviewerSlots || []).map((slot) => {
            const disabled = draft.official_slot === slot.slot_key
            const selected = !disabled && draft.shadow_slots.includes(slot.slot_key)
            return (
              <button
                key={slot.slot_key}
                type="button"
                className={`slot-chip ${selected ? 'slot-chip-active' : ''}`}
                onClick={() => onToggleShadowSlot(slot.slot_key)}
                disabled={disabled}
              >
                {slot.display_name || slot.slot_key}
              </button>
            )
          })}
        </div>
      </div>

      <div className="reviewer-admin-actions">
        <button className="btn btn-outline" onClick={onReset} disabled={saving}>
          {isNew ? 'Clear' : 'Reset'}
        </button>
        <button className="btn btn-primary reviewer-save-btn" onClick={onSave} disabled={saving}>
          {saving ? 'Saving...' : isNew ? 'Add reviewer' : 'Save reviewer'}
        </button>
      </div>
    </div>
  )
}

function ReviewerAdminPanel({
  cockpitData,
  reviewerDrafts,
  newReviewerDraft,
  savingReviewerTarget,
  onChangeDraft,
  onToggleDraftShadowSlot,
  onSaveDraft,
  onResetDraft,
  onChangeNewDraft,
  onToggleNewShadowSlot,
  onCreateReviewer,
  onResetNewReviewer,
}) {
  const slotMembersByProfile = buildSlotMembersByProfile(cockpitData.slotMembers)
  const reviewerSlots = cockpitData.reviewerSlots || []
  const reviewerProfiles = cockpitData.reviewerProfiles || []

  return (
    <div className="dashboard-card reviewer-admin-shell">
      <div className="reviewer-admin-shell-header">
        <div>
          <div className="dashboard-card-title">Reviewer Admin</div>
          <p>Create reviewers, assign official slots, and manage shadow members without direct SQL edits.</p>
        </div>
        <span className="status-badge status-pending">{reviewerProfiles.length} profiles</span>
      </div>

      <div className="reviewer-admin-stack">
        <ReviewerEditor
          title="Add Reviewer"
          subtitle="New reviewers are allowlisted automatically and can be wired into a slot before first login."
          draft={newReviewerDraft}
          reviewerSlots={reviewerSlots}
          authLinked={false}
          saving={savingReviewerTarget === '__new__'}
          isNew
          onChange={onChangeNewDraft}
          onToggleShadowSlot={onToggleNewShadowSlot}
          onSave={onCreateReviewer}
          onReset={onResetNewReviewer}
        />

        {reviewerProfiles.map((profile) => {
          const draft = reviewerDrafts[profile.id] || createReviewerDraft(profile, slotMembersByProfile[profile.id] || [])
          return (
            <ReviewerEditor
              key={profile.id}
              title={profile.display_name || profile.email || profile.id}
              subtitle={profile.email || 'No email yet'}
              draft={draft}
              reviewerSlots={reviewerSlots}
              authLinked={Boolean(profile.auth_user_id)}
              saving={savingReviewerTarget === profile.id}
              isNew={false}
              onChange={(field, value) => onChangeDraft(profile.id, field, value)}
              onToggleShadowSlot={(slotKey) => onToggleDraftShadowSlot(profile.id, slotKey)}
              onSave={() => onSaveDraft(profile.id)}
              onReset={() => onResetDraft(profile.id)}
            />
          )
        })}
      </div>
    </div>
  )
}

function RoutingStagePanel({
  stageConfigs,
  routingCounts,
  routingConfigDrafts,
  savingStageKey,
  onChangeDraft,
  onSaveDraft,
}) {
  return (
    <div className="dashboard-card reviewer-admin-shell">
      <div className="reviewer-admin-shell-header">
        <div>
          <div className="dashboard-card-title">AI Routing</div>
          <p>Active-stage thresholds gate every paper before human assignment.</p>
        </div>
        <span className="status-badge status-pending">{stageConfigs.length} stages</span>
      </div>

      <div className="dashboard-grid dashboard-grid-summary">
        <div className="dashboard-card">
          <div className="dashboard-card-label">Queued</div>
          <div className="dashboard-card-value">{routingCounts.queued_for_ai}</div>
        </div>
        <div className="dashboard-card">
          <div className="dashboard-card-label">Processing</div>
          <div className="dashboard-card-value">{routingCounts.ai_processing}</div>
        </div>
        <div className="dashboard-card">
          <div className="dashboard-card-label">Failed</div>
          <div className="dashboard-card-value">{routingCounts.ai_failed}</div>
        </div>
        <div className="dashboard-card">
          <div className="dashboard-card-label">Human Ready</div>
          <div className="dashboard-card-value">{routingCounts.human_review_ready}</div>
        </div>
        <div className="dashboard-card">
          <div className="dashboard-card-label">AI Final Has Data</div>
          <div className="dashboard-card-value">{routingCounts.ai_finalized_has_data}</div>
        </div>
        <div className="dashboard-card">
          <div className="dashboard-card-label">AI Final No Data</div>
          <div className="dashboard-card-value">{routingCounts.ai_finalized_no_usable_data}</div>
        </div>
      </div>

      <div className="reviewer-admin-stack">
        {(stageConfigs || []).map((stage) => {
          const draft = routingConfigDrafts[stage.stage_key] || {
            positive_threshold: stage.positive_threshold ?? 1,
            negative_threshold: stage.negative_threshold ?? 1,
            audit_rate: stage.audit_rate ?? 0.05,
          }
          return (
            <div key={stage.stage_key} className="reviewer-editor-card">
              <div className="reviewer-editor-header">
                <div>
                  <h3>{stage.display_name || stage.stage_key}</h3>
                  <p>{stage.model_name} · prompt {stage.prompt_version}</p>
                </div>
                <div className="reviewer-editor-badges">
                  <span className={`status-badge ${stage.active ? 'status-done' : 'status-draft'}`}>
                    {stage.active ? 'ACTIVE' : 'INACTIVE'}
                  </span>
                </div>
              </div>

              <div className="reviewer-editor-grid">
                <label className="form-group">
                  <span>Has Data Threshold</span>
                  <input
                    type="number"
                    min="0"
                    max="1"
                    step="0.01"
                    value={draft.positive_threshold}
                    onChange={(event) => onChangeDraft(stage.stage_key, 'positive_threshold', event.target.value)}
                  />
                </label>

                <label className="form-group">
                  <span>No Data Threshold</span>
                  <input
                    type="number"
                    min="0"
                    max="1"
                    step="0.01"
                    value={draft.negative_threshold}
                    onChange={(event) => onChangeDraft(stage.stage_key, 'negative_threshold', event.target.value)}
                  />
                </label>

                <label className="form-group">
                  <span>Audit Rate</span>
                  <input
                    type="number"
                    min="0"
                    max="1"
                    step="0.01"
                    value={draft.audit_rate}
                    onChange={(event) => onChangeDraft(stage.stage_key, 'audit_rate', event.target.value)}
                  />
                </label>
              </div>

              <div className="reviewer-admin-actions">
                <button
                  className="btn btn-primary reviewer-save-btn"
                  onClick={() => onSaveDraft(stage.stage_key)}
                  disabled={savingStageKey === stage.stage_key}
                >
                  {savingStageKey === stage.stage_key ? 'Saving...' : 'Save routing policy'}
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function CockpitView({
  cockpitData,
  onRefresh,
  reviewerDrafts,
  newReviewerDraft,
  savingReviewerTarget,
  routingConfigDrafts,
  savingRoutingStageKey,
  onChangeDraft,
  onToggleDraftShadowSlot,
  onSaveDraft,
  onResetDraft,
  onChangeNewDraft,
  onToggleNewShadowSlot,
  onCreateReviewer,
  onResetNewReviewer,
  onChangeRoutingConfig,
  onSaveRoutingConfig,
}) {
  const reviewerMetrics = computeReviewerMetrics(cockpitData)
  const sourceBreakdown = computeSourceBreakdown(cockpitData)
  const routingCounts = computeRoutingCounts(cockpitData.papers)
  const openConflicts = (cockpitData.conflicts || []).filter((row) => row.status === 'open')
  const openAssignments = (cockpitData.userAssignments || []).filter((row) => OPEN_STATUSES.has(row.status))

  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <div>
          <h2>Cockpit</h2>
          <p>Queue health, agreement metrics, and conflict pressure across the project.</p>
        </div>
        <button className="btn btn-outline" onClick={onRefresh}>Refresh</button>
      </div>

      <div className="dashboard-grid dashboard-grid-summary">
        <div className="dashboard-card">
          <div className="dashboard-card-label">Open Personal Queue</div>
          <div className="dashboard-card-value">{openAssignments.length}</div>
        </div>
        <div className="dashboard-card">
          <div className="dashboard-card-label">Resolved Papers</div>
          <div className="dashboard-card-value">{cockpitData.outcomes.length}</div>
        </div>
        <div className="dashboard-card">
          <div className="dashboard-card-label">Open Conflicts</div>
          <div className="dashboard-card-value">{openConflicts.length}</div>
        </div>
        <div className="dashboard-card">
          <div className="dashboard-card-label">Final Submissions</div>
          <div className="dashboard-card-value">{cockpitData.submissions.length}</div>
        </div>
      </div>

      <RoutingStagePanel
        stageConfigs={cockpitData.routingStageConfigs || []}
        routingCounts={routingCounts}
        routingConfigDrafts={routingConfigDrafts}
        savingStageKey={savingRoutingStageKey}
        onChangeDraft={onChangeRoutingConfig}
        onSaveDraft={onSaveRoutingConfig}
      />

      <div className="dashboard-grid dashboard-grid-main">
        <div className="dashboard-card dashboard-card-table">
          <div className="dashboard-card-title">Reviewer Accuracy</div>
          <div className="table-scroll">
            <table className="dashboard-table">
              <thead>
                <tr>
                  <th>Reviewer</th>
                  <th>Open</th>
                  <th>Submitted</th>
                  <th>Conflicts</th>
                  <th>Resolved</th>
                  <th>Accuracy</th>
                </tr>
              </thead>
              <tbody>
                {reviewerMetrics.map((row) => (
                  <tr key={row.id}>
                    <td>{row.display_name}</td>
                    <td>{row.open}</td>
                    <td>{row.submitted}</td>
                    <td>{row.conflict}</td>
                    <td>{row.resolved}</td>
                    <td>{row.accuracy == null ? '—' : `${row.accuracy}%`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="dashboard-card dashboard-card-table">
          <div className="dashboard-card-title">Resolved Source Yield</div>
          <div className="table-scroll">
            <table className="dashboard-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Template</th>
                  <th>Term</th>
                  <th>Positive</th>
                  <th>Negative</th>
                </tr>
              </thead>
              <tbody>
                {sourceBreakdown.length === 0 ? (
                  <tr>
                    <td colSpan="5">No resolved outcome history yet.</td>
                  </tr>
                ) : sourceBreakdown.map((row) => (
                  <tr key={`${row.source}|${row.template_id}|${row.source_term}`}>
                    <td>{row.source}</td>
                    <td>{row.template_id}</td>
                    <td>{row.source_term || '—'}</td>
                    <td>{row.positive}</td>
                    <td>{row.negative}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="dashboard-card dashboard-card-table">
        <div className="dashboard-card-title">Open Conflicts</div>
        <div className="table-scroll">
          <table className="dashboard-table">
            <thead>
              <tr>
                <th>Paper ID</th>
                <th>Type</th>
                <th>Slot</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {openConflicts.length === 0 ? (
                <tr>
                  <td colSpan="4">No open conflicts.</td>
                </tr>
              ) : openConflicts.map((conflict) => (
                <tr key={conflict.id}>
                  <td>{conflict.paper_id}</td>
                  <td>{conflict.conflict_type}</td>
                  <td>{conflict.slot_key || 'cross-slot'}</td>
                  <td>{conflict.created_at ? new Date(conflict.created_at).toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <ReviewerAdminPanel
        cockpitData={cockpitData}
        reviewerDrafts={reviewerDrafts}
        newReviewerDraft={newReviewerDraft}
        savingReviewerTarget={savingReviewerTarget}
        onChangeDraft={onChangeDraft}
        onToggleDraftShadowSlot={onToggleDraftShadowSlot}
        onSaveDraft={onSaveDraft}
        onResetDraft={onResetDraft}
        onChangeNewDraft={onChangeNewDraft}
        onToggleNewShadowSlot={onToggleNewShadowSlot}
        onCreateReviewer={onCreateReviewer}
        onResetNewReviewer={onResetNewReviewer}
      />
    </div>
  )
}

function SuggestionsReviewView({
  suggestionItems = [],
  onRefresh,
  onSaveReview,
  savingSuggestionId,
}) {
  const [drafts, setDrafts] = useState({})

  const updateDraft = useCallback((itemId, field, value) => {
    setDrafts((previous) => ({
      ...previous,
      [itemId]: {
        ...(previous[itemId] || {}),
        [field]: value,
      },
    }))
  }, [])

  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <div>
          <h2>Suggestion Review Queue</h2>
          <p>Incoming user suggestions are captured here as unapproved backlog review items.</p>
        </div>
        <button className="btn btn-outline" onClick={onRefresh}>Refresh</button>
      </div>

      <div className="dashboard-card">
        <div className="dashboard-card-title">Review Items</div>
        <div className="suggestion-review-list">
          {!suggestionItems.length ? (
            <div className="empty-panel">No suggestion review items yet.</div>
          ) : suggestionItems.map((item) => {
            const draft = drafts[item.id] || {
              status: item.status || 'new',
              follow_up_required: Boolean(item.follow_up_required),
              follow_up_note: item.follow_up_note || '',
              review_note: item.review_note || '',
            }

            return (
              <div key={item.id} className="suggestion-review-item">
                <div className="suggestion-review-header">
                  <div className="suggestion-review-meta">
                    <span className="status-badge status-pending">{item.item_kind || 'suggestion_review'}</span>
                    <span className="status-badge status-draft">{formatSuggestionReviewStatus(item.status)}</span>
                    <span>{item.created_at ? new Date(item.created_at).toLocaleString() : '-'}</span>
                  </div>
                  <div className="suggestion-review-author">
                    {(item.submitted_by_name || '').trim() || item.submitted_by_email || item.submitted_by_auth_user_id || 'Unknown submitter'}
                  </div>
                </div>

                <div className="suggestion-review-body">{item.suggestion_text}</div>

                <div className="suggestion-review-controls">
                  <label className="form-group">
                    <span>Status</span>
                    <select
                      value={draft.status}
                      onChange={(event) => updateDraft(item.id, 'status', event.target.value)}
                    >
                      {SUGGESTION_REVIEW_STATUSES.map((status) => (
                        <option key={status} value={status}>{formatSuggestionReviewStatus(status)}</option>
                      ))}
                    </select>
                  </label>

                  <label className="reviewer-toggle">
                    <input
                      type="checkbox"
                      checked={Boolean(draft.follow_up_required)}
                      onChange={(event) => updateDraft(item.id, 'follow_up_required', event.target.checked)}
                    />
                    Follow-up needed
                  </label>
                </div>

                <label className="form-group">
                  <span>Follow-up note</span>
                  <input
                    value={draft.follow_up_note}
                    onChange={(event) => updateDraft(item.id, 'follow_up_note', event.target.value)}
                    placeholder="Optional follow-up plan"
                  />
                </label>

                <label className="form-group">
                  <span>Review note</span>
                  <textarea
                    value={draft.review_note}
                    onChange={(event) => updateDraft(item.id, 'review_note', event.target.value)}
                    placeholder="Optional triage context"
                  />
                </label>

                <div className="suggestion-review-actions">
                  <button
                    className="btn btn-primary"
                    onClick={() => onSaveReview(item.id, draft)}
                    disabled={savingSuggestionId === item.id}
                  >
                    {savingSuggestionId === item.id ? 'Saving...' : 'Save Review Status'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function AiDetailPanel({ extraction, outcome }) {
  const payload = extraction?.normalized_payload_json || { decision_kind: getAiDecisionKind(extraction), food_items: [] }
  const summary = getNormalizationSummary(extraction)
  const comparison = getAiComparisonStatus(extraction, outcome)
  const metadata = getAiRawMetadata(extraction)
  const rejectionReasons = Object.entries(summary.rejection_reasons || {})

  return (
    <div className="ai-detail-panel">
      <div className="ai-detail-header">
        <div>
          <div className="ai-detail-title">AI Extraction Detail</div>
          <div className="table-secondary-line">
            {extraction?.stage_key || 'No stage'} · {extraction?.prompt_version || 'No prompt version'}
          </div>
        </div>
        <div className="reviewer-admin-badges">
          <span className={`status-badge ${payload.decision_kind === 'has_data' ? 'status-done' : 'status-skipped'}`}>
            {formatDecisionLabel(payload.decision_kind)}
          </span>
          {comparison && <span className={`status-badge ${comparison.badgeClass}`}>{comparison.label}</span>}
        </div>
      </div>

      <div className="ai-detail-grid">
        <div className="ai-detail-metric">
          <span>Model Decision</span>
          <strong>{extraction?.is_useful ? 'Has Data' : 'No Data'}</strong>
        </div>
        <div className="ai-detail-metric">
          <span>Confidence</span>
          <strong>{extraction?.overall_confidence == null ? '—' : Number(extraction.overall_confidence).toFixed(3)}</strong>
        </div>
        <div className="ai-detail-metric">
          <span>Routing Bucket</span>
          <strong>{extraction?.routing_bucket || '—'}</strong>
        </div>
        <div className="ai-detail-metric">
          <span>Rows</span>
          <strong>{summary.accepted_row_count}/{summary.input_row_count}</strong>
        </div>
        <div className="ai-detail-metric">
          <span>Rejected</span>
          <strong>{summary.rejected_row_count}</strong>
        </div>
        <div className="ai-detail-metric">
          <span>Custom Foods</span>
          <strong>{summary.unmapped_food_count}</strong>
        </div>
        <div className="ai-detail-metric">
          <span>Custom Nutrients</span>
          <strong>{summary.unmapped_nutrient_count}</strong>
        </div>
        <div className="ai-detail-metric">
          <span>Destination</span>
          <strong>{formatRouteDestinationLabel(extraction?.route_destination)}</strong>
        </div>
      </div>

      <div className="ai-detail-section">
        <div className="ai-detail-section-title">Reasoning</div>
        <div className="ai-reasoning">{extraction?.reasoning || 'No reasoning stored.'}</div>
      </div>

      {rejectionReasons.length > 0 && (
        <div className="ai-detail-section">
          <div className="ai-detail-section-title">Rejected Rows</div>
          <div className="ai-rejection-list">
            {rejectionReasons.map(([reason, count]) => (
              <span key={reason} className="status-badge status-skipped">{reason}: {count}</span>
            ))}
          </div>
        </div>
      )}

      <div className="ai-json-grid">
        <div className="ai-detail-section">
          <div className="ai-detail-section-title">Normalized DB Payload</div>
          <pre className="ai-json-block">{JSON.stringify(payload, null, 2)}</pre>
        </div>
        <div className="ai-detail-section">
          <div className="ai-detail-section-title">Raw Response Metadata</div>
          <pre className="ai-json-block">{JSON.stringify(metadata, null, 2)}</pre>
        </div>
      </div>
    </div>
  )
}

function AllPapersView({ cockpitData, onRefresh }) {
  const [expandedAiPaperId, setExpandedAiPaperId] = useState(null)
  const reviewerById = buildReviewerMap(cockpitData.reviewerProfiles)
  const slotAssignmentsByPaperId = groupRowsByPaperId(cockpitData.slotAssignments)
  const userAssignmentsByPaperId = groupRowsByPaperId(cockpitData.userAssignments)
  const outcomeByPaperId = Object.fromEntries((cockpitData.outcomes || []).map((row) => [row.paper_id, row]))
  const latestAiExtractionById = Object.fromEntries((cockpitData.aiExtractions || []).map((row) => [row.id, row]))
  const latestAiExtractionByPaperId = {}
  for (const row of cockpitData.aiExtractions || []) {
    if (!row?.paper_id) continue
    const existing = latestAiExtractionByPaperId[row.paper_id]
    if (!existing || new Date(row.created_at || 0).getTime() > new Date(existing.created_at || 0).getTime()) {
      latestAiExtractionByPaperId[row.paper_id] = row
    }
  }
  const rows = (cockpitData.papers || []).map((paper) => ({
    paper,
    slotAssignments: (slotAssignmentsByPaperId[paper.id] || []).slice().sort((left, right) => left.slot_key.localeCompare(right.slot_key)),
    userAssignments: (userAssignmentsByPaperId[paper.id] || []).slice().sort((left, right) => {
      const leftName = reviewerById[left.reviewer_profile_id]?.display_name || reviewerById[left.reviewer_profile_id]?.email || ''
      const rightName = reviewerById[right.reviewer_profile_id]?.display_name || reviewerById[right.reviewer_profile_id]?.email || ''
      return leftName.localeCompare(rightName)
    }),
    outcome: outcomeByPaperId[paper.id] || null,
    latestAiExtraction: latestAiExtractionById[paper.latest_ai_extraction_id] || latestAiExtractionByPaperId[paper.id] || null,
  }))
  const unresolvedCount = rows.filter((row) => !row.outcome).length
  const openAssignmentCount = (cockpitData.userAssignments || []).filter((row) => OPEN_STATUSES.has(row.status)).length

  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <div>
          <h2>All Papers</h2>
          <p>Global paper and assignment overview. This is the admin screen for project-wide visibility.</p>
        </div>
        <button className="btn btn-outline" onClick={onRefresh}>Refresh</button>
      </div>

      <div className="dashboard-grid dashboard-grid-summary">
        <div className="dashboard-card">
          <div className="dashboard-card-label">Tracked Papers</div>
          <div className="dashboard-card-value">{rows.length}</div>
        </div>
        <div className="dashboard-card">
          <div className="dashboard-card-label">Resolved Papers</div>
          <div className="dashboard-card-value">{cockpitData.outcomes.length}</div>
        </div>
        <div className="dashboard-card">
          <div className="dashboard-card-label">Without Final Outcome</div>
          <div className="dashboard-card-value">{unresolvedCount}</div>
        </div>
        <div className="dashboard-card">
          <div className="dashboard-card-label">Open User Assignments</div>
          <div className="dashboard-card-value">{openAssignmentCount}</div>
        </div>
      </div>

      <div className="dashboard-card dashboard-card-table">
        <div className="dashboard-card-title">Paper Workflow Overview</div>
        <div className="table-scroll">
          <table className="dashboard-table">
            <thead>
              <tr>
                <th>Paper</th>
                <th>Routing</th>
                <th>Latest AI</th>
                <th>Official Slots</th>
                <th>Reviewer Tasks</th>
                <th>Final Outcome</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan="6">No papers found.</td>
                </tr>
              ) : rows.map(({ paper, slotAssignments, userAssignments, outcome, latestAiExtraction }) => {
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
                          <span className="table-secondary-line">{paper.routing_bucket || 'No bucket yet'}</span>
                        </div>
                      </td>
                      <td>
                        {latestAiExtraction ? (
                          <div className="table-cell-stack">
                            <div className="table-detail-line">
                              <span>{latestAiExtraction.is_useful ? 'Has Data' : 'No Data'}</span>
                              <span className={`status-badge ${latestAiExtraction.audit_sampled ? 'status-draft' : 'status-pending'}`}>
                                {latestAiExtraction.audit_sampled ? 'AUDIT' : 'LIVE'}
                              </span>
                            </div>
                            <span className="table-secondary-line">
                              conf {latestAiExtraction.overall_confidence == null ? '—' : Number(latestAiExtraction.overall_confidence).toFixed(2)}
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
                        <div className="table-cell-stack">
                          {slotAssignments.length === 0 ? (
                            <span className="table-secondary-line">No slot assignments.</span>
                          ) : slotAssignments.map((assignment) => (
                            <div key={assignment.id} className="table-detail-line">
                              <span>{assignment.slot_key}</span>
                              <span className={`status-badge ${getStatusBadgeClass(assignment.status)}`}>{formatStatusLabel(assignment.status)}</span>
                            </div>
                          ))}
                        </div>
                      </td>
                      <td>
                        <div className="table-cell-stack">
                          {userAssignments.length === 0 ? (
                            <span className="table-secondary-line">No user assignments.</span>
                          ) : userAssignments.map((assignment) => {
                            const reviewer = reviewerById[assignment.reviewer_profile_id]
                            return (
                              <div key={assignment.id} className="table-detail-line">
                                <span>{reviewer?.display_name || reviewer?.email || assignment.reviewer_profile_id}</span>
                                <span className={`status-badge ${getStatusBadgeClass(assignment.status)}`}>{formatStatusLabel(assignment.status)}</span>
                              </div>
                            )
                          })}
                        </div>
                      </td>
                      <td>
                        {outcome ? (
                          <div className="table-cell-stack">
                            <div className="table-detail-line">
                              <span>{formatDecisionLabel(outcome.decision_kind)}</span>
                              <span className="status-badge status-done">{outcome.resolution_source || 'resolved'}</span>
                            </div>
                            <span className="table-secondary-line">{outcome.resolved_at ? new Date(outcome.resolved_at).toLocaleString() : 'No timestamp'}</span>
                          </div>
                        ) : (
                          <span className="status-badge status-pending">Pending</span>
                        )}
                      </td>
                    </tr>
                    {aiExpanded && (
                      <tr className="ai-detail-row">
                        <td colSpan="6">
                          <AiDetailPanel extraction={latestAiExtraction} outcome={outcome} />
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

function ConflictsView({
  conflicts,
  selectedConflictId,
  setSelectedConflictId,
  papersById,
  submissionsById,
  reviewerById,
  resolutionNote,
  setResolutionNote,
  onResolve,
  allNutrients,
  theme,
}) {
  const openConflicts = conflicts.filter((row) => row.status === 'open')
  const selectedConflict =
    openConflicts.find((row) => row.id === selectedConflictId) || openConflicts[0] || null
  const leftSubmission = selectedConflict ? submissionsById[selectedConflict.left_submission_id] : null
  const rightSubmission = selectedConflict ? submissionsById[selectedConflict.right_submission_id] : null
  const paper = selectedConflict ? papersById[selectedConflict.paper_id] : null
  const pdfUrl = paper ? getPublicPdfUrl(paper.filename) : null

  return (
    <div className="workspace conflict-workspace">
      <div className="conflict-sidebar">
        <div className="conflict-sidebar-header">
          <h2>Conflicts</h2>
          <p>{openConflicts.length} open</p>
        </div>
        <div className="conflict-list">
          {openConflicts.length === 0 ? (
            <div className="empty-panel">No open conflicts right now.</div>
          ) : openConflicts.map((conflict) => (
            <button
              key={conflict.id}
              className={`conflict-list-item ${selectedConflict?.id === conflict.id ? 'active' : ''}`}
              onClick={() => setSelectedConflictId(conflict.id)}
            >
              <span>{conflict.conflict_type === 'internal_slot_conflict' ? 'Internal' : 'External'}</span>
              <strong>Paper {conflict.paper_id}</strong>
              <small>{conflict.slot_key || 'cross-slot'}</small>
            </button>
          ))}
        </div>
      </div>

      <PdfViewer
        pdfUrl={pdfUrl}
        allNutrients={allNutrients}
        onAddNutrient={() => {}}
        theme={theme}
      />

      <div className="annotation-panel conflict-panel">
        {!selectedConflict ? (
          <div className="annotation-scroll">
            <div className="empty-panel">Select a conflict to compare both submissions.</div>
          </div>
        ) : (
          <>
            <div className="conflict-header">
              <div>
                <h2>{paper?.title || `Paper ${selectedConflict.paper_id}`}</h2>
                <p>{selectedConflict.conflict_type} · {selectedConflict.slot_key || 'cross-slot'}</p>
              </div>
              <div className="status-badge status-conflict">Needs decision</div>
            </div>
            <div className="annotation-scroll conflict-scroll">
              <div className="payload-grid">
                <PayloadSummary
                  submission={leftSubmission}
                  reviewer={reviewerById[leftSubmission?.reviewer_profile_id]}
                  highlighted={false}
                  onResolve={leftSubmission ? () => onResolve(selectedConflict, leftSubmission.id) : null}
                />
                <PayloadSummary
                  submission={rightSubmission}
                  reviewer={reviewerById[rightSubmission?.reviewer_profile_id]}
                  highlighted={false}
                  onResolve={rightSubmission ? () => onResolve(selectedConflict, rightSubmission.id) : null}
                />
              </div>
            </div>
            <div className="annotation-actions">
              <label className="form-group" style={{ marginBottom: 0 }}>
                <span style={{ display: 'block', marginBottom: 6, color: 'var(--text-secondary)', fontSize: 13 }}>Resolution note</span>
                <input
                  value={resolutionNote}
                  onChange={(event) => setResolutionNote(event.target.value)}
                  placeholder="Why this side wins"
                />
              </label>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default function Annotate({ user, onLogout, theme, toggleTheme }) {
  const [reviewerProfile, setReviewerProfile] = useState(null)
  const [profileError, setProfileError] = useState(null)
  const [activeView, setActiveView] = useState('queue')
  const [assignments, setAssignments] = useState([])
  const [selectedAssignmentId, setSelectedAssignmentId] = useState(null)
  const [foodItems, setFoodItems] = useState([createEmptyFoodItem()])
  const [saving, setSaving] = useState(false)
  const [loadingQueue, setLoadingQueue] = useState(true)
  const [loadingCockpit, setLoadingCockpit] = useState(false)
  const [toast, setToast] = useState(null)
  const [showSuggestion, setShowSuggestion] = useState(false)
  const [showPaperList, setShowPaperList] = useState(false)
  const [allNutrients, setAllNutrients] = useState([])
  const [allFoods, setAllFoods] = useState([])
  const [foodsLoaded, setFoodsLoaded] = useState(false)
  const [testMode, setTestMode] = useState(() => isTestModeEnabled())
  const [cockpitData, setCockpitData] = useState(EMPTY_COCKPIT_DATA)
  const [reviewerDrafts, setReviewerDrafts] = useState({})
  const [routingConfigDrafts, setRoutingConfigDrafts] = useState({})
  const [newReviewerDraft, setNewReviewerDraft] = useState(() => createEmptyReviewerDraft())
  const [savingReviewerTarget, setSavingReviewerTarget] = useState(null)
  const [savingRoutingStageKey, setSavingRoutingStageKey] = useState(null)
  const [savingSuggestionId, setSavingSuggestionId] = useState(null)
  const [selectedConflictId, setSelectedConflictId] = useState(null)
  const [resolutionNote, setResolutionNote] = useState('')
  const undoTimerRef = useRef(null)
  const paperListRef = useRef(null)

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (paperListRef.current && !paperListRef.current.contains(e.target)) {
        setShowPaperList(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const currentAssignment = assignments.find((assignment) => assignment.id === selectedAssignmentId) || null
  const currentPaper = currentAssignment?.paper || null
  const currentPaperIndex = assignments.findIndex((assignment) => assignment.id === selectedAssignmentId)
  const pdfUrl = currentPaper ? getPublicPdfUrl(currentPaper.filename) : null
  const isTesterAccount = Boolean(reviewerProfile?.tester_access)
  const isDeveloperTrainingMode = Boolean(reviewerProfile?.tester_access && reviewerProfile?.cockpit_access)
  const queueStats = {
    open: assignments.filter((assignment) => OPEN_STATUSES.has(assignment.status)).length,
    final: assignments.filter((assignment) => FINAL_STATUSES.has(assignment.status)).length,
    conflict: assignments.filter((assignment) => assignment.status === 'conflict').length,
    resolved: assignments.filter((assignment) => assignment.status === 'resolved').length,
    cancelled: assignments.filter((assignment) => assignment.status === 'cancelled').length,
  }
  const isEditable = currentAssignment ? OPEN_STATUSES.has(currentAssignment.status) : false

  const showToast = useCallback((message, type = 'success') => {
    setToast({ message, type })
    if (undoTimerRef.current) {
      clearTimeout(undoTimerRef.current)
    }
    undoTimerRef.current = setTimeout(() => setToast(null), 3000)
  }, [])

  const refreshQueue = useCallback(async () => {
    if (!reviewerProfile?.id) {
      setAssignments([])
      setSelectedAssignmentId(null)
      setLoadingQueue(false)
      return []
    }

    setLoadingQueue(true)
    try {
      if (isDeveloperTrainingMode) {
        const [paperResponse, slotAssignmentsResponse] = await Promise.all([
          supabase
            .from('papers')
            .select('id,title,abstract,doi,filename,workflow_language,created_at,routing_status')
            .eq('routing_status', 'human_review_ready')
            .in('workflow_language', SUPPORTED_WORKFLOW_LANGUAGES)
            .order('id', { ascending: false })
            .limit(2000),
          supabase
            .from('paper_slot_assignments')
            .select('id,paper_id,slot_key,workflow_language,status,assigned_at,submitted_at,resolved_at,created_at')
            .in('workflow_language', SUPPORTED_WORKFLOW_LANGUAGES)
            .order('assigned_at', { ascending: false })
            .limit(4000),
        ])

        if (paperResponse.error) throw paperResponse.error
        if (slotAssignmentsResponse.error) throw slotAssignmentsResponse.error

        const virtualAssignments = buildDeveloperTrainingAssignments({
          papers: paperResponse.data || [],
          slotAssignments: slotAssignmentsResponse.data || [],
          reviewerProfileId: reviewerProfile.id,
        })

        setAssignments(virtualAssignments)
        setSelectedAssignmentId((previousId) => pickDefaultAssignment(virtualAssignments, previousId))
        return virtualAssignments
      }

      if (isTesterAccount) {
        const { data: paperRows, error: paperError } = await supabase
          .from('papers')
          .select('*')
          .eq('routing_status', 'human_review_ready')
          .order('id', { ascending: false })
          .limit(250)

        if (paperError) throw paperError

        const virtualAssignments = buildGenericTesterAssignments(paperRows || [], reviewerProfile.id)

        setAssignments(virtualAssignments)
        setSelectedAssignmentId((previousId) => pickDefaultAssignment(virtualAssignments, previousId))
        return virtualAssignments
      }

      const { data: assignmentRows, error: assignmentError } = await supabase
        .from('paper_user_assignments')
        .select('*')
        .eq('reviewer_profile_id', reviewerProfile.id)
        .order('assigned_at', { ascending: true })

      if (assignmentError) throw assignmentError

      const orderedAssignments = sortAssignments(assignmentRows || [])
      const paperIds = [...new Set(orderedAssignments.map((assignment) => assignment.paper_id).filter(Boolean))]
      const slotIds = [...new Set(orderedAssignments.map((assignment) => assignment.paper_slot_assignment_id).filter(Boolean))]

      const [paperResponse, slotResponse, outcomeResponse] = await Promise.all([
        paperIds.length
          ? supabase.from('papers').select('*').in('id', paperIds)
          : Promise.resolve({ data: [], error: null }),
        slotIds.length
          ? supabase.from('paper_slot_assignments').select('*').in('id', slotIds)
          : Promise.resolve({ data: [], error: null }),
        paperIds.length
          ? supabase.from('paper_review_outcomes').select('*').in('paper_id', paperIds)
          : Promise.resolve({ data: [], error: null }),
      ])

      if (paperResponse.error) throw paperResponse.error
      if (slotResponse.error) throw slotResponse.error
      if (outcomeResponse.error) throw outcomeResponse.error

      const paperMap = buildPaperMap(paperResponse.data || [])
      const slotMap = Object.fromEntries((slotResponse.data || []).map((row) => [row.id, row]))
      const outcomeMap = Object.fromEntries((outcomeResponse.data || []).map((row) => [row.paper_id, row]))

      const mergedAssignments = orderedAssignments.map((assignment) => ({
        ...assignment,
        paper: paperMap[assignment.paper_id] || null,
        slot_assignment: slotMap[assignment.paper_slot_assignment_id] || null,
        outcome: outcomeMap[assignment.paper_id] || null,
      }))
      setAssignments(mergedAssignments)
      setSelectedAssignmentId((previousId) => pickDefaultAssignment(mergedAssignments, previousId))
      return mergedAssignments
    } catch (error) {
      console.error('Queue refresh failed:', error)
      showToast(`Failed to load queue: ${error.message}`, 'error')
      return []
    } finally {
      setLoadingQueue(false)
    }
  }, [isDeveloperTrainingMode, isTesterAccount, reviewerProfile?.id, showToast])

  const refreshCockpit = useCallback(async () => {
    if (!reviewerProfile?.cockpit_access) return
    setLoadingCockpit(true)
    try {
      const [
        reviewerSlotsResponse,
        reviewerProfilesResponse,
        slotMembersResponse,
        slotAssignmentsResponse,
        userAssignmentsResponse,
        submissionsResponse,
        outcomesResponse,
        conflictsResponse,
        papersResponse,
        aiExtractionsResponse,
        routingStageConfigsResponse,
        searchHitsResponse,
        suggestionReviewItemsResponse,
      ] = await Promise.all([
        supabase.from('reviewer_slots').select('*').order('slot_key', { ascending: true }),
        supabase.from('reviewer_profiles').select('*').order('display_name', { ascending: true }),
        supabase.from('reviewer_slot_members').select('*').order('slot_key', { ascending: true }),
        supabase.from('paper_slot_assignments').select('*').order('assigned_at', { ascending: true }),
        supabase.from('paper_user_assignments').select('*').order('assigned_at', { ascending: true }),
        supabase.from('paper_assignment_submissions').select('*').order('submitted_at', { ascending: false }),
        supabase.from('paper_review_outcomes').select('*').order('resolved_at', { ascending: false }),
        supabase.from('paper_conflicts').select('*').order('created_at', { ascending: false }),
        supabase.from('papers').select('id,title,doi,filename,workflow_language,routing_status,routing_bucket,route_destination,current_stage_key,latest_ai_extraction_id,routing_updated_at').order('id', { ascending: false }),
        supabase.from('ai_extractions').select('*').order('created_at', { ascending: false }).limit(5000),
        supabase.from('routing_stage_configs').select('*').order('display_name', { ascending: true }),
        supabase.from('paper_search_hits').select('paper_id,source,template_id,source_term,query_phrase,workflow_language'),
        supabase.from('backlog_review_items').select('*').order('created_at', { ascending: false }),
      ])

      if (reviewerSlotsResponse.error) throw reviewerSlotsResponse.error
      if (reviewerProfilesResponse.error) throw reviewerProfilesResponse.error
      if (slotMembersResponse.error) throw slotMembersResponse.error
      if (slotAssignmentsResponse.error) throw slotAssignmentsResponse.error
      if (userAssignmentsResponse.error) throw userAssignmentsResponse.error
      if (submissionsResponse.error) throw submissionsResponse.error
      if (outcomesResponse.error) throw outcomesResponse.error
      if (conflictsResponse.error) throw conflictsResponse.error
      if (papersResponse.error) throw papersResponse.error
      if (aiExtractionsResponse.error) throw aiExtractionsResponse.error
      if (routingStageConfigsResponse.error) throw routingStageConfigsResponse.error
      if (searchHitsResponse.error) throw searchHitsResponse.error
      if (suggestionReviewItemsResponse.error) throw suggestionReviewItemsResponse.error

      setCockpitData({
        reviewerSlots: reviewerSlotsResponse.data || [],
        reviewerProfiles: reviewerProfilesResponse.data || [],
        slotMembers: slotMembersResponse.data || [],
        slotAssignments: slotAssignmentsResponse.data || [],
        userAssignments: userAssignmentsResponse.data || [],
        submissions: submissionsResponse.data || [],
        outcomes: outcomesResponse.data || [],
        conflicts: conflictsResponse.data || [],
        papers: papersResponse.data || [],
        aiExtractions: aiExtractionsResponse.data || [],
        routingStageConfigs: routingStageConfigsResponse.data || [],
        searchHits: searchHitsResponse.data || [],
        suggestionReviewItems: suggestionReviewItemsResponse.data || [],
      })

      setSelectedConflictId((previousId) => {
        const openConflicts = (conflictsResponse.data || []).filter((row) => row.status === 'open')
        if (!openConflicts.length) return null
        if (previousId && openConflicts.some((row) => row.id === previousId)) return previousId
        return openConflicts[0].id
      })
    } catch (error) {
      console.error('Cockpit refresh failed:', error)
      showToast(`Failed to load cockpit: ${error.message}`, 'error')
    } finally {
      setLoadingCockpit(false)
    }
  }, [reviewerProfile?.cockpit_access, showToast])

  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      try {
        const { data, error } = await supabase.rpc('sync_reviewer_profile')
        if (error) throw error
        const nextProfile = Array.isArray(data) ? data[0] : data
        if (!cancelled) {
          setReviewerProfile(nextProfile || null)
          setProfileError(null)
          if (nextProfile?.tester_access) {
            setTestMode(true)
            setTestModeEnabled(true)
          }
          if (!(nextProfile?.cockpit_access)) {
            setActiveView('queue')
          }
        }
      } catch (error) {
        console.error('Failed to sync reviewer profile:', error)
        if (!cancelled) {
          setProfileError(error.message)
          showToast(`Profile sync failed: ${error.message}`, 'error')
        }
      }
    }

    bootstrap()
    return () => {
      cancelled = true
    }
  }, [showToast])

  useEffect(() => {
    if (!reviewerProfile) return
    refreshQueue()
    if (reviewerProfile.cockpit_access) {
      refreshCockpit()
    }
  }, [refreshCockpit, refreshQueue, reviewerProfile])

  useEffect(() => {
    if (reviewerProfile && !reviewerProfile.cockpit_access && activeView !== 'queue') {
      setActiveView('queue')
    }
  }, [activeView, reviewerProfile])

  useEffect(() => {
    if (!reviewerProfile?.cockpit_access) return
    const slotMembersByProfile = buildSlotMembersByProfile(cockpitData.slotMembers)
    const nextDrafts = Object.fromEntries(
      (cockpitData.reviewerProfiles || []).map((profile) => [
        profile.id,
        createReviewerDraft(profile, slotMembersByProfile[profile.id] || []),
      ])
    )
    setReviewerDrafts(nextDrafts)
    setNewReviewerDraft(createEmptyReviewerDraft())
  }, [cockpitData.reviewerProfiles, cockpitData.slotMembers, reviewerProfile?.cockpit_access])

  useEffect(() => {
    if (!reviewerProfile?.cockpit_access) return
    const nextDrafts = Object.fromEntries(
      (cockpitData.routingStageConfigs || []).map((stage) => [
        stage.stage_key,
        {
          positive_threshold: stage.positive_threshold ?? 1,
          negative_threshold: stage.negative_threshold ?? 1,
          audit_rate: stage.audit_rate ?? 0.05,
        },
      ])
    )
    setRoutingConfigDrafts(nextDrafts)
  }, [cockpitData.routingStageConfigs, reviewerProfile?.cockpit_access])

  useEffect(() => {
    async function fetchNutrients() {
      const { data, error } = await supabase
        .from('master_nutrients')
        .select('id, standard_name, description')
        .order('standard_name', { ascending: true })

      if (error) {
        console.error('Error fetching nutrients:', error)
        return
      }

      setAllNutrients((data || []).map((nutrient) => ({
        id: nutrient.id,
        name: nutrient.standard_name,
        unit_name: parseUnitFromDescription(nutrient.description),
        rank: 99999,
      })))
    }

    fetchNutrients()
  }, [])

  useEffect(() => {
    let cancelled = false

    async function fetchFoods() {
      const batchSize = 1000
      let from = 0
      const rows = []

      try {
        while (!cancelled) {
          const { data, error } = await supabase
            .from('entities')
            .select('id, canonical_name, category')
            .range(from, from + batchSize - 1)

          if (error) throw error

          const batch = data || []
          rows.push(...batch)
          if (batch.length < batchSize) break
          from += batchSize
        }

        if (!cancelled) {
          setAllFoods(rows)
          setFoodsLoaded(true)
        }
      } catch (error) {
        console.error('Error fetching foods:', error)
      }
    }

    const idleId = typeof window !== 'undefined' && 'requestIdleCallback' in window
      ? window.requestIdleCallback(() => void fetchFoods(), { timeout: 1500 })
      : window.setTimeout(() => void fetchFoods(), 300)

    return () => {
      cancelled = true
      if (typeof window !== 'undefined' && 'cancelIdleCallback' in window && typeof idleId === 'number') {
        window.cancelIdleCallback(idleId)
      } else {
        clearTimeout(idleId)
      }
    }
  }, [])

  useEffect(() => {
    if (!currentAssignment) {
      setFoodItems([createEmptyFoodItem()])
      return
    }

    if (currentAssignment.is_virtual) {
      setFoodItems([createEmptyFoodItem()])
      return
    }

    let cancelled = false

    async function loadAnnotation() {
      const assignmentScoped = await supabase
        .from('annotations')
        .select('*')
        .eq('paper_user_assignment_id', currentAssignment.id)
        .maybeSingle()

      const fallback = assignmentScoped.data
        ? assignmentScoped
        : await supabase
            .from('annotations')
            .select('*')
            .eq('paper_id', currentAssignment.paper_id)
            .eq('user_id', user.id)
            .maybeSingle()

      const annotation = fallback.data
      if (fallback.error) {
        console.error('Annotation load failed:', fallback.error)
        if (!cancelled) setFoodItems([createEmptyFoodItem()])
        return
      }

      if (!annotation || !annotation.has_data) {
        if (!cancelled) setFoodItems([createEmptyFoodItem()])
        return
      }

      const { data: itemRows, error: itemError } = await supabase
        .from('food_items')
        .select('*')
        .eq('annotation_id', annotation.id)
        .order('id', { ascending: true })

      if (itemError) {
        console.error('Food item load failed:', itemError)
        if (!cancelled) setFoodItems([createEmptyFoodItem()])
        return
      }

      const loadedFoodItems = await Promise.all((itemRows || []).map(async (itemRow) => {
        const { data: nutrientRows, error: nutrientError } = await supabase
          .from('annotation_nutrient_values')
          .select('*')
          .eq('food_item_id', itemRow.id)
          .order('id', { ascending: true })

        if (nutrientError) {
          console.error('Nutrient row load failed:', nutrientError)
        }

        return {
          food_name: itemRow.food_name,
          food_fdc_id: itemRow.food_fdc_id,
          is_custom_food: itemRow.is_custom_food,
          nutrients: (nutrientRows || []).map((row) => ({
            nutrient_id: row.nutrient_id,
            nutrient_name: row.nutrient_name,
            value: row.value,
            unit: row.unit,
          })),
        }
      }))

      if (!cancelled) {
        setFoodItems(loadedFoodItems.length > 0 ? loadedFoodItems : [createEmptyFoodItem()])
      }
    }

    loadAnnotation()
    return () => {
      cancelled = true
    }
  }, [currentAssignment, user.id])

  const handleToggleTestMode = useCallback(() => {
    if (reviewerProfile?.tester_access) {
      setTestMode(true)
      setTestModeEnabled(true)
      showToast('Tester accounts are always in test mode.', 'error')
      return
    }
    const next = !testMode
    const message = next
      ? 'Enable test mode? This will disable all database writes and store actions locally.'
      : 'Disable test mode? Database writes will resume.'
    if (typeof window !== 'undefined' && !window.confirm(message)) return
    setTestMode(next)
    setTestModeEnabled(next)
    showToast(next ? 'Test mode enabled — no DB writes.' : 'Test mode disabled.')
  }, [reviewerProfile?.tester_access, showToast, testMode])

  const updateReviewerDraft = useCallback((profileId, field, value) => {
    setReviewerDrafts((previous) => {
      const existing = previous[profileId]
      if (!existing) return previous
      const next = {
        ...existing,
        [field]: value,
      }
      if (field === 'official_slot' && value) {
        next.shadow_slots = (next.shadow_slots || []).filter((slotKey) => slotKey !== value)
      }
      return {
        ...previous,
        [profileId]: next,
      }
    })
  }, [])

  const toggleReviewerDraftShadowSlot = useCallback((profileId, slotKey) => {
    setReviewerDrafts((previous) => {
      const existing = previous[profileId]
      if (!existing || existing.official_slot === slotKey) return previous
      return {
        ...previous,
        [profileId]: {
          ...existing,
          shadow_slots: toggleShadowSlot(existing.shadow_slots, slotKey),
        },
      }
    })
  }, [])

  const resetReviewerDraft = useCallback((profileId) => {
    const slotMembersByProfile = buildSlotMembersByProfile(cockpitData.slotMembers)
    const profile = (cockpitData.reviewerProfiles || []).find((row) => row.id === profileId)
    if (!profile) return
    setReviewerDrafts((previous) => ({
      ...previous,
      [profileId]: createReviewerDraft(profile, slotMembersByProfile[profile.id] || []),
    }))
  }, [cockpitData.reviewerProfiles, cockpitData.slotMembers])

  const updateNewReviewerDraft = useCallback((field, value) => {
    setNewReviewerDraft((previous) => {
      const next = {
        ...previous,
        [field]: value,
      }
      if (field === 'official_slot' && value) {
        next.shadow_slots = (next.shadow_slots || []).filter((slotKey) => slotKey !== value)
      }
      return next
    })
  }, [])

  const toggleNewReviewerShadowSlot = useCallback((slotKey) => {
    setNewReviewerDraft((previous) => {
      if (previous.official_slot === slotKey) return previous
      return {
        ...previous,
        shadow_slots: toggleShadowSlot(previous.shadow_slots, slotKey),
      }
    })
  }, [])

  const resetNewReviewerDraft = useCallback(() => {
    setNewReviewerDraft(createEmptyReviewerDraft())
  }, [])

  const persistReviewerDraft = useCallback(async (draft, targetKey) => {
    const payload = buildReviewerAdminPayload(draft)
    if (!payload.p_email) {
      showToast('Reviewer email is required.', 'error')
      return
    }
    if (!payload.p_display_name) {
      showToast('Reviewer display name is required.', 'error')
      return
    }

    if (testMode) {
      appendTestEvent({
        type: 'reviewer_admin_save',
        target: targetKey,
        payload,
      })
      if (targetKey === '__new__') {
        setNewReviewerDraft(createEmptyReviewerDraft())
      }
      showToast('Reviewer config stored locally (test mode).')
      return
    }

    setSavingReviewerTarget(targetKey)
    try {
      const { data, error } = await supabase.rpc('upsert_reviewer_admin_config', payload)
      if (error) throw error
      const nextProfile = Array.isArray(data) ? data[0] : data
      if (nextProfile?.id && nextProfile.id === reviewerProfile?.id) {
        setReviewerProfile(nextProfile)
      }
      if (targetKey === '__new__') {
        setNewReviewerDraft(createEmptyReviewerDraft())
      }
      await refreshQueue()
      if (!nextProfile || nextProfile.id !== reviewerProfile?.id || nextProfile.cockpit_access) {
        await refreshCockpit()
      }
      showToast(targetKey === '__new__' ? 'Reviewer created.' : 'Reviewer settings saved.')
    } catch (error) {
      console.error('Reviewer config save failed:', error)
      showToast(`Failed to save reviewer: ${error.message}`, 'error')
    } finally {
      setSavingReviewerTarget(null)
    }
  }, [refreshCockpit, refreshQueue, reviewerProfile?.id, showToast, testMode])

  const saveReviewerDraft = useCallback(async (profileId) => {
    const draft = reviewerDrafts[profileId]
    if (!draft) return
    await persistReviewerDraft(draft, profileId)
  }, [persistReviewerDraft, reviewerDrafts])

  const createReviewer = useCallback(async () => {
    await persistReviewerDraft(newReviewerDraft, '__new__')
  }, [newReviewerDraft, persistReviewerDraft])

  const updateRoutingConfigDraft = useCallback((stageKey, field, value) => {
    setRoutingConfigDrafts((previous) => ({
      ...previous,
      [stageKey]: {
        ...(previous[stageKey] || {}),
        [field]: value,
      },
    }))
  }, [])

  const saveRoutingConfigDraft = useCallback(async (stageKey) => {
    const draft = routingConfigDrafts[stageKey]
    if (!draft) return

    const payload = {
      positive_threshold: Number(draft.positive_threshold),
      negative_threshold: Number(draft.negative_threshold),
      audit_rate: Number(draft.audit_rate),
    }
    if (Object.values(payload).some((value) => Number.isNaN(value) || value < 0 || value > 1)) {
      showToast('Routing thresholds and audit rate must stay between 0 and 1.', 'error')
      return
    }

    if (testMode) {
      appendTestEvent({
        type: 'routing_stage_config_save',
        stage_key: stageKey,
        payload,
      })
      showToast('Routing config stored locally (test mode).')
      return
    }

    setSavingRoutingStageKey(stageKey)
    try {
      const { error } = await supabase
        .from('routing_stage_configs')
        .update(payload)
        .eq('stage_key', stageKey)
      if (error) throw error
      await refreshCockpit()
      showToast('Routing policy saved.')
    } catch (error) {
      console.error('Routing policy save failed:', error)
      showToast(`Failed to save routing policy: ${error.message}`, 'error')
    } finally {
      setSavingRoutingStageKey(null)
    }
  }, [refreshCockpit, routingConfigDrafts, showToast, testMode])

  const saveSuggestionReview = useCallback(async (itemId, draft) => {
    if (!itemId || !draft) return
    const nowIso = new Date().toISOString()
    const payload = {
      status: draft.status || 'new',
      follow_up_required: Boolean(draft.follow_up_required),
      follow_up_note: (draft.follow_up_note || '').trim() || null,
      review_note: (draft.review_note || '').trim() || null,
      reviewed_by_auth_user_id: user?.id || null,
      reviewed_at: nowIso,
      updated_at: nowIso,
    }

    if (testMode) {
      appendTestEvent({
        type: 'suggestion_review_status_update',
        suggestion_review_item_id: itemId,
        ...payload,
      })
      setCockpitData((previous) => ({
        ...previous,
        suggestionReviewItems: (previous.suggestionReviewItems || []).map((item) =>
          item.id === itemId ? { ...item, ...payload } : item
        ),
      }))
      showToast('Suggestion review status stored locally (test mode).')
      return
    }

    setSavingSuggestionId(itemId)
    try {
      const { error } = await supabase
        .from('backlog_review_items')
        .update(payload)
        .eq('id', itemId)
      if (error) throw error
      await refreshCockpit()
      showToast('Suggestion review status saved.')
    } catch (error) {
      console.error('Suggestion review update failed:', error)
      showToast(`Failed to save suggestion review: ${error.message}`, 'error')
    } finally {
      setSavingSuggestionId(null)
    }
  }, [refreshCockpit, showToast, testMode, user?.id])

  const ensureAssignmentStillEditable = useCallback(async () => {
    if (!currentAssignment) return false
    const { data, error } = await supabase
      .from('paper_user_assignments')
      .select('status')
      .eq('id', currentAssignment.id)
      .maybeSingle()

    if (error) throw error
    if (!data || !OPEN_STATUSES.has(data.status)) {
      await refreshQueue()
      showToast('This assignment changed on the server. The queue has been refreshed.', 'error')
      return false
    }
    return true
  }, [currentAssignment, refreshQueue, showToast])

  const saveAnnotation = useCallback(async (hasData, status) => {
    if (!currentAssignment || !currentPaper) return
    const validFoodItems = hasData
      ? foodItems.filter(isValidFoodItem).map(normalizeFoodItem)
      : []
    const foodItemCount = validFoodItems.length
    const nutrientValueCount = validFoodItems.reduce((sum, item) => sum + (item.nutrients?.length || 0), 0)

    if (hasData && foodItemCount === 0) {
      showToast('Add at least one valid food item before saving.', 'error')
      return
    }

    setSaving(true)
    try {
      if (testMode) {
        appendTestEvent({
          type: 'assignment_save',
          paper_id: currentPaper.id,
          assignment_id: currentAssignment.id,
          user_id: user.id,
          has_data: hasData,
          status,
          food_item_count: foodItemCount,
          nutrient_value_count: nutrientValueCount,
        })
        setAssignments((previous) => previous.map((assignment) => {
          if (assignment.id !== currentAssignment.id) return assignment
          return {
            ...assignment,
            status: status === 'draft' ? 'draft' : 'submitted',
          }
        }))
        const label = status === 'draft' ? 'Draft saved' : 'Stored locally'
        showToast(`${label} (test mode).`)
        return
      }

      const stillEditable = await ensureAssignmentStillEditable()
      if (!stillEditable) return

      const { data: annotation, error: annotationError } = await supabase
        .from('annotations')
        .upsert(
          {
            paper_id: currentPaper.id,
            user_id: user.id,
            paper_user_assignment_id: currentAssignment.id,
            has_data: hasData,
            status,
            updated_at: new Date().toISOString(),
          },
          { onConflict: 'paper_id,user_id' }
        )
        .select()
        .single()

      if (annotationError) throw annotationError

      await supabase
        .from('food_items')
        .delete()
        .eq('annotation_id', annotation.id)

      if (hasData && validFoodItems.length > 0) {
        for (const item of validFoodItems) {
          const { data: insertedItem, error: itemError } = await supabase
            .from('food_items')
            .insert({
              annotation_id: annotation.id,
              food_name: item.food_name,
              food_fdc_id: item.food_fdc_id,
              is_custom_food: item.is_custom_food || false,
            })
            .select()
            .single()

          if (itemError) throw itemError

          if (item.nutrients?.length) {
            const nutrientRows = item.nutrients.map((nutrient) => ({
              food_item_id: insertedItem.id,
              nutrient_id: nutrient.nutrient_id,
              nutrient_name: nutrient.nutrient_name,
              value: nutrient.value,
              unit: nutrient.unit,
            }))
            const { error: nutrientError } = await supabase
              .from('annotation_nutrient_values')
              .insert(nutrientRows)
            if (nutrientError) throw nutrientError
          }
        }
      }

      const decisionKind = hasData ? 'has_data' : 'no_usable_data'
      const { error: labelEventError } = await supabase
        .from('paper_label_events')
        .insert({
          paper_id: currentPaper.id,
          annotation_id: annotation.id,
          paper_user_assignment_id: currentAssignment.id,
          paper_slot_assignment_id: currentAssignment.paper_slot_assignment_id,
          user_id: user.id,
          has_data: hasData,
          status,
          decision_kind: decisionKind,
          food_item_count: foodItemCount,
          nutrient_value_count: nutrientValueCount,
          source: 'ui',
        })
      if (labelEventError) throw labelEventError

      if (status === 'draft') {
        const { error: touchError } = await supabase.rpc('touch_assignment_workspace', {
          p_paper_user_assignment_id: currentAssignment.id,
          p_annotation_id: annotation.id,
          p_status: 'draft',
        })
        if (touchError) throw touchError
        showToast('Draft saved.')
      } else {
        const { error: submitError } = await supabase.rpc('submit_assignment_review', {
          p_paper_user_assignment_id: currentAssignment.id,
          p_annotation_id: annotation.id,
          p_decision_kind: decisionKind,
          p_submission_metadata: {
            source: 'ui',
            status,
          },
        })
        if (submitError) throw submitError
        showToast(status === 'skipped' ? 'No-usable-data submission sent.' : 'Submission sent.')
      }

      await refreshQueue()
      if (reviewerProfile?.cockpit_access) {
        await refreshCockpit()
      }

      if (status !== 'draft') {
        setSelectedAssignmentId((previousId) => nextOpenAssignmentId(sortAssignments(assignments), previousId))
      }
    } catch (error) {
      console.error('Save failed:', error)
      showToast(`Failed to save: ${error.message}`, 'error')
    } finally {
      setSaving(false)
    }
  }, [
    assignments,
    currentAssignment,
    currentPaper,
    foodItems,
    refreshCockpit,
    refreshQueue,
    reviewerProfile?.cockpit_access,
    showToast,
    testMode,
    user.id,
    ensureAssignmentStillEditable,
  ])

  const handleGlobalNoData = useCallback(async () => {
    if (!currentAssignment || !currentPaper || !isEditable) return
    const confirmed = typeof window !== 'undefined'
      ? window.confirm('Mark this paper as definitely no data for everyone? This will cancel the other assignments for this paper.')
      : false
    if (!confirmed) return

    const reason = typeof window !== 'undefined'
      ? window.prompt('Reason for definitely no data (required):', '')
      : ''
    if (!reason || !reason.trim()) {
      showToast('Definitely-no-data cancelled: reason required.', 'error')
      return
    }

    setSaving(true)
    try {
      if (testMode) {
        appendTestEvent({
          type: 'global_no_data',
          assignment_id: currentAssignment.id,
          paper_id: currentPaper.id,
          user_id: user.id,
          reason: reason.trim(),
        })
        setAssignments((previous) => previous.map((assignment) => (
          assignment.paper_id === currentPaper.id
            ? {
                ...assignment,
                status: 'cancelled',
                outcome: {
                  ...(assignment.outcome || {}),
                  paper_id: assignment.paper_id,
                  decision_kind: 'no_usable_data',
                  resolution_source: 'global_skip',
                },
              }
            : assignment
        )))
        setSelectedAssignmentId((previousId) => nextOpenAssignmentId(sortAssignments(assignments), previousId))
        showToast('Definitely-no-data recorded locally (test mode).')
        return
      }

      const stillEditable = await ensureAssignmentStillEditable()
      if (!stillEditable) return

      const { error } = await supabase.rpc('mark_assignment_global_no_data', {
        p_paper_user_assignment_id: currentAssignment.id,
        p_reason: reason.trim(),
      })
      if (error) throw error

      await refreshQueue()
      if (reviewerProfile?.cockpit_access) {
        await refreshCockpit()
      }
      setSelectedAssignmentId((previousId) => nextOpenAssignmentId(sortAssignments(assignments), previousId))
      showToast('Paper marked as definitely no data.')
    } catch (error) {
      console.error('Global no-data failed:', error)
      showToast(`Failed to mark definitely no data: ${error.message}`, 'error')
    } finally {
      setSaving(false)
    }
  }, [
    assignments,
    currentAssignment,
    currentPaper,
    ensureAssignmentStillEditable,
    isEditable,
    refreshCockpit,
    refreshQueue,
    reviewerProfile?.cockpit_access,
    showToast,
    testMode,
    user.id,
  ])

  const updateFoodItem = (index, updatedItem) => {
    if (!isEditable) return
    setFoodItems((items) => items.map((item, itemIndex) => (itemIndex === index ? updatedItem : item)))
  }

  const removeFoodItem = (index) => {
    if (!isEditable) return
    setFoodItems((items) => {
      const nextItems = items.filter((_, itemIndex) => itemIndex !== index)
      return nextItems.length > 0 ? nextItems : [createEmptyFoodItem()]
    })
  }

  const addFoodItem = () => {
    if (!isEditable) return
    setFoodItems((items) => [...items, createEmptyFoodItem()])
  }
  const handlePdfNutrientAdd = (nutrientEntry) => {
    if (!isEditable) return
    setFoodItems((items) => {
      if (!items.length) return [{ ...createEmptyFoodItem(), nutrients: [nutrientEntry] }]
      const targetIndex = items.length - 1
      return items.map((item, index) => {
        if (index !== targetIndex) return item
        if (nutrientEntry.nutrient_id && item.nutrients.some((nutrient) => nutrient.nutrient_id === nutrientEntry.nutrient_id)) {
          return item
        }
        return {
          ...item,
          nutrients: [...item.nutrients, nutrientEntry],
        }
      })
    })
  }

  const handleResolveConflict = useCallback(async (conflict, submissionId) => {
    if (!conflict || !submissionId) return
    if (testMode) {
      appendTestEvent({
        type: 'resolve_conflict',
        conflict_id: conflict.id,
        submission_id: submissionId,
      })
      showToast('Conflict resolution stored locally (test mode).')
      return
    }
    setSaving(true)
    try {
      const { error } = await supabase.rpc('resolve_paper_conflict', {
        p_conflict_id: conflict.id,
        p_winning_submission_id: submissionId,
        p_resolution_note: resolutionNote || null,
      })
      if (error) throw error
      setResolutionNote('')
      await refreshQueue()
      await refreshCockpit()
      showToast('Conflict resolved.')
    } catch (error) {
      console.error('Conflict resolution failed:', error)
      showToast(`Failed to resolve conflict: ${error.message}`, 'error')
    } finally {
      setSaving(false)
    }
  }, [refreshCockpit, refreshQueue, resolutionNote, showToast, testMode])

  const reviewerById = buildReviewerMap(cockpitData.reviewerProfiles)
  const papersById = buildPaperMap(cockpitData.papers)
  const submissionsById = Object.fromEntries((cockpitData.submissions || []).map((row) => [row.id, row]))

  if (loadingQueue && !assignments.length) {
    return (
      <div className="login-page">
        <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>Loading queue...</div>
      </div>
    )
  }

  return (
    <div className="app-layout">
      <div className="top-bar">
        <div className="top-bar-left">
          <span className="app-name">OpenNutri</span>
          {testMode && <span className="test-mode-pill">TEST MODE</span>}
          {isDeveloperTrainingMode && <span className="status-badge status-draft">DEV TRAINING</span>}
          {reviewerProfile?.official_slot && (
            <span className="status-badge status-pending">{reviewerProfile.official_slot}</span>
          )}
        </div>

        <div className="top-bar-center view-tabs">
          <button className={`nav-btn ${activeView === 'queue' ? 'nav-btn-active' : ''}`} onClick={() => setActiveView('queue')}>
            My Queue
          </button>
          {reviewerProfile?.cockpit_access && (
            <>
              <button className={`nav-btn ${activeView === 'all-papers' ? 'nav-btn-active' : ''}`} onClick={() => setActiveView('all-papers')}>
                All Papers
              </button>
              <button className={`nav-btn ${activeView === 'cockpit' ? 'nav-btn-active' : ''}`} onClick={() => setActiveView('cockpit')}>
                Cockpit
              </button>
              <button className={`nav-btn ${activeView === 'conflicts' ? 'nav-btn-active' : ''}`} onClick={() => setActiveView('conflicts')}>
                Conflicts
              </button>
              <button className={`nav-btn ${activeView === 'suggestions' ? 'nav-btn-active' : ''}`} onClick={() => setActiveView('suggestions')}>
                Suggestions
              </button>
            </>
          )}
        </div>

        <div className="top-bar-right">
          {activeView === 'queue' && (
            <div className="progress-pill">
              <span className="count">{queueStats.open}</span> open
              <div className="progress-bar-mini">
                <div
                  className="fill"
                  style={{ width: assignments.length ? `${(queueStats.final / assignments.length) * 100}%` : '0%' }}
                />
              </div>
            </div>
          )}
          <button className="suggestion-btn" onClick={() => setShowSuggestion(true)} title="Send a suggestion">💡</button>
          <button className={`test-mode-toggle ${testMode ? 'active' : ''}`} onClick={handleToggleTestMode}>
            Test Mode
          </button>
          <button className="theme-toggle" onClick={toggleTheme} title="Toggle light/dark mode">
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
          <span className="user-name">{reviewerProfile?.display_name || user.email}</span>
          <button className="btn btn-outline" onClick={onLogout}>Logout</button>
        </div>
      </div>

      {profileError && (
        <div className="profile-warning">
          Reviewer profile sync failed: {profileError}
        </div>
      )}

      {activeView === 'queue' && (
        <QueueView
          assignments={assignments}
          currentAssignment={currentAssignment}
          currentPaperIndex={currentPaperIndex}
          pdfUrl={pdfUrl}
          theme={theme}
          allNutrients={allNutrients}
          foodItems={foodItems}
          allFoods={allFoods}
          foodsLoaded={foodsLoaded}
          user={user}
          queueStats={queueStats}
          isEditable={isEditable}
          saving={saving}
          showPaperList={showPaperList}
          setShowPaperList={setShowPaperList}
          paperListRef={paperListRef}
          setSelectedAssignmentId={setSelectedAssignmentId}
          addFoodItem={addFoodItem}
          removeFoodItem={removeFoodItem}
          updateFoodItem={updateFoodItem}
          handlePdfNutrientAdd={handlePdfNutrientAdd}
          handleGlobalNoData={handleGlobalNoData}
          saveAnnotation={saveAnnotation}
          getStatusBadgeClass={getStatusBadgeClass}
          formatStatusLabel={formatStatusLabel}
          formatDecisionLabel={formatDecisionLabel}
        />
      )}

      {activeView === 'all-papers' && (
        <AllPapersView
          cockpitData={cockpitData}
          onRefresh={refreshCockpit}
        />
      )}

      {activeView === 'cockpit' && (
        <CockpitView
          cockpitData={cockpitData}
          onRefresh={refreshCockpit}
          reviewerDrafts={reviewerDrafts}
          newReviewerDraft={newReviewerDraft}
          savingReviewerTarget={savingReviewerTarget}
          routingConfigDrafts={routingConfigDrafts}
          savingRoutingStageKey={savingRoutingStageKey}
          onChangeDraft={updateReviewerDraft}
          onToggleDraftShadowSlot={toggleReviewerDraftShadowSlot}
          onSaveDraft={saveReviewerDraft}
          onResetDraft={resetReviewerDraft}
          onChangeNewDraft={updateNewReviewerDraft}
          onToggleNewShadowSlot={toggleNewReviewerShadowSlot}
          onCreateReviewer={createReviewer}
          onResetNewReviewer={resetNewReviewerDraft}
          onChangeRoutingConfig={updateRoutingConfigDraft}
          onSaveRoutingConfig={saveRoutingConfigDraft}
        />
      )}

      {activeView === 'conflicts' && (
        <ConflictsView
          conflicts={cockpitData.conflicts || []}
          selectedConflictId={selectedConflictId}
          setSelectedConflictId={setSelectedConflictId}
          papersById={papersById}
          submissionsById={submissionsById}
          reviewerById={reviewerById}
          resolutionNote={resolutionNote}
          setResolutionNote={setResolutionNote}
          onResolve={handleResolveConflict}
          allNutrients={allNutrients}
          theme={theme}
        />
      )}

      {activeView === 'suggestions' && reviewerProfile?.cockpit_access && (
        <SuggestionsReviewView
          suggestionItems={cockpitData.suggestionReviewItems || []}
          onRefresh={refreshCockpit}
          onSaveReview={saveSuggestionReview}
          savingSuggestionId={savingSuggestionId}
        />
      )}

      {loadingCockpit && reviewerProfile?.cockpit_access && (
        <div className="floating-loading">Refreshing cockpit…</div>
      )}

      {toast && <div className={`toast toast-${toast.type}`}>{toast.message}</div>}

      {showSuggestion && (
        <SuggestionModal
          user={user}
          reviewerProfile={reviewerProfile}
          onClose={() => setShowSuggestion(false)}
          testMode={testMode}
          persistInTestMode={isDeveloperTrainingMode}
        />
      )}
    </div>
  )
}
