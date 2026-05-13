import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { supabase } from '../supabaseClient'
import PdfViewer from '../components/PdfViewer'
import FoodItemForm from '../components/FoodItemForm'
import SuggestionModal from '../components/SuggestionModal'
import { appendTestEvent, isTestModeEnabled, setTestModeEnabled } from '../utils/testMode'

const SUPPORTED_WORKFLOW_LANGUAGES = ['en', 'tr']
const SUGGESTION_REVIEW_STATUSES = ['new', 'triaged', 'planned', 'dismissed', 'done']
const DEFAULT_PIPELINE_FILTERS = {
  range: 'today_utc',
  startAt: '',
  endAt: '',
  language: 'all',
  paperId: '',
}
const PIPELINE_RANGE_OPTIONS = [
  { value: 'today_utc', label: 'Today UTC' },
  { value: 'last_24h', label: 'Last 24h' },
  { value: 'last_7d', label: 'Last 7d' },
  { value: 'last_30d', label: 'Last 30d' },
  { value: 'all', label: 'All time' },
  { value: 'custom', label: 'Custom' },
]

const EMPTY_COCKPIT_DATA = {
  reviewerProfiles: [],
  slotMembers: [],
  papers: [],
  aiExtractions: [],
  routingStageConfigs: [],
  searchHits: [],
  suggestionReviewItems: [],
  labelSubmissions: [],
  labelApprovals: [],
  outcomes: [],
}

function toNumber(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function formatCount(value) {
  return toNumber(value).toLocaleString()
}

function formatPercent(numerator, denominator) {
  const total = toNumber(denominator)
  if (total <= 0) return '0%'
  return `${Math.round((toNumber(numerator) / total) * 100)}%`
}

function formatDuration(seconds) {
  const value = toNumber(seconds)
  if (value <= 0) return '-'
  if (value < 60) return `${value.toFixed(value < 10 ? 1 : 0)}s`
  const minutes = Math.floor(value / 60)
  const remainingSeconds = Math.round(value % 60)
  return `${minutes}m ${remainingSeconds}s`
}

function getTodayUtcStartIso() {
  const now = new Date()
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate())).toISOString()
}

function getPipelineFilterWindow(filters) {
  const now = Date.now()
  if (filters.range === 'all') return { startAt: null, endAt: null }
  if (filters.range === 'last_24h') return { startAt: new Date(now - 24 * 60 * 60 * 1000).toISOString(), endAt: null }
  if (filters.range === 'last_7d') return { startAt: new Date(now - 7 * 24 * 60 * 60 * 1000).toISOString(), endAt: null }
  if (filters.range === 'last_30d') return { startAt: new Date(now - 30 * 24 * 60 * 60 * 1000).toISOString(), endAt: null }
  if (filters.range === 'custom') {
    const startAt = filters.startAt ? new Date(filters.startAt).toISOString() : null
    const endAt = filters.endAt ? new Date(filters.endAt).toISOString() : null
    return { startAt, endAt }
  }
  return { startAt: getTodayUtcStartIso(), endAt: null }
}

function buildPipelineRpcParams(filters) {
  const window = getPipelineFilterWindow(filters)
  const paperId = String(filters.paperId || '').trim()
  const parsedPaperId = paperId ? Number.parseInt(paperId, 10) : null
  return {
    p_start_at: window.startAt,
    p_end_at: window.endAt,
    p_workflow_language: filters.language === 'all' ? null : filters.language,
    p_paper_id: Number.isFinite(parsedPaperId) ? parsedPaperId : null,
  }
}

function getPipelineStage(snapshot, stageKey) {
  return (snapshot?.stages || []).find((stage) => stage.stage_key === stageKey) || {}
}

function buildPipelineSteps(snapshot) {
  const crawler = snapshot?.crawler || {}
  const papers = snapshot?.papers || {}
  const human = snapshot?.human_review || {}
  const gemma = getPipelineStage(snapshot, 'gemma_proof_extraction_v1')
  const gemini = getPipelineStage(snapshot, 'gemini_flash_db_payload_v2')
  const hasBatchCounts = toNumber(crawler.batch_results) > 0
  const searchEntered = hasBatchCounts ? toNumber(crawler.batch_results) : toNumber(crawler.search_hits)
  const searchPassed = hasBatchCounts ? toNumber(crawler.batch_filter_passed) : toNumber(crawler.metadata_passed)
  const searchRejected = hasBatchCounts
    ? toNumber(crawler.batch_search_gate_rejected) + toNumber(crawler.batch_metadata_rejected) + toNumber(crawler.batch_duplicates)
    : toNumber(crawler.search_gate_rejected) + toNumber(crawler.metadata_rejected) + toNumber(crawler.duplicates)
  const uploadEntered = searchPassed
  const uploadAccepted = hasBatchCounts ? toNumber(crawler.batch_accepted) : toNumber(papers.uploaded)
  const uploadRejected = (
    toNumber(crawler.batch_pdf_fetch_fail) +
    toNumber(crawler.batch_pdf_validation_fail) +
    toNumber(crawler.batch_skipped_seen)
  )

  return [
    {
      key: 'search',
      label: 'Crawler Search',
      caption: 'Metadata found by Europe PMC, OpenAlex, Semantic Scholar, or enabled sources.',
      entered: searchEntered,
      accepted: searchPassed,
      rejected: searchRejected,
      passedNext: searchPassed,
      pending: toNumber(crawler.search_hits) - toNumber(crawler.linked_to_paper),
    },
    {
      key: 'upload',
      label: 'PDF Acquisition',
      caption: 'Candidates that survived metadata filtering and became uploaded paper rows.',
      entered: uploadEntered,
      accepted: uploadAccepted,
      rejected: uploadRejected,
      passedNext: uploadAccepted,
      pending: Math.max(0, uploadEntered - uploadAccepted - uploadRejected),
    },
    {
      key: 'gemma',
      label: 'Gemma Screening',
      caption: 'Broad proof extraction. Has-data papers are ranked and passed to Gemini.',
      entered: toNumber(gemma.entered),
      accepted: toNumber(gemma.accepted),
      rejected: toNumber(gemma.rejected) + toNumber(gemma.provisional_skips),
      passedNext: toNumber(gemma.passed_next),
      pending: toNumber(gemma.queued) + toNumber(gemma.processing),
      failed: toNumber(gemma.failed),
    },
    {
      key: 'gemini',
      label: 'Gemini Extraction',
      caption: 'Scarce extraction pass. Useful normalized payloads enter the human queue.',
      entered: toNumber(gemini.entered),
      accepted: toNumber(gemini.accepted),
      rejected: toNumber(gemini.rejected) + toNumber(gemini.provisional_skips),
      passedNext: toNumber(gemini.passed_next),
      pending: toNumber(gemini.queued) + toNumber(gemini.processing),
      failed: toNumber(gemini.failed),
    },
    {
      key: 'human',
      label: 'Human Review',
      caption: 'Gemini-positive papers reviewed by labelers and accepted by the approver.',
      entered: toNumber(human.ready_current) + toNumber(human.submitted),
      accepted: toNumber(human.approved_has_data),
      rejected: toNumber(human.approved_no_data),
      passedNext: toNumber(human.outcomes),
      pending: toNumber(human.ready_current) + toNumber(human.pending_approval_current),
    },
  ]
}

function buildPipelineTraceRows(trace) {
  if (!trace?.paper) return []
  const rows = []
  for (const hit of trace.search_hits || []) {
    rows.push({
      at: hit.discovered_at,
      step: 'Crawler Search',
      status: hit.filter_pass ? 'Accepted' : hit.search_gate_pass ? 'Scored' : 'Rejected',
      detail: `${hit.source || 'source'} · ${hit.template_id || 'template'} · score ${hit.filter_score ?? hit.search_gate_score ?? '-'}`,
    })
  }
  for (const task of trace.stage_tasks || []) {
    rows.push({
      at: task.completed_at || task.updated_at || task.created_at,
      step: task.stage_key,
      status: formatStatusLabel(task.status),
      detail: `attempts ${task.attempt_count ?? 0}${task.last_error ? ` · ${String(task.last_error).slice(0, 160)}` : ''}`,
    })
  }
  for (const extraction of trace.ai_extractions || []) {
    rows.push({
      at: extraction.created_at,
      step: extraction.stage_key,
      status: formatDecisionLabel(extraction.decision_kind),
      detail: `${formatRouteDestinationLabel(extraction.route_destination)} · rows ${extraction.accepted_row_count || 0}/${toNumber(extraction.accepted_row_count) + toNumber(extraction.rejected_row_count)}`,
    })
  }
  for (const submission of trace.label_submissions || []) {
    rows.push({
      at: submission.reviewed_at || submission.submitted_at,
      step: 'Human Submission',
      status: formatStatusLabel(submission.status),
      detail: `${formatDecisionLabel(submission.decision_kind)} · ${submission.food_count || 0} foods`,
    })
  }
  for (const approval of trace.label_approvals || []) {
    rows.push({
      at: approval.approved_at,
      step: 'Approval',
      status: formatDecisionLabel(approval.decision_kind),
      detail: `${approval.food_count || 0} foods`,
    })
  }
  for (const outcome of trace.review_outcomes || []) {
    rows.push({
      at: outcome.resolved_at,
      step: 'Final Outcome',
      status: formatDecisionLabel(outcome.decision_kind),
      detail: outcome.resolution_source || '-',
    })
  }
  return rows.sort((left, right) => new Date(left.at || 0).getTime() - new Date(right.at || 0).getTime())
}

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
    raw_food_name: null,
    preparation_state: null,
    nutrients: [],
  }
}

function isValidFoodItem(item) {
  return Boolean((item?.food_name || '').trim() || item?.food_fdc_id)
}

function normalizeMetadata(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function normalizeOptionalInteger(value) {
  if (value === undefined || value === null || value === '') return null
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) ? parsed : null
}

