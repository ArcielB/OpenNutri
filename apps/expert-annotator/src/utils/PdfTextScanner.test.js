import test from 'node:test'
import assert from 'node:assert/strict'

import { EVIDENCE_STATUS } from './EvidenceLocations.js'
import { buildPageEvidenceHighlightPlan, buildPageTableHighlightPlan, detectPrintedPageNumber } from './PdfTextScanner.js'

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

test('matches a table with a separate caption label and wide multi-column headers', () => {
    const plan = buildPageEvidenceHighlightPlan(
        {
            items: [
                textItem('Table 2', 50, 700, 45),
                textItem('Mean value, standard deviation, and descriptive statistics of dry matter, crude protein, ash content, moisture content, crude fats, crude fiber, and carbohydrate of 30 oat', 50, 688, 520),
                textItem('germplasm.', 50, 676, 60),
                textItem('Oat Germplasm', 60, 656, 60),
                textItem('Dry matter', 150, 656, 45),
                textItem('Crude Protein', 230, 656, 60),
                textItem('Ash Content', 320, 656, 55),
                textItem('Moisture Content', 410, 656, 75),
                textItem('A769', 60, 640, 40),
                textItem('90.26 +/- 0.07', 150, 640, 60),
                textItem('15.57 +/- 0.57', 230, 640, 60),
                textItem('4.53 +/- 0.03', 320, 640, 55),
                textItem('9.80 +/- 0.06', 410, 640, 55),
                textItem('Mean', 60, 624, 40),
                textItem('90.76', 150, 624, 50),
                textItem('14.54', 230, 624, 50),
                textItem('5.86', 320, 624, 40),
                textItem('9.58', 410, 624, 40),
                textItem('A paragraph below the table should not be part of the overlay.', 50, 580, 360),
            ],
        },
        [{ id: 'evidence-1', tableLabel: 'Table 2', pageHint: 4 }],
        4
    )

    assert.equal(plan.matches[0].status, EVIDENCE_STATUS.MATCHED)
    assert.equal(plan.matches[0].matchType, 'table')
    assert.deepEqual(plan.matches[0].regionBounds, {
        left: 50,
        right: 570,
        bottom: 624,
        top: 710,
    })
})

