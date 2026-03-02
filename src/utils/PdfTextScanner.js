/**
 * PdfTextScanner — scans PDF text layer DOM for nutrient name matches
 * and adds highlight styling + click handlers.
 */

// Category headers and meta-entries to skip
const SKIP_NAMES = new Set([
    'proximates',
    'minerals',
    'lipids',
    'vitamins and other components',
    'other',
])

// Short/ambiguous nutrient names that need word-boundary matching
const SHORT_AMBIGUOUS = new Set([
    'water', 'ash', 'solids', 'energy', 'nitrogen', 'starch',
])

/**
 * Build a lookup structure from the nutrients list for efficient matching.
 * @param {Array} nutrients — array of { id, name, unit_name, rank }
 * @returns {Object} { patterns: [{nutrient, regex}], nameMap: Map<lowerName, nutrient> }
 */
export function buildNutrientMatcher(nutrients) {
    const nameMap = new Map()
    const patterns = []

    for (const n of nutrients) {
        const lower = n.name.toLowerCase()

        // Skip category headers
        if (SKIP_NAMES.has(lower)) continue
        // Skip "DO NOT USE" entries
        if (lower.includes('do not use')) continue

        nameMap.set(lower, n)

        // Escape special regex chars in nutrient name
        const escaped = n.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

        // For short/ambiguous names, require word boundaries
        // For longer/specific names, also use word boundaries but they're less likely to false-positive
        const regex = new RegExp(`\\b${escaped}\\b`, 'gi')

        patterns.push({ nutrient: n, regex })
    }

    // Sort by name length descending so longer names match first
    // (e.g., "Vitamin C, total ascorbic acid" before "Vitamin C")
    patterns.sort((a, b) => b.nutrient.name.length - a.nutrient.name.length)

    return { patterns, nameMap }
}

/**
 * Scan a text string for nutrient name matches.
 * @param {string} text — the text content to scan
 * @param {Object} matcher — from buildNutrientMatcher
 * @returns {Set<number>} — set of matched nutrient IDs
 */
export function scanTextForNutrients(text, matcher) {
    const matchedIds = new Set()

    for (const { nutrient, regex } of matcher.patterns) {
        // Reset regex state
        regex.lastIndex = 0
        if (regex.test(text)) {
            matchedIds.add(nutrient.id)
        }
    }

    return matchedIds
}

/**
 * Highlight nutrient names in the PDF text layer DOM.
 * Wraps matched text in <mark> elements with click handlers.
 *
 * @param {HTMLElement} textLayerEl — the .textLayer element from react-pdf
 * @param {Object} matcher — from buildNutrientMatcher
 * @param {Function} onNutrientClick — callback(nutrient, rect) when a highlight is clicked
 * @returns {Function} cleanup — call to remove highlights
 */
export function highlightNutrientsInTextLayer(textLayerEl, matcher, onNutrientClick) {
    if (!textLayerEl) return () => { }

    const marks = []

    // Get all text spans in the text layer
    const spans = textLayerEl.querySelectorAll('span[role="presentation"], span')

    for (const span of spans) {
        // Skip if already processed
        if (span.dataset.nutrientScanned) continue
        span.dataset.nutrientScanned = 'true'

        const originalText = span.textContent
        if (!originalText || originalText.trim().length < 2) continue

        let html = originalText
        let hasMatch = false

        for (const { nutrient, regex } of matcher.patterns) {
            regex.lastIndex = 0
            if (regex.test(originalText)) {
                regex.lastIndex = 0
                html = html.replace(regex, (match) => {
                    hasMatch = true
                    return `<mark class="nutrient-highlight" data-nutrient-id="${nutrient.id}" data-nutrient-name="${nutrient.name}" data-nutrient-unit="${nutrient.unit_name || 'G'}">${match}</mark>`
                })
            }
        }

        if (hasMatch) {
            // Replace span content with highlighted version
            span.innerHTML = html

            // Add click handlers to all marks in this span
            const markEls = span.querySelectorAll('mark.nutrient-highlight')
            for (const mark of markEls) {
                const handler = (e) => {
                    e.stopPropagation()
                    const rect = mark.getBoundingClientRect()
                    const nutrientId = parseInt(mark.dataset.nutrientId)
                    const nutrient = {
                        id: nutrientId,
                        name: mark.dataset.nutrientName,
                        unit_name: mark.dataset.nutrientUnit,
                    }
                    onNutrientClick(nutrient, rect)
                }
                mark.addEventListener('click', handler)
                marks.push({ el: mark, handler })
            }
        }
    }

    // Return cleanup function
    return () => {
        for (const { el, handler } of marks) {
            el.removeEventListener('click', handler)
        }
    }
}