function normalizeOptionalNumber(value) {
  if (value === undefined || value === null || value === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function normalizeFoodItem(item) {
  return {
    food_name: (item?.food_name || '').trim(),
    food_fdc_id: item?.food_fdc_id || null,
    is_custom_food: Boolean(item?.is_custom_food || !item?.food_fdc_id),
    raw_food_name: (item?.raw_food_name || '').trim() || null,
    preparation_state: (item?.preparation_state || '').trim() || null,
    nutrients: (item?.nutrients || [])
      .filter((nutrient) => (
        (nutrient?.nutrient_name || nutrient?.nutrient_id) &&
        nutrient?.value !== undefined &&
        nutrient?.value !== null &&
        nutrient?.unit
      ))
      .map((nutrient) => ({
        nutrient_id: nutrient.nutrient_id || null,
        is_custom_nutrient: Boolean(nutrient.is_custom_nutrient || !nutrient.nutrient_id),
        nutrient_name: (nutrient.nutrient_name || '').trim(),
        raw_nutrient_name: (nutrient.raw_nutrient_name || '').trim() || null,
        value: Number(nutrient.value),
        unit: nutrient.unit,
        basis: String(nutrient.basis || 'per_100g').trim(),
        sample_size: normalizeOptionalInteger(nutrient.sample_size),
        confidence: normalizeOptionalNumber(nutrient.confidence),
        source_citation: (nutrient.source_citation || '').trim() || null,
        metadata: normalizeMetadata(nutrient.metadata),
      })),
  }
}

function buildFoodItemsFromPayload(payload) {
  if (payload?.decision_kind !== 'has_data') return []
  const foodItems = Array.isArray(payload?.food_items) ? payload.food_items : []
  return foodItems
    .map((item) => normalizeFoodItem({
      food_name: item?.food_name || '',
      food_fdc_id: item?.food_fdc_id || null,
      is_custom_food: Boolean(item?.is_custom_food || !item?.food_fdc_id),
      raw_food_name: item?.raw_food_name || null,
      preparation_state: item?.preparation_state || null,
      nutrients: Array.isArray(item?.nutrients) ? item.nutrients : [],
    }))
    .filter(isValidFoodItem)
}

function getPublicPdfUrl(filename) {
  if (!filename) return null
  return supabase.storage.from('papers').getPublicUrl(filename).data.publicUrl
}

function formatDecisionLabel(decisionKind) {
  if (decisionKind === 'has_data') return 'Usable Data'
  if (decisionKind === 'no_usable_data') return 'No Usable Data'
  return 'Unknown'
}

function formatStatusLabel(status) {
  switch (status) {
    case 'draft':
      return 'Draft'
    case 'pending_approval':
      return 'Pending Approval'
    case 'accepted':
      return 'Accepted'
    case 'superseded':
      return 'Superseded'
    case 'done':
      return 'Done'
    case 'skipped':
      return 'Skipped'
    default:
      return status || 'Available'
  }
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
    case 'ai_provisional_no_usable_data':
      return 'AI Provisional: No Data'
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
    case 'next_stage':
      return 'Next Stage'
    case 'provisional_skip':
      return 'Skipped'
    default:
      return destination || 'Pending'
  }
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString() : '-'
}

function getStatusBadgeClass(status) {
  if (status === 'draft') return 'status-draft'
  if (status === 'accepted' || status === 'done') return 'status-done'
  if (status === 'superseded' || status === 'skipped') return 'status-skipped'
  if (status === 'pending_approval') return 'status-conflict'
  return 'status-pending'
}

function getAiDecisionKind(extraction) {
  if (extraction?.normalized_payload_json?.decision_kind) return extraction.normalized_payload_json.decision_kind
  return extraction?.is_useful ? 'has_data' : 'no_usable_data'
}

function shouldShowPaperInUsefulOverview({ paper, outcome, latestAiExtraction }) {
  if (outcome?.decision_kind === 'has_data') return true
  if (outcome?.decision_kind === 'no_usable_data') return false
  if (paper?.routing_status === 'ai_provisional_no_usable_data') return false
  if (paper?.route_destination === 'provisional_skip') return false
  if (!latestAiExtraction) return false
  return getAiDecisionKind(latestAiExtraction) === 'has_data'
}

function getPayloadRowCount(payload) {
  const foods = Array.isArray(payload?.food_items) ? payload.food_items : []
  return foods.reduce((sum, food) => sum + (Array.isArray(food?.nutrients) ? food.nutrients.length : 0), 0)
}

function getNormalizationSummary(extraction) {
  const rawSummary = extraction?.raw_data?.normalization_summary || {}
  const payload = extraction?.normalized_payload_json || {}
  const accepted = Number(rawSummary.accepted_row_count ?? getPayloadRowCount(payload)) || 0
  const input = Number(rawSummary.input_row_count ?? accepted) || 0
  return {
    accepted_row_count: accepted,
    rejected_row_count: Number(rawSummary.rejected_row_count ?? Math.max(0, input - accepted)) || 0,
    input_row_count: input,
    rejection_reasons: rawSummary.rejection_reasons || {},
  }
}

function getAiPrefillStats(extraction) {
  const payload = extraction?.normalized_payload_json || {}
  const foods = Array.isArray(payload?.food_items) ? payload.food_items : []
  const nutrients = foods.flatMap((food) => Array.isArray(food?.nutrients) ? food.nutrients : [])
  const summary = getNormalizationSummary(extraction)
  return {
    decision_kind: payload.decision_kind || getAiDecisionKind(extraction),
    accepted_row_count: summary.accepted_row_count,
    rejected_row_count: summary.rejected_row_count,
    matched_food_count: foods.filter((food) => food?.food_fdc_id && !food?.is_custom_food).length,
    custom_food_count: foods.filter((food) => !food?.food_fdc_id || food?.is_custom_food).length,
    matched_nutrient_count: nutrients.filter((nutrient) => nutrient?.nutrient_id && !nutrient?.is_custom_nutrient).length,
    custom_nutrient_count: nutrients.filter((nutrient) => !nutrient?.nutrient_id || nutrient?.is_custom_nutrient).length,
  }
}

function buildLatestAiExtractionMaps(rows) {
  const byId = {}
  const byPaperId = {}
  for (const row of rows || []) {
    if (row?.id) byId[row.id] = row
    if (!row?.paper_id) continue
    const existing = byPaperId[row.paper_id]
    if (!existing || new Date(row.created_at || 0).getTime() > new Date(existing.created_at || 0).getTime()) {
      byPaperId[row.paper_id] = row
    }
  }
  return { byId, byPaperId }
}

function buildPaperMap(rows) {
  return Object.fromEntries((rows || []).map((row) => [row.id, row]))
}

function buildReviewerMap(rows) {
  return Object.fromEntries((rows || []).map((row) => [row.id, row]))
}

function groupRowsByPaperId(rows) {
  return (rows || []).reduce((accumulator, row) => {
    if (!row?.paper_id) return accumulator
    if (!accumulator[row.paper_id]) accumulator[row.paper_id] = []
    accumulator[row.paper_id].push(row)
    return accumulator
  }, {})
}

function normalizeSuggestionAttachments(rawValue) {
  if (!Array.isArray(rawValue)) return []
  return rawValue
    .map((row) => {
      if (!row || typeof row !== 'object') return null
      const bucket = String(row.bucket || 'suggestion-attachments').trim()
      const path = String(row.path || row.storage_path || '').trim() || null
      const directUrl = String(row.url || row.public_url || '').trim() || null
      const fileName = String(row.file_name || row.name || path || 'attachment').trim()
      const fileSize = Number(row.file_size || row.size || 0) || 0
      const mimeType = String(row.mime_type || row.type || '').trim() || null
      if (!path && !directUrl) return null
      return { bucket, path, directUrl, fileName, fileSize, mimeType }
    })
    .filter(Boolean)
}

function formatBytesLabel(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function SuggestionAttachmentsCell({ rowKey, attachments }) {
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

function countCorrectionItems(diff) {
  if (!diff || typeof diff !== 'object') return 0
  return (
    (diff.decision_changed ? 1 : 0) +
    (Array.isArray(diff.missing_foods) ? diff.missing_foods.length : 0) +
    (Array.isArray(diff.added_foods) ? diff.added_foods.length : 0) +
    (Array.isArray(diff.missing_nutrient_rows) ? diff.missing_nutrient_rows.length : 0) +
    (Array.isArray(diff.added_nutrient_rows) ? diff.added_nutrient_rows.length : 0)
  )
}

function buildGeneralHelpContext({ item, paper, reviewerProfile, foodItems, initializedFromAiExtractionId }) {
  return {
    request_kind: 'general_queue_help_request',
    paper_id: paper?.id || item?.paper_id || null,
    paper_title: paper?.title || null,
    paper_filename: paper?.filename || null,
    paper_doi: paper?.doi || null,
    workflow_language: item?.workflow_language || paper?.workflow_language || null,
    reviewer_profile_id: reviewerProfile?.id || null,
    reviewer_email: reviewerProfile?.email || null,
    reviewer_name: reviewerProfile?.display_name || null,
    latest_ai_extraction_id: item?.latest_ai_extraction?.id || null,
    initialized_from_ai_extraction_id: initializedFromAiExtractionId || null,
    draft_food_items: (foodItems || []).filter(isValidFoodItem).map(normalizeFoodItem),
  }
}

function AiPrefillStatus({ extraction, initializedExtractionId }) {
  if (!extraction) return null
  const stats = getAiPrefillStats(extraction)
  const initialized = Boolean(initializedExtractionId && initializedExtractionId === extraction.id)

  return (
    <div className="ai-prefill-status">
      <span className={`status-badge ${initialized ? 'status-done' : 'status-pending'}`}>
        {initialized ? 'AI Loaded' : 'AI Available'}
      </span>
      <span className={`status-badge ${stats.decision_kind === 'has_data' ? 'status-done' : 'status-skipped'}`}>
        {formatDecisionLabel(stats.decision_kind)}
      </span>
      <span className="status-badge status-pending">{stats.accepted_row_count} rows</span>
      <span className="status-badge status-done">{stats.matched_food_count} DB foods</span>
      <span className="status-badge status-draft">{stats.custom_food_count} custom foods</span>
      <span className="status-badge status-done">{stats.matched_nutrient_count} DB nutrients</span>
      <span className="status-badge status-draft">{stats.custom_nutrient_count} custom nutrients</span>
      {stats.rejected_row_count > 0 && (
        <span className="status-badge status-skipped">{stats.rejected_row_count} rejected</span>
      )}
    </div>
  )
}

function PayloadSummary({ submission, reviewer, title = null }) {
  const payload = submission?.payload_json || {}
  const foodItems = Array.isArray(payload?.food_items) ? payload.food_items : []

  return (
    <div className="payload-card">
      <div className="payload-card-header">
        <div>
          <h3>{title || reviewer?.display_name || reviewer?.email || 'Unknown Labeler'}</h3>
          <p>{formatDecisionLabel(submission?.decision_kind)}</p>
        </div>
      </div>
      <div className="payload-meta">
        <span className={`status-badge ${getStatusBadgeClass(submission?.status)}`}>{formatStatusLabel(submission?.status)}</span>
        <span className="status-badge status-pending">{formatDate(submission?.submitted_at)}</span>
        <span className="status-badge status-draft">{foodItems.length} foods</span>
      </div>
      <div className="payload-scroll">
        {foodItems.length === 0 ? (
          <div className="empty-panel">No extracted foods stored in this submission.</div>
        ) : foodItems.map((foodItem, index) => (
          <div key={`${submission?.id || 'payload'}-${index}`} className="payload-food-block">
            <div className="payload-food-title">
              {foodItem.food_name || 'Unnamed food'}
              {foodItem.food_fdc_id && <span className="payload-food-id">{foodItem.food_fdc_id}</span>}
            </div>
            <div className="payload-nutrients">
              {(foodItem.nutrients || []).length === 0 ? (
                <span className="payload-empty-line">No nutrient rows.</span>
              ) : (foodItem.nutrients || []).map((nutrient, nutrientIndex) => (
                <div key={`${index}-${nutrientIndex}`} className="payload-nutrient-row">
                  <span>{nutrient.nutrient_name || 'Unnamed nutrient'}</span>
                  <span>{nutrient.value ?? '-'} {nutrient.unit || ''}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function HelpRequestModal({ note, setNote, onClose, onSubmit, saving }) {
  return (
    <div className="modal-backdrop">
      <form
        className="help-modal"
        onSubmit={(event) => {
          event.preventDefault()
          onSubmit()
        }}
      >
        <h2>Ask for Help</h2>
        <p>This sends the paper to Arciel with your current draft context.</p>
        <textarea
          value={note}
          placeholder="What is confusing?"
          onChange={(event) => setNote(event.target.value)}
          disabled={saving}
          autoFocus
        />
        <div className="modal-actions">
          <button type="button" className="btn btn-outline" onClick={onClose} disabled={saving}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={saving || !note.trim()} style={{ width: 'auto' }}>
            {saving ? 'Sending...' : 'Send Help Request'}
          </button>
        </div>
      </form>
    </div>
  )
}

function QueueView({
  items,
  currentItem,
  currentIndex,
  pdfUrl,
  theme,
  allNutrients,
  allFoods,
  foodsLoaded,
  user,
  foodItems,
  isEditable,
  saving,
  showPaperList,
  setShowPaperList,
  paperListRef,
  setSelectedQueueId,
  addFoodItem,
  removeFoodItem,
  updateFoodItem,
  handlePdfNutrientAdd,
  handleRequestHelp,
  saveAnnotation,
  aiPrefillExtractionId,
}) {
  return (
    <div className="workspace">
      <PdfViewer pdfUrl={pdfUrl} allNutrients={allNutrients} onAddNutrient={handlePdfNutrientAdd} theme={theme} />

      <div className="annotation-panel">
        <div className="queue-assignment-header">
          {currentItem ? (
            <div className="queue-assignment-toolbar">
              <div className="queue-toolbar-group">
                <div className="paper-list-toggle" ref={paperListRef}>
                  <button className="nav-btn" onClick={() => setShowPaperList((open) => !open)}>
                    {currentIndex >= 0 ? `Paper ${currentIndex + 1}/${items.length}` : 'Queue'} ▾
                  </button>
                  {showPaperList && (
                    <div className="paper-list-dropdown">
                      {items.map((item, index) => (
                        <div
                          key={item.id}
                          className={`paper-list-item ${item.id === currentItem.id ? 'active' : ''}`}
                          onClick={() => {
                            setSelectedQueueId(item.id)
                            setShowPaperList(false)
                          }}
                        >
                          <span className="paper-id">{index + 1}</span>
                          <span className="paper-title">{item.paper?.title || item.paper?.filename || `Paper ${item.paper_id}`}</span>
                          <span className={`status-badge ${getStatusBadgeClass(item.status)}`}>{formatStatusLabel(item.status)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div className="queue-mini-stats">
                  <span className={`status-badge ${getStatusBadgeClass(currentItem.status)}`}>
                    {formatStatusLabel(currentItem.status)}
                  </span>
                  <span className="status-badge status-pending">{items.length} available</span>
                  {currentItem.workflow_language && (
                    <span className="status-badge status-draft">{currentItem.workflow_language.toUpperCase()}</span>
                  )}
                </div>
              </div>
              <div className="queue-nav-buttons">
                <button
                  className="nav-btn"
                  disabled={currentIndex <= 0}
                  onClick={() => setSelectedQueueId(items[Math.max(currentIndex - 1, 0)]?.id || null)}
                >
                  Prev
                </button>
                <button
                  className="nav-btn"
                  disabled={currentIndex < 0 || currentIndex >= items.length - 1}
                  onClick={() => setSelectedQueueId(items[Math.min(currentIndex + 1, items.length - 1)]?.id || null)}
                >
                  Next
                </button>
              </div>
            </div>
          ) : (
            <div className="empty-panel">No papers are currently available in the general queue.</div>
          )}
        </div>

        <div className="annotation-scroll">
          {!currentItem ? (
            <div className="empty-panel">The queue is empty.</div>
          ) : (
            <>
              {!isEditable && (
                <div className="review-lock-banner">
                  This account is read-only for live labeling.
                </div>
              )}
              <AiPrefillStatus extraction={currentItem.latest_ai_extraction} initializedExtractionId={aiPrefillExtractionId} />
              {foodItems.map((item, index) => (
                <FoodItemForm
                  key={`${currentItem.id}-${index}`}
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
                <button className="add-food-btn" onClick={addFoodItem}>+ Add Another Food Item</button>
              )}
            </>
          )}
        </div>

        <div className="annotation-actions">
          <div className="action-row">
            <button className="btn btn-outline" onClick={handleRequestHelp} disabled={saving || !isEditable}>Ask for Help</button>
            <button className="btn btn-skip" onClick={() => saveAnnotation(false, 'skipped')} disabled={saving || !isEditable}>
              No Usable Data
            </button>
            <button className="btn btn-outline" onClick={() => saveAnnotation(true, 'draft')} disabled={saving || !isEditable}>
              Save Draft
            </button>
          </div>
          <div className="action-row">
            <button className="btn btn-success" onClick={() => saveAnnotation(true, 'done')} disabled={saving || !isEditable}>
              {saving ? 'Saving...' : 'Submit Final Extraction'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function ApprovalView({
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

      <PdfViewer pdfUrl={pdfUrl} allNutrients={allNutrients} onAddNutrient={handleApprovalPdfNutrientAdd} theme={theme} />

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
                          <button className="add-food-btn" onClick={addApprovalFoodItem}>+ Add Another Food Item</button>
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

function DashboardView({ cockpitData, reviewerById, paperById, onRefresh }) {
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

function AiDetailPanel({ extraction }) {
  const payload = extraction?.normalized_payload_json || { decision_kind: getAiDecisionKind(extraction), food_items: [] }
  const stats = getAiPrefillStats(extraction)
  const summary = getNormalizationSummary(extraction)
  const foodItems = Array.isArray(payload?.food_items) ? payload.food_items : []
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
          <span className={`status-badge ${stats.decision_kind === 'has_data' ? 'status-done' : 'status-skipped'}`}>
            {formatDecisionLabel(stats.decision_kind)}
          </span>
          <span className={`status-badge ${extraction?.audit_sampled ? 'status-draft' : 'status-pending'}`}>
            {extraction?.audit_sampled ? 'AUDIT' : 'LIVE'}
          </span>
        </div>
      </div>

      <div className="ai-detail-grid">
        <div className="ai-detail-metric">
          <span>Confidence</span>
          <strong>{extraction?.overall_confidence == null ? '-' : Number(extraction.overall_confidence).toFixed(3)}</strong>
        </div>
        <div className="ai-detail-metric">
          <span>Rows</span>
          <strong>{summary.accepted_row_count}/{summary.input_row_count}</strong>
        </div>
        <div className="ai-detail-metric">
          <span>DB Foods</span>
          <strong>{stats.matched_food_count}</strong>
        </div>
        <div className="ai-detail-metric">
          <span>Custom Foods</span>
          <strong>{stats.custom_food_count}</strong>
        </div>
        <div className="ai-detail-metric">
          <span>DB Nutrients</span>
          <strong>{stats.matched_nutrient_count}</strong>
        </div>
        <div className="ai-detail-metric">
          <span>Custom Nutrients</span>
          <strong>{stats.custom_nutrient_count}</strong>
        </div>
        <div className="ai-detail-metric">
          <span>Rejected</span>
          <strong>{summary.rejected_row_count}</strong>
        </div>
        <div className="ai-detail-metric">
          <span>Destination</span>
          <strong>{formatRouteDestinationLabel(extraction?.route_destination)}</strong>
        </div>
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

      <div className="ai-detail-section">
        <div className="ai-detail-section-title">DB-Compliant Extracted Rows</div>
        <div className="payload-scroll">
          {foodItems.length === 0 ? (
            <div className="empty-panel">No food rows are present in the normalized AI payload.</div>
          ) : foodItems.map((foodItem, index) => (
            <div key={`${extraction?.id || 'ai'}-${index}`} className="payload-food-block">
              <div className="payload-food-title">
                {foodItem.food_name || 'Unnamed food'}
                {foodItem.food_fdc_id && <span className="payload-food-id">{foodItem.food_fdc_id}</span>}
                {foodItem.is_custom_food && <span className="status-badge status-draft">Custom</span>}
              </div>
              <div className="payload-nutrients">
                {(foodItem.nutrients || []).length === 0 ? (
                  <span className="payload-empty-line">No nutrient rows.</span>
                ) : (foodItem.nutrients || []).map((nutrient, nutrientIndex) => (
                  <div key={`${index}-${nutrientIndex}`} className="payload-nutrient-row">
                    <span>
                      {nutrient.nutrient_name || 'Unnamed nutrient'}
                      {nutrient.nutrient_id && <span className="payload-food-id"> {nutrient.nutrient_id}</span>}
                    </span>
                    <span>{nutrient.value ?? '-'} {nutrient.unit || ''}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="ai-detail-section">
        <div className="ai-detail-section-title">Normalized DB Payload</div>
        <pre className="ai-json-block">{JSON.stringify(payload, null, 2)}</pre>
      </div>
    </div>
  )
}

function AllPapersView({ cockpitData, reviewerById, onRefresh }) {
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

function PipelineOpsView({
  snapshot,
  filters,
  onFilterChange,
  loading,
  error,
  onRefresh,
  autoRefresh,
  setAutoRefresh,
}) {
  const steps = useMemo(() => buildPipelineSteps(snapshot), [snapshot])
  const gemma = getPipelineStage(snapshot, 'gemma_proof_extraction_v1')
  const gemini = getPipelineStage(snapshot, 'gemini_flash_db_payload_v2')
  const papers = snapshot?.papers || {}
  const human = snapshot?.human_review || {}
  const trace = snapshot?.paper_trace || null
  const traceRows = useMemo(() => buildPipelineTraceRows(trace), [trace])

  const handleFilterChange = (field, value) => {
    onFilterChange((previous) => ({ ...previous, [field]: value }))
  }

  return (
    <div className="dashboard-page pipeline-page">
      <div className="dashboard-header pipeline-header">
        <div>
          <h2>Pipeline Ops</h2>
          <p>Crawler, AI routing, Gemini extraction, and human-review movement in one operational view.</p>
        </div>
        <div className="pipeline-header-actions">
          <label className="pipeline-auto-toggle">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(event) => setAutoRefresh(event.target.checked)}
            />
            Auto refresh
          </label>
          <button className="btn btn-outline" onClick={onRefresh} disabled={loading}>
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      <div className="pipeline-filter-bar">
        <label>
          Window
          <select value={filters.range} onChange={(event) => handleFilterChange('range', event.target.value)}>
            {PIPELINE_RANGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label>
          Start
          <input
            type="datetime-local"
            value={filters.startAt}
            disabled={filters.range !== 'custom'}
            onChange={(event) => handleFilterChange('startAt', event.target.value)}
          />
        </label>
        <label>
          End
          <input
            type="datetime-local"
            value={filters.endAt}
            disabled={filters.range !== 'custom'}
            onChange={(event) => handleFilterChange('endAt', event.target.value)}
          />
        </label>
        <label>
          Language
          <select value={filters.language} onChange={(event) => handleFilterChange('language', event.target.value)}>
            <option value="all">All</option>
            <option value="en">English</option>
            <option value="tr">Turkish</option>
          </select>
        </label>
        <label>
          Paper ID
          <input
            type="number"
            min="1"
            inputMode="numeric"
            placeholder="optional"
            value={filters.paperId}
            onChange={(event) => handleFilterChange('paperId', event.target.value)}
          />
        </label>
      </div>

      {error && <div className="profile-warning pipeline-error">Pipeline snapshot failed: {error}</div>}

      <div className="dashboard-grid dashboard-grid-summary pipeline-summary-grid">
        <div className="dashboard-card">
          <div className="dashboard-card-label">Uploaded In Window</div>
          <div className="dashboard-card-value">{formatCount(papers.uploaded)}</div>
        </div>
        <div className="dashboard-card">
          <div className="dashboard-card-label">Gemma Queue Now</div>
          <div className="dashboard-card-value">{formatCount(gemma.queued)}</div>
        </div>
        <div className="dashboard-card">
          <div className="dashboard-card-label">Gemini Queue Now</div>
          <div className="dashboard-card-value">{formatCount(gemini.queued)}</div>
        </div>
        <div className="dashboard-card">
          <div className="dashboard-card-label">Human Ready Now</div>
          <div className="dashboard-card-value">{formatCount(human.ready_current)}</div>
        </div>
      </div>

      <div className="pipeline-flow">
        {steps.map((step, index) => {
          const denominator = step.entered || step.accepted + step.rejected + step.pending
          const passPercent = denominator > 0 ? Math.min(100, Math.round((step.passedNext / denominator) * 100)) : 0
          return (
            <div className="pipeline-step" key={step.key}>
              <div className="pipeline-step-topline">
                <span className="pipeline-step-index">{index + 1}</span>
                <div>
                  <h3>{step.label}</h3>
                  <p>{step.caption}</p>
                </div>
              </div>
              <div className="pipeline-pass-number">
                <strong>{formatCount(step.passedNext)}</strong>
                <span>passed onward</span>
              </div>
              <div className="pipeline-progress-bar">
                <span style={{ width: `${passPercent}%` }} />
              </div>
              <div className="pipeline-step-stats">
                <span><strong>{formatCount(step.entered)}</strong> entered</span>
                <span><strong>{formatCount(step.accepted)}</strong> accepted</span>
                <span><strong>{formatCount(step.rejected)}</strong> rejected</span>
                <span><strong>{formatCount(step.pending)}</strong> pending</span>
                {!!step.failed && <span><strong>{formatCount(step.failed)}</strong> failed</span>}
              </div>
            </div>
          )
        })}
      </div>

      <div className="dashboard-grid dashboard-grid-main pipeline-main-grid">
        <div className="dashboard-card dashboard-card-table">
          <div className="dashboard-card-title">AI Stage Detail</div>
          <div className="table-scroll">
            <table className="dashboard-table pipeline-stage-table">
              <thead>
                <tr>
                  <th>Stage</th>
                  <th>Current</th>
                  <th>Window</th>
                  <th>Decision</th>
                  <th>Timing</th>
                </tr>
              </thead>
              <tbody>
                {(snapshot?.stages || []).length === 0 ? (
                  <tr><td colSpan="5">No AI stage data loaded.</td></tr>
                ) : (snapshot?.stages || []).map((stage) => (
                  <tr key={stage.stage_key}>
                    <td className="table-title-cell">
                      <div className="table-primary-line">{stage.display_name || stage.stage_key}</div>
                      <div className="table-secondary-line">{stage.model_name || '-'} · {stage.prompt_version || '-'}</div>
                    </td>
                    <td>
                      <div className="table-cell-stack">
                        <span>{formatCount(stage.queued)} queued</span>
                        <span>{formatCount(stage.processing)} processing</span>
                      </div>
                    </td>
                    <td>
                      <div className="table-cell-stack">
                        <span>{formatCount(stage.entered)} entered</span>
                        <span>{formatCount(stage.completed)} completed</span>
                        <span>{formatCount(stage.failed)} failed</span>
                      </div>
                    </td>
                    <td>
                      <div className="table-cell-stack">
                        <span>{formatCount(stage.accepted)} accepted</span>
                        <span>{formatCount(stage.rejected)} rejected</span>
                        <span>{formatCount(stage.passed_next)} passed next</span>
                      </div>
                    </td>
                    <td>
                      <div className="table-cell-stack">
                        <span>{formatDuration(stage.avg_seconds)} average</span>
                        <span className="table-secondary-line">last {formatDate(stage.last_completed_at)}</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="dashboard-card">
          <div className="dashboard-card-title">Current Paper Routing</div>
          <div className="pipeline-routing-list">
            {(snapshot?.routing_status || []).map((row) => (
              <div className="pipeline-routing-row" key={row.routing_status}>
                <span>{formatRoutingStatusLabel(row.routing_status === 'unset' ? null : row.routing_status)}</span>
                <strong>{formatCount(row.count)}</strong>
              </div>
            ))}
          </div>
          <div className="pipeline-routing-footer">
            <span>Approved outcomes in window</span>
            <strong>{formatCount(human.outcomes)} total</strong>
            <span>{formatCount(human.outcomes_has_data)} usable · {formatCount(human.outcomes_no_data)} no data</span>
          </div>
        </div>
      </div>

      <div className="dashboard-card dashboard-card-table">
        <div className="dashboard-card-title">Recent AI Task Errors</div>
        <div className="table-scroll">
          <table className="dashboard-table">
            <thead>
              <tr>
                <th>Paper</th>
                <th>Stage</th>
                <th>Status</th>
                <th>Updated</th>
                <th>Error</th>
              </tr>
            </thead>
            <tbody>
              {(snapshot?.recent_errors || []).length === 0 ? (
                <tr><td colSpan="5">No recent AI task errors in this filter window.</td></tr>
              ) : (snapshot?.recent_errors || []).map((row, index) => (
                <tr key={`${row.paper_id}-${row.stage_key}-${index}`}>
                  <td className="table-title-cell">
                    <div className="table-primary-line">{row.title || `Paper ${row.paper_id}`}</div>
                    <div className="table-secondary-line">Paper {row.paper_id}</div>
                  </td>
                  <td>{row.stage_key}</td>
                  <td>{formatStatusLabel(row.status)} · attempts {row.attempt_count ?? 0}</td>
                  <td>{formatDate(row.updated_at)}</td>
                  <td className="pipeline-error-cell">{row.last_error}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {filters.paperId && (
        <div className="dashboard-card dashboard-card-table pipeline-trace-card">
          <div className="dashboard-card-title">Paper Trace</div>
          {!trace?.paper ? (
            <div className="empty-panel">No paper found for ID {filters.paperId}.</div>
          ) : (
            <>
              <div className="pipeline-trace-heading">
                <div>
                  <div className="table-primary-line">{trace.paper.title || trace.paper.filename || `Paper ${trace.paper.id}`}</div>
                  <div className="table-secondary-line">
                    Paper {trace.paper.id} · {trace.paper.workflow_language?.toUpperCase() || '-'} · {formatRoutingStatusLabel(trace.paper.routing_status)}
                  </div>
                </div>
                <span className="status-badge status-pending">{formatRouteDestinationLabel(trace.paper.route_destination)}</span>
              </div>
              <div className="table-scroll">
                <table className="dashboard-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Step</th>
                      <th>Status</th>
                      <th>Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {traceRows.length === 0 ? (
                      <tr><td colSpan="4">No trace rows for this paper yet.</td></tr>
                    ) : traceRows.map((row, index) => (
                      <tr key={`${row.step}-${row.at}-${index}`}>
                        <td>{formatDate(row.at)}</td>
                        <td>{row.step}</td>
                        <td>{row.status}</td>
                        <td>{row.detail}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      <div className="pipeline-generated-at">
        Snapshot generated {formatDate(snapshot?.generated_at)} · pass rates are {formatPercent(steps.reduce((sum, step) => sum + step.passedNext, 0), steps.reduce((sum, step) => sum + step.entered, 0))} across entered items in this view.
      </div>
    </div>
  )
}

function SuggestionsReviewView({ suggestionItems, onRefresh, onSaveReview, savingSuggestionId }) {
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

function MySuggestionsView({ suggestionItems, loading, onRefresh }) {
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

function ReviewerAdminView({ cockpitData, reviewerDrafts, onChangeDraft, onSaveDraft, savingReviewerTarget }) {
  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <div>
          <h2>Reviewer Admin</h2>
          <p>Manage reviewer access, read-only tester mode, cockpit visibility, and approval authority.</p>
        </div>
      </div>
      <div className="dashboard-card dashboard-card-table">
        <div className="table-scroll">
          <table className="dashboard-table">
            <thead>
              <tr>
                <th>Reviewer</th>
                <th>Languages</th>
                <th>Active</th>
                <th>Tester</th>
                <th>Cockpit</th>
                <th>Can Approve</th>
                <th>Save</th>
              </tr>
            </thead>
            <tbody>
              {(cockpitData.reviewerProfiles || []).map((profile) => {
                const draft = reviewerDrafts[profile.id] || profile
                return (
                  <tr key={profile.id}>
                    <td className="table-title-cell">
                      <div className="table-primary-line">{profile.display_name || profile.email}</div>
                      <div className="table-secondary-line">{profile.email}</div>
                    </td>
                    <td>
                      <div className="reviewer-toggle-row">
                        <label className="reviewer-toggle">
                          <input
                            type="checkbox"
                            checked={Boolean(draft.can_review_en)}
                            onChange={(event) => onChangeDraft(profile.id, 'can_review_en', event.target.checked)}
                          />
                          EN
                        </label>
                        <label className="reviewer-toggle">
                          <input
                            type="checkbox"
                            checked={Boolean(draft.can_review_tr)}
                            onChange={(event) => onChangeDraft(profile.id, 'can_review_tr', event.target.checked)}
                          />
                          TR
                        </label>
                      </div>
                    </td>
                    {['active', 'tester_access', 'cockpit_access', 'can_approve_labels'].map((field) => (
                      <td key={field}>
                        <input
                          type="checkbox"
                          checked={Boolean(draft[field])}
                          onChange={(event) => onChangeDraft(profile.id, field, event.target.checked)}
                        />
                      </td>
                    ))}
                    <td>
                      <button
                        className="btn btn-primary"
                        onClick={() => onSaveDraft(profile.id)}
                        disabled={savingReviewerTarget === profile.id}
                      >
                        {savingReviewerTarget === profile.id ? 'Saving...' : 'Save'}
                      </button>
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

export default function Annotate({ user, onLogout, theme, toggleTheme }) {
  const [reviewerProfile, setReviewerProfile] = useState(null)
  const [profileError, setProfileError] = useState(null)
  const [activeView, setActiveView] = useState('queue')
  const [queueItems, setQueueItems] = useState([])
  const [selectedQueueId, setSelectedQueueId] = useState(null)
  const [foodItems, setFoodItems] = useState([createEmptyFoodItem()])
  const [approvalFoodItems, setApprovalFoodItems] = useState([createEmptyFoodItem()])
  const [approvalDecision, setApprovalDecision] = useState('has_data')
  const [approvalNote, setApprovalNote] = useState('')
  const [selectedApprovalId, setSelectedApprovalId] = useState(null)
  const [allNutrients, setAllNutrients] = useState([])
  const [allFoods, setAllFoods] = useState([])
  const [foodsLoaded, setFoodsLoaded] = useState(false)
  const [aiPrefillSources, setAiPrefillSources] = useState({})
  const [saving, setSaving] = useState(false)
  const [loadingQueue, setLoadingQueue] = useState(true)
  const [loadingCockpit, setLoadingCockpit] = useState(false)
  const [toast, setToast] = useState(null)
  const [showSuggestion, setShowSuggestion] = useState(false)
  const [showHelpRequest, setShowHelpRequest] = useState(false)
  const [helpRequestNote, setHelpRequestNote] = useState('')
  const [testMode, setTestMode] = useState(() => isTestModeEnabled())
  const [showPaperList, setShowPaperList] = useState(false)
  const [cockpitData, setCockpitData] = useState(EMPTY_COCKPIT_DATA)
  const [reviewerDrafts, setReviewerDrafts] = useState({})
  const [savingReviewerTarget, setSavingReviewerTarget] = useState(null)
  const [savingSuggestionId, setSavingSuggestionId] = useState(null)
  const [mySuggestionItems, setMySuggestionItems] = useState([])
  const [loadingMySuggestions, setLoadingMySuggestions] = useState(false)
  const [pipelineFilters, setPipelineFilters] = useState(DEFAULT_PIPELINE_FILTERS)
  const [pipelineSnapshot, setPipelineSnapshot] = useState(null)
  const [pipelineError, setPipelineError] = useState(null)
  const [loadingPipeline, setLoadingPipeline] = useState(false)
  const [pipelineAutoRefresh, setPipelineAutoRefresh] = useState(true)
  const paperListRef = useRef(null)

  const reviewerById = useMemo(() => buildReviewerMap(cockpitData.reviewerProfiles), [cockpitData.reviewerProfiles])
  const paperById = useMemo(() => buildPaperMap(cockpitData.papers), [cockpitData.papers])
  const currentItem = queueItems.find((item) => item.id === selectedQueueId) || null
  const currentPaper = currentItem?.paper || null
  const currentIndex = queueItems.findIndex((item) => item.id === selectedQueueId)
  const currentPdfUrl = getPublicPdfUrl(currentPaper?.filename)
  const isTesterAccount = Boolean(reviewerProfile?.tester_access)
  const canApproveLabels = Boolean(reviewerProfile?.can_approve_labels && !reviewerProfile?.tester_access && !testMode)
  const canSeeCockpit = Boolean(reviewerProfile?.cockpit_access || reviewerProfile?.can_approve_labels)
  const canSubmitSuggestion = Boolean(reviewerProfile && !canSeeCockpit)
  const isEditable = Boolean(currentItem && !isTesterAccount)
  const pendingSubmissions = useMemo(
    () => (cockpitData.labelSubmissions || [])
      .filter((row) => row.status === 'pending_approval')
      .sort((left, right) => new Date(left.submitted_at || 0).getTime() - new Date(right.submitted_at || 0).getTime()),
    [cockpitData.labelSubmissions]
  )
  const selectedSubmission = pendingSubmissions.find((row) => row.id === selectedApprovalId) || pendingSubmissions[0] || null
  const selectedApprovalPaper = selectedSubmission ? paperById[selectedSubmission.paper_id] : null
  const selectedApprovalPdfUrl = getPublicPdfUrl(selectedApprovalPaper?.filename)

  const showToast = useCallback((message, type = 'success') => {
    setToast({ message, type })
    window.clearTimeout(showToast.timer)
    showToast.timer = window.setTimeout(() => setToast(null), 3200)
  }, [])

  const refreshQueue = useCallback(async () => {
    if (!reviewerProfile?.id) {
      setQueueItems([])
      setSelectedQueueId(null)
      setLoadingQueue(false)
      return []
    }

    setLoadingQueue(true)
    try {
      const { data: paperRows, error: paperError } = await supabase.rpc('get_general_queue_papers', { p_limit: 250 })
      if (paperError) throw paperError

      const papers = (paperRows || []).filter((paper) => SUPPORTED_WORKFLOW_LANGUAGES.includes(paper.workflow_language))
      const paperIds = papers.map((paper) => paper.id)
      const [aiResponse, annotationResponse] = await Promise.all([
        paperIds.length
          ? supabase.from('ai_extractions').select('*').in('paper_id', paperIds).order('created_at', { ascending: false })
          : Promise.resolve({ data: [], error: null }),
        paperIds.length
          ? supabase.from('annotations').select('*').eq('user_id', user.id).in('paper_id', paperIds)
          : Promise.resolve({ data: [], error: null }),
      ])
      if (aiResponse.error) throw aiResponse.error
      if (annotationResponse.error) throw annotationResponse.error

      const { byId, byPaperId } = buildLatestAiExtractionMaps(aiResponse.data || [])
      const annotationByPaperId = Object.fromEntries((annotationResponse.data || []).map((row) => [row.paper_id, row]))
      const nextItems = papers.map((paper) => {
        const annotation = annotationByPaperId[paper.id] || null
        return {
          id: `general:${paper.id}`,
          paper_id: paper.id,
          reviewer_profile_id: reviewerProfile.id,
          workflow_language: paper.workflow_language,
          status: annotation?.status === 'draft' ? 'draft' : 'available',
          assigned_at: paper.routing_updated_at || paper.created_at,
          paper,
          annotation,
          latest_ai_extraction: byId[paper.latest_ai_extraction_id] || byPaperId[paper.id] || null,
        }
      })

      setQueueItems(nextItems)
      setSelectedQueueId((previousId) => {
        if (previousId && nextItems.some((item) => item.id === previousId)) return previousId
        return nextItems[0]?.id || null
      })
      return nextItems
    } catch (error) {
      console.error('Queue refresh failed:', error)
      showToast(`Failed to load queue: ${error.message}`, 'error')
      return []
    } finally {
      setLoadingQueue(false)
    }
  }, [reviewerProfile?.id, showToast, user.id])

  const refreshCockpit = useCallback(async () => {
    if (!canSeeCockpit) return
    setLoadingCockpit(true)
    try {
      const [
        profilesResponse,
        slotMembersResponse,
        papersResponse,
        aiExtractionsResponse,
        routingStageConfigsResponse,
        searchHitsResponse,
        suggestionReviewItemsResponse,
        labelSubmissionsResponse,
        labelApprovalsResponse,
        outcomesResponse,
      ] = await Promise.all([
        supabase.from('reviewer_profiles').select('*').order('display_name', { ascending: true }),
        supabase.from('reviewer_slot_members').select('*').order('slot_key', { ascending: true }),
        supabase.from('papers').select('id,title,doi,filename,workflow_language,routing_status,routing_bucket,route_destination,current_stage_key,latest_ai_extraction_id,routing_updated_at,created_at').order('id', { ascending: false }),
        supabase.from('ai_extractions').select('*').order('created_at', { ascending: false }).limit(5000),
        supabase.from('routing_stage_configs').select('*').order('display_name', { ascending: true }),
        supabase.from('paper_search_hits').select('paper_id,source,template_id,source_term,query_phrase,workflow_language'),
        supabase.from('backlog_review_items').select('*').order('created_at', { ascending: false }),
        supabase.from('paper_label_submissions').select('*').order('submitted_at', { ascending: false }),
        supabase.from('paper_label_approvals').select('*').order('approved_at', { ascending: false }),
        supabase.from('paper_review_outcomes').select('*').order('resolved_at', { ascending: false }),
      ])

      for (const response of [
        profilesResponse,
        slotMembersResponse,
        papersResponse,
        aiExtractionsResponse,
        routingStageConfigsResponse,
        searchHitsResponse,
        suggestionReviewItemsResponse,
        labelSubmissionsResponse,
        labelApprovalsResponse,
        outcomesResponse,
      ]) {
        if (response.error) throw response.error
      }

      setCockpitData({
        reviewerProfiles: profilesResponse.data || [],
        slotMembers: slotMembersResponse.data || [],
        papers: papersResponse.data || [],
        aiExtractions: aiExtractionsResponse.data || [],
        routingStageConfigs: routingStageConfigsResponse.data || [],
        searchHits: searchHitsResponse.data || [],
        suggestionReviewItems: suggestionReviewItemsResponse.data || [],
        labelSubmissions: labelSubmissionsResponse.data || [],
        labelApprovals: labelApprovalsResponse.data || [],
        outcomes: outcomesResponse.data || [],
      })
      setSelectedApprovalId((previousId) => {
        const pending = (labelSubmissionsResponse.data || []).filter((row) => row.status === 'pending_approval')
        if (previousId && pending.some((row) => row.id === previousId)) return previousId
        return pending[0]?.id || null
      })
    } catch (error) {
      console.error('Cockpit refresh failed:', error)
      showToast(`Failed to load cockpit: ${error.message}`, 'error')
    } finally {
      setLoadingCockpit(false)
    }
  }, [canSeeCockpit, showToast])

  const refreshPipeline = useCallback(async () => {
    if (!canSeeCockpit) return null
    setLoadingPipeline(true)
    setPipelineError(null)
    try {
      const { data, error } = await supabase.rpc('get_pipeline_ops_snapshot', buildPipelineRpcParams(pipelineFilters))
      if (error) throw error
      setPipelineSnapshot(data || null)
      return data || null
    } catch (error) {
      console.error('Pipeline snapshot refresh failed:', error)
      setPipelineError(error.message)
      return null
    } finally {
      setLoadingPipeline(false)
    }
  }, [canSeeCockpit, pipelineFilters])

  const refreshMySuggestions = useCallback(async () => {
    if (!reviewerProfile?.id || canSeeCockpit) {
      setMySuggestionItems([])
      return
    }
    setLoadingMySuggestions(true)
    try {
      const { data, error } = await supabase
        .from('backlog_review_items')
        .select('*')
        .eq('submitted_by_auth_user_id', user.id)
        .order('created_at', { ascending: false })
      if (error) throw error
      setMySuggestionItems(data || [])
    } catch (error) {
      console.error('My suggestions refresh failed:', error)
      showToast(`Failed to load your suggestions: ${error.message}`, 'error')
    } finally {
      setLoadingMySuggestions(false)
    }
  }, [canSeeCockpit, reviewerProfile?.id, showToast, user.id])

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
          if (!(nextProfile?.cockpit_access || nextProfile?.can_approve_labels)) {
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
    if (canSeeCockpit) refreshCockpit()
    if (!canSeeCockpit) refreshMySuggestions()
  }, [canSeeCockpit, refreshCockpit, refreshMySuggestions, refreshQueue, reviewerProfile])

  useEffect(() => {
    if (!canSeeCockpit || activeView !== 'pipeline') return
    void refreshPipeline()
  }, [activeView, canSeeCockpit, refreshPipeline])

  useEffect(() => {
    if (!canSeeCockpit || activeView !== 'pipeline' || !pipelineAutoRefresh) return undefined
    const intervalId = window.setInterval(() => {
      void refreshPipeline()
    }, 60000)
    return () => window.clearInterval(intervalId)
  }, [activeView, canSeeCockpit, pipelineAutoRefresh, refreshPipeline])

  useEffect(() => {
    if (reviewerProfile && !canSeeCockpit && activeView !== 'queue' && activeView !== 'my-suggestions') {
      setActiveView('queue')
    }
  }, [activeView, canSeeCockpit, reviewerProfile])

  useEffect(() => {
    if (!canSeeCockpit) return
    setReviewerDrafts(Object.fromEntries((cockpitData.reviewerProfiles || []).map((profile) => [profile.id, { ...profile }])))
  }, [canSeeCockpit, cockpitData.reviewerProfiles])

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
    if (!currentItem) {
      setFoodItems([createEmptyFoodItem()])
      return
    }
    let cancelled = false
    async function loadAnnotation() {
      const { data: annotation, error } = await supabase
        .from('annotations')
        .select('*')
        .eq('paper_id', currentItem.paper_id)
        .eq('user_id', user.id)
        .maybeSingle()
      if (error) {
        console.error('Annotation load failed:', error)
        if (!cancelled) setFoodItems([createEmptyFoodItem()])
        return
      }
      if (!annotation) {
        const aiExtractionId = currentItem.latest_ai_extraction?.id || null
        const aiFoodItems = buildFoodItemsFromPayload(currentItem.latest_ai_extraction?.normalized_payload_json)
        if (!cancelled) {
          setFoodItems(aiFoodItems.length > 0 ? aiFoodItems : [createEmptyFoodItem()])
          setAiPrefillSources((previous) => aiExtractionId ? { ...previous, [currentItem.id]: aiExtractionId } : previous)
        }
        return
      }
      if (!annotation.has_data) {
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
      const loaded = await Promise.all((itemRows || []).map(async (itemRow) => {
        const { data: nutrientRows, error: nutrientError } = await supabase
          .from('annotation_nutrient_values')
          .select('*')
          .eq('food_item_id', itemRow.id)
          .order('id', { ascending: true })
        if (nutrientError) console.error('Nutrient row load failed:', nutrientError)
        return {
          food_name: itemRow.food_name,
          food_fdc_id: itemRow.food_fdc_id,
          is_custom_food: itemRow.is_custom_food,
          raw_food_name: itemRow.raw_food_name || null,
          preparation_state: itemRow.preparation_state || null,
          nutrients: (nutrientRows || []).map((row) => ({
            nutrient_id: row.nutrient_id,
            is_custom_nutrient: row.is_custom_nutrient || !row.nutrient_id,
            nutrient_name: row.nutrient_name,
            raw_nutrient_name: row.raw_nutrient_name || null,
            value: row.value,
            unit: row.unit,
            basis: row.basis || 'per_100g',
            sample_size: row.sample_size,
            confidence: row.confidence,
            source_citation: row.source_citation || null,
            metadata: normalizeMetadata(row.metadata),
          })),
        }
      }))
      if (!cancelled) setFoodItems(loaded.length > 0 ? loaded : [createEmptyFoodItem()])
    }
    loadAnnotation()
    return () => {
      cancelled = true
    }
  }, [currentItem, user.id])

  useEffect(() => {
    if (!selectedSubmission) {
      setApprovalFoodItems([createEmptyFoodItem()])
      setApprovalDecision('has_data')
      setApprovalNote('')
      return
    }
    const payloadItems = buildFoodItemsFromPayload(selectedSubmission.payload_json)
    setApprovalFoodItems(payloadItems.length > 0 ? payloadItems : [createEmptyFoodItem()])
    setApprovalDecision(selectedSubmission.decision_kind || 'has_data')
    setApprovalNote('')
  }, [selectedSubmission])

  useEffect(() => {
    function handleClick(event) {
      if (paperListRef.current && !paperListRef.current.contains(event.target)) {
        setShowPaperList(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const saveAnnotationRows = useCallback(async ({ paperId, hasData, status, items }) => {
    const validFoodItems = hasData ? items.filter(isValidFoodItem).map(normalizeFoodItem) : []
    const { data: annotation, error: annotationError } = await supabase
      .from('annotations')
      .upsert(
        {
          paper_id: paperId,
          user_id: user.id,
          has_data: hasData,
          status,
          updated_at: new Date().toISOString(),
        },
        { onConflict: 'paper_id,user_id' }
      )
      .select()
      .single()
    if (annotationError) throw annotationError

    const { error: deleteError } = await supabase.from('food_items').delete().eq('annotation_id', annotation.id)
    if (deleteError) throw deleteError

    for (const item of validFoodItems) {
      const { data: insertedItem, error: itemError } = await supabase
        .from('food_items')
        .insert({
          annotation_id: annotation.id,
          food_name: item.food_name,
          food_fdc_id: item.food_fdc_id,
          is_custom_food: item.is_custom_food || false,
          raw_food_name: item.raw_food_name,
          preparation_state: item.preparation_state,
        })
        .select()
        .single()
      if (itemError) throw itemError

      if (item.nutrients?.length) {
        const nutrientRows = item.nutrients.map((nutrient) => ({
          food_item_id: insertedItem.id,
          nutrient_id: nutrient.nutrient_id,
          is_custom_nutrient: nutrient.is_custom_nutrient || !nutrient.nutrient_id,
          nutrient_name: nutrient.nutrient_name,
          raw_nutrient_name: nutrient.raw_nutrient_name,
          value: nutrient.value,
          unit: nutrient.unit,
          basis: nutrient.basis || 'per_100g',
          sample_size: nutrient.sample_size,
          confidence: nutrient.confidence,
          source_citation: nutrient.source_citation,
          metadata: normalizeMetadata(nutrient.metadata),
        }))
        const { error: nutrientError } = await supabase.from('annotation_nutrient_values').insert(nutrientRows)
        if (nutrientError) throw nutrientError
      }
    }

    return { annotation, validFoodItems }
  }, [user.id])

  const saveAnnotation = useCallback(async (hasData, status) => {
    if (!currentItem || !currentPaper) return
    const validFoodItems = hasData ? foodItems.filter(isValidFoodItem).map(normalizeFoodItem) : []
    const foodItemCount = validFoodItems.length
    const nutrientValueCount = validFoodItems.reduce((sum, item) => sum + (item.nutrients?.length || 0), 0)
    const initializedFromAiExtractionId = aiPrefillSources[currentItem.id] || null

    if (hasData && foodItemCount === 0) {
      showToast('Add at least one valid food item before saving.', 'error')
      return
    }
    if (hasData && status !== 'draft' && nutrientValueCount === 0) {
      showToast('Add at least one nutrient row before final submission.', 'error')
      return
    }

    setSaving(true)
    try {
      if (testMode) {
        appendTestEvent({
          type: 'general_label_save',
          paper_id: currentPaper.id,
          user_id: user.id,
          has_data: hasData,
          status,
          food_item_count: foodItemCount,
          nutrient_value_count: nutrientValueCount,
          initialized_from_ai_extraction_id: initializedFromAiExtractionId,
        })
        showToast(status === 'draft' ? 'Draft stored locally (test mode).' : 'Submission stored locally (test mode).')
        return
      }

      const { annotation } = await saveAnnotationRows({
        paperId: currentPaper.id,
        hasData,
        status,
        items: foodItems,
      })

      const decisionKind = hasData ? 'has_data' : 'no_usable_data'
      const { error: eventError } = await supabase.from('paper_label_events').insert({
        paper_id: currentPaper.id,
        annotation_id: annotation.id,
        user_id: user.id,
        has_data: hasData,
        status,
        decision_kind: decisionKind,
        food_item_count: foodItemCount,
        nutrient_value_count: nutrientValueCount,
        source: 'general_queue_ui',
      })
      if (eventError) throw eventError

      if (status === 'draft') {
        showToast('Draft saved.')
      } else {
        const submissionMetadata = { source: 'general_queue_ui', status }
        if (initializedFromAiExtractionId) submissionMetadata.initialized_from_ai_extraction_id = initializedFromAiExtractionId
        const { error: submitError } = await supabase.rpc('submit_general_label', {
          p_annotation_id: annotation.id,
          p_decision_kind: decisionKind,
          p_submission_metadata: submissionMetadata,
        })
        if (submitError) throw submitError
        showToast(reviewerProfile?.can_approve_labels ? 'Reviewer submission accepted.' : 'Submission sent for approval.')
      }

      await refreshQueue()
      if (canSeeCockpit) await refreshCockpit()
    } catch (error) {
      console.error('Save failed:', error)
      showToast(`Failed to save: ${error.message}`, 'error')
    } finally {
      setSaving(false)
    }
  }, [
    aiPrefillSources,
    canSeeCockpit,
    currentItem,
    currentPaper,
    foodItems,
    refreshCockpit,
    refreshQueue,
    reviewerProfile?.can_approve_labels,
    saveAnnotationRows,
    showToast,
    testMode,
    user.id,
  ])

  const submitHelpRequest = useCallback(async () => {
    if (!currentItem || !currentPaper || !isEditable) return
    const note = helpRequestNote.trim()
    if (!note) {
      showToast('Help request cancelled: note required.', 'error')
      return
    }
    const initializedFromAiExtractionId = aiPrefillSources[currentItem.id] || null
    const context = buildGeneralHelpContext({
      item: currentItem,
      paper: currentPaper,
      reviewerProfile,
      foodItems,
      initializedFromAiExtractionId,
    })
    setSaving(true)
    try {
      if (testMode) {
        appendTestEvent({ type: 'general_queue_help_request', paper_id: currentPaper.id, user_id: user.id, note, context })
        setShowHelpRequest(false)
        setHelpRequestNote('')
        showToast('Help request stored locally (test mode).')
        return
      }
      const { error } = await supabase.from('backlog_review_items').insert({
        item_kind: 'suggestion_review',
        status: 'new',
        submitted_by_auth_user_id: user.id,
        submitted_by_email: user.email || reviewerProfile?.email || null,
        submitted_by_name: reviewerProfile?.display_name || user.email || null,
        suggestion_text: note,
        context,
        attachments: [],
        follow_up_required: true,
      })
      if (error) throw error
      if (canSeeCockpit) await refreshCockpit()
      setShowHelpRequest(false)
      setHelpRequestNote('')
      showToast('Help request sent.')
    } catch (error) {
      console.error('Help request failed:', error)
      showToast(`Failed to send help request: ${error.message}`, 'error')
    } finally {
      setSaving(false)
    }
  }, [
    aiPrefillSources,
    canSeeCockpit,
    currentItem,
    currentPaper,
    foodItems,
    helpRequestNote,
    isEditable,
    refreshCockpit,
    reviewerProfile,
    showToast,
    testMode,
    user.email,
    user.id,
  ])

  const approveSelectedSubmission = useCallback(async () => {
    if (!selectedSubmission || !selectedApprovalPaper || !canApproveLabels) return
    const hasData = approvalDecision === 'has_data'
    const validFoodItems = hasData ? approvalFoodItems.filter(isValidFoodItem).map(normalizeFoodItem) : []
    if (hasData && validFoodItems.length === 0) {
      showToast('Add at least one valid food item before approval.', 'error')
      return
    }
    const approvalNutrientCount = validFoodItems.reduce((sum, item) => sum + (item.nutrients?.length || 0), 0)
    if (hasData && approvalNutrientCount === 0) {
      showToast('Add at least one nutrient row before approval.', 'error')
      return
    }
    setSaving(true)
    try {
      const { annotation } = await saveAnnotationRows({
        paperId: selectedSubmission.paper_id,
        hasData,
        status: hasData ? 'done' : 'skipped',
        items: approvalFoodItems,
      })

      const { error: eventError } = await supabase.from('paper_label_events').insert({
        paper_id: selectedSubmission.paper_id,
        annotation_id: annotation.id,
        user_id: user.id,
        has_data: hasData,
        status: hasData ? 'done' : 'skipped',
        decision_kind: approvalDecision,
        food_item_count: validFoodItems.length,
        nutrient_value_count: approvalNutrientCount,
        source: 'approval_ui',
      })
      if (eventError) throw eventError

      const { error } = await supabase.rpc('approve_label_submission', {
        p_label_submission_id: selectedSubmission.id,
        p_approval_annotation_id: annotation.id,
        p_decision_kind: approvalDecision,
        p_approval_note: approvalNote.trim() || null,
      })
      if (error) throw error
      showToast('Submission approved and final truth saved.')
      await refreshCockpit()
      await refreshQueue()
    } catch (error) {
      console.error('Approval failed:', error)
      showToast(`Failed to approve: ${error.message}`, 'error')
    } finally {
      setSaving(false)
    }
  }, [
    approvalDecision,
    approvalFoodItems,
    approvalNote,
    canApproveLabels,
    refreshCockpit,
    refreshQueue,
    saveAnnotationRows,
    selectedApprovalPaper,
    selectedSubmission,
    showToast,
    user.id,
  ])

  const handleToggleTestMode = useCallback(() => {
    if (reviewerProfile?.tester_access) {
      setTestMode(true)
      setTestModeEnabled(true)
      showToast('Tester accounts are always in test mode.', 'error')
      return
    }
    const next = !testMode
    const message = next
      ? 'Enable test mode? This will disable database writes and store actions locally.'
      : 'Disable test mode? Database writes will resume.'
    if (typeof window !== 'undefined' && !window.confirm(message)) return
    setTestMode(next)
    setTestModeEnabled(next)
    showToast(next ? 'Test mode enabled.' : 'Test mode disabled.')
  }, [reviewerProfile?.tester_access, showToast, testMode])

  const updateReviewerDraft = useCallback((profileId, field, value) => {
    setReviewerDrafts((previous) => ({
      ...previous,
      [profileId]: {
        ...(previous[profileId] || {}),
        [field]: value,
      },
    }))
  }, [])

  const saveReviewerDraft = useCallback(async (profileId) => {
    const draft = reviewerDrafts[profileId]
    if (!draft) return
    const slotMembers = (cockpitData.slotMembers || []).filter((row) => row.reviewer_profile_id === profileId && row.active !== false)
    const shadowSlots = slotMembers.filter((row) => row.member_role === 'shadow').map((row) => row.slot_key).filter(Boolean)
    setSavingReviewerTarget(profileId)
    try {
      if (testMode) {
        appendTestEvent({ type: 'reviewer_admin_save', profile_id: profileId, draft })
        showToast('Reviewer settings stored locally (test mode).')
        return
      }
      const { error } = await supabase.rpc('upsert_reviewer_admin_config', {
        p_email: draft.email,
        p_display_name: draft.display_name,
        p_active: Boolean(draft.active),
        p_can_review_en: Boolean(draft.can_review_en),
        p_can_review_tr: Boolean(draft.can_review_tr),
        p_tester_access: Boolean(draft.tester_access),
        p_official_slot: draft.official_slot || null,
        p_shadow_slots: shadowSlots,
        p_cockpit_access: Boolean(draft.cockpit_access),
        p_can_approve_labels: Boolean(draft.can_approve_labels),
        p_priority_weight_en: Number(draft.priority_weight_en ?? 1) || 1,
        p_priority_weight_tr: Number(draft.priority_weight_tr ?? 1) || 1,
        p_notes: draft.notes || null,
      })
      if (error) throw error
      await refreshCockpit()
      showToast('Reviewer settings saved.')
    } catch (error) {
      console.error('Reviewer save failed:', error)
      showToast(`Failed to save reviewer: ${error.message}`, 'error')
    } finally {
      setSavingReviewerTarget(null)
    }
  }, [cockpitData.slotMembers, refreshCockpit, reviewerDrafts, showToast, testMode])

  const saveSuggestionReview = useCallback(async (itemId, changes) => {
    const payload = {
      ...changes,
      reviewed_by_auth_user_id: user.id,
      reviewed_at: new Date().toISOString(),
    }
    if (testMode) {
      appendTestEvent({ type: 'suggestion_review_update', item_id: itemId, payload })
      showToast('Suggestion review stored locally (test mode).')
      return
    }
    setSavingSuggestionId(itemId)
    try {
      const { error } = await supabase.from('backlog_review_items').update(payload).eq('id', itemId)
      if (error) throw error
      await refreshCockpit()
      showToast('Suggestion review saved.')
    } catch (error) {
      console.error('Suggestion review update failed:', error)
      showToast(`Failed to save suggestion review: ${error.message}`, 'error')
    } finally {
      setSavingSuggestionId(null)
    }
  }, [refreshCockpit, showToast, testMode, user.id])

  const updateFoodItem = (index, updatedItem) => {
    setFoodItems((previous) => previous.map((item, itemIndex) => (itemIndex === index ? updatedItem : item)))
  }
  const removeFoodItem = (index) => {
    setFoodItems((previous) => {
      const next = previous.filter((_, itemIndex) => itemIndex !== index)
      return next.length > 0 ? next : [createEmptyFoodItem()]
    })
  }
  const addFoodItem = () => setFoodItems((previous) => [...previous, createEmptyFoodItem()])
  const handlePdfNutrientAdd = (nutrientEntry) => {
    setFoodItems((previous) => {
      const next = [...previous]
      const target = next[0] || createEmptyFoodItem()
      const nutrients = target.nutrients || []
      if (nutrientEntry.nutrient_id && nutrients.some((row) => row.nutrient_id === nutrientEntry.nutrient_id)) return previous
      next[0] = { ...target, nutrients: [...nutrients, nutrientEntry] }
      return next
    })
  }

  const updateApprovalFoodItem = (index, updatedItem) => {
    if (!canApproveLabels) return
    setApprovalFoodItems((previous) => previous.map((item, itemIndex) => (itemIndex === index ? updatedItem : item)))
  }
  const removeApprovalFoodItem = (index) => {
    if (!canApproveLabels) return
    setApprovalFoodItems((previous) => {
      const next = previous.filter((_, itemIndex) => itemIndex !== index)
      return next.length > 0 ? next : [createEmptyFoodItem()]
    })
  }
  const addApprovalFoodItem = () => {
    if (!canApproveLabels) return
    setApprovalFoodItems((previous) => [...previous, createEmptyFoodItem()])
  }
  const handleApprovalPdfNutrientAdd = (nutrientEntry) => {
    if (!canApproveLabels) return
    setApprovalFoodItems((previous) => {
      const next = [...previous]
      const target = next[0] || createEmptyFoodItem()
      const nutrients = target.nutrients || []
      if (nutrientEntry.nutrient_id && nutrients.some((row) => row.nutrient_id === nutrientEntry.nutrient_id)) return previous
      next[0] = { ...target, nutrients: [...nutrients, nutrientEntry] }
      return next
    })
  }

  if (loadingQueue && !queueItems.length) {
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
          {reviewerProfile?.can_approve_labels && <span className="status-badge status-done">APPROVER</span>}
        </div>

        <div className="top-bar-center view-tabs">
          <button className={`nav-btn ${activeView === 'queue' ? 'nav-btn-active' : ''}`} onClick={() => setActiveView('queue')}>Queue</button>
          {!canSeeCockpit && (
            <button className={`nav-btn ${activeView === 'my-suggestions' ? 'nav-btn-active' : ''}`} onClick={() => setActiveView('my-suggestions')}>My Suggestions</button>
          )}
          {canSeeCockpit && (
            <>
              <button className={`nav-btn ${activeView === 'approval' ? 'nav-btn-active' : ''}`} onClick={() => setActiveView('approval')}>Approval</button>
              <button className={`nav-btn ${activeView === 'dashboard' ? 'nav-btn-active' : ''}`} onClick={() => setActiveView('dashboard')}>Dashboard</button>
              <button className={`nav-btn ${activeView === 'pipeline' ? 'nav-btn-active' : ''}`} onClick={() => setActiveView('pipeline')}>Pipeline</button>
              <button className={`nav-btn ${activeView === 'all-papers' ? 'nav-btn-active' : ''}`} onClick={() => setActiveView('all-papers')}>Useful Papers</button>
              <button className={`nav-btn ${activeView === 'reviewers' ? 'nav-btn-active' : ''}`} onClick={() => setActiveView('reviewers')}>Reviewers</button>
              <button className={`nav-btn ${activeView === 'suggestions' ? 'nav-btn-active' : ''}`} onClick={() => setActiveView('suggestions')}>Suggestions</button>
            </>
          )}
        </div>

        <div className="top-bar-right">
          {activeView === 'queue' && (
            <div className="progress-pill">
              <span className="count">{queueItems.length}</span> available
            </div>
          )}
          {activeView === 'approval' && (
            <div className="progress-pill">
              <span className="count">{pendingSubmissions.length}</span> pending
            </div>
          )}
          {activeView === 'pipeline' && (
            <div className="progress-pill">
              <span className="count">{formatCount(pipelineSnapshot?.human_review?.ready_current)}</span> human ready
            </div>
          )}
          {canSubmitSuggestion && (
            <button className="suggestion-btn" onClick={() => setShowSuggestion(true)} title="Send a suggestion">💡</button>
          )}
          <button className={`test-mode-toggle ${testMode ? 'active' : ''}`} onClick={handleToggleTestMode}>Test Mode</button>
          <button className="theme-toggle" onClick={toggleTheme} title="Toggle light/dark mode">
            {theme === 'dark' ? 'Light' : 'Dark'}
          </button>
          <span className="user-name">{reviewerProfile?.display_name || user.email}</span>
          <button className="btn btn-outline" onClick={onLogout}>Logout</button>
        </div>
      </div>

      {profileError && <div className="profile-warning">Reviewer profile sync failed: {profileError}</div>}

      {activeView === 'queue' && (
        <QueueView
          items={queueItems}
          currentItem={currentItem}
          currentIndex={currentIndex}
          pdfUrl={currentPdfUrl}
          theme={theme}
          allNutrients={allNutrients}
          foodItems={foodItems}
          allFoods={allFoods}
          foodsLoaded={foodsLoaded}
          user={user}
          isEditable={isEditable}
          saving={saving}
          showPaperList={showPaperList}
          setShowPaperList={setShowPaperList}
          paperListRef={paperListRef}
          setSelectedQueueId={setSelectedQueueId}
          addFoodItem={addFoodItem}
          removeFoodItem={removeFoodItem}
          updateFoodItem={updateFoodItem}
          handlePdfNutrientAdd={handlePdfNutrientAdd}
          handleRequestHelp={() => {
            setHelpRequestNote('')
            setShowHelpRequest(true)
          }}
          saveAnnotation={saveAnnotation}
          aiPrefillExtractionId={currentItem ? aiPrefillSources[currentItem.id] : null}
        />
      )}

      {activeView === 'approval' && canSeeCockpit && (
        <ApprovalView
          pendingSubmissions={pendingSubmissions}
          selectedSubmission={selectedSubmission}
          selectedPaper={selectedApprovalPaper}
          reviewerById={reviewerById}
          pdfUrl={selectedApprovalPdfUrl}
          theme={theme}
          allNutrients={allNutrients}
          allFoods={allFoods}
          foodsLoaded={foodsLoaded}
          user={user}
          approvalFoodItems={approvalFoodItems}
          approvalDecision={approvalDecision}
          setApprovalDecision={setApprovalDecision}
          approvalNote={approvalNote}
          setApprovalNote={setApprovalNote}
          canApprove={canApproveLabels}
          saving={saving}
          setSelectedApprovalId={setSelectedApprovalId}
          addApprovalFoodItem={addApprovalFoodItem}
          removeApprovalFoodItem={removeApprovalFoodItem}
          updateApprovalFoodItem={updateApprovalFoodItem}
          handleApprovalPdfNutrientAdd={handleApprovalPdfNutrientAdd}
          approveSelectedSubmission={approveSelectedSubmission}
        />
      )}

      {activeView === 'dashboard' && canSeeCockpit && (
        <DashboardView cockpitData={cockpitData} reviewerById={reviewerById} paperById={paperById} onRefresh={refreshCockpit} />
      )}

      {activeView === 'pipeline' && canSeeCockpit && (
        <PipelineOpsView
          snapshot={pipelineSnapshot}
          filters={pipelineFilters}
          onFilterChange={setPipelineFilters}
          loading={loadingPipeline}
          error={pipelineError}
          onRefresh={refreshPipeline}
          autoRefresh={pipelineAutoRefresh}
          setAutoRefresh={setPipelineAutoRefresh}
        />
      )}

      {activeView === 'all-papers' && canSeeCockpit && (
        <AllPapersView cockpitData={cockpitData} reviewerById={reviewerById} onRefresh={refreshCockpit} />
      )}

      {activeView === 'reviewers' && canSeeCockpit && (
        <ReviewerAdminView
          cockpitData={cockpitData}
          reviewerDrafts={reviewerDrafts}
          onChangeDraft={updateReviewerDraft}
          onSaveDraft={saveReviewerDraft}
          savingReviewerTarget={savingReviewerTarget}
        />
      )}

      {activeView === 'suggestions' && canSeeCockpit && (
        <SuggestionsReviewView
          suggestionItems={cockpitData.suggestionReviewItems || []}
          onRefresh={refreshCockpit}
          onSaveReview={saveSuggestionReview}
          savingSuggestionId={savingSuggestionId}
        />
      )}
      {activeView === 'my-suggestions' && !canSeeCockpit && (
        <MySuggestionsView
          suggestionItems={mySuggestionItems}
          loading={loadingMySuggestions}
          onRefresh={refreshMySuggestions}
        />
      )}

      {loadingCockpit && canSeeCockpit && <div className="floating-loading">Refreshing cockpit...</div>}
      {toast && <div className={`toast toast-${toast.type}`}>{toast.message}</div>}

      {showSuggestion && (
        <SuggestionModal
          user={user}
          reviewerProfile={reviewerProfile}
          onClose={() => setShowSuggestion(false)}
          testMode={testMode}
          onSubmitted={() => {
            setShowSuggestion(false)
            if (canSeeCockpit) refreshCockpit()
            if (!canSeeCockpit) refreshMySuggestions()
          }}
        />
      )}

      {showHelpRequest && (
        <HelpRequestModal
          note={helpRequestNote}
          setNote={setHelpRequestNote}
          onClose={() => setShowHelpRequest(false)}
          onSubmit={submitHelpRequest}
          saving={saving}
        />
      )}
    </div>
  )
}
