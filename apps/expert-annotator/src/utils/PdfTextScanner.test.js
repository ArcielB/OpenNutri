import test from 'node:test'
import assert from 'node:assert/strict'

import { EVIDENCE_STATUS } from './EvidenceLocations.js'
import { buildPageEvidenceHighlightPlan, detectPrintedPageNumber } from './PdfTextScanner.js'

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
    assert.deepEqual(plan.matches[0].regionBounds, {
        left: 50,
        right: 310,
        bottom: 660,
        top: 710,
    })
})

test('includes prose-like food cells when evidence highlights a table', () => {
    const plan = buildPageEvidenceHighlightPlan(
        {
            items: [
                textItem('Table 3. Phytochemical composition', 50, 700, 260),
                textItem('Constituent', 50, 680, 90),
                textItem('Value (mg/100g)', 300, 680, 110),
                textItem('Sida acuta dried leaf sample', 50, 660, 170),
                textItem('1751.67 1255 90', 300, 660, 130),
            ],
        },
        [{ id: 'evidence-1', tableLabel: 'Table 3', pageHint: 95 }],
        1
    )

    assert.equal(plan.matches[0].status, EVIDENCE_STATUS.MATCHED)
    assert.equal(plan.matches[0].matchType, 'table')
    assert.deepEqual([...plan.itemEvidenceIds.keys()].sort((a, b) => a - b), [0, 1, 2, 3, 4])
    assert.deepEqual(plan.matches[0].regionBounds, {
        left: 50,
        right: 430,
        bottom: 660,
        top: 710,
    })
})

test('matches a source quote to the containing paragraph line block', () => {
    const plan = buildPageEvidenceHighlightPlan(
        {
            items: [
                textItem('The edible portion was analyzed after drying.', 50, 700, 260),
                textItem('Pear samples contained 4.6 mg vitamin C per 100 g in the edible portion.', 50, 680, 420),
                textItem('Values were calculated on a fresh weight basis.', 50, 660, 300),
                textItem('Another paragraph starts with different evidence.', 50, 620, 260),
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
    assert.equal(plan.matches[0].matchType, 'paragraph')
    assert.deepEqual([...plan.itemEvidenceIds.keys()], [0, 1, 2])
    assert.deepEqual(plan.matches[0].regionBounds, {
        left: 50,
        right: 470,
        bottom: 660,
        top: 710,
    })
})

test('keeps table matching available when the AI page hint is wrong', () => {
    const plan = buildPageEvidenceHighlightPlan(
        {
            items: [
                textItem('Table 3. Mineral composition', 50, 700, 230),
                textItem('Food Calcium (mg/100g) Iron (mg/100g)', 50, 680, 300),
                textItem('Leaf sample 1751.67 90', 50, 660, 230),
            ],
        },
        [{ id: 'evidence-1', tableLabel: 'Table 3', pageHint: 95 }],
        1
    )

    assert.equal(plan.matches[0].status, EVIDENCE_STATUS.MATCHED)
    assert.equal(plan.matches[0].matchType, 'table')
    assert.deepEqual(plan.matches[0].regionBounds, {
        left: 50,
        right: 350,
        bottom: 660,
        top: 710,
    })
})

test('maps printed page labels to the current PDF page', () => {
    const textContent = {
        items: [
            textItem('www.iosrjournals.org', 230, 20, 140),
            textItem('93 | Page', 820, 20, 70),
            textItem('Introduction', 260, 720, 120),
        ],
    }

    assert.equal(detectPrintedPageNumber(textContent, 1, 6), 93)

    const plan = buildPageEvidenceHighlightPlan(
        textContent,
        [{ id: 'evidence-1', pageHint: 93 }],
        1,
        { printedPageNumber: 93 }
    )

    assert.equal(plan.matches[0].status, EVIDENCE_STATUS.HINTED)
    assert.equal(plan.matches[0].matchType, 'mapped_page_hint')
    assert.equal(plan.matches[0].pageNumber, 1)
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
    assert.equal(plan.matches[0].regionBounds, undefined)
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
