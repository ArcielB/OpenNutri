/**
 * PdfTextScanner — scans PDF text layer DOM for nutrient name matches
 * and adds highlight styling + click handlers.
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

export function highlightNutrientsInTextLayer(textLayerEl, matcher, onNutrientClick) {
    if (!textLayerEl) return () => { }

    const spans = textLayerEl.querySelectorAll('span[role="presentation"], span')

    for (const span of spans) {
        if (span.dataset.nutrientScanned) continue
        span.dataset.nutrientScanned = 'true'

        const originalText = span.textContent || ''
        if (originalText.trim().length < 2) continue

        const matches = collectMatches(originalText, matcher)
        if (matches.length === 0) continue

        const fragment = document.createDocumentFragment()
        let cursor = 0

        for (const match of matches) {
            if (match.start > cursor) {
                fragment.appendChild(document.createTextNode(originalText.slice(cursor, match.start)))
            }

            const mark = document.createElement('mark')
            mark.className = 'nutrient-highlight'
            mark.dataset.nutrientId = String(match.nutrient.id)
            mark.dataset.nutrientName = match.nutrient.name
            mark.dataset.nutrientUnit = match.nutrient.unit_name || 'G'
            mark.textContent = originalText.slice(match.start, match.end)
            fragment.appendChild(mark)

            cursor = match.end
        }

        if (cursor < originalText.length) {
            fragment.appendChild(document.createTextNode(originalText.slice(cursor)))
        }

        span.replaceChildren(fragment)
    }

    const resolveMarkFromEvent = (event) => {
        // PDF.js text layer bazen tıklanan highlight'ı doğrudan event target olarak
        // vermiyor. Bu yüzden target, elementsFromPoint ve caret tabanlı fallback'leri
        // sırayla deneyip gerçekten işaretlenen nutrient öğesini buluyoruz.
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

    // Aynı span içinde çakışan eşleşmeler olduğunda daha erken başlayan ve
    // daha uzun terimleri koruyoruz; bu sayede kısa terimler uzun nutrient
    // adlarını parçalayıp hatalı highlight üretmiyor.
    for (const match of matches) {
        if (match.start < lastEnd) continue
        resolved.push(match)
        lastEnd = match.end
    }

    return resolved
}
