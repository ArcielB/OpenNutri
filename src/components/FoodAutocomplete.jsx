import { useState, useEffect, useRef } from 'react'
import { supabase } from '../supabaseClient'

export default function FoodAutocomplete({ value, foodFdcId, onChange }) {
    const [query, setQuery] = useState(value || '')
    const [results, setResults] = useState([])
    const [showDropdown, setShowDropdown] = useState(false)
    const [loading, setLoading] = useState(false)
    const [selectedIndex, setSelectedIndex] = useState(-1)
    const debounceRef = useRef(null)
    const containerRef = useRef(null)

    // Sync external value changes
    useEffect(() => {
        setQuery(value || '')
    }, [value])

    // Close dropdown on outside click
    useEffect(() => {
        const handleClickOutside = (e) => {
            if (containerRef.current && !containerRef.current.contains(e.target)) {
                setShowDropdown(false)
            }
        }
        document.addEventListener('mousedown', handleClickOutside)
        return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    const search = async (q) => {
        if (!q || q.length < 2) {
            setResults([])
            return
        }
        setLoading(true)
        try {
            const { data, error } = await supabase
                .from('foods')
                .select('fdc_id, description, food_category_id, food_category:food_category_id(description)')
                .ilike('description', `%${q}%`)
                .limit(15)

            if (error) throw error
            setResults(data || [])
            setSelectedIndex(-1)
        } catch (err) {
            console.error('Food search error:', err)
            setResults([])
        } finally {
            setLoading(false)
        }
    }

    const handleInputChange = (e) => {
        const val = e.target.value
        setQuery(val)
        setShowDropdown(true)

        // Debounce
        clearTimeout(debounceRef.current)
        debounceRef.current = setTimeout(() => search(val), 250)

        // If user edits a previously selected food, mark as custom
        if (foodFdcId) {
            onChange({ food_name: val, food_fdc_id: null, is_custom_food: true })
        }
    }

    const handleSelect = (food) => {
        setQuery(food.description)
        setShowDropdown(false)
        onChange({
            food_name: food.description,
            food_fdc_id: food.fdc_id,
            is_custom_food: false,
        })
    }

    const handleBlur = () => {
        // Delay to allow click on dropdown item
        setTimeout(() => {
            if (query && query !== value) {
                onChange({
                    food_name: query,
                    food_fdc_id: null,
                    is_custom_food: true,
                })
            }
        }, 200)
    }

    const handleKeyDown = (e) => {
        if (!showDropdown || results.length === 0) return

        if (e.key === 'ArrowDown') {
            e.preventDefault()
            setSelectedIndex((i) => Math.min(i + 1, results.length - 1))
        } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setSelectedIndex((i) => Math.max(i - 1, 0))
        } else if (e.key === 'Enter' && selectedIndex >= 0) {
            e.preventDefault()
            handleSelect(results[selectedIndex])
        } else if (e.key === 'Escape') {
            setShowDropdown(false)
        }
    }

    return (
        <div className="food-autocomplete" ref={containerRef}>
            <input
                className="food-name-input"
                type="text"
                placeholder="Search food name (e.g., Trabzon ekmeği)..."
                value={query}
                onChange={handleInputChange}
                onFocus={() => query.length >= 2 && setShowDropdown(true)}
                onBlur={handleBlur}
                onKeyDown={handleKeyDown}
            />
            {foodFdcId && (
                <span className="food-match-badge">✓ Matched</span>
            )}
            {!foodFdcId && query && (
                <span className="food-custom-badge">Custom</span>
            )}

            {showDropdown && (query.length >= 2) && (
                <div className="autocomplete-dropdown">
                    {loading && (
                        <div className="autocomplete-item loading">Searching...</div>
                    )}
                    {!loading && results.length === 0 && (
                        <div className="autocomplete-item empty">
                            No matches — press Enter to use as custom food
                        </div>
                    )}
                    {results.map((food, idx) => (
                        <div
                            key={food.fdc_id}
                            className={`autocomplete-item ${idx === selectedIndex ? 'selected' : ''}`}
                            onMouseDown={() => handleSelect(food)}
                            onMouseEnter={() => setSelectedIndex(idx)}
                        >
                            <span className="autocomplete-name">{food.description}</span>
                            {food.food_category?.description && (
                                <span className="autocomplete-category">
                                    {food.food_category.description}
                                </span>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
