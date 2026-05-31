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
// Only count parentheticals that look like actual units (e.g. "(g/100g)", "(mg)",
// "(%)", "(0.5 g)"). Plain editorial parens like "(type 500)" or "(see Table 1)"
// must not flag the fragment as a unit cell — that was costing us paragraph
// candidates whose first line happens to mention a quantity in parens.
const UNIT_TOKEN_RE = /\(\s*(?:[<>~]?\d+(?:[.,]\d+)?\s*)?(?:%|g|mg|µg|μg|ug|kg|ml|l|kcal|kj|iu|ppm|w\s*\/\s*[wv]|v\s*\/\s*v)(?:\s*\/\s*[0-9a-zA-Zµμ%]+)?\s*\)/iu
const UNIT_CODE_TOKEN_RE = /^\d+(?:g|mg|ug|µg|μg|kg|ml|l|kcal|kj|iu)$/iu
const LETTER_RE = /[A-Za-zÇĞİÖŞÜçğıöşü]/g
const LOWER_LETTER_RE = /[a-zçğıöşü]/g
const TOKEN_SPLIT_RE = /\s+/u
const PURE_WHITESPACE_RE = /^\s*$/u
const NUMERIC_TOKEN_RE = /^[<>~]?\d+(?:[.,]\d+)?$/u
const ELLIPSIS_SPLIT_RE = /(?:\.{2,}|…)/u
const SAMPLE_CODE_RE = /^(?:[A-Za-z]{1,4}\d{1,3}|\d{1,3}[A-Za-z]{1,4}|[A-Za-z]-\d{1,3}|\d{1,3}-[A-Za-z]|[A-Za-z]{1,4}\d{1,3}-[A-Za-z]{1,4})$/u
const ABBREVIATION_TOKEN_RE = /^(?:[A-ZÇĞİÖŞÜ]\.){1,4}$/u
const SENTENCE_PUNCTUATION_RE = /[.!?;]/g
const TEXT_PUNCTUATION_RE = /[,.!?;]/g
const NARRATIVE_CONNECTOR_RE = /\b(?:that|which|with|using|revealed|showed|contained|compared|while|because|therefore|however|between|among|through|from|into|after|before)\b/iu
const DOCUMENT_CHROME_RE = /\b(?:department of|university|article information|article history|received|revised|accepted|keywords?|corresponding author|e-?mail|copyright|all rights reserved)\b/iu
const MAX_PARAGRAPH_FRAGMENT_COUNT = 32

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
    const gutters = detectColumnGutters(items, metrics)
    const rows = groupItemsIntoRows(items, metrics, gutters)
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
    const numPages = normalizePositiveInteger(options.numPages)

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
    const gutters = detectColumnGutters(items, metrics)
    const rows = groupItemsIntoRows(items, metrics, gutters)
    if (rows.length === 0) {
        return {
            itemEvidenceIds,
            matches: buildPageHintMatches(locations, pageNumber, printedPageNumber),
        }
    }

    const { confidentRegions: tableRegions, captionFallbacks: tableCaptionFallbacks } =
        buildTableRegionsAndCaptionFallbacks(rows, metrics)
    const paragraphBlocks = buildParagraphBlocks(rows, tableRegions, metrics)

    for (const location of locations) {
        if (!location?.id) continue

        const pageMatchesHint =
            pageNumber &&
            (
                Number(location.pageHint) === Number(pageNumber) ||
                (printedPageNumber && Number(location.pageHint) === printedPageNumber)
            )
        // A page_hint that is larger than the whole PDF can never be a PDF page
        // index — it is a printed/journal page number (e.g. "p. 1217" on a
        // 5-page offprint). Such a hint tells us nothing about where the
        // evidence sits *in this PDF*, so it must not gate content matching;
        // otherwise the caption/quote fallbacks below stay locked and the
        // source renders as a bare unverified chip with nothing to look at.
        const hintExceedsPages = Boolean(location.pageHint && numPages && Number(location.pageHint) > numPages)
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
                    regionKey: buildStableRegionKey('table', pageNumber, tableRegion.regionId, tableRegion.regionBounds),
                })
                matched = true
            }
        }

        // Caption-only fallback for table-labeled sources whose body wasn't
        // detected confidently (sparse data rows, OCR noise, multi-column
        // layouts the region builder gives up on). Highlights just the
        // "Table N ..." caption line so the chip still points the user at
        // something on the page. Gated to the declared hint page for the
        // same reason as the paragraph-quote fallback below: a stray
        // "Table 3" mention in a TOC or references list should not steal
        // the match from the real table on its hint page.
        if (!matched && hasTableMatcher && (pageMatchesHint || hintExceedsPages)) {
            const captionFallback = findMatchingCaptionFallback(tableCaptionFallbacks, location)
            if (captionFallback) {
                const itemIndexes = Array.from(captionFallback.itemIndexes)
                addEvidenceItemIndexes(itemEvidenceIds, itemIndexes, location.id)
                matches.push({
                    evidenceId: location.id,
                    status: EVIDENCE_STATUS.MATCHED,
                    matchType: 'paragraph',
                    pageNumber,
                    itemIndexes,
                    regionBounds: captionFallback.regionBounds,
                    regionKey: buildStableRegionKey('paragraph', pageNumber, captionFallback.regionId, captionFallback.regionBounds),
                })
                matched = true
            }
        }

        // When a source explicitly references a table (e.g. "Table 3"), the
        // paragraph-quote fallback must not run on pages that aren't the
        // declared pageHint. Otherwise the abstract or introduction on page 1
        // — which often paraphrases the same numbers that appear in Table N
        // on a later page — wins the MATCHED slot before the real table is
        // scanned, dragging the chip's pageNumber/regionKey to page 1 and
        // making distinct table sources collapse into the same chip.
        const allowParagraphFallback = !hasTableMatcher || pageMatchesHint || hintExceedsPages
        if (!matched && shouldSearchPage && location.sourceQuote && allowParagraphFallback) {
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
                    regionKey: buildStableRegionKey(quoteMatch.matchType, pageNumber, quoteMatch.regionId, quoteMatch.regionBounds),
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

    const unifiedMatches = unifyOverlappingParagraphMatches(matches, metrics)
    return { itemEvidenceIds, matches: unifiedMatches }
}

