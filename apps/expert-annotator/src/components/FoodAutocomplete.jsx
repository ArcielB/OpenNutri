import { useState, useEffect, useRef } from 'react'
import { supabase } from '../supabaseClient'
import { appendSearchStep, persistSearchSession } from '../utils/searchSessionLogger'

const NOISY_PREFIXES = new Set([
    'babyfood',
    'baby food',
    'fast foods',
    'beverages',
    'restaurant',
    'school lunch',
    'usda commodity',
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
])

const PROCESSING_WORDS = new Set([
    'juice',
    'sauce',
    'dessert',
    'babyfood',
    'baby',
    'yogurt',
    'pie',
    'blend',
    'concentrate',
    'canned',
    'bottled',
    'frozen',
    'dried',
    'strained',
    'sweetened',
    'unsweetened',
    'toasted',
    'microwaved',
    'cooked',
    'boiled',
    'baked',
    'fried',
    'roasted',
    'grilled',
    'stewed',
    'powder',
    'drink',
    'beverage',
])

const WHOLE_FOOD_HINTS = new Set([
    'raw',
    'fresh',
    'with',
    'skin',
    'without',
    'peel',
])

const IRREGULAR_TOKEN_MAP = {
    mice: 'mouse',
    geese: 'goose',
    teeth: 'tooth',
    feet: 'foot',
    children: 'child',
    men: 'man',
    women: 'woman',
}

