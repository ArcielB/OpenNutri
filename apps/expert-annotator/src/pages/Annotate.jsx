import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { supabase } from '../supabaseClient'
import SuggestionModal from '../components/SuggestionModal'
import ThemeIcon from '../components/ThemeIcon'
import HelpRequestModal from '../components/HelpRequestModal'
import QueueView from '../views/QueueView'
import ApprovalView from '../views/ApprovalView'
import DashboardView from '../views/DashboardView'
import AllPapersView from '../views/AllPapersView'
import PipelineOpsView from '../views/PipelineOpsView'
import SuggestionsReviewView from '../views/SuggestionsReviewView'
import MySuggestionsView from '../views/MySuggestionsView'
import ReviewerAdminView from '../views/ReviewerAdminView'
import { appendTestEvent, isTestModeEnabled, setTestModeEnabled } from '../utils/testMode'
import {
  SUPPORTED_WORKFLOW_LANGUAGES,
  DEFAULT_PIPELINE_FILTERS,
  EMPTY_COCKPIT_DATA,
  formatCount,
  buildPipelineRpcParams,
  parseUnitFromDescription,
  createEmptyFoodItem,
  isValidFoodItem,
  normalizeMetadata,
  normalizeFoodItem,
  buildFoodItemsFromPayload,
  getPublicPdfUrl,
  buildLatestAiExtractionMaps,
  buildPaperMap,
  buildReviewerMap,
  buildGeneralHelpContext,
} from '../utils/annotateHelpers'

// Cockpit tabs whose data comes from refreshCockpit(); used to lazy-load that
// heavy payload only when one is opened, instead of eagerly on every login.
const COCKPIT_DATA_VIEWS = ['approval', 'dashboard', 'all-papers', 'reviewers', 'suggestions']

