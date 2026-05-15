import { useState, useEffect, useRef, useCallback, useMemo, useEffectEvent } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import NutrientPopover from './NutrientPopover'
import {
    bindNutrientHighlightInteractions,
    buildPageEvidenceHighlightPlan,
    buildNutrientMatcher,
    buildPageTableHighlightPlan,
    detectPrintedPageNumber,
    renderTextItemWithNutrientHighlights,
} from '../utils/PdfTextScanner'
import { EVIDENCE_STATUS, mergeEvidenceStatuses } from '../utils/EvidenceLocations'

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

export default function PdfViewer({
    pdfUrl,
    allNutrients,
    onAddNutrient,
    theme,
    evidenceLocations = [],
    activeEvidenceId = null,
    activeEvidenceRequestId = null,
    onEvidenceStatusesChange = null,
}) {
    const [numPages, setNumPages] = useState(null)
    const [currentPageNumber, setCurrentPageNumber] = useState(1)
    const [scale, setScale] = useState(1.2)
    const [popover, setPopover] = useState(null) // { nutrient, rect }
    const [pageTextContents, setPageTextContents] = useState(() => ({}))
    const [pageDimensionsByPage, setPageDimensionsByPage] = useState(() => ({}))
    const containerRef = useRef(null)
    const cleanupRef = useRef(null)
    const lastEvidenceStatusesRef = useRef('')

    const nutrientMatcher = useMemo(() => {
        if (!allNutrients || allNutrients.length === 0) {
            return null
        }

        return buildNutrientMatcher(allNutrients)
    }, [allNutrients])

    const buildPageHighlightPlan = useCallback(
        (pageNumber, textContent) => {
            const nextTablePlan = buildPageTableHighlightPlan(textContent)
            const printedPageNumber = detectPrintedPageNumber(textContent, pageNumber, numPages)
            const nextEvidencePlan = buildPageEvidenceHighlightPlan(textContent, evidenceLocations, pageNumber, {
                printedPageNumber,
            })

            return {
                isReady: true,
                printedPageNumber,
                allowedItemIndexes: nextTablePlan.allowedItemIndexes,
                evidenceMatches: nextEvidencePlan.matches,
            }
        },
        [evidenceLocations, numPages]
    )

    const pageHighlightPlans = useMemo(
        () => Object.fromEntries(
            Object.entries(pageTextContents).map(([pageNumber, textContent]) => [
                Number(pageNumber),
                buildPageHighlightPlan(Number(pageNumber), textContent),
            ])
        ),
        [buildPageHighlightPlan, pageTextContents]
    )

    const buildCustomTextRenderer = useCallback(
        (pageNumber) =>
            ({ str, itemIndex }) => {
                const pagePlan = pageHighlightPlans[pageNumber]
                return renderTextItemWithNutrientHighlights(str, nutrientMatcher, {
                    allowHighlight: Boolean(
                        pagePlan?.isReady && pagePlan.allowedItemIndexes.has(itemIndex)
                    ),
                })
            },
        [nutrientMatcher, pageHighlightPlans]
    )

    const evidenceOverlaysByPage = useMemo(
        () => buildEvidenceOverlays(pageHighlightPlans, pageDimensionsByPage),
        [pageDimensionsByPage, pageHighlightPlans]
    )

    function onDocumentLoadSuccess({ numPages }) {
        setNumPages(numPages)
        setCurrentPageNumber(1)
        setPageTextContents({})
        setPageDimensionsByPage({})
        lastEvidenceStatusesRef.current = ''
    }

    const handleNutrientClick = useCallback((nutrient, rect) => {
        setPopover({ nutrient, rect })
    }, [])

    const closePopover = useEffectEvent(() => {
        setPopover(null)
    })

    const handlePageTextSuccess = useCallback((pageNumber, textContent) => {
        setPageTextContents((previous) => ({
            ...previous,
            [pageNumber]: textContent,
        }))
    }, [])

    const handlePageLoadSuccess = useCallback((pageNumber, page) => {
        const nextDimensions = normalizePageDimensions(page)
        if (!nextDimensions) return

        setPageDimensionsByPage((previous) => {
            const current = previous[pageNumber]
            if (
                current?.width === nextDimensions.width &&
                current?.height === nextDimensions.height &&
                current?.originalWidth === nextDimensions.originalWidth &&
                current?.originalHeight === nextDimensions.originalHeight
            ) {
                return previous
            }

            return {
                ...previous,
                [pageNumber]: nextDimensions,
            }
        })
    }, [])

    useEffect(() => {
        if (cleanupRef.current) {
            cleanupRef.current()
            cleanupRef.current = null
        }

        if (!containerRef.current) return

        cleanupRef.current = bindNutrientHighlightInteractions(
            containerRef.current,
            handleNutrientClick
        )
    }, [handleNutrientClick, pdfUrl])

    useEffect(() => {
        closePopover()
    }, [pdfUrl, scale])

    useEffect(() => {
        if (!onEvidenceStatusesChange) return

        const pageMatches = Object.values(pageHighlightPlans).flatMap((plan) => plan.evidenceMatches || [])
        const mappedPageHints = buildMappedPageHintMatches(evidenceLocations, pageHighlightPlans, numPages)
        const statuses = mergeEvidenceStatuses(evidenceLocations, [...pageMatches, ...mappedPageHints])
        const signature = JSON.stringify(statuses)
        if (signature === lastEvidenceStatusesRef.current) return

        lastEvidenceStatusesRef.current = signature
        onEvidenceStatusesChange(statuses)
    }, [evidenceLocations, numPages, onEvidenceStatusesChange, pageHighlightPlans])

    useEffect(() => {
        return () => {
            if (cleanupRef.current) {
                cleanupRef.current()
                cleanupRef.current = null
            }
        }
    }, [])

    useEffect(() => {
        const panel = containerRef.current
        if (!panel || !numPages) return

        const scrollRoot = panel.querySelector('.pdf-container')
        if (!scrollRoot) return

        const observer = new IntersectionObserver(
            (entries) => {
                let bestEntry = null

                for (const entry of entries) {
                    if (!entry.isIntersecting) continue
                    if (!bestEntry || entry.intersectionRatio > bestEntry.intersectionRatio) {
                        bestEntry = entry
                    }
                }

                if (!bestEntry) return

                const nextPage = Number(bestEntry.target.getAttribute('data-page-number') || 1)
                if (Number.isFinite(nextPage)) {
                    setCurrentPageNumber(nextPage)
                }
            },
            {
                root: scrollRoot,
                threshold: [0.25, 0.5, 0.75],
            }
        )

        const pageNodes = scrollRoot.querySelectorAll('[data-page-number]')
        pageNodes.forEach((node) => observer.observe(node))

        return () => observer.disconnect()
    }, [numPages, pdfUrl, scale])

    useEffect(() => {
        if (!activeEvidenceId || !activeEvidenceRequestId) return
        const panel = containerRef.current
        if (!panel) return

        const frameId = window.requestAnimationFrame(() => {
            const matchedEntry = findEvidenceMatchedEntry(pageHighlightPlans, activeEvidenceId)
            const targetPage =
                matchedEntry?.pageNumber ||
                resolveEvidenceHintPage(
                    evidenceLocations.find((location) => location.id === activeEvidenceId),
                    pageHighlightPlans,
                    numPages
                ) ||
                null

            if (!targetPage) return
            const pageNode = panel.querySelector(`[data-page-number="${targetPage}"]`)
            if (pageNode) {
                const overlay = (evidenceOverlaysByPage[Number(targetPage)] || [])
                    .find((entry) => entry.evidenceId === activeEvidenceId) || null
                if (overlay) {
                    scrollPageRegionIntoView(panel, pageNode, overlay)
                } else {
                    pageNode.scrollIntoView({
                        block: matchedEntry?.regionBounds ? 'center' : 'start',
                        inline: 'nearest',
                        behavior: 'smooth',
                    })
                }
                setCurrentPageNumber(Number(targetPage))
            }
        })

        return () => window.cancelAnimationFrame(frameId)
    }, [
        activeEvidenceId,
        activeEvidenceRequestId,
        evidenceOverlaysByPage,
        evidenceLocations,
        numPages,
        pageHighlightPlans,
    ])

    const handlePopoverAdd = (nutrientEntry) => {
        if (onAddNutrient) {
            onAddNutrient(nutrientEntry)
        }
        setPopover(null)
    }

    const panelClassName = `pdf-panel ${theme === 'dark' ? 'pdf-panel-dark' : 'pdf-panel-light'}`

    if (!pdfUrl) {
        return (
            <div className={panelClassName}>
                <div className="pdf-loading">No paper selected</div>
            </div>
        )
    }

    return (
        <div className={panelClassName} ref={containerRef}>
            <div className="pdf-toolbar">
                <button onClick={() => setScale((s) => Math.max(0.5, s - 0.2))}>-</button>
                <button onClick={() => setScale((s) => Math.min(3, s + 0.2))}>+</button>
                <span className="page-info">
                    {numPages ? `${currentPageNumber} / ${numPages}` : '...'}
                </span>
            </div>
            <div className="pdf-container">
                <Document
                    file={pdfUrl}
                    onLoadSuccess={onDocumentLoadSuccess}
                    loading={<div className="pdf-loading">Loading PDF...</div>}
                    error={<div className="pdf-loading">Failed to load PDF</div>}
                >
                    {Array.from({ length: numPages || 0 }, (_, index) => {
                        const pageNumber = index + 1
                        const pageDimensions = pageDimensionsByPage[pageNumber]
                        return (
                            <div
                                className="pdf-page-wrap"
                                data-page-number={pageNumber}
                                key={`pdf-page-${pageNumber}`}
                            >
                                <div
                                    className="pdf-page-stage"
                                    style={buildPageStageStyle(pageDimensions)}
                                >
                                    <Page
                                        pageNumber={pageNumber}
                                        scale={scale}
                                        customTextRenderer={buildCustomTextRenderer(pageNumber)}
                                        renderTextLayer={true}
                                        renderAnnotationLayer={false}
                                        onLoadSuccess={(page) => handlePageLoadSuccess(pageNumber, page)}
                                        onGetTextSuccess={(textContent) =>
                                            handlePageTextSuccess(pageNumber, textContent)
                                        }
                                    />
                                    <EvidenceRegionOverlay overlays={evidenceOverlaysByPage[pageNumber] || []} />
                                </div>
                            </div>
                        )
                    })}
                </Document>
            </div>

            {/* Nutrient popover - floats on top of PDF */}
            {popover && (
                <NutrientPopover
                    nutrient={popover.nutrient}
                    anchorRect={popover.rect}
                    onAdd={handlePopoverAdd}
                    onClose={() => setPopover(null)}
                />
            )}
        </div>
    )
}

