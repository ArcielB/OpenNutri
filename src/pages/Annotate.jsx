import { useState, useEffect, useCallback } from 'react'
import { supabase } from '../supabaseClient'
import PdfViewer from '../components/PdfViewer'
import FoodItemForm from '../components/FoodItemForm'
import SuggestionModal from '../components/SuggestionModal'
import { useTheme } from '../hooks/useTheme'

const R2_BASE_URL = import.meta.env.VITE_R2_PUBLIC_URL || ''

function createEmptyFoodItem() {
    return {
        food_name: '',
        food_fdc_id: null,
        is_custom_food: false,
        nutrients: [],
    }
}

export default function Annotate({ user, onLogout }) {
    const [papers, setPapers] = useState([])
    const [currentIndex, setCurrentIndex] = useState(0)
    const [foodItems, setFoodItems] = useState([createEmptyFoodItem()])
    const [annotationStatus, setAnnotationStatus] = useState({}) // paper_id -> status
    const [saving, setSaving] = useState(false)
    const [toast, setToast] = useState(null)
    const [showPaperList, setShowPaperList] = useState(false)
    const [showSuggestion, setShowSuggestion] = useState(false)
    const [allNutrients, setAllNutrients] = useState([])
    const { theme, toggleTheme } = useTheme()

    // Load nutrients master list once
    useEffect(() => {
        async function fetchNutrients() {
            const { data, error } = await supabase
                .from('nutrients')
                .select('id, name, unit_name, rank')
                .order('rank', { ascending: true })

            if (error) {
                console.error('Error fetching nutrients:', error)
                return
            }
            setAllNutrients(data || [])
        }
        fetchNutrients()
    }, [])

    // Load papers list
    useEffect(() => {
        async function fetchPapers() {
            const { data, error } = await supabase
                .from('papers')
                .select('*')
                .order('id', { ascending: true })

            if (error) {
                console.error('Error fetching papers:', error)
                return
            }
            setPapers(data || [])
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

    const currentPaper = papers[currentIndex] || null
    const pdfUrl = currentPaper
        ? `${R2_BASE_URL}/${currentPaper.filename}`
        : null

    const doneCount = Object.values(annotationStatus).filter(
        (s) => s === 'done' || s === 'skipped'
    ).length

    // Show toast
    const showToast = useCallback((message, type = 'success') => {
        setToast({ message, type })
        setTimeout(() => setToast(null), 3000)
    }, [])

    // Save annotation
    const saveAnnotation = async (hasData, status) => {
        if (!currentPaper) return
        setSaving(true)

        try {
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
            if (hasData && foodItems.length > 0) {
                for (const item of foodItems) {
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
                />

                <div className="annotation-panel">
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
                            />
                        ))}

                        <button className="add-food-btn" onClick={addFoodItem}>
                            + Add Another Food Item
                        </button>
                    </div>

                    <div className="annotation-actions">
                        <div className="action-row">
                            <button
                                className="btn btn-skip"
                                onClick={() => saveAnnotation(false, 'skipped')}
                                disabled={saving}
                            >
                                ⊘ No Usable Data
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
                <SuggestionModal user={user} onClose={() => setShowSuggestion(false)} />
            )}
        </div>
    )
}
