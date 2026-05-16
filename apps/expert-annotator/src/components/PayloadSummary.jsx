import {
  formatDate,
  formatDecisionLabel,
  formatStatusLabel,
  getStatusBadgeClass,
} from '../utils/annotateHelpers'

export default function PayloadSummary({ submission, reviewer, title = null }) {
  const payload = submission?.payload_json || {}
  const foodItems = Array.isArray(payload?.food_items) ? payload.food_items : []

  return (
    <div className="payload-card">
      <div className="payload-card-header">
        <div>
          <h3>{title || reviewer?.display_name || reviewer?.email || 'Unknown Labeler'}</h3>
          <p>{formatDecisionLabel(submission?.decision_kind)}</p>
        </div>
      </div>
      <div className="payload-meta">
        <span className={`status-badge ${getStatusBadgeClass(submission?.status)}`}>{formatStatusLabel(submission?.status)}</span>
        <span className="status-badge status-pending">{formatDate(submission?.submitted_at)}</span>
        <span className="status-badge status-draft">{foodItems.length} foods</span>
      </div>
      <div className="payload-scroll">
        {foodItems.length === 0 ? (
          <div className="empty-panel">No extracted foods stored in this submission.</div>
        ) : foodItems.map((foodItem, index) => (
          <div key={`${submission?.id || 'payload'}-${index}`} className="payload-food-block">
            <div className="payload-food-title">
              {foodItem.food_name || 'Unnamed food'}
              {foodItem.food_fdc_id && <span className="payload-food-id">{foodItem.food_fdc_id}</span>}
            </div>
            <div className="payload-nutrients">
              {(foodItem.nutrients || []).length === 0 ? (
                <span className="payload-empty-line">No nutrient rows.</span>
              ) : (foodItem.nutrients || []).map((nutrient, nutrientIndex) => (
                <div key={`${index}-${nutrientIndex}`} className="payload-nutrient-row">
                  <span>{nutrient.nutrient_name || 'Unnamed nutrient'}</span>
                  <span>{nutrient.value ?? '-'} {nutrient.unit || ''}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