function EvidenceRegionOverlay({ overlays }) {
    if (!overlays?.length) return null

    return (
        <div className="evidence-region-overlay" aria-hidden="true">
            {overlays.map((overlay, index) => (
                <div
                    key={`${overlay.evidenceId}-${overlay.type}-${index}`}
                    className={`evidence-region-box evidence-region-box-${overlay.type}`}
                    data-evidence-region-id={overlay.evidenceId}
                    style={{
                        left: overlay.left,
                        top: overlay.top,
                        width: overlay.width,
                        height: overlay.height,
                    }}
                />
            ))}
        </div>
    )
}

function findEvidenceMatchedEntry(pageHighlightPlans, evidenceId) {
    for (const [pageNumber, plan] of Object.entries(pageHighlightPlans || {})) {
        const match = (plan.evidenceMatches || []).find(
            (match) => match.evidenceId === evidenceId && match.status === EVIDENCE_STATUS.MATCHED
        )
        if (match) {
            return {
                ...match,
                pageNumber: Number(pageNumber),
            }
        }
    }
    return null
}

function buildEvidenceOverlays(pageHighlightPlans, pageDimensionsByPage) {
    const overlaysByPage = {}

    for (const [pageNumber, plan] of Object.entries(pageHighlightPlans || {})) {
        const overlays = (plan.evidenceMatches || []).map(
            (entry) =>
                entry.status === EVIDENCE_STATUS.MATCHED && entry.regionBounds
                    ? buildOverlayForRegionBounds(
                        entry.regionBounds,
                        pageDimensionsByPage[Number(pageNumber)],
                        entry.matchType,
                        entry.evidenceId
                    )
                    : null
        ).filter(Boolean)

        if (overlays.length > 0) {
            overlaysByPage[Number(pageNumber)] = overlays
        }
    }

    return overlaysByPage
}

