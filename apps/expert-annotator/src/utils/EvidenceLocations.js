const TABLE_LABEL_RE = /\b(?:table|tablo|çizelge)\s*[.:#-]?\s*([0-9]+[A-Za-z]?)/iu
const PAGE_HINT_RE = /\b(?:p(?:age)?\.?|sayfa)\s*([0-9]{1,4})\b/iu

export const EVIDENCE_STATUS = {
    MATCHED: 'matched',
    HINTED: 'hinted',
    UNVERIFIED: 'unverified',
}

export function buildEvidenceLocationsFromFoodItems(foodItems) {
    const grouped = new Map()

    for (const foodItem of Array.isArray(foodItems) ? foodItems : []) {
        for (const nutrient of Array.isArray(foodItem?.nutrients) ? foodItem.nutrients : []) {
            const location = buildEvidenceLocationFromNutrient(nutrient)
            if (!location) continue

            const existing = grouped.get(location.groupKey)
            if (existing) {
                existing.rowCount += 1
                existing.foodNames.add(cleanText(foodItem?.food_name))
                existing.nutrientNames.add(cleanText(nutrient?.nutrient_name))
                if (!existing.sourceQuote && location.sourceQuote) {
                    existing.sourceQuote = location.sourceQuote
                }
                if (!existing.sourceCitation && location.sourceCitation) {
                    existing.sourceCitation = location.sourceCitation
                }
                if (!existing.pageHint && location.pageHint) {
                    existing.pageHint = location.pageHint
                }
                continue
            }

            grouped.set(location.groupKey, {
                ...location,
                rowCount: 1,
                foodNames: new Set([cleanText(foodItem?.food_name)].filter(Boolean)),
                nutrientNames: new Set([cleanText(nutrient?.nutrient_name)].filter(Boolean)),
            })
        }
    }

    return Array.from(grouped.values())
        .map((location, index) => ({
            ...location,
            id: `evidence-${index + 1}`,
            foodNames: Array.from(location.foodNames),
            nutrientNames: Array.from(location.nutrientNames),
        }))
        .sort(compareEvidenceLocations)
}

export function getEvidenceDisplayLabel(location) {
    if (location?.tableLabel) return location.tableLabel
    if (location?.sourceLocationType === 'section' && location.sectionHeading) {
        return truncateLabel(location.sectionHeading, 34)
    }
    if (location?.sourceLocationType === 'paragraph') return 'Paragraph evidence'
    if (location?.sourceQuote) return 'Paragraph evidence'
    if (location?.pageHint) return `Page ${location.pageHint}`
    return 'Evidence'
}

export function getDefaultEvidenceStatus(location) {
    if (location?.pageHint) {
        return {
            status: EVIDENCE_STATUS.HINTED,
            label: 'Page hint',
            pageNumber: location.pageHint,
            matchType: 'page_hint',
        }
    }
    return {
        status: EVIDENCE_STATUS.UNVERIFIED,
        label: 'Unverified',
        pageNumber: null,
        matchType: null,
    }
}

export function mergeEvidenceStatuses(locations, pageMatches) {
    const statuses = Object.fromEntries(
        (locations || []).map((location) => [location.id, getDefaultEvidenceStatus(location)])
    )

    for (const match of pageMatches || []) {
        if (!match?.evidenceId || !statuses[match.evidenceId]) continue
        const current = statuses[match.evidenceId]
        if (current.status === EVIDENCE_STATUS.MATCHED) continue
        if (match.status === EVIDENCE_STATUS.MATCHED) {
            statuses[match.evidenceId] = {
                status: EVIDENCE_STATUS.MATCHED,
                label: match.matchType === 'table' ? 'Matched table' : 'Matched text',
                pageNumber: match.pageNumber || current.pageNumber || null,
                matchType: match.matchType || 'text',
                regionKey: match.regionKey || null,
            }
            continue
        }
        if (
            match.status === EVIDENCE_STATUS.HINTED &&
            (current.status === EVIDENCE_STATUS.UNVERIFIED || match.matchType === 'mapped_page_hint')
        ) {
            statuses[match.evidenceId] = {
                status: EVIDENCE_STATUS.HINTED,
                label: match.matchType === 'mapped_page_hint'
                    ? `Printed page ${match.sourcePageNumber} maps to PDF page ${match.pageNumber}`
                    : 'Page hint',
                pageNumber: match.pageNumber || current.pageNumber || null,
                matchType: match.matchType === 'mapped_page_hint' ? 'mapped_page_hint' : 'page_hint',
                sourcePageNumber: match.sourcePageNumber || null,
            }
        }
    }

    return statuses
}

export function buildEvidenceDisplayGroups(locations, statuses = {}) {
    const groups = new Map()

    for (const location of locations || []) {
        if (!location?.id) continue

        const status = statuses[location.id] || getDefaultEvidenceStatus(location)
        const displayKey = buildEvidenceDisplayGroupKey(location, status)
        const existing = groups.get(displayKey)

        if (existing) {
            existing.locations.push(location)
            existing.evidenceIds.push(location.id)
            existing.rowCount += Number(location.rowCount || 0)
            continue
        }

        groups.set(displayKey, {
            id: displayKey,
            location,
            locations: [location],
            evidenceIds: [location.id],
            status,
            rowCount: Number(location.rowCount || 0),
        })
    }

    return Array.from(groups.values())
}

function buildEvidenceLocationFromNutrient(nutrient) {
    const metadata = normalizeMetadata(nutrient?.metadata)
    const sourceCitation = cleanText(nutrient?.source_citation || metadata.source_citation)
    const sourceQuote = cleanText(metadata.source_quote || nutrient?.source_quote)
    const tableLabel = normalizeTableLabel(metadata.table_label || nutrient?.table_label || sourceCitation)
    const pageHint = normalizePageHint(metadata.page_hint ?? nutrient?.page_hint ?? sourceCitation)
    const sourceLocationType = normalizeLocationType(
        metadata.source_location_type ||
        nutrient?.source_location_type ||
        inferLocationType({ tableLabel, sourceQuote, sourceCitation })
    )
    const sectionHeading = cleanText(metadata.section_heading || nutrient?.section_heading)
    const paragraphHint = cleanText(
        metadata.paragraph_hint ||
        metadata.paragraph_label ||
        metadata.paragraph_location ||
        nutrient?.paragraph_hint
    )

    if (!sourceCitation && !sourceQuote && !tableLabel && !pageHint && !sectionHeading && !paragraphHint) {
        return null
    }

    const groupKey = buildEvidenceGroupKey({
        tableLabel,
        pageHint,
        sourceCitation,
        sourceQuote,
        sectionHeading,
        paragraphHint,
        sourceLocationType,
    })

    return {
        groupKey,
        sourceCitation,
        sourceQuote,
        tableLabel,
        pageHint,
        sourceLocationType,
        sectionHeading,
        paragraphHint,
    }
}

function buildEvidenceGroupKey(location) {
    const pagePart = location.pageHint ? `p${location.pageHint}` : 'p?'
    if (location.tableLabel) {
        return ['table', pagePart, normalizeKey(location.tableLabel)].join('|')
    }
    if (location.sourceCitation) {
        return [
            'citation',
            pagePart,
            normalizeKey(location.sourceCitation),
            normalizeKey(location.sourceQuote),
        ].join('|')
    }
    if (location.sourceQuote) {
        return ['quote', pagePart, normalizeKey(location.sourceQuote)].join('|')
    }
    if (location.sectionHeading || location.paragraphHint) {
        return [
            location.sourceLocationType || 'section',
            pagePart,
            normalizeKey(location.sectionHeading),
            normalizeKey(location.paragraphHint),
        ].join('|')
    }
    return ['page', pagePart].join('|')
}

function buildEvidenceDisplayGroupKey(location, status) {
    if (status?.status === EVIDENCE_STATUS.MATCHED && status.regionKey) {
        return [
            'matched',
            status.matchType || 'text',
            status.pageNumber || '?',
            status.regionKey,
        ].join('|')
    }

    if (
        status?.status === EVIDENCE_STATUS.HINTED &&
        status.pageNumber &&
        !location?.tableLabel &&
        !location?.sourceQuote
    ) {
        return [
            'hinted',
            status.matchType || 'page_hint',
            status.pageNumber,
        ].join('|')
    }

    return location?.groupKey || location?.id || 'unknown'
}

function compareEvidenceLocations(left, right) {
    const leftPage = left.pageHint ?? Number.MAX_SAFE_INTEGER
    const rightPage = right.pageHint ?? Number.MAX_SAFE_INTEGER
    if (leftPage !== rightPage) return leftPage - rightPage
    if (left.tableLabel && !right.tableLabel) return -1
    if (!left.tableLabel && right.tableLabel) return 1
    return getEvidenceDisplayLabel(left).localeCompare(getEvidenceDisplayLabel(right))
}

function inferLocationType({ tableLabel, sourceQuote, sourceCitation }) {
    if (tableLabel) return 'table'
    if (/\bparagraph\b/i.test(sourceCitation || '')) return 'paragraph'
    if (sourceQuote) return 'paragraph'
    return ''
}

function normalizeLocationType(value) {
    const normalized = cleanText(value).toLowerCase()
    if (['table', 'paragraph', 'section'].includes(normalized)) return normalized
    return ''
}

function normalizeTableLabel(value) {
    const text = cleanText(value)
    const match = text.match(TABLE_LABEL_RE)
    if (!match) return ''
    return `Table ${match[1].toUpperCase()}`
}

function normalizePageHint(value) {
    if (typeof value === 'number' && Number.isInteger(value) && value > 0) return value
    const text = cleanText(value)
    if (!text) return null
    if (/^[0-9]{1,4}$/.test(text)) return Number(text)
    const match = text.match(PAGE_HINT_RE)
    if (!match) return null
    const page = Number(match[1])
    return Number.isInteger(page) && page > 0 ? page : null
}

function normalizeMetadata(value) {
    return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function truncateLabel(value, maxLength) {
    const text = cleanText(value)
    if (text.length <= maxLength) return text
    return `${text.slice(0, maxLength - 1).trim()}...`
}

function normalizeKey(value) {
    return cleanText(value).toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim()
}

function cleanText(value) {
    return String(value ?? '').replace(/\s+/g, ' ').trim()
}
