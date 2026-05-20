import { EVIDENCE_STATUS } from './EvidenceLocations.js'

const STORAGE_KEY = 'opennutri-evidence-status-cache:v1'
const MAX_PAPERS = 64

function readSnapshot() {
    if (typeof window === 'undefined') return { order: [], byPaperId: {} }
    try {
        const raw = window.localStorage.getItem(STORAGE_KEY)
        if (!raw) return { order: [], byPaperId: {} }
        const parsed = JSON.parse(raw)
        if (!parsed || typeof parsed !== 'object') return { order: [], byPaperId: {} }
        const order = Array.isArray(parsed.order) ? parsed.order.map(String) : []
        const byPaperId = parsed.byPaperId && typeof parsed.byPaperId === 'object' ? parsed.byPaperId : {}
        return { order, byPaperId }
    } catch {
        return { order: [], byPaperId: {} }
    }
}

function writeSnapshot(snapshot) {
    if (typeof window === 'undefined') return
    try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot))
    } catch {
        try {
            const fallback = {
                order: snapshot.order.slice(0, 1),
                byPaperId: snapshot.order.length
                    ? { [snapshot.order[0]]: snapshot.byPaperId[snapshot.order[0]] }
                    : {},
            }
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(fallback))
        } catch {
            // Give up silently.
        }
    }
}

export function readEvidenceStatusCache(paperId) {
    if (!paperId) return null
    const snapshot = readSnapshot()
    return snapshot.byPaperId[String(paperId)] || null
}

export function writeEvidenceStatusCache(paperId, payload) {
    if (!paperId) return
    if (!payload || Object.keys(payload).length === 0) return
    const key = String(paperId)
    const snapshot = readSnapshot()
    const existing = snapshot.byPaperId[key] || {}
    const merged = { ...existing, ...payload }
    snapshot.byPaperId[key] = merged
    snapshot.order = [key, ...snapshot.order.filter((id) => id !== key)]
    while (snapshot.order.length > MAX_PAPERS) {
        const oldest = snapshot.order.pop()
        delete snapshot.byPaperId[oldest]
    }
    writeSnapshot(snapshot)
}

export function buildCachePayloadFromStatuses(evidenceLocations, statuses) {
    const payload = {}
    for (const location of evidenceLocations || []) {
        if (!location?.id || !location.groupKey) continue
        const status = statuses?.[location.id]
        if (!status) continue
        if (status.status !== EVIDENCE_STATUS.MATCHED || !status.regionKey) continue
        payload[location.groupKey] = {
            regionKey: status.regionKey,
            matchType: status.matchType || 'text',
            pageNumber: status.pageNumber || null,
            label: status.label || null,
            regionBounds: normalizeBounds(status.regionBounds),
        }
    }
    return payload
}

function normalizeBounds(bounds) {
    if (!bounds || typeof bounds !== 'object') return null
    const { left, right, top, bottom } = bounds
    if ([left, right, top, bottom].some((value) => typeof value !== 'number' || !Number.isFinite(value))) {
        return null
    }
    return { left, right, top, bottom }
}

export function applyCachedDedup(locations, cache) {
    if (!Array.isArray(locations) || locations.length < 2) return locations
    if (!cache || typeof cache !== 'object') return locations

    const buckets = new Map()
    const unbucketed = []
    for (const location of locations) {
        if (!location?.groupKey) {
            unbucketed.push(location)
            continue
        }
        const cached = cache[location.groupKey]
        const regionKey = cached?.regionKey
        if (!regionKey) {
            unbucketed.push(location)
            continue
        }
        const bucket = buckets.get(regionKey) || []
        bucket.push(location)
        buckets.set(regionKey, bucket)
    }

    if (buckets.size === 0) return locations

    const result = [...unbucketed]
    for (const bucket of buckets.values()) {
        if (bucket.length === 1) {
            result.push(bucket[0])
            continue
        }
        bucket.sort((a, b) => (b.sourceQuote?.length || 0) - (a.sourceQuote?.length || 0))
        const canonical = { ...bucket[0] }
        const foodNames = new Set(canonical.foodNames || [])
        const nutrientNames = new Set(canonical.nutrientNames || [])
        let rowCount = canonical.rowCount || 0
        for (let i = 1; i < bucket.length; i += 1) {
            const other = bucket[i]
            rowCount += other.rowCount || 0
            for (const name of other.foodNames || []) foodNames.add(name)
            for (const name of other.nutrientNames || []) nutrientNames.add(name)
            if (!canonical.pageHint && other.pageHint) canonical.pageHint = other.pageHint
            if (!canonical.sourceCitation && other.sourceCitation) canonical.sourceCitation = other.sourceCitation
        }
        canonical.foodNames = Array.from(foodNames)
        canonical.nutrientNames = Array.from(nutrientNames)
        canonical.rowCount = rowCount
        result.push(canonical)
    }

    return result
}