function buildOverlayForRegionBounds(regionBounds, pageDimensions, matchType, evidenceId) {
    if (!regionBounds || !pageDimensions) {
        return null
    }

    const {
        width: pageWidth,
        height: pageHeight,
        originalWidth,
        originalHeight,
    } = pageDimensions

    if (
        !isPositiveFiniteNumber(pageWidth) ||
        !isPositiveFiniteNumber(pageHeight) ||
        !isPositiveFiniteNumber(originalWidth) ||
        !isPositiveFiniteNumber(originalHeight)
    ) {
        return null
    }

    const pdfLeft = clampNumber(Math.min(regionBounds.left, regionBounds.right), 0, originalWidth)
    const pdfRight = clampNumber(Math.max(regionBounds.left, regionBounds.right), 0, originalWidth)
    const pdfBottom = clampNumber(Math.min(regionBounds.bottom, regionBounds.top), 0, originalHeight)
    const pdfTop = clampNumber(Math.max(regionBounds.bottom, regionBounds.top), 0, originalHeight)

    if (pdfRight <= pdfLeft || pdfTop <= pdfBottom) {
        return null
    }

    const scaleX = pageWidth / originalWidth
    const scaleY = pageHeight / originalHeight
    const rawLeft = pdfLeft * scaleX
    const rawRight = pdfRight * scaleX
    const rawTop = (originalHeight - pdfTop) * scaleY
    const rawBottom = (originalHeight - pdfBottom) * scaleY
    const padding = matchType === 'table' ? 14 : 10
    const left = clampNumber(rawLeft - padding, 0, pageWidth)
    const top = clampNumber(rawTop - padding, 0, pageHeight)
    const right = clampNumber(rawRight + padding, 0, pageWidth)
    const bottom = clampNumber(rawBottom + padding, 0, pageHeight)
    const width = Math.max(0, right - left)
    const height = Math.max(0, bottom - top)

    if (width <= 0 || height <= 0) {
        return null
    }

    return {
        type: matchType === 'table' ? 'table' : 'paragraph',
        evidenceId,
        left,
        top,
        width,
        height,
    }
}

