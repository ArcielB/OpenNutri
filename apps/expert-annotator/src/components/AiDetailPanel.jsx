import {
  formatDecisionLabel,
  formatRouteDestinationLabel,
  getAiDecisionKind,
  getAiPrefillStats,
  getNormalizationSummary,
  formatModelStageLabel,
} from '../utils/annotateHelpers'

export default function AiDetailPanel({ extraction }) {
  const payload = extraction?.normalized_payload_json || { decision_kind: getAiDecisionKind(extraction), food_items: [] }
  const stats = getAiPrefillStats(extraction)
  const summary = getNormalizationSummary(extraction)
  const foodItems = Array.isArray(payload?.food_items) ? payload.food_items : []
  const rejectionReasons = Object.entries(summary.rejection_reasons || {})

  return (
    <div className="ai-detail-panel">
      <div className="ai-detail-header">
        <div>
          <div className="ai-detail-title">AI Extraction Detail</div>
          <div className="table-secondary-line">
            {formatModelStageLabel(extraction)} · {extraction?.prompt_version || 'No prompt version'}
          </div>
        </div>
        <div className="reviewer-admin-badges">
          <span className={`status-badge ${stats.decision_kind === 'has_data' ? 'status-done' : 'status-skipped'}`}>
            {formatDecisionLabel(stats.decision_kind)}
          </span>
          <span className={`status-badge ${extraction?.audit_sampled ? 'status-draft' : 'status-pending'}`}>
            {extraction?.audit_sampled ? 'AUDIT' : 'LIVE'}
          </span>
        </div>
      </div>

      <div className="ai-detail-grid">
        <div className="ai-detail-metric">
          <span>Confidence</span>
          <strong>{extraction?.overall_confidence == null ? '-' : Number(extraction.overall_confidence).toFixed(3)}</strong>
        </div>
        <div className="ai-detail-metric">
          <span>Rows</span>
          <strong>{summary.accepted_row_count}/{summary.input_row_count}</strong>
        </div>
        <div className="ai-detail-metric">
          <span>DB Foods</span>
          <strong>{stats.matched_food_count}</strong>
        </div>
        <div className="ai-detail-metric">
          <span>Custom Foods</span>
          <strong>{stats.custom_food_count}</strong>
        </div>
        <div className="ai-detail-metric">
          <span>DB Nutrients</span>
          <strong>{stats.matched_nutrient_count}</strong>
        </div>
        <div className="ai-detail-metric">
          <span>Custom Nutrients</span>
          <strong>{stats.custom_nutrient_count}</strong>
        </div>
        <div className="ai-detail-metric">
          <span>Rejected</span>
          <strong>{summary.rejected_row_count}</strong>
        </div>
        <div className="ai-detail-metric">
          <span>Destination</span>
          <strong>{formatRouteDestinationLabel(extraction?.route_destination)}</strong>
        </div>
      </div>

      {rejectionReasons.length > 0 && (
        <div className="ai-detail-section">
          <div className="ai-detail-section-title">Rejected Rows</div>
          <div className="ai-rejection-list">
            {rejectionReasons.map(([reason, count]) => (
              <span key={reason} className="status-badge status-skipped">{reason}: {count}</span>
            ))}
          </div>
        </div>
      )}

      <div className="ai-detail-section">
        <div className="ai-detail-section-title">DB-Compliant Extracted Rows</div>
        <div className="payload-scroll">
          {foodItems.length === 0 ? (
            <div className="empty-panel">No food rows are present in the normalized AI payload.</div>
          ) : foodItems.map((foodItem, index) => (
            <div key={`${extraction?.id || 'ai'}-${index}`} className="payload-food-block">
              <div className="payload-food-title">
                {foodItem.food_name || 'Unnamed food'}
                {foodItem.food_fdc_id && <span className="payload-food-id">{foodItem.food_fdc_id}</span>}
                {foodItem.is_custom_food && <span className="status-badge status-draft">Custom</span>}
              </div>
              <div className="payload-nutrients">
                {(foodItem.nutrients || []).length === 0 ? (
                  <span className="payload-empty-line">No nutrient rows.</span>
                ) : (foodItem.nutrients || []).map((nutrient, nutrientIndex) => (
                  <div key={`${index}-${nutrientIndex}`} className="payload-nutrient-row">
                    <span>
                      {nutrient.nutrient_name || 'Unnamed nutrient'}
                      {nutrient.nutrient_id && <span className="payload-food-id"> {nutrient.nutrient_id}</span>}
                    </span>
                    <span>{nutrient.value ?? '-'} {nutrient.unit || ''}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="ai-detail-section">
        <div className="ai-detail-section-title">Normalized DB Payload</div>
        <pre className="ai-json-block">{JSON.stringify(payload, null, 2)}</pre>
      </div>
    </div>
  )
}
