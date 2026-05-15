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
    renderTextItemWithEvidenceHighlight,
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
    const [evidenceOverlaysByPage, setEvidenceOverlaysByPage] = useState({})
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
                evidenceItemIdsByIndex: nextEvidencePlan.itemEvidenceIds,
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
                const nutrientHtml = renderTextItemWithNutrientHighlights(str, nutrientMatcher, {
                    allowHighlight: Boolean(
                        pagePlan?.isReady && pagePlan.allowedItemIndexes.has(itemIndex)
                    ),
                })
                return renderTextItemWithEvidenceHighlight(
                    nutrientHtml,
                    pagePlan?.evidenceItemIdsByIndex?.get(itemIndex),
                    activeEvidenceId
                )
            },
        [activeEvidenceId, nutrientMatcher, pageHighlightPlans]
    )

    function onDocumentLoadSuccess({ numPages }) {
        setNumPages(numPages)
        setCurrentPageNumber(1)
        setPageTextContents({})
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
            const matchedNode = Array.from(panel.querySelectorAll('[data-evidence-ids]'))
                .find((node) => (node.dataset.evidenceIds || '').split(/\s+/).includes(activeEvidenceId))

            if (matchedNode) {
                matchedNode.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'smooth' })
                const pageNode = matchedNode.closest('[data-page-number]')
                const pageNumber = Number(pageNode?.getAttribute('data-page-number') || 0)
                if (Number.isFinite(pageNumber) && pageNumber > 0) {
                    setCurrentPageNumber(pageNumber)
                }
                return
            }

            const targetPage =
                findEvidenceMatchedPage(pageHighlightPlans, activeEvidenceId) ||
                resolveEvidenceHintPage(
                    evidenceLocations.find((location) => location.id === activeEvidenceId),
                    pageHighlightPlans,
                    numPages
                ) ||
                null

            if (!targetPage) return
            const pageNode = panel.querySelector(`[data-page-number="${targetPage}"]`)
            if (pageNode) {
                pageNode.scrollIntoView({ block: 'start', inline: 'nearest', behavior: 'smooth' })
                setCurrentPageNumber(Number(targetPage))
            }
        })

        return () => window.cancelAnimationFrame(frameId)
    }, [
        activeEvidenceId,
        activeEvidenceRequestId,
        evidenceLocations,
        numPages,
        pageHighlightPlans,
    ])

    useEffect(() => {
        const panel = containerRef.current
        if (!panel || !activeEvidenceId) {
            const frameId = window.requestAnimationFrame(() => setEvidenceOverlaysByPage({}))
            return () => window.cancelAnimationFrame(frameId)
        }

        let cancelled = false
        const frameIds = []

        const buildOverlays = () => {
            if (cancelled) return
            setEvidenceOverlaysByPage(buildActiveEvidenceOverlays(panel, activeEvidenceId, pageHighlightPlans))
        }

        frameIds.push(window.requestAnimationFrame(() => {
            frameIds.push(window.requestAnimationFrame(buildOverlays))
        }))

        window.addEventListener('resize', buildOverlays)

        return () => {
            cancelled = true
            frameIds.forEach((frameId) => window.cancelAnimationFrame(frameId))
            window.removeEventListener('resize', buildOverlays)
        }
    }, [activeEvidenceId, activeEvidenceRequestId, pageHighlightPlans, pdfUrl, scale])

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
                        return (
                            <div
                                className="pdf-page-wrap"
                                data-page-number={pageNumber}
                                key={`pdf-page-${pageNumber}`}
                            >
                                <Page
                                    pageNumber={pageNumber}
                                    scale={scale}
                                    customTextRenderer={buildCustomTextRenderer(pageNumber)}
                                    renderTextLayer={true}
                                    renderAnnotationLayer={false}
                                    onGetTextSuccess={(textContent) =>
                                        handlePageTextSuccess(pageNumber, textContent)
                                    }
                                />
                                <EvidenceRegionOverlay overlays={evidenceOverlaysByPage[pageNumber] || []} />
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
                    key={`${overlay.type}-${index}`}
                    className={`evidence-region-box evidence-region-box-${overlay.type}`}
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

function findEvidenceMatchedPage(pageHighlightPlans, evidenceId) {
    for (const [pageNumber, plan] of Object.entries(pageHighlightPlans || {})) {
        const hasMatch = (plan.evidenceMatches || []).some(
            (match) => match.evidenceId === evidenceId && match.status === 'matched'
        )
        if (hasMatch) return Number(pageNumber)
    }
    return null
}

function buildActiveEvidenceOverlays(panel, activeEvidenceId, pageHighlightPlans) {
    const overlaysByPage = {}

    for (const [pageNumber, plan] of Object.entries(pageHighlightPlans || {})) {
        const match = (plan.evidenceMatches || []).find(
            (entry) => entry.evidenceId === activeEvidenceId && entry.status === EVIDENCE_STATUS.MATCHED
        )
        if (!match) continue

        const pageNode = panel.querySelector(`[data-page-number="${pageNumber}"]`)
        if (!pageNode) continue

        const matchedNodes = Array.from(pageNode.querySelectorAll('[data-evidence-ids]'))
            .filter((node) => (node.dataset.evidenceIds || '').split(/\s+/).includes(activeEvidenceId))
        if (matchedNodes.length === 0) continue

        const overlay = buildOverlayForMatchedNodes(pageNode, matchedNodes, match.matchType)
        if (!overlay) continue

        overlaysByPage[Number(pageNumber)] = [overlay]
    }

    return overlaysByPage
}

function buildOverlayForMatchedNodes(pageNode, matchedNodes, matchType) {
    const pageRect = pageNode.getBoundingClientRect()
    const pageSurface = pageNode.querySelector('.react-pdf__Page') || pageNode
    const surfaceRect = pageSurface.getBoundingClientRect()
    const nodeRects = matchedNodes
        .map((node) => node.getBoundingClientRect())
        .filter((rect) => rect.width > 0 && rect.height > 0)

    if (nodeRects.length === 0 || surfaceRect.width <= 0 || surfaceRect.height <= 0) {
        return null
    }

    const union = unionDomRects(nodeRects)
    const padding = matchType === 'table' ? 12 : 8
    const left = clampNumber(union.left - pageRect.left - padding, surfaceRect.left - pageRect.left, surfaceRect.right - pageRect.left)
    const top = clampNumber(union.top - pageRect.top - padding, surfaceRect.top - pageRect.top, surfaceRect.bottom - pageRect.top)
    const right = clampNumber(union.right - pageRect.left + padding, surfaceRect.left - pageRect.left, surfaceRect.right - pageRect.left)
    const bottom = clampNumber(union.bottom - pageRect.top + padding, surfaceRect.top - pageRect.top, surfaceRect.bottom - pageRect.top)
    const width = Math.max(0, right - left)
    const height = Math.max(0, bottom - top)

    if (width <= 0 || height <= 0) {
        return null
    }

    return {
        type: matchType === 'table' ? 'table' : 'paragraph',
        left,
        top,
        width,
        height,
    }
}

function unionDomRects(rects) {
    return rects.reduce((union, rect) => ({
        left: Math.min(union.left, rect.left),
        top: Math.min(union.top, rect.top),
        right: Math.max(union.right, rect.right),
        bottom: Math.max(union.bottom, rect.bottom),
    }), {
        left: rects[0].left,
        top: rects[0].top,
        right: rects[0].right,
        bottom: rects[0].bottom,
    })
}

function clampNumber(value, minValue, maxValue) {
    return Math.min(maxValue, Math.max(minValue, value))
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
