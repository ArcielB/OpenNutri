import { useState, useRef, useEffect } from 'react'
import {
    SEARCH_LOG_DEBOUNCE_MS,
    appendSearchStep,
    persistSearchSession,
} from '../utils/searchSessionLogger'
import {
    buildTokenVariants,
    extractAliasSegments,
    findPrefixMatch,
    findTokenRelationIndex,
    isDerivedPrefixMatch,
    isFuzzyTokenMatch,
    isInflectionalTokenMatch,
    normalizeText,
    tokenize,
} from '../utils/fuzzyMatch'

const SKIP_NAMES = new Set([
    'proximates', 'minerals', 'lipids', 'vitamins and other components', 'other',
])

const STOPWORDS = new Set([
    'and',
    'or',
    'with',
    'without',
    'in',
    'of',
    'for',
    'the',
    'a',
    'an',
    'to',
    'from',
    'total',
])

function rankDefaultNutrients(nutrients) {
    return nutrients
        .filter((n) => {
            const lowerName = n.name.toLowerCase()
            if (SKIP_NAMES.has(lowerName)) return false
            if (lowerName.includes('do not use')) return false
            return true
        })
        .sort((a, b) => {
            if ((a.rank || 99999) !== (b.rank || 99999)) return (a.rank || 99999) - (b.rank || 99999)
            return a.name.localeCompare(b.name)
        })
        .slice(0, 15)
}

function scoreNutrientMatch(nutrient, query) {
    const name = nutrient.name || ''
    const aliases = extractAliasSegments(name)
    const normalizedName = normalizeText(name, { keepParens: true })
    const normalizedAliases = aliases.map(normalizeText)
    const queryTokens = tokenize(query).filter((token) => !STOPWORDS.has(token))
    const nameTokens = tokenize(name, { keepParens: true })
    const aliasTokens = tokenize(aliases.join(' '))
    const queryLooksGeneric = queryTokens.length === 1
    const primaryToken = queryTokens[0] || ''
    const normalizedQuery = normalizeText(query, { keepParens: true })

    let score = 0

    if (queryLooksGeneric && primaryToken) {
        const tokenVariants = new Set(buildTokenVariants(primaryToken))
        const allTokens = [...nameTokens, ...aliasTokens]
        const hasUsefulTokenMatch = allTokens.some((token) =>
            tokenVariants.has(token) || token.startsWith(primaryToken) || isFuzzyTokenMatch(primaryToken, token)
        )

        if (!hasUsefulTokenMatch) {
            return { ...nutrient, matchScore: -9999 }
        }
    }

    if (normalizedName === normalizedQuery) score += 2000
    if (normalizedAliases.some((alias) => alias === normalizedQuery)) score += 1800
    if (normalizedName.startsWith(normalizedQuery)) score += 900
    if (normalizedAliases.some((alias) => alias.startsWith(normalizedQuery))) score += 1000

    if (nameTokens[0] === primaryToken) score += 220
    if (aliasTokens[0] === primaryToken) score += 260

    let matchedTokens = 0
    let earliestPosition = 999

    for (const token of queryTokens) {
        const nameMatch = findTokenRelationIndex(nameTokens, token)
        const aliasMatch = findTokenRelationIndex(aliasTokens, token)

        let tokenScore = 0
        if (aliasMatch.relation === 'exact') tokenScore = 240
        else if (nameMatch.relation === 'exact') tokenScore = 180
        else if (aliasMatch.relation === 'derived') tokenScore = queryLooksGeneric ? 150 : 50
        else if (nameMatch.relation === 'derived') tokenScore = queryLooksGeneric ? 110 : 30
        else if (aliasMatch.relation === 'fuzzy') tokenScore = queryLooksGeneric ? 95 : 45
        else if (nameMatch.relation === 'fuzzy') tokenScore = queryLooksGeneric ? 80 : 35

        if (tokenScore > 0) {
            matchedTokens += 1
            const matchIndexes = [aliasMatch.index, nameMatch.index].filter((idx) => idx >= 0)
            earliestPosition = Math.min(earliestPosition, ...matchIndexes)
            score += tokenScore
        }
    }

    const fullCoverage = queryTokens.length > 0 && matchedTokens === queryTokens.length
    if (fullCoverage) score += 220
    else score -= (queryTokens.length - matchedTokens) * 180

    if (earliestPosition < 999) score -= earliestPosition * 30

    score -= Math.max(0, nameTokens.length - Math.max(queryTokens.length, 1)) * 20

    if (queryLooksGeneric) {
        const aliasContainsPrimary = aliasTokens.some((token) => isInflectionalTokenMatch(primaryToken, token))
        const nameContainsPrimary = nameTokens.some((token) => isInflectionalTokenMatch(primaryToken, token))
        const derivedPrefixCount = nameTokens.filter((token) => isDerivedPrefixMatch(primaryToken, token)).length
        const aliasPrefixMatch = findPrefixMatch(aliasTokens, primaryToken)
        const namePrefixMatch = findPrefixMatch(nameTokens, primaryToken)

        if (aliasContainsPrimary) score += 280
        if (nameContainsPrimary) score += 120
        score -= derivedPrefixCount * 180

        if (!aliasContainsPrimary && aliasPrefixMatch.found) {
            score += Math.max(0, 240 - aliasPrefixMatch.delta * 60)
            score -= aliasPrefixMatch.index * 8
        }
        if (!nameContainsPrimary && namePrefixMatch.found) {
            score += Math.max(0, 140 - namePrefixMatch.delta * 45)
            score -= namePrefixMatch.index * 14
        }
    }

    return { ...nutrient, matchScore: score }
}

