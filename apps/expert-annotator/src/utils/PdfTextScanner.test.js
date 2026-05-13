import test from 'node:test'
import assert from 'node:assert/strict'

import { EVIDENCE_STATUS } from './EvidenceLocations.js'
import { buildPageEvidenceHighlightPlan } from './PdfTextScanner.js'

function textItem(str, x, y, width = 200, height = 10) {
    return {
        str,
        width,
        height,
        transform: [1, 0, 0, height, x, y],
    }
}

test('matches a table label to a whole detected table region', () => {
    const plan = buildPageEvidenceHighlightPlan(
        {
            items: [
                textItem('Table 2. Composition of apple samples', 50, 700, 260),
                textItem('Food Protein (g/100g) Fat (g/100g)', 50, 680, 260),
                textItem('Apple 0.3 0.2', 50, 660, 140),
                textItem('Nearby paragraph without composition evidence.', 50, 620, 300),
            ],
        },
        [{ id: 'evidence-1', tableLabel: 'Table 2', pageHint: 5 }],
        5
    )

    assert.equal(plan.matches[0].status, EVIDENCE_STATUS.MATCHED)
    assert.equal(plan.matches[0].matchType, 'table')
    assert.deepEqual([...plan.itemEvidenceIds.keys()].sort((a, b) => a - b), [0, 1, 2])
})

test('matches a source quote to the containing paragraph line block', () => {
    const plan = buildPageEvidenceHighlightPlan(
        {
            items: [
                textItem('Introduction text.', 50, 700, 120),
                textItem('Pear samples contained 4.6 mg vitamin C per 100 g in the edible portion.', 50, 680, 420),
                textItem('Another paragraph.', 50, 650, 140),
            ],
        },
        [
            {
                id: 'evidence-1',
                sourceLocationType: 'paragraph',
                sourceQuote: 'Pear samples contained 4.6 mg vitamin C per 100 g',
            },
        ],
        2
    )

    assert.equal(plan.matches[0].status, EVIDENCE_STATUS.MATCHED)
    assert.equal(plan.matches[0].matchType, 'quote')
    assert.deepEqual([...plan.itemEvidenceIds.keys()], [1])
})

test('keeps page-only hints navigable without broad highlighting', () => {
    const plan = buildPageEvidenceHighlightPlan(
        {
            items: [
                textItem('Methods text.', 50, 700, 120),
            ],
        },
        [{ id: 'evidence-1', pageHint: 7 }],
        7
    )

    assert.equal(plan.matches[0].status, EVIDENCE_STATUS.HINTED)
    assert.equal(plan.matches[0].matchType, 'page_hint')
    assert.equal(plan.itemEvidenceIds.size, 0)
})

test('leaves unmatched evidence unverified by returning no false match', () => {
    const plan = buildPageEvidenceHighlightPlan(
        {
            items: [
                textItem('Table 1. Moisture results', 50, 700, 180),
                textItem('Food Moisture (%)', 50, 680, 160),
                textItem('Apple 84.1', 50, 660, 120),
            ],
        },
        [{ id: 'evidence-1', tableLabel: 'Table 9', sourceQuote: 'Protein 0.3 g/100g' }],
        1
    )

    assert.equal(plan.matches.length, 0)
    assert.equal(plan.itemEvidenceIds.size, 0)
})