function clampNumber(value, minValue, maxValue) {
    return Math.min(maxValue, Math.max(minValue, value))
}

function isPositiveFiniteNumber(value) {
    return Number.isFinite(value) && value > 0
}

function normalizePageDimensions(page) {
    const width = Number(page?.width)
    const height = Number(page?.height)
    const originalWidth = Number(page?.originalWidth)
    const originalHeight = Number(page?.originalHeight)

    if (
        !isPositiveFiniteNumber(width) ||
        !isPositiveFiniteNumber(height) ||
        !isPositiveFiniteNumber(originalWidth) ||
        !isPositiveFiniteNumber(originalHeight)
    ) {
        return null
    }

    return {
        width,
        height,
        originalWidth,
        originalHeight,
    }
}

function buildPageStageStyle(pageDimensions) {
    if (!pageDimensions) return undefined
    return {
        width: pageDimensions.width,
        height: pageDimensions.height,
    }
}

function scrollPageRegionIntoView(panel, pageNode, overlay) {
    const scrollRoot = panel.querySelector('.pdf-container')
    const stageNode = pageNode.querySelector('.pdf-page-stage') || pageNode

    if (!scrollRoot || !stageNode) {
        pageNode.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'smooth' })
        return
    }

    const scrollRootRect = scrollRoot.getBoundingClientRect()
    const stageRect = stageNode.getBoundingClientRect()
    const targetTop =
        scrollRoot.scrollTop +
        (stageRect.top - scrollRootRect.top) +
        overlay.top +
        overlay.height / 2 -
        scrollRoot.clientHeight / 2
    const targetLeft =
        scrollRoot.scrollLeft +
        (stageRect.left - scrollRootRect.left) +
        overlay.left +
        overlay.width / 2 -
        scrollRoot.clientWidth / 2

    scrollRoot.scrollTo({
        top: clampNumber(targetTop, 0, Math.max(0, scrollRoot.scrollHeight - scrollRoot.clientHeight)),
        left: clampNumber(targetLeft, 0, Math.max(0, scrollRoot.scrollWidth - scrollRoot.clientWidth)),
        behavior: 'smooth',
    })
}