test('snaps quote evidence inside a detected table to the whole table block', () => {
    const plan = buildPageEvidenceHighlightPlan(
        {
            items: [
                textItem('Table 3. Mineral and vitamin content', 50, 700, 260),
                textItem('Mineral (mg/100g) Amount References', 50, 680, 420),
                textItem('Phosphorus 375.0 37 55 67', 50, 660, 360),
                textItem('Zinc 2.33', 50, 640, 160),
                textItem('Selenium 0.04', 50, 620, 160),
                textItem('Vitamins (mg/100g) Amount References', 50, 580, 420),
            ],
        },
        [{ id: 'evidence-1', sourceQuote: 'Zinc 2.33' }],
        6
    )

    assert.equal(plan.matches[0].status, EVIDENCE_STATUS.MATCHED)
    assert.equal(plan.matches[0].matchType, 'table')
    assert.deepEqual([...plan.itemEvidenceIds.keys()].sort((a, b) => a - b), [0, 1, 2, 3, 4])
    assert.deepEqual(plan.matches[0].regionBounds, {
        left: 50,
        right: 470,
        bottom: 620,
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

test('uses one stable paragraph block for separate quotes in the same paragraph', () => {
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
                sourceQuote: 'edible portion was analyzed',
            },
            {
                id: 'evidence-2',
                sourceQuote: 'fresh weight basis',
            },
        ],
        2
    )

    assert.equal(plan.matches.length, 2)
    assert.deepEqual(plan.matches[0].regionBounds, plan.matches[1].regionBounds)
    assert.deepEqual(plan.matches[0].itemIndexes, plan.matches[1].itemIndexes)
})

test('keeps numeric abstract evidence in one paragraph block without side metadata', () => {
    const plan = buildPageEvidenceHighlightPlan(
        {
            items: [
                textItem('Department of Chemistry, Example University', 80, 573, 360),
                textItem('Abstract', 210, 555, 60),
                textItem('Article History:', 435, 545, 80),
                textItem('Leaves of sweet potato grown in Tepi area was studied for their class of', 62, 544, 350),
                textItem('phytochemicals, mineral and proximate composition using standard analytical methods. The', 62, 534, 350),
                textItem('revealed potassium (3608.854mg/100g), sodium', 62, 524, 350),
                textItem('continued with (32.079+/-0.12mg/100g), calcium (320.125+/-0.36 mg/100g), magnesium (118.75+/-0.02mg', 62, 514, 350),
                textItem('/100g), copper (1.828+/-0.11mg/100g), zinc (5.647+/-0.14mg/100g), and iron (73.881+/-0.03mg/100g)', 62, 504, 350),
                textItem('and manganese (9.590+/-0.06mg/100g). These results revealed that the leaves of sweet', 62, 494, 350),
                textItem('Ipomoea batatas', 435, 499, 70),
                textItem('Copyright@2014 Journal. All Rights Reserved.', 210, 426, 240),
            ],
        },
        [
            { id: 'evidence-1', sourceQuote: '(32.079+/-0.12mg/100g)' },
            { id: 'evidence-2', sourceQuote: 'magnesium (118.75+/-0.02mg /100g)' },
            { id: 'evidence-3', sourceQuote: 'manganese (9.590+/-0.06mg/100g)' },
        ],
        1
    )

    assert.equal(plan.matches.length, 3)
    assert.deepEqual(plan.matches[0].regionBounds, plan.matches[1].regionBounds)
    assert.deepEqual(plan.matches[0].regionBounds, plan.matches[2].regionBounds)
    assert.equal(plan.matches[0].regionBounds.left, 62)
    assert.equal(plan.matches[0].regionBounds.right, 412)
    assert.equal(plan.matches[0].regionBounds.bottom, 494)
    assert.equal(plan.matches[0].regionBounds.top, 524)
})

test('does not treat narrative prose after a table as nutrient highlight eligible', () => {
    const plan = buildPageTableHighlightPlan({
        items: [
            textItem('Table 1: Results of proximate analysis', 50, 700, 260),
            textItem('Constituent Value (%)', 50, 680, 200),
            textItem('Protein 6.37', 50, 660, 120),
            textItem('The result revealed that the leaves Ipomoea batatas leaves are a source of protein.', 300, 650, 360),
        ],
    })

    assert.equal(plan.allowedItemIndexes.has(0), true)
    assert.equal(plan.allowedItemIndexes.has(1), true)
    assert.equal(plan.allowedItemIndexes.has(2), true)
    assert.equal(plan.allowedItemIndexes.has(3), false)
})

test('keeps different paragraph blocks non-overlapping', () => {
    const plan = buildPageEvidenceHighlightPlan(
        {
            items: [
                textItem('Pear samples were dried before analysis.', 50, 700, 260),
                textItem('Values were calculated on a fresh weight basis.', 50, 680, 300),
                textItem('Apple samples were measured separately.', 50, 620, 260),
                textItem('The reported vitamin C values used duplicate assays.', 50, 600, 360),
            ],
        },
        [
            {
                id: 'evidence-1',
                sourceQuote: 'fresh weight basis',
            },
            {
                id: 'evidence-2',
                sourceQuote: 'duplicate assays',
            },
        ],
        2
    )

    assert.equal(plan.matches.length, 2)
    assert.notDeepEqual(plan.matches[0].regionBounds, plan.matches[1].regionBounds)
    assert.ok(plan.matches[0].regionBounds.bottom > plan.matches[1].regionBounds.top)
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

test('splits fragments at column gutters narrower than fragmentGapThreshold', () => {
    // Recreates the failure in paper 1314 p.3: two columns separated by a 14pt
    // gutter (narrower than fragmentGapThreshold). Without page-level gutter
    // detection PDF.js items get fused into one cross-column fragment and the
    // matched paragraph bounds bleed all the way to the right column.
    const items = []
    // Left column prose, multiple rows
    for (let i = 0; i < 6; i += 1) {
        items.push(textItem(`commercial wheat flour line ${i} with chemical composition details`, 72, 700 - i * 14, 227))
    }
    // Right column prose at the same y rows
    for (let i = 0; i < 6; i += 1) {
        items.push(textItem(`right column body text on line ${i} of the methods section`, 313, 700 - i * 14, 227))
    }

    const plan = buildPageEvidenceHighlightPlan(
        { items },
        [{ id: 'evidence-left', sourceLocationType: 'paragraph', sourceQuote: 'commercial wheat flour line 1' }],
        3
    )

    assert.equal(plan.matches[0].status, EVIDENCE_STATUS.MATCHED)
    assert.equal(plan.matches[0].matchType, 'paragraph')
    assert.ok(
        plan.matches[0].regionBounds.right < 310,
        `expected paragraph bounds to stay in left column, got right=${plan.matches[0].regionBounds.right}`
    )
    assert.match(plan.matches[0].regionKey, /^paragraph:3:paragraph-/)
})

test('many quotes for the same bullet paragraph collapse to one regionKey', () => {
    // Mirrors paper 1314 p.3 paragraph evidence: the bullet item has lines that
    // are paragraph candidates (continuation lines) and lines that are not
    // (first line with "(type 500)" parens, last line too short to qualify).
    // Every quote that lands anywhere in this bullet should resolve to the
    // same paragraph block id so one chip is shown.
    const items = [
        textItem('• commercial wheat flour (type 500) (average', 72, 550, 227),
        textItem('chemical composition: fat 0.90 g/100 g of which', 72, 538, 227),
        textItem('saturated 0.30 g; carbohydrates 70.30 g/100 g, of', 72, 525, 227),
        textItem('which sugars 3.40 g, fiber 4.00 g/100 g; protein', 72, 512, 227),
        textItem('10.80g/100 g);', 72, 500, 67),
    ]
    const plan = buildPageEvidenceHighlightPlan(
        { items },
        [
            { id: 'q1', sourceQuote: 'commercial wheat flour (type 500)', pageHint: 3 },
            { id: 'q2', sourceQuote: 'fiber 4.00 g/100 g', pageHint: 3 },
            { id: 'q3', sourceQuote: 'of which sugars 3.40 g', pageHint: 3 },
            { id: 'q4', sourceQuote: 'protein 10.80 g/100 g', pageHint: 3 },
        ],
        3
    )

    const keys = new Set(plan.matches.map((m) => m.regionKey))
    assert.equal(keys.size, 1, `expected one regionKey for one bullet paragraph, got: ${[...keys].join(', ')}`)
    plan.matches.forEach((m) => assert.equal(m.status, EVIDENCE_STATUS.MATCHED))
    assert.match([...keys][0], /^paragraph:3:paragraph-/)
})

test('digit-letter boundary normalisation lets quotes with spaces match fused PDF items', () => {
    // PDF.js doesn't insert whitespace between visually-adjacent items, so an
    // item like "10.80" + "g/100 g);" becomes "10.80g/100 g);" in the
    // fragment text. The matcher must still match a quote written as
    // "10.80 g/100 g".
    const items = [
        textItem('first prose line that contains protein content references', 72, 540, 260),
        textItem('which fragment ends with the word protein', 72, 525, 230),
        textItem('10.80g/100 g);', 72, 512, 67),
    ]
    const plan = buildPageEvidenceHighlightPlan(
        { items },
        [{ id: 'q', sourceQuote: 'protein 10.80 g/100 g', pageHint: 2 }],
        2
    )

    assert.equal(plan.matches[0]?.status, EVIDENCE_STATUS.MATCHED)
})

test('clips paragraph bounds to the dominant column when one fragment overflows', () => {
    const plan = buildPageEvidenceHighlightPlan(
        {
            items: [
                textItem('commercial wheat flour (type 500) (average composition: fat 0.90 g/100 g of which', 50, 700, 240),
                textItem('saturated 0.30 g; carbohydrates 70.30 g/100 g, of which sugars 3.40 g, fiber 4.00 g/100 g;', 50, 685, 240),
                // PDF.js sometimes fuses both columns into one fragment when the gutter is narrow.
                textItem('protein 10.80 g/100 g). Control sample 10 %', 50, 670, 520),
                textItem('flour from cold-pressed pumpkin seed cake (average chemical composition).', 50, 640, 240),
            ],
        },
        [
            {
                id: 'evidence-1',
                sourceLocationType: 'paragraph',
                sourceQuote: 'commercial wheat flour (type 500)',
            },
        ],
        1
    )

    assert.equal(plan.matches[0].status, EVIDENCE_STATUS.MATCHED)
    assert.equal(plan.matches[0].matchType, 'paragraph')
    // The cross-column fragment (right=570) should be excluded so bounds stay in the left column.
    assert.ok(
        plan.matches[0].regionBounds.right <= 320,
        `expected right <= 320, got ${plan.matches[0].regionBounds.right}`
    )
})

test('stable paragraph region key is identical for separate quotes in one block', () => {
    const plan = buildPageEvidenceHighlightPlan(
        {
            items: [
                textItem('The edible portion was analyzed after drying.', 50, 700, 260),
                textItem('Pear samples contained 4.6 mg vitamin C per 100 g in the edible portion.', 50, 680, 420),
                textItem('Values were calculated on a fresh weight basis.', 50, 660, 300),
            ],
        },
        [
            { id: 'evidence-1', sourceQuote: 'edible portion was analyzed' },
            { id: 'evidence-2', sourceQuote: 'fresh weight basis' },
        ],
        2
    )

    assert.equal(plan.matches.length, 2)
    assert.equal(plan.matches[0].regionKey, plan.matches[1].regionKey)
    assert.match(plan.matches[0].regionKey, /^paragraph:2:paragraph-/)
})

test('stable table region key is identical for evidences pointing at the same table', () => {
    const plan = buildPageEvidenceHighlightPlan(
        {
            items: [
                textItem('Table 2. Composition of apple samples', 50, 700, 260),
                textItem('Food Protein (g/100g) Fat (g/100g)', 50, 680, 260),
                textItem('Apple 0.3 0.2', 50, 660, 140),
            ],
        },
        [
            { id: 'evidence-1', tableLabel: 'Table 2', pageHint: 5 },
            { id: 'evidence-2', tableLabel: 'Table 2', pageHint: 5, sourceQuote: 'Apple 0.3 0.2' },
        ],
        5
    )

    assert.equal(plan.matches.length, 2)
    assert.equal(plan.matches[0].regionKey, plan.matches[1].regionKey)
    assert.match(plan.matches[0].regionKey, /^table:5:table-2-/)
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
