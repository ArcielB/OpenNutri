import { useCallback, useEffect, useRef, useState } from 'react'
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
const FINAL_STATUSES = new Set(['submitted', 'conflict', 'resolved'])
const EMPTY_COCKPIT_DATA = {
  reviewerProfiles: [],
  userAssignments: [],
  submissions: [],
  outcomes: [],
  conflicts: [],
  papers: [],
  searchHits: [],
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

function CockpitView({ cockpitData, onRefresh }) {
  const reviewerMetrics = computeReviewerMetrics(cockpitData)
  const sourceBreakdown = computeSourceBreakdown(cockpitData)
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

      <div className="pdf-panel">
        <PdfViewer
          pdfUrl={pdfUrl}
          allNutrients={allNutrients}
          onAddNutrient={() => {}}
          theme={theme}
        />
      </div>

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
  const [selectedConflictId, setSelectedConflictId] = useState(null)
  const [resolutionNote, setResolutionNote] = useState('')
  const undoTimerRef = useRef(null)

  const currentAssignment = assignments.find((assignment) => assignment.id === selectedAssignmentId) || null
  const currentPaper = currentAssignment?.paper || null
  const currentPaperIndex = assignments.findIndex((assignment) => assignment.id === selectedAssignmentId)
  const pdfUrl = currentPaper ? getPublicPdfUrl(currentPaper.filename) : null
  const queueStats = {
    open: assignments.filter((assignment) => OPEN_STATUSES.has(assignment.status)).length,
    final: assignments.filter((assignment) => FINAL_STATUSES.has(assignment.status)).length,
    conflict: assignments.filter((assignment) => assignment.status === 'conflict').length,
    resolved: assignments.filter((assignment) => assignment.status === 'resolved').length,
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
    setLoadingQueue(true)
    try {
      const { data: assignmentRows, error: assignmentError } = await supabase
        .from('paper_user_assignments')
        .select('*')
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
    } catch (error) {
      console.error('Queue refresh failed:', error)
      showToast(`Failed to load queue: ${error.message}`, 'error')
    } finally {
      setLoadingQueue(false)
    }
  }, [showToast])

  const refreshCockpit = useCallback(async () => {
    if (!reviewerProfile?.cockpit_access) return
    setLoadingCockpit(true)
    try {
      const [
        reviewerProfilesResponse,
        userAssignmentsResponse,
        submissionsResponse,
        outcomesResponse,
        conflictsResponse,
        papersResponse,
        searchHitsResponse,
      ] = await Promise.all([
        supabase.from('reviewer_profiles').select('*').order('display_name', { ascending: true }),
        supabase.from('paper_user_assignments').select('*').order('assigned_at', { ascending: true }),
        supabase.from('paper_assignment_submissions').select('*').order('submitted_at', { ascending: false }),
        supabase.from('paper_review_outcomes').select('*').order('resolved_at', { ascending: false }),
        supabase.from('paper_conflicts').select('*').order('created_at', { ascending: false }),
        supabase.from('papers').select('id,title,doi,filename,workflow_language').order('id', { ascending: false }),
        supabase.from('paper_search_hits').select('paper_id,source,template_id,source_term,query_phrase,workflow_language'),
      ])

      if (reviewerProfilesResponse.error) throw reviewerProfilesResponse.error
      if (userAssignmentsResponse.error) throw userAssignmentsResponse.error
      if (submissionsResponse.error) throw submissionsResponse.error
      if (outcomesResponse.error) throw outcomesResponse.error
      if (conflictsResponse.error) throw conflictsResponse.error
      if (papersResponse.error) throw papersResponse.error
      if (searchHitsResponse.error) throw searchHitsResponse.error

      setCockpitData({
        reviewerProfiles: reviewerProfilesResponse.data || [],
        userAssignments: userAssignmentsResponse.data || [],
        submissions: submissionsResponse.data || [],
        outcomes: outcomesResponse.data || [],
        conflicts: conflictsResponse.data || [],
        papers: papersResponse.data || [],
        searchHits: searchHitsResponse.data || [],
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
    const next = !testMode
    const message = next
      ? 'Enable test mode? This will disable all database writes and store actions locally.'
      : 'Disable test mode? Database writes will resume.'
    if (typeof window !== 'undefined' && !window.confirm(message)) return
    setTestMode(next)
    setTestModeEnabled(next)
    showToast(next ? 'Test mode enabled — no DB writes.' : 'Test mode disabled.')
  }, [showToast, testMode])

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
              <button className={`nav-btn ${activeView === 'cockpit' ? 'nav-btn-active' : ''}`} onClick={() => setActiveView('cockpit')}>
                Cockpit
              </button>
              <button className={`nav-btn ${activeView === 'conflicts' ? 'nav-btn-active' : ''}`} onClick={() => setActiveView('conflicts')}>
                Conflicts
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
        <div className="workspace">
          <div className="pdf-panel">
            <div className="pdf-top-strip">
              <div className="paper-list-toggle">
                <button className="nav-btn" onClick={() => setShowPaperList((open) => !open)}>
                  {currentPaperIndex >= 0 ? `Assignment ${currentPaperIndex + 1}/${assignments.length}` : 'Queue'} ▾
                </button>
                {showPaperList && (
                  <div className="paper-list-dropdown">
                    {assignments.map((assignment, index) => (
                      <div
                        key={assignment.id}
                        className={`paper-list-item ${assignment.id === selectedAssignmentId ? 'active' : ''}`}
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
                <span className="status-badge status-pending">{queueStats.open} open</span>
                <span className="status-badge status-draft">{queueStats.conflict} conflict</span>
                <span className="status-badge status-done">{queueStats.resolved} resolved</span>
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
            <PdfViewer
              pdfUrl={pdfUrl}
              allNutrients={allNutrients}
              onAddNutrient={handlePdfNutrientAdd}
              theme={theme}
            />
          </div>

          <div className="annotation-panel">
            <div className="queue-assignment-header">
              {currentAssignment ? (
                <>
                  <div>
                    <h2>{currentPaper?.title || currentPaper?.filename || `Paper ${currentAssignment.paper_id}`}</h2>
                    <p>
                      {currentAssignment.workflow_language?.toUpperCase()} · {currentAssignment.slot_assignment?.slot_key || reviewerProfile?.official_slot || 'slot pending'}
                      {currentPaper?.doi && ` · DOI: ${currentPaper.doi}`}
                    </p>
                  </div>
                  <div className={`status-badge ${getStatusBadgeClass(currentAssignment.status)}`}>
                    {formatStatusLabel(currentAssignment.status)}
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
      )}

      {activeView === 'cockpit' && (
        <CockpitView
          cockpitData={cockpitData}
          onRefresh={refreshCockpit}
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

      {loadingCockpit && reviewerProfile?.cockpit_access && (
        <div className="floating-loading">Refreshing cockpit…</div>
      )}

      {toast && <div className={`toast toast-${toast.type}`}>{toast.message}</div>}

      {showSuggestion && (
        <SuggestionModal
          user={user}
          onClose={() => setShowSuggestion(false)}
          testMode={testMode}
        />
      )}
    </div>
  )
}
