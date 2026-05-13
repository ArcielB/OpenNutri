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
    renderTextItemWithEvidenceHighlight,
    renderTextItemWithNutrientHighlights,
} from '../utils/PdfTextScanner'
import { mergeEvidenceStatuses } from '../utils/EvidenceLocations'

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
            const nextEvidencePlan = buildPageEvidenceHighlightPlan(textContent, evidenceLocations, pageNumber)

            return {
                isReady: true,
                allowedItemIndexes: nextTablePlan.allowedItemIndexes,
                evidenceItemIdsByIndex: nextEvidencePlan.itemEvidenceIds,
                evidenceMatches: nextEvidencePlan.matches,
            }
        },
        [evidenceLocations]
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
        const statuses = mergeEvidenceStatuses(evidenceLocations, pageMatches)
        const signature = JSON.stringify(statuses)
        if (signature === lastEvidenceStatusesRef.current) return

        lastEvidenceStatusesRef.current = signature
        onEvidenceStatusesChange(statuses)
    }, [evidenceLocations, onEvidenceStatusesChange, pageHighlightPlans])

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
                evidenceLocations.find((location) => location.id === activeEvidenceId)?.pageHint ||
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

function findEvidenceMatchedPage(pageHighlightPlans, evidenceId) {
    for (const [pageNumber, plan] of Object.entries(pageHighlightPlans || {})) {
        const hasMatch = (plan.evidenceMatches || []).some(
            (match) => match.evidenceId === evidenceId && match.status === 'matched'
        )
        if (hasMatch) return Number(pageNumber)
    }
    return null
}
