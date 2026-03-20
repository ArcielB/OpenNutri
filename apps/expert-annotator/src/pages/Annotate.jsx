import { useState, useEffect, useCallback, useRef } from 'react'
import { supabase } from '../supabaseClient'
import PdfViewer from '../components/PdfViewer'
import FoodItemForm from '../components/FoodItemForm'
import SuggestionModal from '../components/SuggestionModal'
import { appendTestEvent, isTestModeEnabled, setTestModeEnabled } from '../utils/testMode'

const R2_BASE_URL = import.meta.env.VITE_R2_PUBLIC_URL || ''

// Parse unit from master_nutrients description field (format: "Unit: g. USDA nutrient_nbr: ...")
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

const GLOBAL_SKIP_REASON = 'quick_skip'
const GLOBAL_SKIP_UNDO_MS = 10000

export default function Annotate({ user, onLogout, theme, toggleTheme }) {
    const [papers, setPapers] = useState([])
    const [currentIndex, setCurrentIndex] = useState(0)
    const [foodItems, setFoodItems] = useState([createEmptyFoodItem()])
    const [annotationStatus, setAnnotationStatus] = useState({}) // paper_id -> status
    const [saving, setSaving] = useState(false)
    const [toast, setToast] = useState(null)
    const [showPaperList, setShowPaperList] = useState(false)
    const [showSuggestion, setShowSuggestion] = useState(false)
    const [allNutrients, setAllNutrients] = useState([])
    const [allFoods, setAllFoods] = useState([])
    const [foodsLoaded, setFoodsLoaded] = useState(false)
    const [testMode, setTestMode] = useState(() => isTestModeEnabled())
    const [globalNoDataIds, setGlobalNoDataIds] = useState([])
    const [undoGlobalSkip, setUndoGlobalSkip] = useState(null)
    const undoTimerRef = useRef(null)

    // Load nutrients master list once
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
            // Map to the shape the rest of the app expects
            const mapped = (data || []).map(n => ({
                id: n.id,
                name: n.standard_name,
                unit_name: parseUnitFromDescription(n.description),
                rank: 99999,
            }))
            setAllNutrients(mapped)
        }
        fetchNutrients()
    }, [])

    // Load foods catalog once in the background so search can switch to local ranking.
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

        const startPreload = () => {
            void fetchFoods()
        }

        const idleId = typeof window !== 'undefined' && 'requestIdleCallback' in window
            ? window.requestIdleCallback(startPreload, { timeout: 1500 })
            : window.setTimeout(startPreload, 300)

        return () => {
            cancelled = true
            if (typeof window !== 'undefined' && 'cancelIdleCallback' in window && typeof idleId === 'number') {
                window.cancelIdleCallback(idleId)
            } else {
                clearTimeout(idleId)
            }
        }
    }, [])

    // Load papers list (excluding globally skipped items)
    useEffect(() => {
        async function fetchPapers() {
            const [{ data: labelRows, error: labelError }, { data: paperRows, error: paperError }] =
                await Promise.all([
                    supabase
                        .from('paper_global_labels')
                        .select('paper_id, label')
                        .eq('label', 'definitely_no_data'),
                    supabase
                        .from('papers')
                        .select('*')
                        .order('id', { ascending: true }),
                ])

            if (labelError) {
                console.error('Error fetching global labels:', labelError)
            }
            const globalIds = new Set((labelRows || []).map((row) => row.paper_id))
            setGlobalNoDataIds([...globalIds])

            if (paperError) {
                console.error('Error fetching papers:', paperError)
                return
            }
            const filtered = (paperRows || []).filter((paper) => !globalIds.has(paper.id))
            setPapers(filtered)
        }
        fetchPapers()
    }, [])

    // Load annotation statuses for this user
    useEffect(() => {
        async function fetchStatuses() {
            const { data, error } = await supabase
                .from('annotations')
                .select('paper_id, status, has_data')
                .eq('user_id', user.id)

            if (error) {
                console.error('Error fetching statuses:', error)
                return
            }

            const statusMap = {}
                ; (data || []).forEach((a) => {
                    statusMap[a.paper_id] = a.status
                })
            setAnnotationStatus(statusMap)
        }
        fetchStatuses()
    }, [user.id])

    // Load existing annotation when paper changes
    useEffect(() => {
        if (!papers.length) return
        const paper = papers[currentIndex]
        if (!paper) return

        async function loadAnnotation() {
            const { data: annotation } = await supabase
                .from('annotations')
                .select('*')
                .eq('paper_id', paper.id)
                .eq('user_id', user.id)
                .single()

            if (annotation && annotation.has_data) {
                // Load food items
                const { data: items } = await supabase
                    .from('food_items')
                    .select('*')
                    .eq('annotation_id', annotation.id)
                    .order('id', { ascending: true })

                if (items && items.length > 0) {
                    // For each food item, load its nutrient values
                    const foodItemsWithNutrients = await Promise.all(
                        items.map(async (item) => {
                            const { data: nutrientValues } = await supabase
                                .from('annotation_nutrient_values')
                                .select('*')
                                .eq('food_item_id', item.id)
                                .order('id', { ascending: true })

                            return {
                                food_name: item.food_name,
                                food_fdc_id: item.food_fdc_id,
                                is_custom_food: item.is_custom_food,
                                nutrients: (nutrientValues || []).map((nv) => ({
                                    nutrient_id: nv.nutrient_id,
                                    nutrient_name: nv.nutrient_name,
                                    value: nv.value,
                                    unit: nv.unit,
                                })),
                            }
                        })
                    )
                    setFoodItems(foodItemsWithNutrients)
                } else {
                    setFoodItems([createEmptyFoodItem()])
                }
            } else {
                setFoodItems([createEmptyFoodItem()])
            }
        }
        loadAnnotation()
    }, [currentIndex, papers, user.id])

    useEffect(() => {
        if (papers.length && currentIndex >= papers.length) {
            setCurrentIndex(papers.length - 1)
        }
    }, [currentIndex, papers.length])

    useEffect(() => {
        if (!undoGlobalSkip) return undefined
        if (undoTimerRef.current) {
            clearTimeout(undoTimerRef.current)
        }
        undoTimerRef.current = setTimeout(() => {
            setUndoGlobalSkip(null)
        }, GLOBAL_SKIP_UNDO_MS)
        return () => {
            if (undoTimerRef.current) {
                clearTimeout(undoTimerRef.current)
            }
        }
    }, [undoGlobalSkip])

    const currentPaper = papers[currentIndex] || null
    const pdfUrl = currentPaper
        ? supabase.storage.from('papers').getPublicUrl(currentPaper.filename).data.publicUrl
        : null
    const isGlobalSkipped = currentPaper ? globalNoDataIds.includes(currentPaper.id) : false

    const doneCount = papers.reduce((count, paper) => {
        const status = annotationStatus[paper.id]
        return status === 'done' || status === 'skipped' ? count + 1 : count
    }, 0)

    // Show toast
    const showToast = useCallback((message, type = 'success') => {
        setToast({ message, type })
        setTimeout(() => setToast(null), 3000)
    }, [])

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

    // Save annotation
    const saveAnnotation = async (hasData, status) => {
        if (!currentPaper) return
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
                    type: 'annotation_save',
                    paper_id: currentPaper.id,
                    user_id: user.id,
                    has_data: hasData,
                    status,
                    food_item_count: foodItemCount,
                    nutrient_value_count: nutrientValueCount,
                })

                setAnnotationStatus((prev) => ({
                    ...prev,
                    [currentPaper.id]: status,
                }))

                const label = status === 'skipped' ? 'Skipped' : status === 'draft' ? 'Draft saved' : 'Saved'
                showToast(`${label} (test mode) — Paper ${currentIndex + 1}`)

                if ((status === 'done' || status === 'skipped') && currentIndex < papers.length - 1) {
                    setCurrentIndex((i) => i + 1)
                }
                return
            }
            // Upsert annotation
            const { data: ann, error: annError } = await supabase
                .from('annotations')
                .upsert(
                    {
                        paper_id: currentPaper.id,
                        user_id: user.id,
                        has_data: hasData,
                        status: status,
                        updated_at: new Date().toISOString(),
                    },
                    { onConflict: 'paper_id,user_id' }
                )
                .select()
                .single()

            if (annError) throw annError

            // Delete old food items (cascade deletes nutrient values too)
            await supabase
                .from('food_items')
                .delete()
                .eq('annotation_id', ann.id)

            // Insert new food items if has_data
            if (hasData && validFoodItems.length > 0) {
                for (const item of validFoodItems) {
                    // Insert the food item
                    const { data: insertedItem, error: itemError } = await supabase
                        .from('food_items')
                        .insert({
                            annotation_id: ann.id,
                            food_name: item.food_name,
                            food_fdc_id: item.food_fdc_id,
                            is_custom_food: item.is_custom_food || false,
                        })
                        .select()
                        .single()

                    if (itemError) throw itemError

                    // Insert nutrient values for this food item
                    if (item.nutrients && item.nutrients.length > 0) {
                        const nutrientRows = item.nutrients.map((n) => ({
                            food_item_id: insertedItem.id,
                            nutrient_id: n.nutrient_id,
                            nutrient_name: n.nutrient_name,
                            value: n.value,
                            unit: n.unit,
                        }))

                        const { error: nvError } = await supabase
                            .from('annotation_nutrient_values')
                            .insert(nutrientRows)

                        if (nvError) throw nvError
                    }
                }
            }

            const { error: labelError } = await supabase
                .from('paper_label_events')
                .insert({
                    paper_id: currentPaper.id,
                    annotation_id: ann.id,
                    user_id: user.id,
                    has_data: hasData,
                    status,
                    food_item_count: foodItemCount,
                    nutrient_value_count: nutrientValueCount,
                    source: 'ui',
                })

            if (labelError) throw labelError

            // Update local status
            setAnnotationStatus((prev) => ({
                ...prev,
                [currentPaper.id]: status,
            }))

            const label = status === 'skipped' ? 'Skipped' : status === 'draft' ? 'Draft saved' : 'Saved'
            showToast(`${label} — Paper ${currentIndex + 1}`)

            // Auto-advance on done/skipped
            if ((status === 'done' || status === 'skipped') && currentIndex < papers.length - 1) {
                setCurrentIndex((i) => i + 1)
            }
        } catch (err) {
            console.error('Save error:', err)
            showToast('Failed to save: ' + err.message, 'error')
        } finally {
            setSaving(false)
        }
    }

    const handleGlobalNoData = async () => {
        if (!currentPaper || isGlobalSkipped) return
        const reason = GLOBAL_SKIP_REASON

        setSaving(true)
        try {
            if (testMode) {
                appendTestEvent({
                    type: 'global_no_data',
                    paper_id: currentPaper.id,
                    user_id: user.id,
                    reason,
                })
            } else {
                const { error: globalError } = await supabase
                    .from('paper_global_labels')
                    .insert({
                        paper_id: currentPaper.id,
                        user_id: user.id,
                        label: 'definitely_no_data',
                        reason,
                    })
                if (globalError) throw globalError

                const { error: labelError } = await supabase
                    .from('paper_label_events')
                    .insert({
                        paper_id: currentPaper.id,
                        annotation_id: null,
                        user_id: user.id,
                        has_data: false,
                        status: 'skipped',
                        food_item_count: 0,
                        nutrient_value_count: 0,
                        source: 'global_no_data',
                    })
                if (labelError) throw labelError
            }

            const removedPaper = currentPaper
            const removedIndex = currentIndex
            const remaining = papers.filter((paper) => paper.id !== currentPaper.id)
            setPapers(remaining)
            setGlobalNoDataIds((prev) => [...new Set([...prev, currentPaper.id])])
            setAnnotationStatus((prev) => {
                const next = { ...prev }
                delete next[currentPaper.id]
                return next
            })
            setCurrentIndex((idx) => Math.min(idx, Math.max(remaining.length - 1, 0)))
            setUndoGlobalSkip({ paper: removedPaper, index: removedIndex })
            showToast(testMode ? 'Global skip recorded locally (test mode).' : 'Marked as global no data.')
        } catch (err) {
            console.error('Global skip error:', err)
            showToast('Failed to mark global skip: ' + err.message, 'error')
        } finally {
            setSaving(false)
        }
    }

    const handleUndoGlobalSkip = async () => {
        if (!undoGlobalSkip) return
        setSaving(true)
        try {
            if (!testMode) {
                const { error: globalDeleteError } = await supabase
                    .from('paper_global_labels')
                    .delete()
                    .eq('paper_id', undoGlobalSkip.paper.id)
                    .eq('label', 'definitely_no_data')
                    .eq('user_id', user.id)
                if (globalDeleteError) throw globalDeleteError

                await supabase
                    .from('paper_label_events')
                    .delete()
                    .eq('paper_id', undoGlobalSkip.paper.id)
                    .eq('user_id', user.id)
                    .eq('source', 'global_no_data')
            } else {
                appendTestEvent({
                    type: 'undo_global_no_data',
                    paper_id: undoGlobalSkip.paper.id,
                    user_id: user.id,
                })
            }

            setGlobalNoDataIds((prev) => prev.filter((id) => id !== undoGlobalSkip.paper.id))
            setPapers((prev) => {
                if (prev.some((paper) => paper.id === undoGlobalSkip.paper.id)) return prev
                const next = [...prev]
                const insertAt = Math.min(Math.max(undoGlobalSkip.index, 0), next.length)
                next.splice(insertAt, 0, undoGlobalSkip.paper)
                return next
            })
            setCurrentIndex((idx) => (idx >= undoGlobalSkip.index ? idx + 1 : idx))
            setUndoGlobalSkip(null)
            showToast('Global skip undone.')
        } catch (err) {
            console.error('Undo global skip error:', err)
            showToast('Failed to undo global skip: ' + err.message, 'error')
        } finally {
            setSaving(false)
        }
    }

    // Food items handlers
    const updateFoodItem = (idx, updatedItem) => {
        setFoodItems((items) =>
            items.map((item, i) => (i === idx ? updatedItem : item))
        )
    }

    const removeFoodItem = (idx) => {
        setFoodItems((items) => {
            const newItems = items.filter((_, i) => i !== idx)
            return newItems.length === 0 ? [createEmptyFoodItem()] : newItems
        })
    }

    const addFoodItem = () => {
        setFoodItems((items) => [...items, createEmptyFoodItem()])
    }

    // Handle nutrient added from PDF popover
    const handlePdfNutrientAdd = (nutrientEntry) => {
        // Add to the first food item (or last one if multiple)
        setFoodItems((items) => {
            if (items.length === 0) return [{ ...createEmptyFoodItem(), nutrients: [nutrientEntry] }]
            const targetIdx = items.length - 1
            const target = items[targetIdx]

            // Prevent duplicates
            if (nutrientEntry.nutrient_id && target.nutrients.some((n) => n.nutrient_id === nutrientEntry.nutrient_id)) {
                return items
            }

            return items.map((item, i) =>
                i === targetIdx
                    ? { ...item, nutrients: [...item.nutrients, nutrientEntry] }
                    : item
            )
        })
    }

    const goToPaper = (idx) => {
        setCurrentIndex(idx)
        setShowPaperList(false)
    }

    return (
        <div className="app-layout">
            {/* Top Bar */}
            <div className="top-bar">
                <div className="top-bar-left">
                    <span className="app-name">🔬 OpenNutri</span>
                    {testMode && <span className="test-mode-pill">TEST MODE</span>}
                    <div className="paper-list-toggle">
                        <button
                            className="nav-btn"
                            onClick={() => setShowPaperList(!showPaperList)}
                        >
                            Paper {currentIndex + 1}/{papers.length} ▾
                        </button>
                        {showPaperList && (
                            <div className="paper-list-dropdown">
                                {papers.map((p, idx) => (
                                    <div
                                        key={p.id}
                                        className={`paper-list-item ${idx === currentIndex ? 'active' : ''}`}
                                        onClick={() => goToPaper(idx)}
                                    >
                                        <span className="paper-id">{idx + 1}</span>
                                        <span className="paper-title">
                                            {p.title || p.filename}
                                        </span>
                                        {annotationStatus[p.id] === 'done' && (
                                            <span className="status-badge status-done">✓</span>
                                        )}
                                        {annotationStatus[p.id] === 'skipped' && (
                                            <span className="status-badge status-skipped">—</span>
                                        )}
                                        {annotationStatus[p.id] === 'draft' && (
                                            <span className="status-badge status-draft">◐</span>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                <div className="top-bar-center">
                    <button
                        className="nav-btn"
                        disabled={currentIndex <= 0}
                        onClick={() => setCurrentIndex((i) => i - 1)}
                    >
                        ← Prev
                    </button>
                    <button
                        className="nav-btn"
                        disabled={currentIndex >= papers.length - 1}
                        onClick={() => setCurrentIndex((i) => i + 1)}
                    >
                        Next →
                    </button>
                </div>

                <div className="top-bar-right">
                    <div className="progress-pill">
                        <span className="count">{doneCount}</span> / {papers.length}
                        <div className="progress-bar-mini">
                            <div
                                className="fill"
                                style={{
                                    width: papers.length
                                        ? `${(doneCount / papers.length) * 100}%`
                                        : '0%',
                                }}
                            />
                        </div>
                    </div>
                    <button className="suggestion-btn" onClick={() => setShowSuggestion(true)} title="Send a suggestion">
                        💡
                    </button>
                    <button
                        className={`test-mode-toggle ${testMode ? 'active' : ''}`}
                        onClick={handleToggleTestMode}
                        title="Toggle test mode"
                    >
                        Test Mode
                    </button>
                    <button className="theme-toggle" onClick={toggleTheme} title="Toggle light/dark mode">
                        {theme === 'dark' ? '☀️' : '🌙'}
                    </button>
                    <span className="user-name">{user.email}</span>
                    <button className="btn btn-outline" onClick={onLogout}>
                        Logout
                    </button>
                </div>
            </div>

            {/* Workspace */}
            <div className="workspace">
                <PdfViewer
                    pdfUrl={pdfUrl}
                    allNutrients={allNutrients}
                    onAddNutrient={handlePdfNutrientAdd}
                    theme={theme}
                />

                <div className="annotation-panel">
                    {testMode && (
                        <div className="test-mode-banner">
                            Test mode is active. No database writes will occur.
                        </div>
                    )}
                    <div className="annotation-scroll">
                        {currentPaper && (
                            <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '16px' }}>
                                {currentPaper.title || currentPaper.filename}
                                {currentPaper.doi && (
                                    <span> · DOI: {currentPaper.doi}</span>
                                )}
                            </p>
                        )}

                        {foodItems.map((item, idx) => (
                            <FoodItemForm
                                key={idx}
                                index={idx}
                                data={item}
                                onChange={(updated) => updateFoodItem(idx, updated)}
                                onDelete={() => removeFoodItem(idx)}
                                allNutrients={allNutrients}
                                allFoods={allFoods}
                                foodsLoaded={foodsLoaded}
                                userId={user.id}
                            />
                        ))}

                        <button className="add-food-btn" onClick={addFoodItem}>
                            + Add Another Food Item
                        </button>
                    </div>

                    <div className="annotation-actions">
                        <div className="action-row">
                            <button
                                className="btn btn-danger btn-global-skip"
                                onClick={handleGlobalNoData}
                                disabled={saving || isGlobalSkipped}
                            >
                                🛑 Definitely No Data (Global)
                            </button>
                        </div>
                        {undoGlobalSkip && (
                            <div className="undo-banner">
                                <span>Global skip applied.</span>
                                <button
                                    className="btn btn-outline"
                                    onClick={handleUndoGlobalSkip}
                                    disabled={saving}
                                    type="button"
                                >
                                    Undo
                                </button>
                            </div>
                        )}
                        <div className="action-row">
                            <button
                                className="btn btn-skip"
                                onClick={() => saveAnnotation(false, 'skipped')}
                                disabled={saving}
                            >
                                ⊘ No Usable Data (Personal)
                            </button>
                            <button
                                className="btn btn-outline"
                                onClick={() => saveAnnotation(true, 'draft')}
                                disabled={saving}
                            >
                                Save Draft
                            </button>
                        </div>
                        <button
                            className="btn btn-success"
                            onClick={() => saveAnnotation(true, 'done')}
                            disabled={saving}
                            style={{ width: '100%' }}
                        >
                            {saving ? 'Saving...' : '✓ Save & Next Paper'}
                        </button>
                    </div>
                </div>
            </div>

            {/* Toast Notification */}
            {toast && (
                <div className={`toast toast-${toast.type}`}>{toast.message}</div>
            )}

            {/* Suggestion Modal */}
            {showSuggestion && (
                <SuggestionModal user={user} onClose={() => setShowSuggestion(false)} testMode={testMode} />
            )}
        </div>
    )
}