// Distinct evidence quotes that semantically land in the same paragraph but
// resolve to slightly different matched fragments will produce different
// region bounds and therefore different regionKey values. The chip list in
// the sidebar dedups by regionKey, so without unifying them the user sees
// three "Paragraph evidence" chips all pointing at the same paragraph. We
// run union-find over matches on this page: any pair of paragraph matches
// with significant horizontal overlap and small vertical gap collapse to
// a single regionKey (and union regionBounds).
function unifyOverlappingParagraphMatches(matches, metrics) {
    if (!Array.isArray(matches) || matches.length < 2) return matches

    const candidates = []
    for (let index = 0; index < matches.length; index += 1) {
        const match = matches[index]
        if (
            match?.status !== EVIDENCE_STATUS.MATCHED ||
            !match.regionBounds ||
            match.matchType !== 'paragraph'
        ) continue
        candidates.push({ match, index })
    }
    if (candidates.length < 2) return matches

    const proximityPdfUnits = clamp((metrics?.medianHeight || 10) * 2.5, 18, 36)
    const parent = candidates.map((_, i) => i)
    const find = (i) => {
        let root = i
        while (parent[root] !== root) root = parent[root]
        let cursor = i
        while (parent[cursor] !== root) {
            const next = parent[cursor]
            parent[cursor] = root
            cursor = next
        }
        return root
    }
    const union = (i, j) => {
        const rootI = find(i)
        const rootJ = find(j)
        if (rootI !== rootJ) parent[rootI] = rootJ
    }

    for (let i = 0; i < candidates.length; i += 1) {
        for (let j = i + 1; j < candidates.length; j += 1) {
            if (paragraphRegionsShouldUnify(
                candidates[i].match.regionBounds,
                candidates[j].match.regionBounds,
                proximityPdfUnits
            )) {
                union(i, j)
            }
        }
    }

    const groupsByRoot = new Map()
    for (let i = 0; i < candidates.length; i += 1) {
        const root = find(i)
        if (!groupsByRoot.has(root)) groupsByRoot.set(root, [])
        groupsByRoot.get(root).push(candidates[i])
    }

    const updated = matches.slice()
    for (const group of groupsByRoot.values()) {
        if (group.length < 2) continue
        const unionBounds = group.reduce((acc, { match }) => ({
            left: Math.min(acc.left, match.regionBounds.left),
            right: Math.max(acc.right, match.regionBounds.right),
            bottom: Math.min(acc.bottom, match.regionBounds.bottom),
            top: Math.max(acc.top, match.regionBounds.top),
        }), { ...group[0].match.regionBounds })
        const canonicalKey = buildRegionBoundsKey('paragraph', unionBounds)
        for (const { match, index } of group) {
            updated[index] = {
                ...match,
                regionBounds: unionBounds,
                regionKey: canonicalKey,
            }
        }
    }

    return updated
}

function paragraphRegionsShouldUnify(a, b, proximityPdfUnits) {
    if (!a || !b) return false
    const horizontalOverlap = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left))
    const narrowerWidth = Math.max(1, Math.min(a.right - a.left, b.right - b.left))
    if (horizontalOverlap / narrowerWidth < 0.5) return false

    const verticalGap =
        a.bottom > b.top ? a.bottom - b.top :
        b.bottom > a.top ? b.bottom - a.top :
        0
    return verticalGap <= proximityPdfUnits
}

