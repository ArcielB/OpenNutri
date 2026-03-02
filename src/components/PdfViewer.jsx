import { useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

export default function PdfViewer({ pdfUrl }) {
    const [numPages, setNumPages] = useState(null)
    const [pageNumber, setPageNumber] = useState(1)
    const [scale, setScale] = useState(1.2)

    function onDocumentLoadSuccess({ numPages }) {
        setNumPages(numPages)
        setPageNumber(1)
    }

    if (!pdfUrl) {
        return (
            <div className="pdf-panel">
                <div className="pdf-loading">No paper selected</div>
            </div>
        )
    }

    return (
        <div className="pdf-panel">
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
                    />
                </Document>
            </div>
        </div>
    )
}
