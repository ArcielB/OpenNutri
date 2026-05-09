const IRREGULAR_TOKEN_MAP = {
    mice: 'mouse',
    geese: 'goose',
    teeth: 'tooth',
    feet: 'foot',
    children: 'child',
    men: 'man',
    women: 'woman',
}

export function normalizeText(value, { keepParens = false } = {}) {
    const source = (value || '').toLowerCase().replace(/['â€™]/g, '')
    const pattern = keepParens ? /[^a-z0-9()]+/g : /[^a-z0-9]+/g
    return source.replace(pattern, ' ').trim()
}

export function normalizeToken(token) {
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

export function tokenize(value, { keepParens = false } = {}) {
    const normalized = normalizeText(value, { keepParens })
    const cleaned = keepParens ? normalized.replace(/[()]/g, ' ') : normalized
    return cleaned
        .split(/\s+/)
        .filter(Boolean)
        .map(normalizeToken)
}

export function extractAliasSegments(value) {
    return [...(value || '').matchAll(/\(([^)]+)\)/g)]
        .map((match) => match[1]?.trim())
        .filter(Boolean)
}

export function isInflectionalTokenMatch(queryToken, candidateToken) {
    if (!queryToken || !candidateToken) return false
    return normalizeToken(queryToken) === normalizeToken(candidateToken)
}

export function isDerivedPrefixMatch(queryToken, candidateToken) {
    if (!queryToken || !candidateToken) return false
    if (!candidateToken.startsWith(queryToken)) return false
    if (isInflectionalTokenMatch(queryToken, candidateToken)) return false
    return candidateToken.length - queryToken.length >= 2
}

function levenshteinDistance(a, b, maxDistance = 2) {
    if (a === b) return 0
    const aLen = a.length
    const bLen = b.length
    if (Math.abs(aLen - bLen) > maxDistance) return maxDistance + 1
    if (aLen === 0) return bLen
    if (bLen === 0) return aLen

    let previous = new Array(bLen + 1)
    let current = new Array(bLen + 1)

    for (let j = 0; j <= bLen; j += 1) previous[j] = j

    for (let i = 1; i <= aLen; i += 1) {
        current[0] = i
        let minInRow = current[0]
        const aChar = a.charCodeAt(i - 1)
        for (let j = 1; j <= bLen; j += 1) {
            const cost = aChar === b.charCodeAt(j - 1) ? 0 : 1
            current[j] = Math.min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + cost
            )
            if (current[j] < minInRow) minInRow = current[j]
        }
        if (minInRow > maxDistance) return maxDistance + 1
        const swap = previous
        previous = current
        current = swap
    }

    return previous[bLen]
}

function getAllowedFuzzyDistance(tokenLength) {
    if (tokenLength >= 8) return 2
    if (tokenLength >= 4) return 1
    return 0
}

function isSingleAdjacentTransposition(left, right) {
    if (!left || !right) return false
    if (left.length !== right.length || left.length < 2) return false
    const mismatches = []
    for (let index = 0; index < left.length; index += 1) {
        if (left[index] !== right[index]) mismatches.push(index)
        if (mismatches.length > 2) return false
    }
    if (mismatches.length !== 2) return false
    const [first, second] = mismatches
    if (second !== first + 1) return false
    return left[first] === right[second] && left[second] === right[first]
}

export function isFuzzyTokenMatch(queryToken, candidateToken) {
    if (!queryToken || !candidateToken) return false
    const query = normalizeToken(queryToken)
    const candidate = normalizeToken(candidateToken)
    if (!query || !candidate) return false
    if (query === candidate) return false
    if (isSingleAdjacentTransposition(query, candidate)) return true
    const allowed = getAllowedFuzzyDistance(Math.max(query.length, candidate.length))
    if (allowed <= 0) return false
    const distance = levenshteinDistance(query, candidate, allowed)
    return distance <= allowed
}

export function findTokenRelationIndex(tokens, queryToken) {
    const exactIndex = tokens.findIndex((candidate) => isInflectionalTokenMatch(queryToken, candidate))
    if (exactIndex >= 0) return { relation: 'exact', index: exactIndex }

    const derivedIndex = tokens.findIndex((candidate) => isDerivedPrefixMatch(queryToken, candidate))
    if (derivedIndex >= 0) return { relation: 'derived', index: derivedIndex }

    const fuzzyIndex = tokens.findIndex((candidate) => isFuzzyTokenMatch(queryToken, candidate))
    if (fuzzyIndex >= 0) return { relation: 'fuzzy', index: fuzzyIndex }

    return { relation: 'none', index: -1 }
}

export function findPrefixMatch(tokens, queryToken) {
    let bestIndex = -1
    let bestDelta = 999

    tokens.forEach((candidate, index) => {
        if (!candidate.startsWith(queryToken)) return
        const delta = candidate.length - queryToken.length
        if (delta < bestDelta) {
            bestDelta = delta
            bestIndex = index
        }
    })

    if (bestIndex < 0) return { found: false, index: -1, delta: 999 }
    return { found: true, index: bestIndex, delta: bestDelta }
}

export function buildTokenVariants(token) {
    const singular = normalizeToken(token)
    const variants = new Set([token, singular, `${singular}s`, `${singular}oes`])
    if (singular.endsWith('y')) variants.add(`${singular.slice(0, -1)}ies`)
    return [...variants].filter((value) => value.length >= 2)
}
