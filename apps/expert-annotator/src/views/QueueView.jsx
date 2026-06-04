import { useEffect, useMemo, useState } from 'react'
import PdfViewer from '../components/PdfViewer'
import FoodItemForm from '../components/FoodItemForm'
import EvidenceStrip from '../components/EvidenceStrip'
import { buildEvidenceLocationsFromFoodItems } from '../utils/EvidenceLocations'
import { useEvidenceStatusCache } from '../hooks/useEvidenceStatusCache'
import {
  buildFoodItemsFromPayload,
  formatStatusLabel,
  getPublicPdfUrl,
  getStatusBadgeClass,
} from '../utils/annotateHelpers'
import { prefetchPdf } from '../utils/pdfCache'

export default function QueueView({
  items,
  currentItem,
  currentIndex,
  pdfUrl,
  theme,
  allNutrients,
  allFoods,
  foodsLoaded,
  user,
  foodItems,
  isEditable,
  saving,
  showPaperList,
  setShowPaperList,
  paperListRef,
  setSelectedQueueId,
  addFoodItem,
  removeFoodItem,
  updateFoodItem,
  handlePdfNutrientAdd,
  handleRequestHelp,
  saveAnnotation,
}) {
  const evidenceFoodItems = useMemo(() => {
    const hasVisibleRows = (foodItems || []).some((item) => (item?.nutrients || []).length > 0)
    if (hasVisibleRows) return foodItems
    return buildFoodItemsFromPayload(currentItem?.latest_ai_extraction?.normalized_payload_json)
  }, [currentItem?.latest_ai_extraction?.normalized_payload_json, foodItems])
  const paperId = currentItem?.paper_id ?? currentItem?.paper?.id ?? null
  const rawEvidenceLocations = useMemo(
    () => buildEvidenceLocationsFromFoodItems(evidenceFoodItems),
    [evidenceFoodItems]
  )
  const {
    scanEvidenceLocations,
    displayEvidenceLocations,
    evidenceStatuses,
    setEvidenceStatuses,
    cachedEvidenceOverlays,
  } = useEvidenceStatusCache(paperId, rawEvidenceLocations)
  const [activeEvidence, setActiveEvidence] = useState(null)
  const activeEvidenceId = scanEvidenceLocations.some((location) => location.id === activeEvidence?.id)
    ? activeEvidence.id
    : null

  // Warm the durable PDF cache for the next paper(s) during idle time so that
  // hitting "Next" renders from cache instead of waiting on a fresh fetch.
  useEffect(() => {
    if (currentIndex < 0 || !items?.length) return undefined
    const upcoming = items.slice(currentIndex + 1, currentIndex + 3)
    const urls = upcoming
      .map((item) => getPublicPdfUrl(item.paper?.filename, item.paper?.pdf_url))
      .filter(Boolean)
    if (urls.length === 0) return undefined
    const schedule = window.requestIdleCallback || ((cb) => window.setTimeout(cb, 600))
    const unschedule = window.cancelIdleCallback || window.clearTimeout
    const handle = schedule(() => urls.forEach((url) => prefetchPdf(url)), { timeout: 3000 })
    return () => unschedule(handle)
  }, [currentIndex, items])

  return (
    <div className="workspace">
      <PdfViewer
        pdfUrl={pdfUrl}
        allNutrients={allNutrients}
        onAddNutrient={handlePdfNutrientAdd}
        theme={theme}
        evidenceLocations={scanEvidenceLocations}
        activeEvidenceId={activeEvidenceId}
        activeEvidenceRequestId={activeEvidenceId ? activeEvidence?.requestId || null : null}
        onEvidenceStatusesChange={setEvidenceStatuses}
        cachedEvidenceOverlays={cachedEvidenceOverlays}
      />

      <div className="annotation-panel">
        <div className="queue-assignment-header">
          {currentItem ? (
            <div className="queue-assignment-toolbar">
              <div className="queue-toolbar-group">
                <div className="paper-list-toggle" ref={paperListRef}>
                  <button className="nav-btn nav-btn-with-icon" onClick={() => setShowPaperList((open) => !open)}>
                    <span>{currentIndex >= 0 ? `Paper ${currentIndex + 1}/${items.length}` : 'Queue'}</span>
                    <span className="chevron-icon" aria-hidden="true" />
                  </button>
                  {showPaperList && (
                    <div className="paper-list-dropdown">
                      {items.map((item, index) => (
                        <div
                          key={item.id}
                          className={`paper-list-item ${item.id === currentItem.id ? 'active' : ''}`}
                          onClick={() => {
                            setSelectedQueueId(item.id)
                            setShowPaperList(false)
                          }}
                        >
                          <span className="paper-id">{index + 1}</span>
                          <span className="paper-title">{item.paper?.title || item.paper?.filename || `Paper ${item.paper_id}`}</span>
                          <span className={`status-badge ${getStatusBadgeClass(item.status)}`}>{formatStatusLabel(item.status)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div className="queue-mini-stats">
                  <span className={`status-badge ${getStatusBadgeClass(currentItem.status)}`}>
                    {formatStatusLabel(currentItem.status)}
                  </span>
                  <span className="status-badge status-pending">{items.length} available</span>
                  {currentItem.workflow_language && (
                    <span className="status-badge status-draft">{currentItem.workflow_language.toUpperCase()}</span>
                  )}
                </div>
              </div>
              <div className="queue-nav-buttons">
                <button
                  className="nav-btn"
                  disabled={currentIndex <= 0}
                  onClick={() => setSelectedQueueId(items[Math.max(currentIndex - 1, 0)]?.id || null)}
                >
                  Prev
                </button>
                <button
                  className="nav-btn"
                  disabled={currentIndex < 0 || currentIndex >= items.length - 1}
                  onClick={() => setSelectedQueueId(items[Math.min(currentIndex + 1, items.length - 1)]?.id || null)}
                >
                  Next
                </button>
              </div>
            </div>
          ) : (
            <div className="empty-panel">No papers are currently available in the general queue.</div>
          )}
        </div>

        <div className="annotation-scroll">
          {!currentItem ? (
            <div className="empty-panel">The queue is empty.</div>
          ) : (
            <>
              {!isEditable && (
                <div className="review-lock-banner">
                  This account is read-only for live labeling.
                </div>
              )}
              <EvidenceStrip
                locations={displayEvidenceLocations}
                statuses={evidenceStatuses}
                selectedEvidenceId={activeEvidenceId}
                onSelect={(location) => setActiveEvidence({ id: location.id, requestId: Date.now() })}
              />
              {foodItems.map((item, index) => (
                <FoodItemForm
                  key={`${currentItem.id}-${index}`}
                  index={index}
                  data={item}
                  onChange={(updated) => updateFoodItem(index, updated)}
                  onDelete={() => removeFoodItem(index)}
                  allNutrients={allNutrients}
                  allFoods={allFoods}
                  foodsLoaded={foodsLoaded}
                  userId={user.id}
                />
              ))}
              {isEditable && (
                <button className="add-food-btn" onClick={addFoodItem}>Add Food</button>
              )}
            </>
          )}
        </div>

        <div className="annotation-actions">
          <div className="action-row">
            <button className="btn btn-outline" onClick={handleRequestHelp} disabled={saving || !isEditable}>Ask for Help</button>
            <button className="btn btn-skip" onClick={() => saveAnnotation(false, 'skipped')} disabled={saving || !isEditable}>
              No Usable Data
            </button>
            <button className="btn btn-outline" onClick={() => saveAnnotation(true, 'draft')} disabled={saving || !isEditable}>
              Save Draft
            </button>
          </div>
          <div className="action-row">
            <button className="btn btn-success" onClick={() => saveAnnotation(true, 'done')} disabled={saving || !isEditable}>
              {saving ? 'Saving...' : 'Submit Reviewed Data'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