function normalizeText(value) {
    return value
        .toLowerCase()
        .replace(/['’]/g, '')
        .replace(/[^a-z0-9]+/g, ' ')
        .trim()
}

function normalizeToken(token) {
    if (!token) return token
    if (IRREGULAR_TOKEN_MAP[token]) return IRREGULAR_TOKEN_MAP[token]
    if (token.endsWith('ies') && token.length > 4) return `${token.slice(0, -3)}y`
    if (token.endsWith('oes') && token.length > 4) return token.slice(0, -2)
    if (
        token.endsWith('s') &&
        token.length > 3 &&
        !token.endsWith('ss') &&
        !token.endsWith('us') &&
        !token.endsWith('is')
    ) return token.slice(0, -1)
    return token
}

function tokenize(value) {
    return normalizeText(value)
        .split(/\s+/)
        .filter(Boolean)
        .map(normalizeToken)
}

function isInflectionalTokenMatch(queryToken, candidateToken) {
    if (!queryToken || !candidateToken) return false
    if (candidateToken === queryToken) return true

    const singularQuery = normalizeToken(queryToken)
    const singularCandidate = normalizeToken(candidateToken)

    return singularCandidate === singularQuery
}

function isDerivedPrefixMatch(queryToken, candidateToken) {
    if (!queryToken || !candidateToken) return false
    if (!candidateToken.startsWith(queryToken)) return false
    if (isInflectionalTokenMatch(queryToken, candidateToken)) return false
    return candidateToken.length - queryToken.length >= 2
}

function findTokenRelationIndex(tokens, queryToken) {
    const exactIndex = tokens.findIndex((candidate) => isInflectionalTokenMatch(queryToken, candidate))
    if (exactIndex >= 0) {
        return { relation: 'exact', index: exactIndex }
    }

    const derivedIndex = tokens.findIndex((candidate) => isDerivedPrefixMatch(queryToken, candidate))
    if (derivedIndex >= 0) {
        return { relation: 'derived', index: derivedIndex }
    }

    return { relation: 'none', index: -1 }
}

function findPrefixMatch(tokens, queryToken) {
    let bestIndex = -1
    let bestDelta = 999

    tokens.forEach((candidate, index) => {
        if (!candidate.startsWith(queryToken)) return
        const delta = candidate.length - queryToken.length
        if (delta < 0) return
        if (delta < bestDelta) {
            bestDelta = delta
            bestIndex = index
        }
    })

    if (bestIndex < 0) {
        return { found: false, index: -1, delta: 999 }
    }

    return { found: true, index: bestIndex, delta: bestDelta }
}

function extractBaseName(canonicalName) {
    const parts = canonicalName
        .split(',')
        .map((part) => part.trim())
        .filter(Boolean)

    if (parts.length === 0) return canonicalName

    const firstPart = normalizeText(parts[0])
    if (parts.length > 1 && NOISY_PREFIXES.has(firstPart)) {
        return parts[1]
    }

    return parts[0]
}

function extractAliasSegments(value) {
    return [...value.matchAll(/\(([^)]+)\)/g)]
        .map((match) => match[1]?.trim())
        .filter(Boolean)
}

function escapeLike(value) {
    return value.replace(/[%_,]/g, ' ')
}

function buildQueryTerms(query) {
    const normalized = normalizeText(query)
    const words = normalized.split(/\s+/).filter(Boolean)
    const meaningfulWords = words.filter((word) => !STOPWORDS.has(word))
    const terms = [normalized, ...meaningfulWords]
        .filter((term) => term.length >= 2)
        .slice(0, 4)

    return [...new Set(terms)]
}

function buildTokenVariants(token) {
    const variants = new Set([token, normalizeToken(token)])
    const singular = normalizeToken(token)
    if (singular.endsWith('y')) variants.add(`${singular.slice(0, -1)}ies`)
    variants.add(`${singular}s`)
    variants.add(`${singular}oes`)
    return [...variants].filter((value) => value.length >= 2)
}

function dedupeFoods(rows) {
    const seen = new Set()
    const result = []
    for (const row of rows) {
        if (!row?.id || seen.has(row.id)) continue
        seen.add(row.id)
        result.push(row)
    }
    return result
}

function rankFoods(rows, query) {
    return dedupeFoods(rows)
        .map((food) => scoreFoodMatch(food, query))
        .filter((food) => food.matchScore > -5000)
        .sort((a, b) => {
            if (b.matchScore !== a.matchScore) return b.matchScore - a.matchScore
            return a.canonical_name.localeCompare(b.canonical_name)
        })
        .slice(0, 15)
}

function rankDefaultFoods(rows) {
    return dedupeFoods(rows)
        .sort((a, b) => {
            const aLen = (a.canonical_name || '').length
            const bLen = (b.canonical_name || '').length
            if (aLen !== bLen) return aLen - bLen
            return (a.canonical_name || '').localeCompare(b.canonical_name || '')
        })
        .slice(0, 15)
}

function scoreFoodMatch(food, query) {
    const canonical = food.canonical_name || ''
    const baseName = extractBaseName(canonical)
    const aliasSegments = extractAliasSegments(canonical)

    const normalizedQuery = normalizeText(query)
    const queryTokens = tokenize(query).filter((token) => !STOPWORDS.has(token))
    const canonicalTokens = tokenize(canonical)
    const baseTokens = tokenize(baseName)
    const aliasTokens = tokenize(aliasSegments.join(' '))

    const normalizedCanonical = normalizeText(canonical)
    const normalizedBase = normalizeText(baseName)
    const normalizedAliases = aliasSegments.map(normalizeText)
    const queryLooksGeneric = queryTokens.length === 1
    const primaryToken = queryTokens[0] || ''

    let score = 0

    if (queryLooksGeneric && primaryToken) {
        const tokenVariants = new Set(buildTokenVariants(primaryToken))
        const allTokens = [...canonicalTokens, ...aliasTokens]
        const hasUsefulTokenMatch = allTokens.some((token) =>
            tokenVariants.has(token) || token.startsWith(primaryToken)
        )
        if (!hasUsefulTokenMatch) {
            return {
                ...food,
                matchScore: -9999,
            }
        }
    }

    if (normalizedCanonical === normalizedQuery) score += 2000
    if (normalizedBase === normalizedQuery) score += 1700
    if (normalizedAliases.some((alias) => alias === normalizedQuery)) score += 1600

    if (normalizedCanonical.startsWith(normalizedQuery)) score += 900
    if (normalizedBase.startsWith(normalizedQuery)) score += 1200
    if (normalizedAliases.some((alias) => alias.startsWith(normalizedQuery))) score += 800

    if (canonicalTokens[0] === queryTokens[0]) score += 180
    if (baseTokens[0] === queryTokens[0]) score += 260
    if (aliasTokens[0] === queryTokens[0]) score += 180

    let matchedTokens = 0
    let earliestPosition = 999

    for (const token of queryTokens) {
        const baseMatch = findTokenRelationIndex(baseTokens, token)
        const canonicalMatch = findTokenRelationIndex(canonicalTokens, token)
        const aliasMatch = findTokenRelationIndex(aliasTokens, token)

        let tokenScore = 0
        if (baseMatch.relation === 'exact') tokenScore = 260
        else if (canonicalMatch.relation === 'exact') tokenScore = 180
        else if (aliasMatch.relation === 'exact') tokenScore = 170
        else if (baseMatch.relation === 'derived') tokenScore = queryLooksGeneric ? 180 : 80
        else if (canonicalMatch.relation === 'derived') tokenScore = queryLooksGeneric ? 120 : 40
        else if (aliasMatch.relation === 'derived') tokenScore = queryLooksGeneric ? 110 : 30

        if (tokenScore > 0) {
            matchedTokens += 1
            const matchIndexes = [baseMatch.index, canonicalMatch.index, aliasMatch.index].filter((idx) => idx >= 0)
            earliestPosition = Math.min(
                earliestPosition,
                ...matchIndexes
            )
            score += tokenScore
        }
    }

    const fullCoverage = queryTokens.length > 0 && matchedTokens === queryTokens.length
    if (fullCoverage) score += 260
    else score -= (queryTokens.length - matchedTokens) * 180

    if (earliestPosition < 999) score -= earliestPosition * 35

    score -= Math.max(0, baseTokens.length - Math.max(queryTokens.length, 1)) * 18
    score -= Math.max(0, canonicalTokens.length - baseTokens.length) * 10

    if (queryLooksGeneric) {
        const extraProcessingWords = canonicalTokens.filter(
            (token) => PROCESSING_WORDS.has(token) && !queryTokens.includes(token)
        ).length
        score -= extraProcessingWords * 55

        const baseContainsPrimary = baseTokens.some((token) => isInflectionalTokenMatch(primaryToken, token))
        const canonicalContainsPrimary = canonicalTokens.some((token) => isInflectionalTokenMatch(primaryToken, token))
        const aliasContainsPrimary = aliasTokens.some((token) => isInflectionalTokenMatch(primaryToken, token))
        const startsWithPrimary = baseTokens[0] === primaryToken || canonicalTokens[0] === primaryToken
        const wholeFoodHints = canonicalTokens.filter((token) => WHOLE_FOOD_HINTS.has(token)).length
        const derivedPrefixCount = canonicalTokens.filter((token) => isDerivedPrefixMatch(primaryToken, token)).length
        const basePrefixMatch = findPrefixMatch(baseTokens, primaryToken)
        const canonicalPrefixMatch = findPrefixMatch(canonicalTokens, primaryToken)
        const aliasPrefixMatch = findPrefixMatch(aliasTokens, primaryToken)

        if (startsWithPrimary) score += 120
        if (baseContainsPrimary) score += 220
        if (canonicalContainsPrimary) score += 100
        if (aliasContainsPrimary) score += 150
        if (wholeFoodHints > 0) score += Math.min(wholeFoodHints, 2) * 45
        score -= derivedPrefixCount * 140

        if (!baseContainsPrimary && basePrefixMatch.found) {
            score += Math.max(0, 260 - basePrefixMatch.delta * 70)
            score -= basePrefixMatch.index * 25
        }
        if (!canonicalContainsPrimary && canonicalPrefixMatch.found) {
            score += Math.max(0, 170 - canonicalPrefixMatch.delta * 55)
            score -= canonicalPrefixMatch.index * 18
        }
        if (!aliasContainsPrimary && aliasPrefixMatch.found) {
            score += Math.max(0, 200 - aliasPrefixMatch.delta * 60)
            score -= aliasPrefixMatch.index * 10
        }

        const hasProcessedPrimaryPair = canonicalTokens.some(
            (token, idx) => isInflectionalTokenMatch(primaryToken, token) && PROCESSING_WORDS.has(canonicalTokens[idx + 1])
        )
        if (hasProcessedPrimaryPair) score -= 180

        if (canonicalTokens.includes('babyfood') || canonicalTokens.includes('baby')) score -= 180
        if (canonicalTokens.includes('restaurant')) score -= 180
    }

    if (canonical.includes(',')) score -= (canonical.match(/,/g) || []).length * 8

    return {
        ...food,
        matchScore: score,
    }
}

export default function FoodAutocomplete({ value, foodFdcId, onChange, allFoods = [], foodsLoaded = false, userId }) {
    const [query, setQuery] = useState(value || '')
    const [results, setResults] = useState([])
    const [showDropdown, setShowDropdown] = useState(false)
    const [loading, setLoading] = useState(false)
    const [selectedIndex, setSelectedIndex] = useState(-1)
    const debounceRef = useRef(null)
    const containerRef = useRef(null)
    const sessionRef = useRef(null)

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
        if (!q || q.trim().length < 1) {
            if (foodsLoaded) {
                setLoading(false)
                const ranked = rankDefaultFoods(allFoods)
                setResults(ranked)
                setSelectedIndex(-1)
            } else {
                setResults([])
            }
            return
        }

        if (foodsLoaded) {
            setLoading(false)
            const ranked = rankFoods(allFoods, q)
            setResults(ranked)
            setSelectedIndex(-1)
            appendSearchStep(sessionRef, {
                query: q,
                shownOptions: ranked,
                optionType: 'food',
                inputSource: 'typed',
            })
            return
        }

        setLoading(true)
        try {
            const queryTerms = buildQueryTerms(q)
            if (queryTerms.length === 0) {
                setResults([])
                return
            }

            const primaryToken = tokenize(q).find((token) => !STOPWORDS.has(token)) || ''
            const tokenVariants = primaryToken ? buildTokenVariants(primaryToken) : []

            const prefixFilters = tokenVariants
                .map((term) => `canonical_name.ilike.${escapeLike(term)}%`)
                .join(',')

            const broadFilters = [...new Set([
                ...queryTerms.map((term) => `canonical_name.ilike.%${escapeLike(term)}%`),
                ...tokenVariants.map((term) => `canonical_name.ilike.%${escapeLike(term)}%`),
            ])].join(',')

            const [prefixRes, broadRes] = await Promise.all([
                prefixFilters
                    ? supabase
                        .from('entities')
                        .select('id, canonical_name, category')
                        .or(prefixFilters)
                        .limit(60)
                    : Promise.resolve({ data: [], error: null }),
                supabase
                    .from('entities')
                    .select('id, canonical_name, category')
                    .or(broadFilters)
                    .limit(160),
            ])

            if (prefixRes.error) throw prefixRes.error
            if (broadRes.error) throw broadRes.error

            const ranked = rankFoods([...(prefixRes.data || []), ...(broadRes.data || [])], q)

            setResults(ranked)
            setSelectedIndex(-1)
            appendSearchStep(sessionRef, {
                query: q,
                shownOptions: ranked,
                optionType: 'food',
                inputSource: 'typed',
            })
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
        clearTimeout(debounceRef.current)
        void persistSearchSession(sessionRef, {
            userId,
            status: 'resolved',
            selectedOption: {
                id: food.id,
                label: food.canonical_name,
                type: 'food',
            },
        })
        setQuery(food.canonical_name)
        setShowDropdown(false)
        onChange({
            food_name: food.canonical_name,
            food_fdc_id: food.id,
            is_custom_food: false,
        })
    }

    const handleBlur = () => {
        // Delay to allow click on dropdown item
        setTimeout(() => {
            const trimmedQuery = query.trim()
            if (query && query !== value) {
                onChange({
                    food_name: trimmedQuery,
                    food_fdc_id: null,
                    is_custom_food: true,
                })
            }
            if (sessionRef.current) {
                clearTimeout(debounceRef.current)
                if (trimmedQuery) {
                    void persistSearchSession(sessionRef, {
                        userId,
                        status: 'resolved',
                        selectedOption: {
                            id: null,
                            label: trimmedQuery,
                            type: 'custom_food',
                        },
                    })
                } else {
                    void persistSearchSession(sessionRef, {
                        userId,
                        status: 'abandoned',
                    })
                }
            }
        }, 200)
    }

    const handleKeyDown = (e) => {
        if (!showDropdown) return

        if (e.key === 'ArrowDown' && results.length > 0) {
            e.preventDefault()
            setSelectedIndex((i) => Math.min(i + 1, results.length - 1))
        } else if (e.key === 'ArrowUp' && results.length > 0) {
            e.preventDefault()
            setSelectedIndex((i) => Math.max(i - 1, 0))
        } else if (e.key === 'Enter') {
            e.preventDefault()
            if (selectedIndex >= 0 && results.length > 0) {
                // Select matched food
                handleSelect(results[selectedIndex])
            } else if (query.trim().length >= 2) {
                // Accept as custom food
                setShowDropdown(false)
                clearTimeout(debounceRef.current)
                void persistSearchSession(sessionRef, {
                    userId,
                    status: 'resolved',
                    selectedOption: {
                        id: null,
                        label: query.trim(),
                        type: 'custom_food',
                    },
                })
                onChange({
                    food_name: query.trim(),
                    food_fdc_id: null,
                    is_custom_food: true,
                })
            }
        } else if (e.key === 'Escape') {
            setShowDropdown(false)
        }
    }

    return (
        <div className="food-autocomplete" ref={containerRef}>
            <input
                className={`food-name-input ${!foodFdcId && query ? 'custom-food-input' : ''}`}
                type="text"
                placeholder="Search food name..."
                value={query}
                onChange={handleInputChange}
                onFocus={() => {
                    setShowDropdown(true)
                    search(query)
                }}
                onBlur={handleBlur}
                onKeyDown={handleKeyDown}
            />
            {foodFdcId && (
                <span className="food-match-badge">✓ Matched</span>
            )}
            {!foodFdcId && query && (
                <span className="food-custom-badge">Custom</span>
            )}

            {showDropdown && (
                <div className="autocomplete-dropdown">
                    {loading && (
                        <div className="autocomplete-item loading">Searching...</div>
                    )}
                    {!loading && results.length === 0 && !foodsLoaded && allFoods.length === 0 && query.length < 1 && (
                        <div className="autocomplete-item loading">Loading full food catalog in background...</div>
                    )}
                    {!loading && results.length === 0 && query.length >= 1 && (
                        <div className="autocomplete-item empty">
                            No matches — press Enter to use as custom food
                        </div>
                    )}
                    {results.map((food, idx) => (
                        <div
                            key={food.id}
                            className={`autocomplete-item ${idx === selectedIndex ? 'selected' : ''}`}
                            onMouseDown={() => handleSelect(food)}
                            onMouseEnter={() => setSelectedIndex(idx)}
                        >
                            <span className="autocomplete-name">{food.canonical_name}</span>
                            {food.category && (
                                <span className="autocomplete-category">
                                    {food.category}
                                </span>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
