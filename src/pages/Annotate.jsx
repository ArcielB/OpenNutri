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
        moisture: null, moisture_unit: 'g/100g',
        protein: null, protein_unit: 'g/100g',
        fat: null, fat_unit: 'g/100g',
        carbohydrate: null, carbohydrate_unit: 'g/100g',
        ash: null, ash_unit: 'g/100g',
        energy: null, energy_unit: 'kcal/100g',
        fiber: null, fiber_unit: 'g/100g',
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
    const { theme, toggleTheme } = useTheme()

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
                const { data: items } = await supabase
                    .from('food_items')
                    .select('*')
                    .eq('annotation_id', annotation.id)
                    .order('id', { ascending: true })

                if (items && items.length > 0) {
                    setFoodItems(items)
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

            // Delete old food items
            await supabase
                .from('food_items')
                .delete()
                .eq('annotation_id', ann.id)

            // Insert new food items if has_data
            if (hasData && foodItems.length > 0) {
                const itemsToInsert = foodItems.map((item) => ({
                    annotation_id: ann.id,
                    food_name: item.food_name,
                    moisture: item.moisture,
                    moisture_unit: item.moisture_unit,
                    protein: item.protein,
                    protein_unit: item.protein_unit,
                    fat: item.fat,
                    fat_unit: item.fat_unit,
                    carbohydrate: item.carbohydrate,
                    carbohydrate_unit: item.carbohydrate_unit,
                    ash: item.ash,
                    ash_unit: item.ash_unit,
                    energy: item.energy,
                    energy_unit: item.energy_unit,
                    fiber: item.fiber,
                    fiber_unit: item.fiber_unit,
                }))

                const { error: itemsError } = await supabase
                    .from('food_items')
                    .insert(itemsToInsert)

                if (itemsError) throw itemsError
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
                <PdfViewer pdfUrl={pdfUrl} />

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
