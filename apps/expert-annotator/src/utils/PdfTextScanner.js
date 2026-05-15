import { EVIDENCE_STATUS } from './EvidenceLocations.js'

/**
 * PdfTextScanner renders highlight markup for individual PDF text items,
 * builds precision-first table-only highlight plans from PDF.js text content,
 * and binds delegated interactions on the text layer after PDF.js finishes
 * rendering it.
 */

const SKIP_NAMES = new Set([
    'proximates',
    'minerals',
    'lipids',
    'vitamins and other components',
    'other',
])

const CAPTION_PREFIX_RE = /^(table|tablo|çizelge)\s+(\d+)(?=$|[\s.:-])/iu
const SOURCE_TABLE_LABEL_RE = /\b(?:table|tablo|çizelge)\s*[.:#-]?\s*([0-9]+[A-Za-z]?)/iu
const PAGE_LABEL_WITH_NUMBER_RE = /\b(?:page|p\.?|sayfa)\s*[#:.-]?\s*([0-9]{1,4})\b/iu
const NUMBER_WITH_PAGE_LABEL_RE = /\b([0-9]{1,4})\s*(?:[|/:.-]\s*)?(?:page|sayfa)\b/iu
const STANDALONE_PAGE_NUMBER_RE = /^[^\p{L}\p{N}]?([0-9]{1,4})[^\p{L}\p{N}]?$/u
const HEADER_TOKEN_RE = /\b(%RSD|RSD|ANAL[Iİ]T)\b/iu
const UNIT_TOKEN_RE = /\([^)]{1,24}\)/u
const LETTER_RE = /[A-Za-zÇĞİÖŞÜçğıöşü]/g
const LOWER_LETTER_RE = /[a-zçğıöşü]/g
const TOKEN_SPLIT_RE = /\s+/u
const PURE_WHITESPACE_RE = /^\s*$/u
const NUMERIC_TOKEN_RE = /^[<>~]?\d+(?:[.,]\d+)?$/u
const ELLIPSIS_SPLIT_RE = /(?:\.{2,}|…)/u
const SAMPLE_CODE_RE = /^(?:[A-Za-z]{1,4}\d{1,3}|\d{1,3}[A-Za-z]{1,4}|[A-Za-z]-\d{1,3}|\d{1,3}-[A-Za-z]|[A-Za-z]{1,4}\d{1,3}-[A-Za-z]{1,4})$/u
const ABBREVIATION_TOKEN_RE = /^(?:[A-ZÇĞİÖŞÜ]\.){1,4}$/u
const MAX_PARAGRAPH_FRAGMENT_COUNT = 14

export function buildNutrientMatcher(nutrients) {
    const patterns = []

    for (const nutrient of nutrients) {
        const lowerName = nutrient.name.toLowerCase()
        if (SKIP_NAMES.has(lowerName)) continue
        if (lowerName.includes('do not use')) continue

        patterns.push({
            nutrient,
            regex: buildBoundaryRegex(nutrient.name),
        })
    }

    patterns.sort((left, right) => right.nutrient.name.length - left.nutrient.name.length)
    return { patterns }
}

export function buildPageTableHighlightPlan(textContent) {
    const items = extractPositionedTextItems(textContent)
    if (items.length === 0) {
        return createEmptyHighlightPlan()
    }

    const metrics = buildPageMetrics(items)
    const rows = groupItemsIntoRows(items, metrics)
    if (rows.length === 0) {
        return createEmptyHighlightPlan()
    }

    const captionBlocks = buildCaptionBlocks(rows, metrics)
    if (captionBlocks.length === 0) {
        return createEmptyHighlightPlan()
    }

    const confidentRegions = []

    for (let index = 0; index < captionBlocks.length; index += 1) {
        const block = captionBlocks[index]
        const nextBlock = captionBlocks[index + 1] || null
        const region = buildTableRegionForCaptionBlock(block, rows, metrics, nextBlock?.startRowIndex ?? rows.length)

        if (!region.isConfident) {
            continue
        }

        confidentRegions.push(region)
    }

    if (confidentRegions.length === 0) {
        return createEmptyHighlightPlan()
    }

    const allowedItemIndexes = new Set()

    for (const region of confidentRegions) {
        for (const itemIndex of region.allowedItemIndexes) {
            allowedItemIndexes.add(itemIndex)
        }
    }

    return {
        allowedItemIndexes,
        tableRegions: confidentRegions.map((region) => ({
            captionText: region.captionText,
            captionNumber: region.captionNumber,
            bodyRowCount: region.bodyRowCount,
        })),
    }
}

export function buildPageEvidenceHighlightPlan(textContent, evidenceLocations = [], pageNumber = null, options = {}) {
    const locations = Array.isArray(evidenceLocations) ? evidenceLocations : []
    const itemEvidenceIds = new Map()
    const matches = []
    const printedPageNumber = normalizePositiveInteger(options.printedPageNumber)

    if (locations.length === 0) {
        return { itemEvidenceIds, matches }
    }

    const items = extractPositionedTextItems(textContent)
    if (items.length === 0) {
        return {
            itemEvidenceIds,
            matches: buildPageHintMatches(locations, pageNumber, printedPageNumber),
        }
    }

    const metrics = buildPageMetrics(items)
    const rows = groupItemsIntoRows(items, metrics)
    if (rows.length === 0) {
        return {
            itemEvidenceIds,
            matches: buildPageHintMatches(locations, pageNumber, printedPageNumber),
        }
    }

    const tableRegions = buildConfidentTableRegions(rows, metrics)
    const paragraphBlocks = buildParagraphBlocks(rows, tableRegions, metrics)

    for (const location of locations) {
        if (!location?.id) continue

        const pageMatchesHint =
            pageNumber &&
            (
                Number(location.pageHint) === Number(pageNumber) ||
                (printedPageNumber && Number(location.pageHint) === printedPageNumber)
            )
        const hasTableMatcher = Boolean(parseTableNumber(location.tableLabel || location.sourceCitation) !== null)
        const hasQuoteMatcher = Boolean(location.sourceQuote)
        const shouldSearchPage = !location.pageHint || pageMatchesHint || hasTableMatcher || hasQuoteMatcher
        let matched = false

        if (shouldSearchPage && hasTableMatcher) {
            const tableRegion = findMatchingTableRegion(tableRegions, location)
            if (tableRegion) {
                const itemIndexes = Array.from(tableRegion.evidenceItemIndexes || tableRegion.allowedItemIndexes)
                addEvidenceItemIndexes(itemEvidenceIds, itemIndexes, location.id)
                matches.push({
                    evidenceId: location.id,
                    status: EVIDENCE_STATUS.MATCHED,
                    matchType: 'table',
                    pageNumber,
                    itemIndexes,
                    regionBounds: tableRegion.regionBounds,
                })
                matched = true
            }
        }

        if (!matched && shouldSearchPage && location.sourceQuote) {
            const quoteMatch = findSourceQuoteTextMatch(rows, location, metrics, tableRegions, paragraphBlocks)
            if (quoteMatch) {
                const itemIndexes = Array.from(quoteMatch.itemIndexes)
                addEvidenceItemIndexes(itemEvidenceIds, itemIndexes, location.id)
                matches.push({
                    evidenceId: location.id,
                    status: EVIDENCE_STATUS.MATCHED,
                    matchType: quoteMatch.matchType,
                    pageNumber,
                    itemIndexes,
                    regionBounds: quoteMatch.regionBounds,
                })
                matched = true
            }
        }

        if (!matched && pageMatchesHint) {
            matches.push({
                evidenceId: location.id,
                status: EVIDENCE_STATUS.HINTED,
                matchType: printedPageNumber && Number(location.pageHint) === printedPageNumber && Number(location.pageHint) !== Number(pageNumber)
                    ? 'mapped_page_hint'
                    : 'page_hint',
                pageNumber,
                sourcePageNumber: location.pageHint || null,
                itemIndexes: [],
            })
        }
    }

    return { itemEvidenceIds, matches }
}

export function detectPrintedPageNumber(textContent, pdfPageNumber = null, pdfPageCount = null) {
    const items = extractPositionedTextItems(textContent)
    if (items.length === 0) return null

    const metrics = buildPageMetrics(items)
    const rows = groupItemsIntoRows(items, metrics)
    if (rows.length === 0) return null

    const visibleItems = items.filter((item) => !item.isWhitespace)
    if (visibleItems.length === 0) return null

    const minY = Math.min(...visibleItems.map((item) => item.y))
    const maxY = Math.max(...visibleItems.map((item) => item.y + item.height))
    const pageHeight = Math.max(1, maxY - minY)
    const edgeBand = Math.max(pageHeight * 0.16, metrics.medianHeight * 4)
    const edgeRows = rows.filter((row) =>
        row.centerY <= minY + edgeBand || row.centerY >= maxY - edgeBand
    )

    for (const row of edgeRows) {
        const pageNumber = extractLabeledPrintedPageNumber(rowSearchText(row), pdfPageCount)
        if (pageNumber) return pageNumber
    }

    for (const row of edgeRows) {
        const pageNumber = extractStandalonePrintedPageNumber(rowSearchText(row), pdfPageNumber, pdfPageCount)
        if (pageNumber) return pageNumber
    }

    return null
}

export function scanTextForNutrients(text, matcher) {
    const matchedIds = new Set()

    for (const { nutrient, regex } of matcher.patterns) {
        regex.lastIndex = 0
        if (regex.test(text)) {
            matchedIds.add(nutrient.id)
        }
    }

    return matchedIds
}

export function renderTextItemWithNutrientHighlights(text, matcher, options = {}) {
    const originalText = text || ''
    const { allowHighlight = true } = options

    if (!originalText) {
        return ''
    }

    if (!matcher || !allowHighlight) {
        return escapeHtmlText(originalText)
    }

    const matches = collectMatches(originalText, matcher)
    if (matches.length === 0) {
        return escapeHtmlText(originalText)
    }

    let html = ''
    let cursor = 0

    for (const match of matches) {
        if (match.start > cursor) {
            html += escapeHtmlText(originalText.slice(cursor, match.start))
        }

        html += `<mark class="nutrient-highlight" data-nutrient-id="${escapeHtmlAttribute(String(match.nutrient.id))}" data-nutrient-name="${escapeHtmlAttribute(match.nutrient.name)}" data-nutrient-unit="${escapeHtmlAttribute(match.nutrient.unit_name || 'G')}">${escapeHtmlText(originalText.slice(match.start, match.end))}</mark>`
        cursor = match.end
    }

    if (cursor < originalText.length) {
        html += escapeHtmlText(originalText.slice(cursor))
    }

    return html
}

export function bindNutrientHighlightInteractions(interactionRootEl, onNutrientClick) {
    if (!interactionRootEl) return () => { }

    const resolveMarkFromEvent = (event) => {
        const directTarget = event.target?.closest?.('mark.nutrient-highlight')
        if (directTarget && interactionRootEl.contains(directTarget)) {
            return directTarget
        }

        const pointTargets = document.elementsFromPoint?.(event.clientX, event.clientY) || []
        for (const element of pointTargets) {
            const mark = element?.closest?.('mark.nutrient-highlight')
            if (mark && interactionRootEl.contains(mark)) {
                return mark
            }
        }

        const caretNode =
            document.caretPositionFromPoint?.(event.clientX, event.clientY)?.offsetNode ||
            document.caretRangeFromPoint?.(event.clientX, event.clientY)?.startContainer ||
            null

        const caretParent = caretNode?.nodeType === Node.TEXT_NODE ? caretNode.parentElement : caretNode
        const caretMark = caretParent?.closest?.('mark.nutrient-highlight')
        if (caretMark && interactionRootEl.contains(caretMark)) {
            return caretMark
        }

        return null
    }

    const openPopoverForEvent = (event) => {
        const mark = resolveMarkFromEvent(event)
        if (!mark) return

        event.preventDefault()
        event.stopPropagation()

        onNutrientClick(
            {
                id: mark.dataset.nutrientId,
                name: mark.dataset.nutrientName,
                unit_name: mark.dataset.nutrientUnit,
            },
            mark.getBoundingClientRect()
        )
    }

    interactionRootEl.addEventListener('pointerup', openPopoverForEvent, true)
    interactionRootEl.addEventListener('click', openPopoverForEvent, true)

    return () => {
        interactionRootEl.removeEventListener('pointerup', openPopoverForEvent, true)
        interactionRootEl.removeEventListener('click', openPopoverForEvent, true)
    }
}

function createEmptyHighlightPlan() {
    return {
        allowedItemIndexes: new Set(),
        tableRegions: [],
    }
}

function buildBoundaryRegex(name) {
    const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    return new RegExp(`(^|[^A-Za-z0-9])(${escaped})(?=[^A-Za-z0-9]|$)`, 'gi')
}

function extractPositionedTextItems(textContent) {
    if (!textContent?.items) {
        return []
    }

    const positioned = []

    textContent.items.forEach((item, itemIndex) => {
        if (!item || typeof item.str !== 'string') {
            return
        }

        if (item.str === '') {
            return
        }

        const width = Math.abs(item.width || 0)
        const height = Math.abs(item.height || item.transform?.[3] || 0)
        const x = Number(item.transform?.[4] || 0)
        const y = Number(item.transform?.[5] || 0)
        const right = x + width

        positioned.push({
            itemIndex,
            str: item.str,
            x,
            y,
            right,
            top: y + height,
            bottom: y,
            width,
            height,
            centerY: y + height / 2,
            isWhitespace: PURE_WHITESPACE_RE.test(item.str),
        })
    })

    return positioned
}

function buildPageMetrics(items) {
    const visibleItems = items.filter((item) => !item.isWhitespace)
    const heights = visibleItems.map((item) => item.height).filter((value) => value > 0)
    const medianHeight = median(heights, 10)

    const sortedByY = [...visibleItems].sort((left, right) => right.centerY - left.centerY)
    const rowGapCandidates = []

    for (let index = 1; index < sortedByY.length; index += 1) {
        const gap = sortedByY[index - 1].centerY - sortedByY[index].centerY
        if (gap > 0) {
            rowGapCandidates.push(gap)
        }
    }

    const medianRowGap = median(rowGapCandidates, 14)

    return {
        rowTolerance: clamp(medianHeight * 0.7, 3, 7),
        fragmentGapThreshold: clamp(medianHeight * 1.7, 16, 26),
        captionMergeGap: clamp(medianRowGap * 2.2, 18, 36),
        captionContinuationGap: clamp(medianRowGap * 1.4, 16, 26),
        bodyGapThreshold: clamp(medianRowGap * 1.9, 24, 34),
        paragraphGapThreshold: clamp(medianRowGap * 1.6, 18, 30),
        bandMargin: clamp(medianHeight * 1.8, 16, 28),
        medianHeight,
    }
}

function groupItemsIntoRows(items, metrics) {
    const sorted = [...items].sort((left, right) => {
        if (Math.abs(right.centerY - left.centerY) > 0.001) {
            return right.centerY - left.centerY
        }

        return left.x - right.x
    })

    const rows = []

    for (const item of sorted) {
        const currentRow = rows[rows.length - 1]

        if (!currentRow || Math.abs(currentRow.centerY - item.centerY) > metrics.rowTolerance) {
            rows.push({
                rowIndex: rows.length,
                items: [item],
                centerY: item.centerY,
            })
            continue
        }

        currentRow.items.push(item)
        currentRow.centerY =
            (currentRow.centerY * (currentRow.items.length - 1) + item.centerY) / currentRow.items.length
    }

    return rows
        .map((row) => finalizeRow(row, metrics))
        .filter((row) => row.fragments.length > 0)
        .map((row, rowIndex) => ({
            ...row,
            rowIndex,
        }))
}

function finalizeRow(row, metrics) {
    const items = [...row.items].sort((left, right) => left.x - right.x)
    const fragments = []
    let currentItems = []

    for (const item of items) {
        const previousItem = currentItems[currentItems.length - 1]
        const gap = previousItem ? item.x - previousItem.right : 0

        if (previousItem && gap > metrics.fragmentGapThreshold) {
            const fragment = createFragment(currentItems, row.rowIndex)
            if (fragment) {
                fragments.push(fragment)
            }
            currentItems = [item]
            continue
        }

        currentItems.push(item)
    }

    const trailingFragment = createFragment(currentItems, row.rowIndex)
    if (trailingFragment) {
        fragments.push(trailingFragment)
    }

    const visibleItems = items.filter((item) => !item.isWhitespace)

    return {
        rowIndex: row.rowIndex,
        centerY: row.centerY,
        minX: visibleItems.length > 0 ? Math.min(...visibleItems.map((item) => item.x)) : 0,
        maxX: visibleItems.length > 0 ? Math.max(...visibleItems.map((item) => item.right)) : 0,
        fragments,
    }
}

function createFragment(items, rowIndex) {
    if (!items || items.length === 0) {
        return null
    }

    const visibleItems = items.filter((item) => !item.isWhitespace)
    if (visibleItems.length === 0) {
        return null
    }

    const text = items.map((item) => item.str).join('')
    const normalizedText = normalizeFragmentText(text)
    if (!normalizedText) {
        return null
    }

    const tokens = normalizedText.split(TOKEN_SPLIT_RE).filter(Boolean)
    const numericTokenCount = tokens.filter((token) => NUMERIC_TOKEN_RE.test(stripEdgePunctuation(token))).length
    const sampleCodeCount = tokens.filter((token) => isSampleCodeToken(token)).length
    const abbreviationTokenCount = tokens.filter((token) => ABBREVIATION_TOKEN_RE.test(token)).length
    const letterCount = countMatches(normalizedText, LETTER_RE)
    const lowerLetterCount = countMatches(normalizedText, LOWER_LETTER_RE)
    const digitCount = countMatches(normalizedText, /\d/g)
    const allCapsTokenCount = tokens.filter((token) => isAllCapsToken(token)).length
    const hasCaptionMatch = normalizedText.match(CAPTION_PREFIX_RE)
    const hasHeaderToken = HEADER_TOKEN_RE.test(normalizedText)
    const hasUnitLabel = UNIT_TOKEN_RE.test(normalizedText)
    const majorClusterCount = countMajorClusters(items)
    const wordCount = tokens.length
    const lowerLetterRatio = lowerLetterCount / Math.max(1, letterCount)
    const digitRatio = digitCount / Math.max(1, normalizedText.replace(/\s+/g, '').length)

    const looksProseLike =
        !hasCaptionMatch &&
        !hasHeaderToken &&
        !hasUnitLabel &&
        wordCount >= 5 &&
        lowerLetterRatio >= 0.45 &&
        numericTokenCount <= 1 &&
        sampleCodeCount === 0 &&
        allCapsTokenCount === 0

    let tableScore = 0

    if (!looksProseLike) {
        if (hasHeaderToken) tableScore += 3
        if (hasUnitLabel) tableScore += 2
        if (allCapsTokenCount > 0 && wordCount <= 3) tableScore += 2
        if (numericTokenCount >= 2) tableScore += 2
        if (digitRatio >= 0.18) tableScore += 1
        if (sampleCodeCount >= 1) tableScore += 1
        if (abbreviationTokenCount >= 2) tableScore += 2
        if (majorClusterCount >= 3 && wordCount <= 8) tableScore += 1
        if (wordCount <= 3 && (numericTokenCount >= 1 || hasUnitLabel || hasHeaderToken)) {
            tableScore += 1
        }
    }

    return {
        rowIndex,
        items,
        visibleItems,
        visibleItemIndexes: visibleItems.map((item) => item.itemIndex),
        text,
        normalizedText,
        tokens,
        wordCount,
        numericTokenCount,
        sampleCodeCount,
        hasHeaderToken,
        hasUnitLabel,
        hasCaptionAnchor: Boolean(hasCaptionMatch),
        captionNumber: hasCaptionMatch ? Number(hasCaptionMatch[2]) : null,
        looksProseLike,
        tableScore,
        isTableLike: tableScore >= 2,
        x: Math.min(...visibleItems.map((item) => item.x)),
        right: Math.max(...visibleItems.map((item) => item.right)),
        bottom: Math.min(...visibleItems.map((item) => item.bottom)),
        top: Math.max(...visibleItems.map((item) => item.top)),
        centerX:
            (Math.min(...visibleItems.map((item) => item.x)) +
                Math.max(...visibleItems.map((item) => item.right))) /
            2,
    }
}

function buildCaptionBlocks(rows, metrics) {
    const anchorFragments = []

    rows.forEach((row) => {
        row.fragments.forEach((fragment) => {
            if (!fragment.hasCaptionAnchor) {
                return
            }

            anchorFragments.push({
                rowIndex: row.rowIndex,
                fragment,
            })
        })
    })

    const captionBlocks = []

    for (const anchor of anchorFragments) {
        const previousBlock = captionBlocks[captionBlocks.length - 1]
        const canMerge =
            previousBlock &&
            previousBlock.captionNumber === anchor.fragment.captionNumber &&
            anchor.rowIndex - previousBlock.endRowIndex <= 3 &&
            verticalGapBetweenRows(rows[previousBlock.endRowIndex], rows[anchor.rowIndex]) <= metrics.captionMergeGap &&
            spansOverlap(previousBlock.band, spanFromFragment(anchor.fragment))

        if (canMerge) {
            previousBlock.fragments.push(anchor.fragment)
            previousBlock.endRowIndex = anchor.rowIndex
            previousBlock.band = unionSpan(previousBlock.band, spanFromFragment(anchor.fragment))
            continue
        }

        captionBlocks.push({
            captionNumber: anchor.fragment.captionNumber,
            fragments: [anchor.fragment],
            startRowIndex: anchor.rowIndex,
            endRowIndex: anchor.rowIndex,
            band: spanFromFragment(anchor.fragment),
        })
    }

    captionBlocks.forEach((block) => extendCaptionBlock(block, rows, metrics))

    return captionBlocks
}

function extendCaptionBlock(block, rows, metrics) {
    let cursor = block.endRowIndex + 1
    let continuationRows = 0

    while (cursor < rows.length && continuationRows < 3) {
        const row = rows[cursor]
        const previousRow = rows[cursor - 1]

        if (verticalGapBetweenRows(previousRow, row) > metrics.captionContinuationGap) {
            break
        }

        if (row.fragments.some((fragment) => fragment.hasCaptionAnchor)) {
            break
        }

        const overlappingFragments = row.fragments.filter((fragment) =>
            spansOverlap(block.band, spanFromFragment(fragment))
        )

        if (overlappingFragments.length !== 1) {
            break
        }

        const [fragment] = overlappingFragments
        if (fragment.isTableLike) {
            break
        }

        if (!isCaptionContinuationFragment(fragment, continuationRows)) {
            break
        }

        block.fragments.push(fragment)
        block.endRowIndex = cursor
        block.band = unionSpan(block.band, spanFromFragment(fragment))
        cursor += 1
        continuationRows += 1
    }
}

function isCaptionContinuationFragment(fragment, continuationRows) {
    if (!fragment || fragment.isTableLike || fragment.hasCaptionAnchor) {
        return false
    }

    if (!fragment.looksProseLike && fragment.wordCount <= 5) {
        return true
    }

    return continuationRows < 2 && fragment.wordCount <= 34
}

function buildTableRegionForCaptionBlock(block, rows, metrics, nextBlockStartRowIndex) {
    let band = expandSpan(block.band, metrics.bandMargin)
    const bodyFragments = []
    const evidenceFragments = []
    const bodyRowIndexes = []
    let lastAcceptedRowIndex = null
    let hasAcceptedDataLikeRow = false

    for (let rowIndex = block.endRowIndex + 1; rowIndex < nextBlockStartRowIndex; rowIndex += 1) {
        const row = rows[rowIndex]

        if (row.fragments.some((fragment) => fragment.hasCaptionAnchor)) {
            break
        }

        if (lastAcceptedRowIndex !== null) {
            const gap = verticalGapBetweenRows(rows[lastAcceptedRowIndex], row)
            if (gap > metrics.bodyGapThreshold) {
                break
            }
        }

        const overlappingFragments = row.fragments.filter((fragment) =>
            spansOverlap(band, spanFromFragment(fragment))
        )

        if (overlappingFragments.length === 0) {
            if (lastAcceptedRowIndex !== null) {
                const gap = verticalGapBetweenRows(rows[lastAcceptedRowIndex], row)
                if (gap > metrics.captionContinuationGap) {
                    break
                }
            }
            continue
        }

        const rowSelection = selectFragmentsForTableRow(overlappingFragments, {
            hasAcceptedDataLikeRow,
            rowsSinceCaption: rowIndex - block.endRowIndex - 1,
        })
        const fragmentsToInclude = rowSelection.fragmentsToInclude

        if (fragmentsToInclude.length === 0) {
            break
        }

        bodyFragments.push(...fragmentsToInclude)
        evidenceFragments.push(...overlappingFragments)
        bodyRowIndexes.push(rowIndex)
        lastAcceptedRowIndex = rowIndex
        hasAcceptedDataLikeRow = hasAcceptedDataLikeRow || rowSelection.hasDataLikeFragment

        for (const fragment of fragmentsToInclude) {
            band = unionSpan(band, spanFromFragment(fragment))
        }
    }

    const bodyScore = bodyFragments.reduce((total, fragment) => total + fragment.tableScore, 0)
    const hasDataLikeFragment = bodyFragments.some(
        (fragment) => fragment.numericTokenCount > 0 || fragment.sampleCodeCount > 0
    )
    const isConfident =
        bodyRowIndexes.length > 0 && (bodyRowIndexes.length >= 2 || bodyScore >= 4 || hasDataLikeFragment)

    if (!isConfident) {
        return {
            isConfident: false,
            allowedItemIndexes: new Set(),
        }
    }

    const allowedItemIndexes = new Set()
    const evidenceItemIndexes = new Set()

    block.fragments.forEach((fragment) => {
        fragment.visibleItemIndexes.forEach((itemIndex) => {
            allowedItemIndexes.add(itemIndex)
            evidenceItemIndexes.add(itemIndex)
        })
    })

    bodyFragments.forEach((fragment) => {
        fragment.visibleItemIndexes.forEach((itemIndex) => {
            allowedItemIndexes.add(itemIndex)
        })
    })

    evidenceFragments.forEach((fragment) => {
        fragment.visibleItemIndexes.forEach((itemIndex) => {
            evidenceItemIndexes.add(itemIndex)
        })
    })

    return {
        isConfident: true,
        captionNumber: block.captionNumber,
        captionText: block.fragments.map((fragment) => fragment.normalizedText).join(' '),
        bodyRowCount: new Set(bodyRowIndexes).size,
        allowedItemIndexes,
        evidenceItemIndexes,
        blockItemIndexes: evidenceItemIndexes,
        regionBounds: boundsFromFragments([...block.fragments, ...evidenceFragments]),
    }
}

function buildConfidentTableRegions(rows, metrics) {
    const captionBlocks = buildCaptionBlocks(rows, metrics)
    if (captionBlocks.length === 0) {
        return []
    }

    const confidentRegions = []
    for (let index = 0; index < captionBlocks.length; index += 1) {
        const block = captionBlocks[index]
        const nextBlock = captionBlocks[index + 1] || null
        const region = buildTableRegionForCaptionBlock(block, rows, metrics, nextBlock?.startRowIndex ?? rows.length)
        if (region.isConfident) {
            confidentRegions.push(region)
        }
    }

    return confidentRegions
}

function buildPageHintMatches(locations, pageNumber, printedPageNumber = null) {
    if (!pageNumber) return []
    return locations
        .filter((location) => {
            if (!location?.id || !location.pageHint) return false
            return (
                Number(location.pageHint) === Number(pageNumber) ||
                (printedPageNumber && Number(location.pageHint) === Number(printedPageNumber))
            )
        })
        .map((location) => ({
            evidenceId: location.id,
            status: EVIDENCE_STATUS.HINTED,
            matchType: printedPageNumber && Number(location.pageHint) === Number(printedPageNumber) && Number(location.pageHint) !== Number(pageNumber)
                ? 'mapped_page_hint'
                : 'page_hint',
            pageNumber,
            sourcePageNumber: location.pageHint || null,
            itemIndexes: [],
        }))
}

function findMatchingTableRegion(tableRegions, location) {
    const tableNumber = parseTableNumber(location.tableLabel || location.sourceCitation)
    if (tableNumber !== null) {
        const numberedMatch = tableRegions.find((region) => Number(region.captionNumber) === tableNumber)
        if (numberedMatch) return numberedMatch
    }

    const tableLabel = normalizeSearchText(location.tableLabel)
    if (!tableLabel) return null

    return tableRegions.find((region) => normalizeSearchText(region.captionText).includes(tableLabel)) || null
}

function findSourceQuoteTextMatch(rows, location, metrics, tableRegions = [], paragraphBlocks = []) {
    const matcher = buildSourceQuoteMatcher(location.sourceQuote)
    if (!matcher) return null

    const fragments = buildSearchFragments(rows)
    const fragmentMatch = findSourceQuoteFragmentMatch(fragments, matcher)
    if (fragmentMatch) {
        const matchedFragments = fragments.slice(fragmentMatch.startIndex, fragmentMatch.endIndex)
        const matchedItemIndexes = itemIndexesForSearchFragments(matchedFragments)
        return buildBlockMatchForItemIndexes(matchedItemIndexes, {
            tableRegions,
            paragraphBlocks,
            fallbackMatch: () => {
                const evidenceFragments = expandFragmentsToParagraph(fragments, fragmentMatch.startIndex, fragmentMatch.endIndex, rows, metrics)
                return {
                    itemIndexes: itemIndexesForSearchFragments(evidenceFragments),
                    matchType: 'paragraph',
                    regionBounds: boundsFromSearchFragments(evidenceFragments),
                }
            },
        })
    }

    const rowMatch = findSourceQuoteRowMatch(rows, matcher)
    if (!rowMatch) return null

    const matchedItemIndexes = itemIndexesForRows(rowMatch.rows)
    return buildBlockMatchForItemIndexes(matchedItemIndexes, {
        tableRegions,
        paragraphBlocks,
        fallbackMatch: () => {
            const evidenceRows = expandRowsToParagraph(rows, rowMatch.startIndex, rowMatch.endIndex, metrics)
            return {
                itemIndexes: itemIndexesForRows(evidenceRows),
                matchType: 'paragraph',
                regionBounds: boundsFromRows(evidenceRows),
            }
        },
    })
}

function buildBlockMatchForItemIndexes(matchedItemIndexes, options = {}) {
    const { tableRegions = [], paragraphBlocks = [], fallbackMatch = null } = options
    const tableRegion = findBlockForItemIndexes(tableRegions, matchedItemIndexes, 'blockItemIndexes')
    if (tableRegion) {
        return {
            itemIndexes: new Set(tableRegion.blockItemIndexes || tableRegion.evidenceItemIndexes),
            matchType: 'table',
            regionBounds: tableRegion.regionBounds,
        }
    }

    const paragraphBlock = findBlockForItemIndexes(paragraphBlocks, matchedItemIndexes, 'itemIndexes')
    if (paragraphBlock) {
        return {
            itemIndexes: new Set(paragraphBlock.itemIndexes),
            matchType: 'paragraph',
            regionBounds: paragraphBlock.regionBounds,
        }
    }

    return fallbackMatch ? fallbackMatch() : null
}

function findSourceQuoteRowMatch(rows, matcher) {
    const maxWindowSize = Math.min(4, rows.length)
    for (let windowSize = 1; windowSize <= maxWindowSize; windowSize += 1) {
        for (let startIndex = 0; startIndex <= rows.length - windowSize; startIndex += 1) {
            const endIndex = startIndex + windowSize
            const windowText = rows.slice(startIndex, endIndex).map(rowSearchText).join(' ')
            if (sourceQuoteMatchesText(matcher, windowText)) {
                return {
                    startIndex,
                    endIndex,
                    rows: rows.slice(startIndex, endIndex),
                }
            }
        }
    }

    return null
}

function buildSearchFragments(rows) {
    const fragments = []
    for (const row of rows) {
        for (const fragment of row.fragments) {
            fragments.push({
                row,
                fragment,
            })
        }
    }
    return fragments
}

function buildParagraphBlocks(rows, tableRegions, metrics) {
    const tableItemIndexes = new Set()
    for (const region of tableRegions || []) {
        for (const itemIndex of region.blockItemIndexes || []) {
            tableItemIndexes.add(itemIndex)
        }
    }

    const fragments = buildSearchFragments(rows)
        .filter((entry) =>
            isParagraphCandidateFragment(entry.fragment) &&
            !fragmentHasAnyItemIndex(entry.fragment, tableItemIndexes)
        )

    const blocks = []
    const assigned = new Set()

    for (let index = 0; index < fragments.length; index += 1) {
        if (assigned.has(index)) continue

        const blockEntries = [fragments[index]]
        assigned.add(index)
        let baseSpan = spanFromFragment(fragments[index].fragment)
        let anchorIndex = index

        while (blockEntries.length < MAX_PARAGRAPH_FRAGMENT_COUNT) {
            const candidateIndex = findAdjacentParagraphFragmentIndex(
                fragments,
                anchorIndex,
                1,
                baseSpan,
                rows,
                metrics
            )
            if (candidateIndex === null || assigned.has(candidateIndex)) break

            blockEntries.push(fragments[candidateIndex])
            assigned.add(candidateIndex)
            anchorIndex = candidateIndex
            baseSpan = unionSpan(baseSpan, spanFromFragment(fragments[candidateIndex].fragment))
        }

        blocks.push({
            blockId: `paragraph-${blocks.length + 1}`,
            entries: blockEntries,
            itemIndexes: itemIndexesForSearchFragments(blockEntries),
            regionBounds: boundsFromSearchFragments(blockEntries),
        })
    }

    return blocks
}

function findSourceQuoteFragmentMatch(fragments, matcher) {
    const maxWindowSize = Math.min(6, fragments.length)
    for (let windowSize = 1; windowSize <= maxWindowSize; windowSize += 1) {
        for (let startIndex = 0; startIndex <= fragments.length - windowSize; startIndex += 1) {
            const endIndex = startIndex + windowSize
            const windowText = fragments
                .slice(startIndex, endIndex)
                .map((entry) => entry.fragment.normalizedText)
                .join(' ')
            if (sourceQuoteMatchesText(matcher, windowText)) {
                return { startIndex, endIndex }
            }
        }
    }

    return null
}

function expandFragmentsToParagraph(fragments, startIndex, endIndex, rows, metrics) {
    const selected = new Set()
    for (let index = startIndex; index < endIndex; index += 1) {
        selected.add(index)
    }

    let baseSpan = fragments
        .slice(startIndex, endIndex)
        .map((entry) => spanFromFragment(entry.fragment))
        .reduce((span, nextSpan) => unionSpan(span, nextSpan))
    let firstIndex = startIndex
    let lastIndex = endIndex - 1

    while (selected.size < MAX_PARAGRAPH_FRAGMENT_COUNT) {
        const candidateIndex = findAdjacentParagraphFragmentIndex(
            fragments,
            firstIndex,
            -1,
            baseSpan,
            rows,
            metrics
        )
        if (candidateIndex === null) break
        selected.add(candidateIndex)
        firstIndex = candidateIndex
        baseSpan = unionSpan(baseSpan, spanFromFragment(fragments[candidateIndex].fragment))
    }

    while (selected.size < MAX_PARAGRAPH_FRAGMENT_COUNT) {
        const candidateIndex = findAdjacentParagraphFragmentIndex(
            fragments,
            lastIndex,
            1,
            baseSpan,
            rows,
            metrics
        )
        if (candidateIndex === null) break
        selected.add(candidateIndex)
        lastIndex = candidateIndex
        baseSpan = unionSpan(baseSpan, spanFromFragment(fragments[candidateIndex].fragment))
    }

    return Array.from(selected)
        .sort((left, right) => left - right)
        .map((index) => fragments[index])
}

function findAdjacentParagraphFragmentIndex(fragments, anchorIndex, direction, baseSpan, rows, metrics) {
    const anchor = fragments[anchorIndex]
    if (!anchor) return null

    for (
        let candidateIndex = anchorIndex + direction;
        candidateIndex >= 0 && candidateIndex < fragments.length;
        candidateIndex += direction
    ) {
        const candidate = fragments[candidateIndex]
        const decision = getParagraphFragmentDecision(candidate, anchor, baseSpan, rows, metrics)
        if (decision === 'skip') continue
        if (decision === 'include') return candidateIndex
        return null
    }

    return null
}

function getParagraphFragmentDecision(candidate, anchor, baseSpan, rows, metrics) {
    if (!candidate || !anchor) return 'stop'
    const candidateRow = rows[candidate.row.rowIndex]
    const anchorRow = rows[anchor.row.rowIndex]
    if (!candidateRow || !anchorRow) return 'stop'

    const rowGap = Math.abs(candidateRow.centerY - anchorRow.centerY)
    const candidateSpan = spanFromFragment(candidate.fragment)
    const sameColumn = spansLikelySameColumn(baseSpan, candidateSpan)

    if (!sameColumn && rowGap <= metrics.rowTolerance * 1.5) {
        return 'skip'
    }

    if (!sameColumn || rowGap > metrics.paragraphGapThreshold) {
        return 'stop'
    }

    if (!isParagraphCandidateFragment(candidate.fragment)) {
        return 'stop'
    }

    return 'include'
}

function expandRowsToParagraph(rows, startIndex, endIndex, metrics) {
    const selected = new Set()
    for (let index = startIndex; index < endIndex; index += 1) {
        selected.add(index)
    }

    let baseSpan = rows
        .slice(startIndex, endIndex)
        .map((row) => ({ left: row.minX, right: row.maxX }))
        .reduce((span, nextSpan) => unionSpan(span, nextSpan))
    let firstIndex = startIndex
    let lastIndex = endIndex - 1

    while (selected.size < MAX_PARAGRAPH_FRAGMENT_COUNT && firstIndex > 0) {
        const candidateIndex = firstIndex - 1
        const candidate = rows[candidateIndex]
        const anchor = rows[firstIndex]
        if (!isParagraphCandidateRow(candidate) ||
            verticalGapBetweenRows(candidate, anchor) > metrics.paragraphGapThreshold ||
            !spansLikelySameColumn(baseSpan, { left: candidate.minX, right: candidate.maxX })
        ) {
            break
        }
        selected.add(candidateIndex)
        firstIndex = candidateIndex
        baseSpan = unionSpan(baseSpan, { left: candidate.minX, right: candidate.maxX })
    }

    while (selected.size < MAX_PARAGRAPH_FRAGMENT_COUNT && lastIndex < rows.length - 1) {
        const candidateIndex = lastIndex + 1
        const candidate = rows[candidateIndex]
        const anchor = rows[lastIndex]
        if (!isParagraphCandidateRow(candidate) ||
            verticalGapBetweenRows(anchor, candidate) > metrics.paragraphGapThreshold ||
            !spansLikelySameColumn(baseSpan, { left: candidate.minX, right: candidate.maxX })
        ) {
            break
        }
        selected.add(candidateIndex)
        lastIndex = candidateIndex
        baseSpan = unionSpan(baseSpan, { left: candidate.minX, right: candidate.maxX })
    }

    return Array.from(selected)
        .sort((left, right) => left - right)
        .map((index) => rows[index])
}

function buildSourceQuoteMatcher(sourceQuote) {
    const normalizedQuote = normalizeSearchText(sourceQuote)
    if (normalizedQuote.length < 8) return null

    const chunks = String(sourceQuote || '')
        .split(ELLIPSIS_SPLIT_RE)
        .map(normalizeSearchText)
        .filter((chunk) => chunk.length >= 4)

    return {
        normalizedQuote,
        chunks: chunks.length > 1 ? chunks : [],
    }
}

function sourceQuoteMatchesText(matcher, text) {
    const normalizedText = normalizeSearchText(text)
    if (normalizedText.includes(matcher.normalizedQuote)) {
        return true
    }

    if (matcher.chunks.length === 0) {
        return false
    }

    let cursor = 0
    for (const chunk of matcher.chunks) {
        const index = normalizedText.indexOf(chunk, cursor)
        if (index < 0) return false
        cursor = index + chunk.length
    }
    return true
}

function rowSearchText(row) {
    return row.fragments.map((fragment) => fragment.normalizedText).join(' ')
}

function itemIndexesForRows(rows) {
    const itemIndexes = new Set()
    for (const row of rows) {
        for (const fragment of row.fragments) {
            fragment.visibleItemIndexes.forEach((itemIndex) => itemIndexes.add(itemIndex))
        }
    }
    return itemIndexes
}

function itemIndexesForSearchFragments(fragments) {
    const itemIndexes = new Set()
    for (const entry of fragments) {
        entry.fragment.visibleItemIndexes.forEach((itemIndex) => itemIndexes.add(itemIndex))
    }
    return itemIndexes
}

function findBlockForItemIndexes(blocks, itemIndexes, itemIndexKey) {
    let bestBlock = null
    let bestOverlapCount = 0

    for (const block of blocks || []) {
        const blockItemIndexes = block?.[itemIndexKey]
        if (!blockItemIndexes) continue

        let overlapCount = 0
        for (const itemIndex of itemIndexes || []) {
            if (blockItemIndexes.has(itemIndex)) {
                overlapCount += 1
            }
        }

        if (overlapCount > bestOverlapCount) {
            bestBlock = block
            bestOverlapCount = overlapCount
        }
    }

    return bestBlock
}

function fragmentHasAnyItemIndex(fragment, itemIndexes) {
    if (!itemIndexes || itemIndexes.size === 0) return false
    return fragment.visibleItemIndexes.some((itemIndex) => itemIndexes.has(itemIndex))
}

function boundsFromRows(rows) {
    const fragments = []
    for (const row of rows) {
        fragments.push(...row.fragments)
    }
    return boundsFromFragments(fragments)
}

function boundsFromSearchFragments(fragments) {
    return boundsFromFragments(fragments.map((entry) => entry.fragment))
}

function boundsFromFragments(fragments) {
    const visibleFragments = fragments.filter((fragment) =>
        Number.isFinite(fragment?.x) &&
        Number.isFinite(fragment?.right) &&
        Number.isFinite(fragment?.bottom) &&
        Number.isFinite(fragment?.top)
    )
    if (visibleFragments.length === 0) return null

    return visibleFragments.reduce((bounds, fragment) => ({
        left: Math.min(bounds.left, fragment.x),
        right: Math.max(bounds.right, fragment.right),
        bottom: Math.min(bounds.bottom, fragment.bottom),
        top: Math.max(bounds.top, fragment.top),
    }), {
        left: visibleFragments[0].x,
        right: visibleFragments[0].right,
        bottom: visibleFragments[0].bottom,
        top: visibleFragments[0].top,
    })
}

function addEvidenceItemIndexes(itemEvidenceIds, itemIndexes, evidenceId) {
    for (const itemIndex of itemIndexes) {
        if (!itemEvidenceIds.has(itemIndex)) {
            itemEvidenceIds.set(itemIndex, new Set())
        }
        itemEvidenceIds.get(itemIndex).add(evidenceId)
    }
}

function parseTableNumber(value) {
    const match = String(value || '').match(SOURCE_TABLE_LABEL_RE)
    if (!match) return null
    const parsed = Number.parseInt(match[1], 10)
    return Number.isFinite(parsed) ? parsed : null
}

function normalizeSearchText(value) {
    return String(value || '')
        .toLowerCase()
        .replace(/[^\p{L}\p{N}%]+/gu, ' ')
        .replace(/\s+/g, ' ')
        .trim()
}

function expandSpan(span, margin) {
    return {
        left: span.left - margin,
        right: span.right + margin,
    }
}

function spanFromFragment(fragment) {
    return {
        left: fragment.x,
        right: fragment.right,
    }
}

function unionSpan(left, right) {
    return {
        left: Math.min(left.left, right.left),
        right: Math.max(left.right, right.right),
    }
}

function spansOverlap(left, right, margin = 0) {
    return right.right >= left.left - margin && right.left <= left.right + margin
}

function spansLikelySameColumn(left, right) {
    const overlap = Math.min(left.right, right.right) - Math.max(left.left, right.left)
    const leftWidth = Math.max(1, left.right - left.left)
    const rightWidth = Math.max(1, right.right - right.left)
    if (overlap >= Math.min(leftWidth, rightWidth) * 0.28) {
        return true
    }
    const leftCenter = (left.left + left.right) / 2
    const rightCenter = (right.left + right.right) / 2
    const centerDistance = Math.abs(leftCenter - rightCenter)
    return centerDistance <= Math.max(40, Math.min(leftWidth, rightWidth) * 0.45)
}

function verticalGapBetweenRows(upperRow, lowerRow) {
    return upperRow.centerY - lowerRow.centerY
}

function countMajorClusters(items) {
    const visibleItems = items.filter((item) => !item.isWhitespace)
    if (visibleItems.length === 0) {
        return 0
    }

    let clusters = 1

    for (let index = 1; index < items.length; index += 1) {
        const previousItem = items[index - 1]
        const currentItem = items[index]
        const rawGap = currentItem.x - previousItem.right
        const wideWhitespace = previousItem.isWhitespace && previousItem.width >= 13

        if (rawGap > 12 || wideWhitespace) {
            clusters += 1
        }
    }

    return clusters
}

function selectFragmentsForTableRow(overlappingFragments, context) {
    const { hasAcceptedDataLikeRow, rowsSinceCaption } = context
    const eligibleFragments = overlappingFragments.filter((fragment) => !fragment.looksProseLike)

    if (eligibleFragments.length === 0) {
        return createEmptyRowSelection()
    }

    const tableLikeFragments = eligibleFragments.filter((fragment) => fragment.isTableLike)
    const shortHeaderFragments = eligibleFragments.filter(isShortHeaderCandidateFragment)
    const rowWordCount = eligibleFragments.reduce((total, fragment) => total + fragment.wordCount, 0)
    const rowHasMultipleCells = eligibleFragments.length >= 2
    const rowHasExplicitHeaderSignal = eligibleFragments.some(
        (fragment) => fragment.hasHeaderToken || fragment.hasUnitLabel
    )
    const rowHasDataLikeFragment = eligibleFragments.some(isDataLikeFragment)
    const headerWordLimit = Math.max(9, eligibleFragments.length * 3)
    const rowIsHeaderLike =
        shortHeaderFragments.length === eligibleFragments.length &&
        rowWordCount <= headerWordLimit &&
        (rowHasMultipleCells || rowHasExplicitHeaderSignal || tableLikeFragments.length > 0)

    if (tableLikeFragments.length > 0) {
        const fragmentsToInclude = rowIsHeaderLike
            ? uniqueFragments([...tableLikeFragments, ...shortHeaderFragments])
            : tableLikeFragments

        return {
            fragmentsToInclude,
            hasDataLikeFragment: rowHasDataLikeFragment,
        }
    }

    const allowHeaderOnlyRow = rowIsHeaderLike && (hasAcceptedDataLikeRow || rowsSinceCaption <= 1)

    if (!allowHeaderOnlyRow) {
        return createEmptyRowSelection()
    }

    return {
        fragmentsToInclude: shortHeaderFragments,
        hasDataLikeFragment: false,
    }
}

function createEmptyRowSelection() {
    return {
        fragmentsToInclude: [],
        hasDataLikeFragment: false,
    }
}

function uniqueFragments(fragments) {
    return Array.from(new Set(fragments))
}

function isShortHeaderCandidateFragment(fragment) {
    return !fragment.looksProseLike && fragment.wordCount > 0 && fragment.wordCount <= 4
}

function isDataLikeFragment(fragment) {
    return fragment.numericTokenCount > 0 || fragment.sampleCodeCount > 0
}

function isParagraphCandidateRow(row) {
    if (!row?.fragments?.length) return false
    return row.fragments.some(isParagraphCandidateFragment)
}

function isParagraphCandidateFragment(fragment) {
    return (
        fragment.wordCount >= 3 &&
        !fragment.hasCaptionAnchor &&
        !fragment.hasHeaderToken
    )
}

function isAllCapsToken(token) {
    const letters = token.match(LETTER_RE) || []
    if (letters.length < 3) {
        return false
    }

    return letters.every((letter) => letter === letter.toUpperCase())
}

function isSampleCodeToken(token) {
    const cleaned = stripEdgePunctuation(token)

    if (!cleaned || NUMERIC_TOKEN_RE.test(cleaned)) {
        return false
    }

    return SAMPLE_CODE_RE.test(cleaned)
}

function stripEdgePunctuation(token) {
    return token.replace(/^[^\p{L}\p{N}%]+|[^\p{L}\p{N}%]+$/gu, '')
}

function normalizeFragmentText(text) {
    return text.replace(/\s+/g, ' ').trim()
}

function extractLabeledPrintedPageNumber(text, pdfPageCount) {
    const normalized = normalizeFragmentText(text)
    const pageFirstMatch = normalized.match(PAGE_LABEL_WITH_NUMBER_RE)
    const pageFirst = normalizePrintedPageCandidate(pageFirstMatch?.[1], pdfPageCount)
    if (pageFirst) return pageFirst

    const numberFirstMatch = normalized.match(NUMBER_WITH_PAGE_LABEL_RE)
    return normalizePrintedPageCandidate(numberFirstMatch?.[1], pdfPageCount)
}

function extractStandalonePrintedPageNumber(text, pdfPageNumber, pdfPageCount) {
    const normalized = normalizeFragmentText(text)
    const match = normalized.match(STANDALONE_PAGE_NUMBER_RE)
    const candidate = normalizePrintedPageCandidate(match?.[1], pdfPageCount)
    if (!candidate) return null

    if (pdfPageCount && candidate > pdfPageCount) return candidate
    if (pdfPageNumber && candidate === Number(pdfPageNumber)) return candidate
    return null
}

function normalizePrintedPageCandidate(value) {
    const pageNumber = normalizePositiveInteger(value)
    if (!pageNumber || pageNumber > 5000) return null
    return pageNumber
}

function normalizePositiveInteger(value) {
    const parsed = Number.parseInt(value, 10)
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function median(values, fallback) {
    if (!values || values.length === 0) {
        return fallback
    }

    const sorted = [...values].sort((left, right) => left - right)
    const middle = Math.floor(sorted.length / 2)

    if (sorted.length % 2 === 0) {
        return (sorted[middle - 1] + sorted[middle]) / 2
    }

    return sorted[middle]
}

function countMatches(value, regex) {
    const matches = value.match(regex)
    return matches ? matches.length : 0
}

function clamp(value, minValue, maxValue) {
    return Math.min(maxValue, Math.max(minValue, value))
}

function escapeHtmlText(value) {
    return String(value).replace(/[&<>"']/g, mapEscapedHtmlChar)
}

function escapeHtmlAttribute(value) {
    return String(value).replace(/[&<>"']/g, mapEscapedHtmlChar)
}

function mapEscapedHtmlChar(char) {
    switch (char) {
        case '&':
            return '&amp;'
        case '<':
            return '&lt;'
        case '>':
            return '&gt;'
        case '"':
            return '&quot;'
        case '\'':
            return '&#39;'
        default:
            return char
    }
}

function collectMatches(text, matcher) {
    const matches = []

    for (const { nutrient, regex } of matcher.patterns) {
        regex.lastIndex = 0

        for (const result of text.matchAll(regex)) {
            const fullMatch = result[0]
            const matchedText = result[2]
            const fullIndex = result.index ?? -1

            if (fullIndex < 0) continue

            const leadingOffset = fullMatch.indexOf(matchedText)
            const start = fullIndex + leadingOffset
            const end = start + matchedText.length

            if (start < 0 || end <= start) continue

            matches.push({ nutrient, start, end })
        }
    }

    if (matches.length === 0) {
        return matches
    }

    matches.sort((left, right) => {
        if (left.start !== right.start) return left.start - right.start
        const leftLength = left.end - left.start
        const rightLength = right.end - right.start
        return rightLength - leftLength
    })

    const resolved = []
    let lastEnd = -1

    // When matches overlap inside a single text item, keep the earlier and
    // longer match so short names do not fragment longer nutrient names.
    for (const match of matches) {
        if (match.start < lastEnd) continue
        resolved.push(match)
        lastEnd = match.end
    }

    return resolved
}
