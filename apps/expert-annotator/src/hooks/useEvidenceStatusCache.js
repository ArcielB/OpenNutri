import { useCallback, useEffect, useMemo, useState } from 'react'
import { applyCachedDedup, buildCachePayloadFromStatuses } from '../utils/evidenceStatusCache'
import {
    fetchRemoteDedup,
    readLocalDedup,
    writeLocalDedup,
    writeRemoteDedup,
} from '../utils/evidenceDedupStorage'

export function useEvidenceStatusCache(paperId, rawEvidenceLocations) {
    const [dedupCache, setDedupCache] = useState(null)
    const [knownPaperId, setKnownPaperId] = useState(null)
    const [statuses, setStatusesState] = useState({})
    const [lastWriteSignature, setLastWriteSignature] = useState('')

    if (knownPaperId !== paperId) {
        setKnownPaperId(paperId)
        setDedupCache(paperId ? readLocalDedup(paperId) : null)
        setStatusesState({})
        setLastWriteSignature('')
    }

    useEffect(() => {
        if (!paperId) return undefined
        let cancelled = false
        fetchRemoteDedup(paperId).then((remote) => {
            if (cancelled) return
            if (!remote || Object.keys(remote).length === 0) return
            setDedupCache((previous) => {
                const base = previous && typeof previous === 'object' ? previous : {}
                const merged = { ...base, ...remote }
                writeLocalDedup(paperId, merged)
                return merged
            })
        })
        return () => {
            cancelled = true
        }
    }, [paperId])

    const displayEvidenceLocations = useMemo(() => {
        if (!dedupCache || Object.keys(dedupCache).length === 0) return rawEvidenceLocations
        return applyCachedDedup(rawEvidenceLocations, dedupCache)
    }, [dedupCache, rawEvidenceLocations])

    const setStatuses = useCallback(
        (next) => {
            setStatusesState(next)
            if (!paperId) return
            const payload = buildCachePayloadFromStatuses(rawEvidenceLocations, next)
            if (Object.keys(payload).length === 0) return

            const existing = dedupCache && typeof dedupCache === 'object' ? dedupCache : {}
            const merged = { ...existing, ...payload }
            const signature = JSON.stringify(merged)
            if (signature === lastWriteSignature) return

            setLastWriteSignature(signature)
            setDedupCache(merged)
            writeLocalDedup(paperId, merged)
            writeRemoteDedup(paperId, payload).catch(() => {})
        },
        [paperId, rawEvidenceLocations, dedupCache, lastWriteSignature]
    )

    const cachedEvidenceOverlays = useMemo(() => buildCachedEvidenceOverlays(dedupCache), [dedupCache])

    return {
        scanEvidenceLocations: rawEvidenceLocations,
        displayEvidenceLocations,
        evidenceStatuses: statuses,
        setEvidenceStatuses: setStatuses,
        cachedEvidenceOverlays,
    }
}

function buildCachedEvidenceOverlays(dedupCache) {
    if (!dedupCache || typeof dedupCache !== 'object') return null
    const byPage = new Map()
    for (const entry of Object.values(dedupCache)) {
        if (!entry || typeof entry !== 'object') continue
        const { regionBounds, pageNumber, matchType, regionKey } = entry
        if (!regionBounds || !pageNumber || !regionKey) continue
        const bucket = byPage.get(pageNumber) || new Map()
        if (!bucket.has(regionKey)) {
            bucket.set(regionKey, {
                regionKey,
                matchType: matchType || 'paragraph',
                regionBounds,
                pageNumber,
            })
        }
        byPage.set(pageNumber, bucket)
    }
    if (byPage.size === 0) return null
    const result = {}
    for (const [pageNumber, bucket] of byPage.entries()) {
        result[pageNumber] = Array.from(bucket.values())
    }
    return result
}
