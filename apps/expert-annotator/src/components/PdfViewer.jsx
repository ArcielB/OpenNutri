import { useState, useEffect, useRef, useCallback } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import NutrientPopover from './NutrientPopover'
import { buildNutrientMatcher, highlightNutrientsInTextLayer } from '../utils/PdfTextScanner'

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

export default function PdfViewer({ pdfUrl, allNutrients, onAddNutrient, theme }) {
    const [numPages, setNumPages] = useState(null)
    const [pageNumber, setPageNumber] = useState(1)
    const [scale, setScale] = useState(1.2)
    const [popover, setPopover] = useState(null) // { nutrient, rect }
    const containerRef = useRef(null)
    const cleanupRef = useRef(null)
    const matcherRef = useRef(null)

    // Build matcher when nutrients change
    useEffect(() => {
        if (allNutrients && allNutrients.length > 0) {
            matcherRef.current = buildNutrientMatcher(allNutrients)
        }
    }, [allNutrients])

    function onDocumentLoadSuccess({ numPages }) {
        setNumPages(numPages)
        setPageNumber(1)
    }

    // After each page render, scan and highlight nutrient names
    const handlePageRenderSuccess = useCallback(() => {
        // Clean up previous highlights
        if (cleanupRef.current) {
            cleanupRef.current()
            cleanupRef.current = null
        }

        if (!matcherRef.current || !containerRef.current) return

        // Find the text layer — react-pdf renders it as a div with class "textLayer"
        const textLayer = containerRef.current.querySelector('.textLayer')
        if (!textLayer) return

        const cleanup = highlightNutrientsInTextLayer(
            textLayer,
            matcherRef.current,
            (nutrient, rect) => {
                setPopover({ nutrient, rect })
            }
        )
        cleanupRef.current = cleanup
    }, [])

    // Clean up on unmount or URL change
    useEffect(() => {
        return () => {
            if (cleanupRef.current) {
                cleanupRef.current()
            }
        }
    }, [pdfUrl])

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
                        renderTextLayer={true}
                        renderAnnotationLayer={false}
                        onRenderTextLayerSuccess={handlePageRenderSuccess}
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
