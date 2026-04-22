/**
 * PdfTextScanner renders highlight markup for individual PDF text items and
 * binds delegated interactions on the text layer after PDF.js finishes
 * rendering it.
 */

const SKIP_NAMES = new Set([
    'proximates',
    'minerals',
    'lipids',
    'vitamins and other components',
    'other',
])

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

export function renderTextItemWithNutrientHighlights(text, matcher) {
    const originalText = text || ''

    if (!originalText) {
        return ''
    }

    if (!matcher) {
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

export function bindNutrientHighlightInteractions(textLayerEl, onNutrientClick) {
    if (!textLayerEl) return () => { }

    const resolveMarkFromEvent = (event) => {
        const directTarget = event.target?.closest?.('mark.nutrient-highlight')
        if (directTarget && textLayerEl.contains(directTarget)) {
            return directTarget
        }

        const pointTargets = document.elementsFromPoint?.(event.clientX, event.clientY) || []
        for (const element of pointTargets) {
            const mark = element?.closest?.('mark.nutrient-highlight')
            if (mark && textLayerEl.contains(mark)) {
                return mark
            }
        }

        const caretNode =
            document.caretPositionFromPoint?.(event.clientX, event.clientY)?.offsetNode ||
            document.caretRangeFromPoint?.(event.clientX, event.clientY)?.startContainer ||
            null

        const caretParent = caretNode?.nodeType === Node.TEXT_NODE ? caretNode.parentElement : caretNode
        const caretMark = caretParent?.closest?.('mark.nutrient-highlight')
        if (caretMark && textLayerEl.contains(caretMark)) {
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

    textLayerEl.addEventListener('pointerup', openPopoverForEvent, true)
    textLayerEl.addEventListener('click', openPopoverForEvent, true)

    return () => {
        textLayerEl.removeEventListener('pointerup', openPopoverForEvent, true)
        textLayerEl.removeEventListener('click', openPopoverForEvent, true)
    }
}

function buildBoundaryRegex(name) {
    const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    return new RegExp(`(^|[^A-Za-z0-9])(${escaped})(?=[^A-Za-z0-9]|$)`, 'gi')
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