export default function NutrientAutocomplete({ allNutrients, addedNutrientIds, onAdd, userId }) {
    const [query, setQuery] = useState('')
    const [results, setResults] = useState([])
    const [showDropdown, setShowDropdown] = useState(false)
    const [selectedIndex, setSelectedIndex] = useState(-1)
    const containerRef = useRef(null)
    const sessionRef = useRef(null)
    const logDebounceRef = useRef(null)

    useEffect(() => {
        const handleClickOutside = (e) => {
            if (containerRef.current && !containerRef.current.contains(e.target)) {
                setShowDropdown(false)
            }
        }
        document.addEventListener('mousedown', handleClickOutside)
        return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    useEffect(() => () => {
        clearTimeout(logDebounceRef.current)
    }, [])

    const search = (q) => {
        if (!q || q.trim().length < 1) {
            setResults(rankDefaultNutrients(allNutrients).filter((n) => !addedNutrientIds.has(n.id)))
            setSelectedIndex(-1)
            return
        }

        const ranked = allNutrients
            .filter((n) => {
                const lowerName = n.name.toLowerCase()
                if (SKIP_NAMES.has(lowerName)) return false
                if (lowerName.includes('do not use')) return false
                if (addedNutrientIds.has(n.id)) return false
                return true
            })
            .map((n) => scoreNutrientMatch(n, q))
            .filter((n) => n.matchScore > -5000)
            .sort((a, b) => {
                if (b.matchScore !== a.matchScore) return b.matchScore - a.matchScore
                return (a.rank || 99999) - (b.rank || 99999)
            })

        setResults(ranked.slice(0, 15))
        setSelectedIndex(-1)
    }

    const scheduleLogStep = (q, shownResults) => {
        clearTimeout(logDebounceRef.current)
        logDebounceRef.current = setTimeout(() => {
            appendSearchStep(sessionRef, {
                query: q,
                shownOptions: shownResults,
                optionType: 'nutrient',
                inputSource: 'typed',
            })
        }, SEARCH_LOG_DEBOUNCE_MS)
    }

    const handleInputChange = (e) => {
        const val = e.target.value
        setQuery(val)
        setShowDropdown(true)
        search(val)
    }

    const handleSelect = (nutrient) => {
        clearTimeout(logDebounceRef.current)
        void persistSearchSession(sessionRef, {
            userId,
            status: 'resolved',
            selectedOption: {
                id: nutrient.id,
                label: nutrient.name,
                type: nutrient.id ? 'nutrient' : 'custom_nutrient',
            },
        })
        onAdd({
            nutrient_id: nutrient.id || null,
            is_custom_nutrient: !nutrient.id,
            nutrient_name: nutrient.name,
            raw_nutrient_name: nutrient.name,
            unit: formatUnit(nutrient.unit_name),
            basis: 'per_100g',
            value: null,
            sample_size: null,
            confidence: null,
            source_citation: null,
            metadata: {},
        })
        setQuery('')
        setShowDropdown(false)
        setResults([])
    }

    const handleBlur = () => {
        setTimeout(() => {
            if (!sessionRef.current) return
            clearTimeout(logDebounceRef.current)
            void persistSearchSession(sessionRef, {
                userId,
                status: 'abandoned',
            })
        }, 200)
    }

    useEffect(() => {
        if (!showDropdown) return
        scheduleLogStep(query, results)
    }, [query, results, showDropdown])

    const handleKeyDown = (e) => {
        if (!showDropdown || query.length === 0) return

        const maxIndex = results.length === 0 ? 0 : results.length - 1

        if (e.key === 'ArrowDown') {
            e.preventDefault()
            setSelectedIndex((i) => Math.min(i + 1, maxIndex))
        } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setSelectedIndex((i) => Math.max(i - 1, 0))
        } else if (e.key === 'Enter') {
            e.preventDefault()
            if (results.length === 0) {
                handleSelect({ id: null, name: query, unit_name: 'g/100g' })
            } else if (selectedIndex >= 0) {
                handleSelect(results[selectedIndex])
            }
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
                onFocus={() => {
                    setShowDropdown(true)
                    search(query)
                }}
                onBlur={handleBlur}
                onKeyDown={handleKeyDown}
            />

            {showDropdown && (
                <div className="autocomplete-dropdown">
                    {query.length >= 1 && results.length === 0 ? (
                        <div
                            className={`autocomplete-item custom-nutrient-option ${selectedIndex === 0 || selectedIndex === -1 ? 'selected' : ''}`}
                            onMouseDown={() => handleSelect({ id: null, name: query, unit_name: 'g/100g' })}
                            onMouseEnter={() => setSelectedIndex(0)}
                        >
                            <span className="autocomplete-name"><strong>+ Add "{query}"</strong> as custom nutrient</span>
                        </div>
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

