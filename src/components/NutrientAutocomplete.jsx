import { useState, useRef, useEffect } from 'react'

// Category headers & meta-entries to exclude
const SKIP_NAMES = new Set([
    'proximates', 'minerals', 'lipids', 'vitamins and other components', 'other',
])

export default function NutrientAutocomplete({ allNutrients, addedNutrientIds, onAdd }) {
    const [query, setQuery] = useState('')
    const [results, setResults] = useState([])
    const [showDropdown, setShowDropdown] = useState(false)
    const [selectedIndex, setSelectedIndex] = useState(-1)
    const containerRef = useRef(null)

    // Close on outside click
    useEffect(() => {
        const handleClickOutside = (e) => {
            if (containerRef.current && !containerRef.current.contains(e.target)) {
                setShowDropdown(false)
            }
        }
        document.addEventListener('mousedown', handleClickOutside)
        return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    const search = (q) => {
        if (!q || q.length < 1) {
            setResults([])
            return
        }
        const lower = q.toLowerCase()
        const filtered = allNutrients.filter((n) => {
            if (SKIP_NAMES.has(n.name.toLowerCase())) return false
            if (n.name.toLowerCase().includes('do not use')) return false
            if (addedNutrientIds.has(n.id)) return false
            return n.name.toLowerCase().includes(lower)
        })
        // Prioritize results that start with the query
        filtered.sort((a, b) => {
            const aStarts = a.name.toLowerCase().startsWith(lower) ? 0 : 1
            const bStarts = b.name.toLowerCase().startsWith(lower) ? 0 : 1
            if (aStarts !== bStarts) return aStarts - bStarts
            return (a.rank || 99999) - (b.rank || 99999)
        })
        setResults(filtered.slice(0, 15))
        setSelectedIndex(-1)
    }

    const handleInputChange = (e) => {
        const val = e.target.value
        setQuery(val)
        setShowDropdown(true)
        search(val)
    }

    const handleSelect = (nutrient) => {
        onAdd({
            nutrient_id: nutrient.id,
            nutrient_name: nutrient.name,
            unit: formatUnit(nutrient.unit_name),
            value: null,
        })
        setQuery('')
        setShowDropdown(false)
        setResults([])
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
        <div className="nutrient-autocomplete" ref={containerRef}>
            <input
                type="text"
                className="nutrient-search-input"
                placeholder="🔍 Add nutrient..."
                value={query}
                onChange={handleInputChange}
                onFocus={() => query && setShowDropdown(true)}
                onKeyDown={handleKeyDown}
            />

            {showDropdown && query.length >= 1 && (
                <div className="autocomplete-dropdown">
                    {results.length === 0 ? (
                        <div className="autocomplete-item empty">No matching nutrients</div>
                    ) : (
                        results.map((n, idx) => (
                            <div
                                key={n.id}
                                className={`autocomplete-item ${idx === selectedIndex ? 'selected' : ''}`}
                                onMouseDown={() => handleSelect(n)}
                                onMouseEnter={() => setSelectedIndex(idx)}
                            >
                                <span className="autocomplete-name">{n.name}</span>
                                <span className="autocomplete-unit">{formatUnit(n.unit_name)}</span>
                            </div>
                        ))
                    )}
                </div>
            )}
        </div>
    )
}

function formatUnit(unitName) {
    if (!unitName) return 'g/100g'
    const u = unitName.toUpperCase()
    if (u === 'G') return 'g/100g'
    if (u === 'MG') return 'mg/100g'
    if (u === 'UG' || u === 'ΜG') return 'μg/100g'
    if (u === 'KCAL') return 'kcal/100g'
    if (u === 'KJ') return 'kJ/100g'
    if (u === 'IU') return 'IU/100g'
    return `${unitName}/100g`
}
