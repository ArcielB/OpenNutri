import test from 'node:test'
import assert from 'node:assert/strict'

import { EVIDENCE_STATUS } from './EvidenceLocations.js'
import {
    applyCachedDedup,
    buildCachePayloadFromStatuses,
    readEvidenceStatusCache,
    writeEvidenceStatusCache,
} from './evidenceStatusCache.js'

const memoryStorage = (() => {
    let store = {}
    return {
        getItem: (key) => (key in store ? store[key] : null),
        setItem: (key, value) => { store[key] = String(value) },
        removeItem: (key) => { delete store[key] },
        clear: () => { store = {} },
    }
})()

globalThis.window = { localStorage: memoryStorage }

test('writeEvidenceStatusCache merges new entries with existing entries for the paper', () => {
    memoryStorage.clear()
    writeEvidenceStatusCache('paper-1', {
        'g-a': { regionKey: 'R1', matchType: 'paragraph', pageNumber: 3, label: null },
        'g-b': { regionKey: 'R1', matchType: 'paragraph', pageNumber: 3, label: null },
    })
    writeEvidenceStatusCache('paper-1', {
        'g-c': { regionKey: 'R2', matchType: 'paragraph', pageNumber: 5, label: null },
    })

    const cache = readEvidenceStatusCache('paper-1')
    assert.equal(cache['g-a'].regionKey, 'R1')
    assert.equal(cache['g-b'].regionKey, 'R1')
    assert.equal(cache['g-c'].regionKey, 'R2')
})

test('applyCachedDedup collapses locations whose groupKeys share a regionKey in cache', () => {
    const cache = {
        'g-1': { regionKey: 'R1' },
        'g-2': { regionKey: 'R1' },
        'g-3': { regionKey: 'R1' },
        'g-4': { regionKey: 'R2' },
    }
    const locations = [
        { id: 'evidence-1', groupKey: 'g-1', sourceQuote: 'short', foodNames: ['A'], nutrientNames: ['Iron'], rowCount: 1 },
        { id: 'evidence-2', groupKey: 'g-2', sourceQuote: 'a longer quote with more words', foodNames: ['B'], nutrientNames: ['Calcium'], rowCount: 1 },
        { id: 'evidence-3', groupKey: 'g-3', sourceQuote: 'medium quote', foodNames: ['C'], nutrientNames: ['Vitamin C'], rowCount: 1 },
        { id: 'evidence-4', groupKey: 'g-4', sourceQuote: 'unrelated quote', foodNames: ['D'], nutrientNames: ['Zinc'], rowCount: 1 },
    ]

    const result = applyCachedDedup(locations, cache)
    assert.equal(result.length, 2)
    const r1 = result.find((location) => location.groupKey === 'g-2')
    const r2 = result.find((location) => location.groupKey === 'g-4')
    assert.ok(r1, 'canonical for R1 is the longest-quote location')
    assert.deepEqual(r1.foodNames.sort(), ['A', 'B', 'C'].sort())
    assert.deepEqual(r1.nutrientNames.sort(), ['Calcium', 'Iron', 'Vitamin C'].sort())
    assert.equal(r1.rowCount, 3)
    assert.ok(r2)
})

test('applyCachedDedup leaves locations alone when cache has no regionKey for them', () => {
    const locations = [
        { id: 'evidence-1', groupKey: 'g-1', sourceQuote: 'x', foodNames: [], nutrientNames: [], rowCount: 1 },
        { id: 'evidence-2', groupKey: 'g-2', sourceQuote: 'y', foodNames: [], nutrientNames: [], rowCount: 1 },
    ]
    const result = applyCachedDedup(locations, {})
    assert.equal(result.length, 2)
})

test('buildCachePayloadFromStatuses ignores non-matched statuses', () => {
    const locations = [
        { id: 'evidence-1', groupKey: 'g-1' },
        { id: 'evidence-2', groupKey: 'g-2' },
    ]
    const statuses = {
        'evidence-1': {
            status: EVIDENCE_STATUS.MATCHED,
            label: 'Matched text',
            pageNumber: 1,
            matchType: 'paragraph',
            regionKey: 'R',
        },
        'evidence-2': { status: EVIDENCE_STATUS.UNVERIFIED, label: 'Unverified' },
    }
    const payload = buildCachePayloadFromStatuses(locations, statuses)
    assert.equal(Object.keys(payload).length, 1)
    assert.equal(payload['g-1'].regionKey, 'R')
})
