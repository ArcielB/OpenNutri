import { supabase } from '../supabaseClient'

export const SUPPORTED_WORKFLOW_LANGUAGES = ['en', 'tr']
export const SUGGESTION_REVIEW_STATUSES = ['new', 'triaged', 'planned', 'dismissed', 'done']
export const DEFAULT_PIPELINE_FILTERS = {
  range: 'all',
  startAt: '',
  endAt: '',
}
export const PIPELINE_RANGE_OPTIONS = [
  { value: 'all', label: 'All time' },
  { value: 'today_utc', label: 'Today' },
  { value: 'last_24h', label: '24 hours' },
  { value: 'last_7d', label: '7 days' },
  { value: 'last_30d', label: '30 days' },
  { value: 'custom', label: 'Custom' },
]

export const EMPTY_COCKPIT_DATA = {
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

export function toNumber(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

export function formatCount(value) {
  return toNumber(value).toLocaleString()
}

export function formatPercent(numerator, denominator) {
  const total = toNumber(denominator)
  if (total <= 0) return '0%'
  return `${Math.round((toNumber(numerator) / total) * 100)}%`
}

export function getTodayUtcStartIso() {
  const now = new Date()
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate())).toISOString()
}

export function getPipelineFilterWindow(filters) {
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

export function buildPipelineRpcParams(filters) {
  const window = getPipelineFilterWindow(filters)
  return {
    p_start_at: window.startAt,
    p_end_at: window.endAt,
    p_workflow_language: null,
    p_paper_id: null,
  }
}

export function getPipelineStage(snapshot, stageKey) {
  return (snapshot?.stages || []).find((stage) => stage.stage_key === stageKey) || {}
}

export function buildPipelineSteps(snapshot) {
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
  const uploadAccepted = Math.max(toNumber(crawler.batch_accepted), toNumber(papers.uploaded), toNumber(gemma.entered))
  const gemmaRejected = toNumber(gemma.rejected) + toNumber(gemma.provisional_skips) + toNumber(gemma.failed)
  const geminiRejected = toNumber(gemini.rejected) + toNumber(gemini.provisional_skips) + toNumber(gemini.failed)
  const geminiEntered = toNumber(gemini.entered)
  const gemmaKept = Math.max(toNumber(gemma.accepted), geminiEntered)

  return [
    {
      key: 'search',
      label: 'Found by search',
      count: searchEntered,
      rejectedHere: 0,
      note: 'Papers found by the crawler.',
    },
    {
      key: 'filter',
      label: 'Passed first filter',
      count: searchPassed,
      rejectedHere: searchRejected,
      note: 'Still looks like food composition.',
    },
    {
      key: 'upload',
      label: 'PDF saved',
      count: uploadAccepted,
      rejectedHere: Math.max(0, uploadEntered - uploadAccepted),
      note: 'The paper PDF was downloaded and stored.',
    },
    {
      key: 'gemma-start',
      label: 'Sent to Gemma',
      count: toNumber(gemma.entered),
      rejectedHere: Math.max(0, uploadAccepted - toNumber(gemma.entered)),
      note: 'Gemma checks many papers cheaply.',
    },
    {
      key: 'gemma-useful',
      label: 'Gemma kept',
      count: gemmaKept,
      rejectedHere: gemmaRejected,
      note: 'Gemma found possible usable data.',
    },
    {
      key: 'gemini-start',
      label: 'Sent to Gemini',
      count: geminiEntered,
      rejectedHere: Math.max(0, gemmaKept - geminiEntered),
      note: 'Only the best candidates use Gemini.',
    },
    {
      key: 'gemini-useful',
      label: 'Sent to humans',
      count: toNumber(gemini.passed_next),
      rejectedHere: geminiRejected,
      note: 'Gemini produced usable rows.',
    },
    {
      key: 'human',
      label: 'Accepted by humans',
      count: toNumber(human.outcomes_has_data),
      rejectedHere: toNumber(human.outcomes_no_data),
      note: 'Final approved useful papers.',
    },
  ]
}

export function parseUnitFromDescription(desc) {
  if (!desc) return 'G'
  const match = desc.match(/^Unit:\s*(\S+)/)
  return match ? match[1].replace(/\.$/, '') : 'G'
}

export function createEmptyFoodItem() {
  return {
    food_name: '',
    food_fdc_id: null,
    is_custom_food: false,
    raw_food_name: null,
    preparation_state: null,
    nutrients: [],
  }
}

export function isValidFoodItem(item) {
  return Boolean((item?.food_name || '').trim() || item?.food_fdc_id)
}

export function normalizeMetadata(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

export function normalizeOptionalInteger(value) {
  if (value === undefined || value === null || value === '') return null
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) ? parsed : null
}

export function normalizeOptionalNumber(value) {
  if (value === undefined || value === null || value === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

export function normalizeFoodItem(item) {
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

export function buildFoodItemsFromPayload(payload) {
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

export function getPublicPdfUrl(filename) {
  if (!filename) return null
  return supabase.storage.from('papers').getPublicUrl(filename).data.publicUrl
}

export function formatDecisionLabel(decisionKind) {
  if (decisionKind === 'has_data') return 'Usable Data'
  if (decisionKind === 'no_usable_data') return 'No Usable Data'
  return 'Unknown'
}

export function formatStatusLabel(status) {
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

export function formatRoutingStatusLabel(status) {
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

export function formatRouteDestinationLabel(destination) {
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

export function formatDate(value) {
  return value ? new Date(value).toLocaleString() : '-'
}

export function getStatusBadgeClass(status) {
  if (status === 'draft') return 'status-draft'
  if (status === 'accepted' || status === 'done') return 'status-done'
  if (status === 'superseded' || status === 'skipped') return 'status-skipped'
  if (status === 'pending_approval') return 'status-conflict'
  return 'status-pending'
}

export function getAiDecisionKind(extraction) {
  if (extraction?.normalized_payload_json?.decision_kind) return extraction.normalized_payload_json.decision_kind
  return extraction?.is_useful ? 'has_data' : 'no_usable_data'
}

export function shouldShowPaperInUsefulOverview({ paper, outcome, latestAiExtraction }) {
  if (outcome?.decision_kind === 'has_data') return true
  if (outcome?.decision_kind === 'no_usable_data') return false
  if (paper?.routing_status === 'ai_provisional_no_usable_data') return false
  if (paper?.route_destination === 'provisional_skip') return false
  if (!latestAiExtraction) return false
  return getAiDecisionKind(latestAiExtraction) === 'has_data'
}

export function getPayloadRowCount(payload) {
  const foods = Array.isArray(payload?.food_items) ? payload.food_items : []
  return foods.reduce((sum, food) => sum + (Array.isArray(food?.nutrients) ? food.nutrients.length : 0), 0)
}

export function getNormalizationSummary(extraction) {
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

export function getAiPrefillStats(extraction) {
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

export function buildLatestAiExtractionMaps(rows) {
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

export function buildPaperMap(rows) {
  return Object.fromEntries((rows || []).map((row) => [row.id, row]))
}

export function buildReviewerMap(rows) {
  return Object.fromEntries((rows || []).map((row) => [row.id, row]))
}

export function groupRowsByPaperId(rows) {
  return (rows || []).reduce((accumulator, row) => {
    if (!row?.paper_id) return accumulator
    if (!accumulator[row.paper_id]) accumulator[row.paper_id] = []
    accumulator[row.paper_id].push(row)
    return accumulator
  }, {})
}

export function normalizeSuggestionAttachments(rawValue) {
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

export function formatBytesLabel(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function countCorrectionItems(diff) {
  if (!diff || typeof diff !== 'object') return 0
  return (
    (diff.decision_changed ? 1 : 0) +
    (Array.isArray(diff.missing_foods) ? diff.missing_foods.length : 0) +
    (Array.isArray(diff.added_foods) ? diff.added_foods.length : 0) +
    (Array.isArray(diff.missing_nutrient_rows) ? diff.missing_nutrient_rows.length : 0) +
    (Array.isArray(diff.added_nutrient_rows) ? diff.added_nutrient_rows.length : 0)
  )
}

export function buildGeneralHelpContext({ item, paper, reviewerProfile, foodItems, initializedFromAiExtractionId }) {
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