export function detectPrintedPageNumber(textContent, pdfPageNumber = null, pdfPageCount = null) {
    const items = extractPositionedTextItems(textContent)
    if (items.length === 0) return null

    const metrics = buildPageMetrics(items)
    const gutters = detectColumnGutters(items, metrics)
    const rows = groupItemsIntoRows(items, metrics, gutters)
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

function detectColumnGutters(items, metrics) {
    const visibleItems = items.filter((item) => !item.isWhitespace && item.width > 0)
    if (visibleItems.length < 12) return []

    const xs = visibleItems.flatMap((item) => [item.x, item.right])
    const minX = Math.min(...xs)
    const maxX = Math.max(...xs)
    if (maxX - minX < 100) return []

    const yBandHeight = Math.max(metrics.medianHeight, 8)
    const ys = visibleItems.flatMap((item) => [item.y, item.y + item.height])
    const minY = Math.min(...ys)
    const maxY = Math.max(...ys)
    const yBandCount = Math.max(1, Math.ceil((maxY - minY) / yBandHeight) + 1)

    const binWidth = 2
    const binCount = Math.ceil((maxX - minX) / binWidth) + 1
    const bandsByBin = Array.from({ length: binCount }, () => new Set())

    for (const item of visibleItems) {
        const startBin = Math.max(0, Math.floor((item.x - minX) / binWidth))
        const endBin = Math.min(binCount - 1, Math.floor((item.right - minX) / binWidth))
        const yBand = Math.floor((item.y - minY) / yBandHeight)
        for (let bin = startBin; bin <= endBin; bin += 1) {
            bandsByBin[bin].add(yBand)
        }
    }

    // A gutter is an x range where very few y bands have content. Edge margins
    // (leading/trailing whitespace) are excluded later.
    const gutterCoverageMax = Math.max(2, yBandCount * 0.08)
    const minGutterWidthPt = 6
    const minGutterBins = Math.max(1, Math.ceil(minGutterWidthPt / binWidth))

    const gutters = []
    let runStart = null
    for (let bin = 0; bin < binCount; bin += 1) {
        const isGutter = bandsByBin[bin].size <= gutterCoverageMax
        if (isGutter) {
            if (runStart === null) runStart = bin
        } else if (runStart !== null) {
            if (bin - runStart >= minGutterBins) {
                gutters.push({
                    leftX: minX + runStart * binWidth,
                    rightX: minX + bin * binWidth,
                    centerX: minX + ((runStart + bin) / 2) * binWidth,
                })
            }
            runStart = null
        }
    }
    if (runStart !== null && binCount - runStart >= minGutterBins) {
        gutters.push({
            leftX: minX + runStart * binWidth,
            rightX: minX + binCount * binWidth,
            centerX: minX + ((runStart + binCount) / 2) * binWidth,
        })
    }

    // Drop edge margins: only count gutters that have substantial content on
    // both sides. This is what distinguishes a real column gutter from the
    // page margins.
    const significant = gutters.filter((gutter) => {
        const leftBin = Math.floor((gutter.leftX - minX) / binWidth)
        const rightBin = Math.ceil((gutter.rightX - minX) / binWidth)
        let leftSideCovered = false
        let rightSideCovered = false
        for (let bin = 0; bin < leftBin; bin += 1) {
            if (bandsByBin[bin].size > gutterCoverageMax) {
                leftSideCovered = true
                break
            }
        }
        for (let bin = rightBin; bin < binCount; bin += 1) {
            if (bandsByBin[bin].size > gutterCoverageMax) {
                rightSideCovered = true
                break
            }
        }
        return leftSideCovered && rightSideCovered
    })

    return significant
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

function groupItemsIntoRows(items, metrics, gutters = []) {
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
        .map((row) => finalizeRow(row, metrics, gutters))
        .filter((row) => row.fragments.length > 0)
        .map((row, rowIndex) => ({
            ...row,
            rowIndex,
        }))
}

function finalizeRow(row, metrics, gutters = []) {
    const items = [...row.items].sort((left, right) => left.x - right.x)
    const fragments = []
    let currentItems = []

    for (const item of items) {
        const previousItem = currentItems[currentItems.length - 1]
        const gap = previousItem ? item.x - previousItem.right : 0
        const crossesGutter = Boolean(
            previousItem && gutters.some((g) => g.centerX > previousItem.right && g.centerX < item.x)
        )

        if (previousItem && (gap > metrics.fragmentGapThreshold || crossesGutter)) {
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
    const sentencePunctuationCount = countMatches(normalizedText, SENTENCE_PUNCTUATION_RE)
    const textPunctuationCount = countMatches(normalizedText, TEXT_PUNCTUATION_RE)

    const looksProseLike =
        !hasCaptionMatch &&
        !hasHeaderToken &&
        !hasUnitLabel &&
        wordCount >= 5 &&
        lowerLetterRatio >= 0.45 &&
        numericTokenCount <= 1 &&
        sampleCodeCount === 0 &&
        allCapsTokenCount === 0

    const looksNarrativeLike =
        !hasCaptionMatch &&
        !hasHeaderToken &&
        wordCount >= 8 &&
        letterCount >= 12 &&
        lowerLetterRatio >= 0.45 &&
        sampleCodeCount === 0 &&
        allCapsTokenCount <= 1 &&
        majorClusterCount <= 2 &&
        (
            sentencePunctuationCount > 0 ||
            textPunctuationCount >= 2 ||
            NARRATIVE_CONNECTOR_RE.test(normalizedText)
        )

    let tableScore = 0

    if (!looksProseLike && !looksNarrativeLike) {
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
        lowerLetterRatio,
        sentencePunctuationCount,
        textPunctuationCount,
        hasHeaderToken,
        hasUnitLabel,
        hasCaptionAnchor: Boolean(hasCaptionMatch),
        captionNumber: hasCaptionMatch ? Number(hasCaptionMatch[2]) : null,
        looksProseLike,
        looksNarrativeLike,
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
        regionId: `table-${block.captionNumber ?? 'x'}-${block.startRowIndex}`,
        allowedItemIndexes,
        evidenceItemIndexes,
        blockItemIndexes: evidenceItemIndexes,
        regionBounds: boundsFromFragments([...block.fragments, ...evidenceFragments]),
    }
}

// One pass produces both the high-confidence table regions (caption + body
// detected) and a minimal caption-only fallback for every caption block we
// recognize, including ones whose body extraction wasn't confident. The
// fallback list is consumed by the evidence matcher so that table-labeled
// sources still get *some* highlight (just the caption row) when the body
// is too messy to detect — rather than leaving the source as a bare "Page
// hint" chip with nothing on the page to look at.
function buildTableRegionsAndCaptionFallbacks(rows, metrics) {
    const captionBlocks = buildCaptionBlocks(rows, metrics)
    if (captionBlocks.length === 0) {
        return { confidentRegions: [], captionFallbacks: [] }
    }

    const confidentRegions = []
    const captionFallbacks = []
    for (let index = 0; index < captionBlocks.length; index += 1) {
        const block = captionBlocks[index]
        const nextBlock = captionBlocks[index + 1] || null
        const region = buildTableRegionForCaptionBlock(block, rows, metrics, nextBlock?.startRowIndex ?? rows.length)
        if (region.isConfident) {
            confidentRegions.push(region)
        }
        if (block.captionNumber !== null && block.captionNumber !== undefined) {
            const itemIndexes = new Set()
            block.fragments.forEach((fragment) => {
                fragment.visibleItemIndexes.forEach((itemIndex) => itemIndexes.add(itemIndex))
            })
            captionFallbacks.push({
                captionNumber: block.captionNumber,
                captionText: block.fragments.map((fragment) => fragment.normalizedText).join(' '),
                regionId: `table-caption-${block.captionNumber}-${block.startRowIndex}`,
                itemIndexes,
                regionBounds: boundsFromFragments(block.fragments),
            })
        }
    }

    return { confidentRegions, captionFallbacks }
}

function findMatchingCaptionFallback(captionFallbacks, location) {
    if (!captionFallbacks?.length) return null
    const tableNumber = parseTableNumber(location.tableLabel || location.sourceCitation)
    if (tableNumber !== null) {
        const numberedMatch = captionFallbacks.find((region) => Number(region.captionNumber) === tableNumber)
        if (numberedMatch) return numberedMatch
    }
    const tableLabel = normalizeSearchText(location.tableLabel)
    if (!tableLabel) return null
    return captionFallbacks.find((region) => normalizeSearchText(region.captionText).includes(tableLabel)) || null
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

    const paragraphFragments = (paragraphBlocks || []).flatMap((block) => block.entries || [])
    const paragraphFragmentMatch = findSourceQuoteFragmentMatch(paragraphFragments, matcher)
    if (paragraphFragmentMatch) {
        const matchedFragments = paragraphFragments.slice(paragraphFragmentMatch.startIndex, paragraphFragmentMatch.endIndex)
        const matchedItemIndexes = itemIndexesForSearchFragments(matchedFragments)
        return buildBlockMatchForItemIndexes(matchedItemIndexes, {
            tableRegions,
            paragraphBlocks,
            fallbackMatch: () => snapToNearestParagraphBlock(
                {
                    itemIndexes: matchedItemIndexes,
                    matchType: 'paragraph',
                    regionBounds: boundsFromSearchFragments(matchedFragments),
                },
                paragraphBlocks
            ),
        })
    }

    const fragments = buildSearchFragments(rows)
    const fragmentMatch = findSourceQuoteFragmentMatch(fragments, matcher)
    if (fragmentMatch) {
        const matchedFragments = fragments.slice(fragmentMatch.startIndex, fragmentMatch.endIndex)
        const matchedItemIndexes = itemIndexesForSearchFragments(matchedFragments)
        return buildBlockMatchForItemIndexes(matchedItemIndexes, {
            tableRegions,
            paragraphBlocks,
            fallbackMatch: () => {
                const evidenceFragments = clipEntriesToDominantColumn(
                    expandFragmentsToParagraph(fragments, fragmentMatch.startIndex, fragmentMatch.endIndex, rows, metrics)
                )
                return snapToNearestParagraphBlock(
                    {
                        itemIndexes: itemIndexesForSearchFragments(evidenceFragments),
                        matchType: 'paragraph',
                        regionBounds: boundsFromSearchFragments(evidenceFragments),
                    },
                    paragraphBlocks
                )
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
            const evidenceEntries = clipEntriesToDominantColumn(
                evidenceRows.flatMap((row) => row.fragments.map((fragment) => ({ row, fragment })))
            )
            return snapToNearestParagraphBlock(
                {
                    itemIndexes: itemIndexesForSearchFragments(evidenceEntries),
                    matchType: 'paragraph',
                    regionBounds: boundsFromSearchFragments(evidenceEntries),
                },
                paragraphBlocks
            )
        },
    })
}

// When the matched fragments don't sit inside any paragraph block's
// itemIndexes (e.g. the bullet's first line was rejected as a paragraph
// candidate because of a parenthetical), reuse the nearest same-column
// paragraph block's id and bounds. This keeps the chip and overlay dedup
// identity-based instead of leaving every near-miss with its own
// bounds-based regionKey.
function snapToNearestParagraphBlock(fallbackResult, paragraphBlocks) {
    if (!fallbackResult?.regionBounds || !paragraphBlocks?.length) {
        return fallbackResult
    }
    const nearest = findNearestSameColumnBlock(paragraphBlocks, fallbackResult.regionBounds)
    if (!nearest) return fallbackResult
    return {
        ...fallbackResult,
        regionBounds: nearest.regionBounds,
        regionId: nearest.blockId,
        itemIndexes: new Set(nearest.itemIndexes),
    }
}

function findNearestSameColumnBlock(blocks, regionBounds) {
    let bestBlock = null
    let bestDistance = Infinity
    for (const block of blocks) {
        const blockBounds = block?.regionBounds
        if (!blockBounds) continue
        if (!spansLikelySameColumn(
            { left: blockBounds.left, right: blockBounds.right },
            { left: regionBounds.left, right: regionBounds.right }
        )) {
            continue
        }
        const verticalGap = verticalDistanceBetweenBounds(blockBounds, regionBounds)
        if (verticalGap < bestDistance) {
            bestDistance = verticalGap
            bestBlock = block
        }
    }
    // Cap on how far the snap can stretch — anything beyond a handful of lines
    // is more likely a genuinely separate paragraph that shouldn't share a chip.
    return bestDistance <= 60 ? bestBlock : null
}

function verticalDistanceBetweenBounds(a, b) {
    if (a.top < b.bottom) return b.bottom - a.top
    if (b.top < a.bottom) return a.bottom - b.top
    return 0
}

function buildBlockMatchForItemIndexes(matchedItemIndexes, options = {}) {
    const { tableRegions = [], paragraphBlocks = [], fallbackMatch = null } = options
    const tableRegion = findBlockForItemIndexes(tableRegions, matchedItemIndexes, 'blockItemIndexes')
    if (tableRegion) {
        return {
            itemIndexes: new Set(tableRegion.blockItemIndexes || tableRegion.evidenceItemIndexes),
            matchType: 'table',
            regionBounds: tableRegion.regionBounds,
            regionId: tableRegion.regionId || null,
        }
    }

    const paragraphBlock = findBlockForItemIndexes(paragraphBlocks, matchedItemIndexes, 'itemIndexes')
    if (paragraphBlock) {
        return {
            itemIndexes: new Set(paragraphBlock.itemIndexes),
            matchType: 'paragraph',
            regionBounds: paragraphBlock.regionBounds,
            regionId: paragraphBlock.blockId || null,
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
    return groupFragmentsByColumn(fragments)
}

// Cluster fragments by their left edge into approximate columns, then sort
// each column top-to-bottom. Windowed source-quote matching needs adjacent
// entries in the search array to actually be visually adjacent on the page;
// otherwise a single right-column fragment slotted between two left-column
// rows blocks the join and the match silently fails.
function groupFragmentsByColumn(entries) {
    if (entries.length <= 1) return entries
    const sortedByX = [...entries].sort((a, b) => a.fragment.x - b.fragment.x)
    const columnTolerance = 30
    const columns = []
    for (const entry of sortedByX) {
        let placed = false
        for (const column of columns) {
            if (Math.abs(entry.fragment.x - column.x) <= columnTolerance) {
                column.entries.push(entry)
                column.x = (column.x * (column.entries.length - 1) + entry.fragment.x) / column.entries.length
                placed = true
                break
            }
        }
        if (!placed) {
            columns.push({ x: entry.fragment.x, entries: [entry] })
        }
    }
    for (const column of columns) {
        column.entries.sort((a, b) => b.row.centerY - a.row.centerY)
    }
    columns.sort((a, b) => a.x - b.x)
    return columns.flatMap((column) => column.entries)
}

function buildParagraphCandidateEntries(rows, tableItemIndexes, metrics) {
    const entries = []

    for (const row of rows) {
        const usableFragments = row.fragments.filter((fragment) =>
            !fragmentHasAnyItemIndex(fragment, tableItemIndexes) &&
            !isDocumentChromeFragment(fragment)
        )
        if (usableFragments.length === 0) continue

        const segments = splitFragmentsIntoLineSegments(usableFragments, metrics)
        segments.forEach((segment, segmentIndex) => {
            if (!isParagraphCandidateSegment(segment)) {
                return
            }

            const paragraphSegmentKey = `${row.rowIndex}:${segmentIndex}`
            segment.forEach((fragment) => {
                entries.push({
                    row,
                    fragment,
                    paragraphSegmentKey,
                })
            })
        })
    }

    return entries
}

function splitFragmentsIntoLineSegments(fragments, metrics) {
    const sorted = [...fragments].sort((left, right) => left.x - right.x)
    const segments = []
    let current = []
    const gapThreshold = Math.max(metrics.fragmentGapThreshold, metrics.medianHeight * 2)

    for (const fragment of sorted) {
        const previous = current[current.length - 1]
        const gap = previous ? fragment.x - previous.right : 0

        if (previous && gap > gapThreshold) {
            segments.push(current)
            current = [fragment]
            continue
        }

        current.push(fragment)
    }

    if (current.length > 0) {
        segments.push(current)
    }

    return segments
}

function isParagraphCandidateSegment(segment) {
    if (!segment?.length) return false
    if (segment.some(isParagraphCandidateFragment)) return true

    const text = segment.map((fragment) => fragment.normalizedText).join(' ')
    const tokens = text.split(TOKEN_SPLIT_RE).filter(Boolean)
    const wordCount = tokens.length
    const letterCount = countMatches(text, LETTER_RE)
    const lowerLetterCount = countMatches(text, LOWER_LETTER_RE)
    const lowerLetterRatio = lowerLetterCount / Math.max(1, letterCount)
    const textPunctuationCount = countMatches(text, TEXT_PUNCTUATION_RE)
    const numericTokenCount = tokens.filter((token) => NUMERIC_TOKEN_RE.test(stripEdgePunctuation(token))).length
    const sampleCodeCount = tokens.filter((token) => isSampleCodeToken(token)).length

    return (
        wordCount >= 5 &&
        letterCount >= 8 &&
        lowerLetterRatio >= 0.35 &&
        textPunctuationCount >= 1 &&
        sampleCodeCount === 0 &&
        numericTokenCount < wordCount
    )
}

function buildParagraphBlocks(rows, tableRegions, metrics) {
    const tableItemIndexes = new Set()
    for (const region of tableRegions || []) {
        for (const itemIndex of region.blockItemIndexes || []) {
            tableItemIndexes.add(itemIndex)
        }
    }

    const fragments = buildParagraphCandidateEntries(rows, tableItemIndexes, metrics)

    const blocks = []
    const assigned = new Set()

    for (let index = 0; index < fragments.length; index += 1) {
        if (assigned.has(index)) continue

        const blockEntries = [fragments[index]]
        assigned.add(index)
        let anchorIndex = index

        while (blockEntries.length < MAX_PARAGRAPH_FRAGMENT_COUNT) {
            const candidateIndex = findAdjacentParagraphFragmentIndex(
                fragments,
                anchorIndex,
                1,
                rows,
                metrics
            )
            if (candidateIndex === null || assigned.has(candidateIndex)) break

            blockEntries.push(fragments[candidateIndex])
            assigned.add(candidateIndex)
            anchorIndex = candidateIndex
        }

        const clippedEntries = clipEntriesToDominantColumn(blockEntries)

        blocks.push({
            blockId: `paragraph-${blocks.length + 1}`,
            entries: clippedEntries,
            itemIndexes: itemIndexesForSearchFragments(clippedEntries),
            regionBounds: boundsFromSearchFragments(clippedEntries),
        })
    }

    return mergeAdjacentParagraphBlocks(blocks, rows, tableRegions, metrics)
}

// Two prose lines in a paragraph that has an interleaved numeric / values-only
// line (e.g. "average contents of 22.04 ± 1.25 g/100 g, 51.65 ± 2.54 g/100 g")
// end up in different blocks: the numeric line fails isParagraphCandidateFragment
// (too many numerics, isTableLike), gets filtered from candidate entries, and
// the row-gap from prose-before to prose-after then exceeds paragraphGapThreshold.
// Two quotes that both land in this paragraph would otherwise resolve to different
// blockIds and render as two offset overlay boxes.
function mergeAdjacentParagraphBlocks(blocks, rows, tableRegions, metrics) {
    if (!Array.isArray(blocks) || blocks.length < 2) return blocks

    const tableRowIndexes = collectTableRowIndexes(rows, tableRegions)
    const sortedBlocks = [...blocks]
        .filter((block) => block.regionBounds && block.entries?.length)
        .sort((left, right) => right.regionBounds.top - left.regionBounds.top)

    let working = sortedBlocks
    let safetyHops = working.length

    while (safetyHops > 0) {
        safetyHops -= 1
        let mergedAny = false
        const next = []
        let index = 0
        while (index < working.length) {
            const upper = working[index]
            const lower = working[index + 1]
            if (lower && canMergeParagraphBlocks(upper, lower, rows, tableRowIndexes, metrics)) {
                next.push(mergeTwoParagraphBlocks(upper, lower, rows))
                index += 2
                mergedAny = true
            } else {
                next.push(upper)
                index += 1
            }
        }
        working = next
        if (!mergedAny) break
    }
    return working
}

function collectTableRowIndexes(rows, tableRegions) {
    const result = new Set()
    for (const region of tableRegions || []) {
        const bounds = region?.regionBounds
        if (!bounds) continue
        for (const row of rows) {
            if (row.centerY <= bounds.top && row.centerY >= bounds.bottom) {
                result.add(row.rowIndex)
            }
        }
    }
    return result
}

function canMergeParagraphBlocks(upper, lower, rows, tableRowIndexes, metrics) {
    const upperSpan = { left: upper.regionBounds.left, right: upper.regionBounds.right }
    const lowerSpan = { left: lower.regionBounds.left, right: lower.regionBounds.right }
    if (!spansLikelySameColumn(upperSpan, lowerSpan)) return false

    const upperMaxRow = maxRowIndexInBlock(upper)
    const lowerMinRow = minRowIndexInBlock(lower)
    if (upperMaxRow === null || lowerMinRow === null) return false
    if (lowerMinRow - upperMaxRow < 2) return false

    const combinedSpan = unionSpan(upperSpan, lowerSpan)
    let previousRow = rows[upperMaxRow]
    if (!previousRow) return false

    for (let rowIndex = upperMaxRow + 1; rowIndex < lowerMinRow; rowIndex += 1) {
        const row = rows[rowIndex]
        if (!row) return false
        if (verticalGapBetweenRows(previousRow, row) > metrics.paragraphGapThreshold) return false
        if (!isParagraphInternalDataRow(row, combinedSpan, tableRowIndexes)) return false
        previousRow = row
    }

    const lowerFirstRow = rows[lowerMinRow]
    if (!lowerFirstRow) return false
    if (verticalGapBetweenRows(previousRow, lowerFirstRow) > metrics.paragraphGapThreshold) return false

    return true
}

function isParagraphInternalDataRow(row, blockSpan, tableRowIndexes) {
    if (tableRowIndexes.has(row.rowIndex)) return false
    if (isParagraphCandidateRow(row)) return false
    if (!row.fragments?.length) return false

    for (const fragment of row.fragments) {
        if (fragment.hasCaptionAnchor) return false
        if (fragment.hasHeaderToken) return false
        if (isDocumentChromeFragment(fragment)) return false
    }

    const hasDataLikeFragment = row.fragments.some(isDataLikeFragment)
    if (!hasDataLikeFragment) return false

    return spansLikelySameColumn(blockSpan, { left: row.minX, right: row.maxX })
}

function maxRowIndexInBlock(block) {
    let result = null
    for (const entry of block?.entries || []) {
        const rowIndex = entry?.row?.rowIndex
        if (!Number.isInteger(rowIndex)) continue
        if (result === null || rowIndex > result) result = rowIndex
    }
    return result
}

function minRowIndexInBlock(block) {
    let result = null
    for (const entry of block?.entries || []) {
        const rowIndex = entry?.row?.rowIndex
        if (!Number.isInteger(rowIndex)) continue
        if (result === null || rowIndex < result) result = rowIndex
    }
    return result
}

function mergeTwoParagraphBlocks(upper, lower, rows) {
    const combinedEntries = [...upper.entries, ...lower.entries]
    const combinedItemIndexes = new Set([...upper.itemIndexes, ...lower.itemIndexes])

    const upperMaxRow = maxRowIndexInBlock(upper)
    const lowerMinRow = minRowIndexInBlock(lower)
    if (upperMaxRow !== null && lowerMinRow !== null) {
        for (let rowIndex = upperMaxRow + 1; rowIndex < lowerMinRow; rowIndex += 1) {
            const row = rows[rowIndex]
            if (!row) continue
            for (const fragment of row.fragments) {
                for (const itemIndex of fragment.visibleItemIndexes) {
                    combinedItemIndexes.add(itemIndex)
                }
            }
        }
    }

    return {
        blockId: upper.blockId,
        entries: combinedEntries,
        itemIndexes: combinedItemIndexes,
        regionBounds: {
            left: Math.min(upper.regionBounds.left, lower.regionBounds.left),
            right: Math.max(upper.regionBounds.right, lower.regionBounds.right),
            bottom: Math.min(upper.regionBounds.bottom, lower.regionBounds.bottom),
            top: Math.max(upper.regionBounds.top, lower.regionBounds.top),
        },
    }
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

    let firstIndex = startIndex
    let lastIndex = endIndex - 1

    while (selected.size < MAX_PARAGRAPH_FRAGMENT_COUNT) {
        const candidateIndex = findAdjacentParagraphFragmentIndex(
            fragments,
            firstIndex,
            -1,
            rows,
            metrics
        )
        if (candidateIndex === null) break
        selected.add(candidateIndex)
        firstIndex = candidateIndex
    }

    while (selected.size < MAX_PARAGRAPH_FRAGMENT_COUNT) {
        const candidateIndex = findAdjacentParagraphFragmentIndex(
            fragments,
            lastIndex,
            1,
            rows,
            metrics
        )
        if (candidateIndex === null) break
        selected.add(candidateIndex)
        lastIndex = candidateIndex
    }

    return Array.from(selected)
        .sort((left, right) => left - right)
        .map((index) => fragments[index])
}

function findAdjacentParagraphFragmentIndex(fragments, anchorIndex, direction, rows, metrics) {
    const anchor = fragments[anchorIndex]
    if (!anchor) return null

    for (
        let candidateIndex = anchorIndex + direction;
        candidateIndex >= 0 && candidateIndex < fragments.length;
        candidateIndex += direction
    ) {
        const candidate = fragments[candidateIndex]
        const decision = getParagraphFragmentDecision(candidate, anchor, rows, metrics)
        if (decision === 'skip') continue
        if (decision === 'include') return candidateIndex
        return null
    }

    return null
}

function getParagraphFragmentDecision(candidate, anchor, rows, metrics) {
    if (!candidate || !anchor) return 'stop'
    const candidateRow = rows[candidate.row.rowIndex]
    const anchorRow = rows[anchor.row.rowIndex]
    if (!candidateRow || !anchorRow) return 'stop'

    const rowGap = Math.abs(candidateRow.centerY - anchorRow.centerY)
    const candidateSpan = spanFromFragment(candidate.fragment)
    const anchorSpan = spanFromFragment(anchor.fragment)
    const sameColumn = spansLikelySameColumn(anchorSpan, candidateSpan)

    // Cross-column candidates never join the anchor's block. The segmentKey
    // path that used to override this was inviting bleed: when the segment
    // gap threshold (max of fragmentGap and medianHeight*2) is slightly
    // larger than the actual column gutter, a left-column fragment and a
    // right-column fragment on near-the-same y end up with the same
    // segmentKey and would otherwise merge. Column membership is the
    // authoritative signal here.
    if (!sameColumn) {
        if (rowGap <= metrics.rowTolerance * 1.5) {
            return 'skip'
        }
        return 'stop'
    }

    if (rowGap > metrics.paragraphGapThreshold) {
        return 'stop'
    }

    if (!candidate.paragraphSegmentKey && !isParagraphCandidateFragment(candidate.fragment)) {
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

function buildStableRegionKey(matchType, pageNumber, regionId, regionBounds) {
    const pagePart = pageNumber != null ? String(pageNumber) : '?'
    if (regionId) {
        return [matchType === 'table' ? 'table' : 'paragraph', pagePart, regionId].join(':')
    }
    return buildRegionBoundsKey(matchType, regionBounds)
}

function clipEntriesToDominantColumn(entries) {
    if (!Array.isArray(entries) || entries.length <= 2) {
        return entries
    }

    const lefts = entries.map((entry) => entry.fragment.x)
    const rights = entries.map((entry) => entry.fragment.right)
    const medianLeft = median(lefts, 0)
    const medianRight = median(rights, 0)
    // Robust spread via median absolute deviation. Resists single wide outliers
    // (e.g. a row where PDF.js fused two columns into one fragment) better than
    // IQR, which would absorb the outlier into q3.
    const madLeft = median(lefts.map((value) => Math.abs(value - medianLeft)), 0)
    const madRight = median(rights.map((value) => Math.abs(value - medianRight)), 0)
    const leftFence = Math.max(20, madLeft * 3)
    const rightFenceUp = Math.max(30, madRight * 3)
    // Paragraph endings are legitimately shorter than the column, so the lower
    // fence is much looser than the upper one.
    const rightFenceDown = Math.max(80, madRight * 6)

    const filtered = entries.filter((entry) => {
        const x = entry.fragment.x
        const right = entry.fragment.right
        return (
            Math.abs(x - medianLeft) <= leftFence &&
            right <= medianRight + rightFenceUp &&
            right >= medianRight - rightFenceDown
        )
    })

    return filtered.length >= Math.max(2, Math.ceil(entries.length / 2)) ? filtered : entries
}

function buildRegionBoundsKey(matchType, regionBounds) {
    if (
        !regionBounds ||
        !Number.isFinite(regionBounds.left) ||
        !Number.isFinite(regionBounds.right) ||
        !Number.isFinite(regionBounds.bottom) ||
        !Number.isFinite(regionBounds.top)
    ) {
        return null
    }

    return [
        matchType === 'table' ? 'table' : 'paragraph',
        regionBounds.left.toFixed(1),
        regionBounds.right.toFixed(1),
        regionBounds.bottom.toFixed(1),
        regionBounds.top.toFixed(1),
    ].join(':')
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
        // Insert whitespace at digit-letter boundaries so PDF items rendered
        // without an explicit space ("10.80g/100 g") still normalise the same
        // way as the quote ("10.80 g/100 g"). Applied to both sides so the
        // matcher and the searched text stay aligned.
        .replace(/([0-9])([\p{L}])/gu, '$1 $2')
        .replace(/([\p{L}])([0-9])/gu, '$1 $2')
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
    const eligibleFragments = overlappingFragments.filter((fragment) =>
        !fragment.looksProseLike && !fragment.looksNarrativeLike
    )

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

    // Once a data-like row has been accepted, keep accepting further rows that
    // carry data-like content even if none of their fragments individually score
    // isTableLike. Inside an established table the row's context is the signal:
    // a cell like "Nd" or a lone "1.50" only scores 1 on its own but is plainly
    // part of the table body.
    if (hasAcceptedDataLikeRow && rowHasDataLikeFragment) {
        return {
            fragmentsToInclude: eligibleFragments,
            hasDataLikeFragment: true,
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
    if (
        !fragment ||
        fragment.hasCaptionAnchor ||
        fragment.hasHeaderToken ||
        isDocumentChromeFragment(fragment)
    ) {
        return false
    }

    if (fragment.wordCount < 5) {
        return false
    }

    return (
        fragment.looksProseLike ||
        fragment.looksNarrativeLike ||
        (
            fragment.wordCount >= 6 &&
            fragment.lowerLetterRatio >= 0.45 &&
            !fragment.isTableLike
        )
    )
}

function isDocumentChromeFragment(fragment) {
    return DOCUMENT_CHROME_RE.test(fragment?.normalizedText || '')
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

    if (UNIT_CODE_TOKEN_RE.test(cleaned)) {
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
