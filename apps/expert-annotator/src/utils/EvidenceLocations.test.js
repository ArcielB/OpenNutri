import test from 'node:test'
import assert from 'node:assert/strict'

import {
    EVIDENCE_STATUS,
    buildEvidenceLocationsFromFoodItems,
    getDefaultEvidenceStatus,
    getEvidenceDisplayLabel,
    mergeEvidenceStatuses,
} from './EvidenceLocations.js'

test('groups repeated normalized payload rows into one table evidence location', () => {
    const locations = buildEvidenceLocationsFromFoodItems([
        {
            food_name: 'Apple',
            nutrients: [
                {
                    nutrient_name: 'Protein',
                    source_citation: 'Table 2, row 1',
                    metadata: {
                        table_label: 'Table 2',
                        page_hint: 5,
                        source_quote: 'Apple protein 0.3 g/100g',
                    },
                },
                {
                    nutrient_name: 'Fat',
                    source_citation: 'Table 2, row 1',
                    metadata: {
                        table_label: 'Table 2',
                        page_hint: 5,
                        source_quote: 'Apple fat 0.2 g/100g',
                    },
                },
            ],
        },
    ])

    assert.equal(locations.length, 1)
    assert.equal(locations[0].rowCount, 2)
    assert.equal(locations[0].tableLabel, 'Table 2')
    assert.equal(locations[0].pageHint, 5)
    assert.equal(getEvidenceDisplayLabel(locations[0]), 'Table 2')
})

test('keeps paragraph and page-only evidence visible as unverified hints', () => {
    const locations = buildEvidenceLocationsFromFoodItems([
        {
            food_name: 'Pear',
            nutrients: [
                {
                    nutrient_name: 'Vitamin C',
                    metadata: {
                        source_location_type: 'paragraph',
                        source_quote: 'Pear samples contained 4.6 mg vitamin C per 100 g.',
                    },
                },
                {
                    nutrient_name: 'Moisture',
                    metadata: {
                        page_hint: 9,
                    },
                },
            ],
        },
    ])

    const paragraph = locations.find((location) => location.sourceLocationType === 'paragraph')
    const pageOnly = locations.find((location) => location.pageHint === 9)

    assert.equal(getEvidenceDisplayLabel(paragraph), 'Paragraph evidence')
    assert.equal(getDefaultEvidenceStatus(paragraph).status, EVIDENCE_STATUS.UNVERIFIED)
    assert.equal(getEvidenceDisplayLabel(pageOnly), 'Page 9')
    assert.equal(getDefaultEvidenceStatus(pageOnly).status, EVIDENCE_STATUS.HINTED)
})

test('confirmed page matches upgrade default evidence statuses', () => {
    const locations = buildEvidenceLocationsFromFoodItems([
        {
            food_name: 'Apple',
            nutrients: [
                {
                    nutrient_name: 'Protein',
                    source_citation: 'Table 1',
                    metadata: { table_label: 'Table 1', page_hint: 3 },
                },
                {
                    nutrient_name: 'Iron',
                    metadata: { source_quote: 'Iron 0.1 mg/100g' },
                },
            ],
        },
    ])

    const statuses = mergeEvidenceStatuses(locations, [
        {
            evidenceId: locations[0].id,
            status: EVIDENCE_STATUS.MATCHED,
            matchType: 'table',
            pageNumber: 3,
        },
    ])

    assert.equal(statuses[locations[0].id].status, EVIDENCE_STATUS.MATCHED)
    assert.equal(statuses[locations[0].id].label, 'Matched table')
    assert.equal(statuses[locations[1].id].status, EVIDENCE_STATUS.UNVERIFIED)
})