// Build a queue item from a get_general_queue_cards row. The card carries only
// what the queue needs (no paper abstract / unused columns) plus the latest AI
// payload and this user's annotation status, so the whole queue loads in one
// lean round-trip.
function buildQueueItemFromCard(card) {
  return {
    id: `general:${card.id}`,
    paper_id: card.id,
    workflow_language: card.workflow_language,
    status: card.annotation_status === 'draft' ? 'draft' : 'available',
    assigned_at: card.routing_updated_at || card.created_at,
    paper: {
      id: card.id,
      title: card.title,
      filename: card.filename,
      pdf_url: card.pdf_url,
      workflow_language: card.workflow_language,
      routing_updated_at: card.routing_updated_at,
      created_at: card.created_at,
      latest_ai_extraction_id: card.latest_ai_extraction_id,
    },
    annotation: card.annotation_status ? { status: card.annotation_status } : null,
    latest_ai_extraction: card.latest_ai_extraction_id
      ? { id: card.latest_ai_extraction_id, normalized_payload_json: card.latest_normalized_payload_json }
      : null,
  }
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
  const [cockpitLoaded, setCockpitLoaded] = useState(false)
  const [reviewerDrafts, setReviewerDrafts] = useState({})
  const [savingReviewerTarget, setSavingReviewerTarget] = useState(null)
  const [savingSuggestionId, setSavingSuggestionId] = useState(null)
  const [mySuggestionItems, setMySuggestionItems] = useState([])
  const [loadingMySuggestions, setLoadingMySuggestions] = useState(false)
  const [pipelineFilters, setPipelineFilters] = useState(DEFAULT_PIPELINE_FILTERS)
  const [pipelineSnapshot, setPipelineSnapshot] = useState(null)
  const [pipelineError, setPipelineError] = useState(null)
  const [loadingPipeline, setLoadingPipeline] = useState(false)
  const paperListRef = useRef(null)

  const reviewerById = useMemo(() => buildReviewerMap(cockpitData.reviewerProfiles), [cockpitData.reviewerProfiles])
  const paperById = useMemo(() => buildPaperMap(cockpitData.papers), [cockpitData.papers])
  const currentItem = queueItems.find((item) => item.id === selectedQueueId) || null
  const currentPaper = currentItem?.paper || null
  const currentIndex = queueItems.findIndex((item) => item.id === selectedQueueId)
  const currentPdfUrl = getPublicPdfUrl(currentPaper?.filename, currentPaper?.pdf_url)
  const isTesterAccount = Boolean(reviewerProfile?.tester_access)
  const canApproveLabels = Boolean(reviewerProfile?.can_approve_labels && !reviewerProfile?.tester_access && !testMode)
  const canSeeCockpit = Boolean(
    reviewerProfile?.cockpit_access
    || reviewerProfile?.tester_access
    || reviewerProfile?.can_approve_labels
  )
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
  const selectedApprovalPdfUrl = getPublicPdfUrl(selectedApprovalPaper?.filename, selectedApprovalPaper?.pdf_url)

  const showToast = useCallback((message, type = 'success') => {
    setToast({ message, type })
    window.clearTimeout(showToast.timer)
    showToast.timer = window.setTimeout(() => setToast(null), 3200)
  }, [])

  // Legacy queue load: three round-trips (papers RPC, then AI extractions +
  // annotations). Kept as a fallback for when get_general_queue_cards has not
  // been deployed to the database yet.
  const loadQueueItemsLegacy = useCallback(async () => {
    const { data: paperRows, error: paperError } = await supabase.rpc('get_general_queue_papers', { p_limit: 250 })
    if (paperError) throw paperError

    const papers = (paperRows || []).filter((paper) => SUPPORTED_WORKFLOW_LANGUAGES.includes(paper.workflow_language))
    const paperIds = papers.map((paper) => paper.id)
    const latestAiExtractionIds = Array.from(new Set(
      papers.map((paper) => paper.latest_ai_extraction_id).filter(Boolean)
    ))
    const [aiResponse, annotationResponse] = await Promise.all([
      latestAiExtractionIds.length
        ? supabase.from('ai_extractions').select('id, paper_id, created_at, normalized_payload_json').in('id', latestAiExtractionIds).order('created_at', { ascending: false })
        : Promise.resolve({ data: [], error: null }),
      paperIds.length
        ? supabase.from('annotations').select('*').eq('user_id', user.id).in('paper_id', paperIds)
        : Promise.resolve({ data: [], error: null }),
    ])
    if (aiResponse.error) throw aiResponse.error
    if (annotationResponse.error) throw annotationResponse.error

    const { byId, byPaperId } = buildLatestAiExtractionMaps(aiResponse.data || [])
    const annotationByPaperId = Object.fromEntries((annotationResponse.data || []).map((row) => [row.paper_id, row]))
    return papers.map((paper) => {
      const annotation = annotationByPaperId[paper.id] || null
      return {
        id: `general:${paper.id}`,
        paper_id: paper.id,
        workflow_language: paper.workflow_language,
        status: annotation?.status === 'draft' ? 'draft' : 'available',
        assigned_at: paper.routing_updated_at || paper.created_at,
        paper,
        annotation,
        latest_ai_extraction: byId[paper.latest_ai_extraction_id] || byPaperId[paper.id] || null,
      }
    })
  }, [user.id])

  const refreshQueue = useCallback(async () => {
    setLoadingQueue(true)
    try {
      // Fast path: one lean RPC returns the queue cards (no paper abstract or
      // unused columns) already joined with the latest AI payload and this
      // user's annotation status — three round-trips collapsed into one.
      const { data: cardData, error: cardError } = await supabase.rpc('get_general_queue_cards', { p_limit: 250 })
      let nextItems
      if (!cardError) {
        nextItems = (Array.isArray(cardData) ? cardData : [])
          .filter((card) => SUPPORTED_WORKFLOW_LANGUAGES.includes(card.workflow_language))
          .map(buildQueueItemFromCard)
      } else if (cardError.code === 'PGRST202') {
        // RPC not deployed yet — fall back to the legacy multi-query path.
        nextItems = await loadQueueItemsLegacy()
      } else {
        throw cardError
      }

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
  }, [loadQueueItemsLegacy, showToast])

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
        supabase.from('papers').select('id,title,doi,filename,pdf_url,workflow_language,routing_status,routing_bucket,route_destination,current_stage_key,latest_ai_extraction_id,routing_updated_at,created_at').order('id', { ascending: false }),
        supabase.rpc('get_cockpit_ai_extractions', { p_limit: 5000 }),
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
          if (!(nextProfile?.cockpit_access || nextProfile?.tester_access || nextProfile?.can_approve_labels)) {
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

  // The queue only needs the authenticated session, not the reviewer profile,
  // so load it immediately on mount in parallel with the profile sync instead of
  // waiting for that round-trip to finish first.
  useEffect(() => {
    refreshQueue()
  }, [refreshQueue])

  useEffect(() => {
    if (!reviewerProfile || canSeeCockpit) return
    refreshMySuggestions()
  }, [canSeeCockpit, refreshMySuggestions, reviewerProfile])

  useEffect(() => {
    if (!canSeeCockpit || activeView !== 'pipeline') return
    void refreshPipeline()
  }, [activeView, canSeeCockpit, refreshPipeline])

  // Lazy-load cockpit data on first visit to a cockpit tab, not eagerly on login.
  // refreshCockpit pulls a large payload (papers + AI extractions), so deferring
  // it keeps the default Queue view fast for admin/cockpit accounts.
  useEffect(() => {
    if (!canSeeCockpit || cockpitLoaded) return
    if (!COCKPIT_DATA_VIEWS.includes(activeView)) return
    let cancelled = false
    refreshCockpit().finally(() => {
      if (!cancelled) setCockpitLoaded(true)
    })
    return () => {
      cancelled = true
    }
  }, [activeView, canSeeCockpit, cockpitLoaded, refreshCockpit])

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

  // No full-screen "Loading queue" gate: the shell (top bar + workspace) paints
  // immediately and QueueView shows its own loading state while the queue loads.

  return (
    <div className="app-layout">
      <div className="top-bar">
        <div className="top-bar-left">
          <span className="app-name">OpenNutri</span>
          {testMode && <span className="test-mode-pill">{reviewerProfile?.tester_access ? 'READ ONLY' : 'TEST MODE'}</span>}
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
            <button className="suggestion-btn" onClick={() => setShowSuggestion(true)}>Suggest</button>
          )}
          {!reviewerProfile?.tester_access && (
            <button className={`test-mode-toggle ${testMode ? 'active' : ''}`} onClick={handleToggleTestMode}>Test Mode</button>
          )}
          <button
            className="theme-toggle"
            onClick={toggleTheme}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            <ThemeIcon theme={theme} />
          </button>
          <span className="user-name">{reviewerProfile?.display_name || user.email}</span>
          <button className="btn btn-outline" onClick={onLogout}>Logout</button>
        </div>
      </div>

      {profileError && <div className="profile-warning">Reviewer profile sync failed: {profileError}</div>}

      {activeView === 'queue' && (
        <QueueView
          items={queueItems}
          loadingQueue={loadingQueue}
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