function buildMappedPageHintMatches(evidenceLocations, pageHighlightPlans, numPages) {
    return (evidenceLocations || [])
        .map((location) => {
            const pageNumber = resolveEvidenceHintPage(location, pageHighlightPlans, numPages)
            if (!location?.id || !location.pageHint || !pageNumber || Number(pageNumber) === Number(location.pageHint)) {
                return null
            }
            return {
                evidenceId: location.id,
                status: EVIDENCE_STATUS.HINTED,
                matchType: 'mapped_page_hint',
                pageNumber,
                sourcePageNumber: location.pageHint,
                itemIndexes: [],
            }
        })
        .filter(Boolean)
}

function resolveEvidenceHintPage(location, pageHighlightPlans, numPages) {
    if (!location?.pageHint) return null
    const pageHint = Number(location.pageHint)
    if (!Number.isFinite(pageHint) || pageHint <= 0) return null

    const printedPageMatch = resolvePrintedPageHint(pageHint, pageHighlightPlans, numPages)
    if (printedPageMatch) return printedPageMatch

    if (numPages && pageHint <= Number(numPages)) {
        return pageHint
    }

    return null
}

function resolvePrintedPageHint(pageHint, pageHighlightPlans, numPages) {
    const entries = Object.entries(pageHighlightPlans || {})
        .map(([pageNumber, plan]) => ({
            pageNumber: Number(pageNumber),
            printedPageNumber: Number(plan?.printedPageNumber),
        }))
        .filter((entry) =>
            Number.isFinite(entry.pageNumber) &&
            entry.pageNumber > 0 &&
            Number.isFinite(entry.printedPageNumber) &&
            entry.printedPageNumber > 0
        )

    const exactMatch = entries.find((entry) => entry.printedPageNumber === Number(pageHint))
    if (exactMatch) return exactMatch.pageNumber

    const offsets = new Map()
    for (const entry of entries) {
        const offset = entry.printedPageNumber - entry.pageNumber
        offsets.set(offset, (offsets.get(offset) || 0) + 1)
    }

    const sortedOffsets = Array.from(offsets.entries()).sort((left, right) => right[1] - left[1])
    for (const [offset] of sortedOffsets) {
        const resolvedPage = Number(pageHint) - offset
        if (Number.isInteger(resolvedPage) && resolvedPage > 0 && (!numPages || resolvedPage <= Number(numPages))) {
            return resolvedPage
        }
    }

    return null
}
