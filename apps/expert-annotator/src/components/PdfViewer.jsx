import { useState, useEffect, useRef, useCallback, useMemo, useEffectEvent } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import NutrientPopover from './NutrientPopover'
import {
    bindNutrientHighlightInteractions,
    buildNutrientMatcher,
    buildPageTableHighlightPlan,
    renderTextItemWithNutrientHighlights,
} from '../utils/PdfTextScanner'

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

export default function PdfViewer({ pdfUrl, allNutrients, onAddNutrient, theme }) {
    const [numPages, setNumPages] = useState(null)
    const [pageNumber, setPageNumber] = useState(1)
    const [scale, setScale] = useState(1.2)
    const [popover, setPopover] = useState(null) // { nutrient, rect }
    const [pageHighlightPlan, setPageHighlightPlan] = useState(() => ({
        pdfUrl: null,
        pageNumber: null,
        isReady: false,
        allowedItemIndexes: new Set(),
    }))
    const containerRef = useRef(null)
    const cleanupRef = useRef(null)

    const nutrientMatcher = useMemo(() => {
        if (!allNutrients || allNutrients.length === 0) {
            return null
        }

        return buildNutrientMatcher(allNutrients)
    }, [allNutrients])

    const customTextRenderer = useCallback(
        ({ str, itemIndex }) =>
            renderTextItemWithNutrientHighlights(str, nutrientMatcher, {
                allowHighlight:
                    pageHighlightPlan.isReady &&
                    pageHighlightPlan.pdfUrl === pdfUrl &&
                    pageHighlightPlan.pageNumber === pageNumber &&
                    pageHighlightPlan.allowedItemIndexes.has(itemIndex),
            }),
        [nutrientMatcher, pageHighlightPlan, pdfUrl, pageNumber]
    )

    function onDocumentLoadSuccess({ numPages }) {
        setNumPages(numPages)
        setPageNumber(1)
    }

    const handleNutrientClick = useCallback((nutrient, rect) => {
        setPopover({ nutrient, rect })
    }, [])

    const closePopover = useEffectEvent(() => {
        setPopover(null)
    })

    const handlePageTextSuccess = useCallback(
        (textContent) => {
            const nextPlan = buildPageTableHighlightPlan(textContent)

            setPageHighlightPlan({
                pdfUrl,
                pageNumber,
                isReady: true,
                allowedItemIndexes: nextPlan.allowedItemIndexes,
            })
        },
        [pdfUrl, pageNumber]
    )

    const handleTextLayerRenderSuccess = useCallback(() => {
        if (cleanupRef.current) {
            cleanupRef.current()
            cleanupRef.current = null
        }

        if (!containerRef.current) return

        const textLayer = containerRef.current.querySelector('.textLayer')
        if (!textLayer) return

        cleanupRef.current = bindNutrientHighlightInteractions(
            textLayer,
            handleNutrientClick
        )
    }, [handleNutrientClick])

    useEffect(() => {
        closePopover()

        return () => {
            if (cleanupRef.current) {
                cleanupRef.current()
                cleanupRef.current = null
            }
        }
    }, [pageNumber, pdfUrl, scale])

    useEffect(() => {
        return () => {
            if (cleanupRef.current) {
                cleanupRef.current()
                cleanupRef.current = null
            }
        }
    }, [])

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
                <button onClick={() => setScale((s) => Math.max(0.5, s - 0.2))}>−</button>
                <button onClick={() => setScale((s) => Math.min(3, s + 0.2))}>+</button>
                <span className="page-info">
                    {numPages ? `${pageNumber} / ${numPages}` : '...'}
                </span>
                <button
                    onClick={() => setPageNumber((p) => Math.max(1, p - 1))}
                    disabled={pageNumber <= 1}
                >
                    ◄ Prev
                </button>
                <button
                    onClick={() => setPageNumber((p) => Math.min(numPages || 1, p + 1))}
                    disabled={pageNumber >= (numPages || 1)}
                >
                    Next ►
                </button>
            </div>
            <div className="pdf-container">
                <Document
                    file={pdfUrl}
                    onLoadSuccess={onDocumentLoadSuccess}
                    loading={<div className="pdf-loading">Loading PDF...</div>}
                    error={<div className="pdf-loading">Failed to load PDF</div>}
                >
                    <Page
                        pageNumber={pageNumber}
                        scale={scale}
                        customTextRenderer={customTextRenderer}
                        renderTextLayer={true}
                        renderAnnotationLayer={false}
                        onGetTextSuccess={handlePageTextSuccess}
                        onRenderTextLayerSuccess={handleTextLayerRenderSuccess}
                    />
                </Document>
            </div>

            {/* Nutrient popover — floats on top of PDF */}
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
