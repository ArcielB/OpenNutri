import {
  buildEvidenceDisplayGroups,
  getDefaultEvidenceStatus,
  getEvidenceDisplayLabel,
} from '../utils/EvidenceLocations'

function buildEvidenceTitle(location, status, group = null) {
  return [
    getEvidenceDisplayLabel(location),
    status.label,
    group?.evidenceIds?.length > 1 ? `${group.evidenceIds.length} sources resolve to this location` : null,
    location.sourceCitation,
    location.sourceQuote,
  ].filter(Boolean).join(' · ')
}

export default function EvidenceStrip({ locations, statuses, selectedEvidenceId, onSelect }) {
  if (!locations.length) return null

  const groups = buildEvidenceDisplayGroups(locations, statuses)

  return (
    <div className="evidence-strip" aria-label="Source hints">
      <div className="evidence-strip-heading">
        <span className="evidence-strip-label">Sources</span>
        <span className="evidence-strip-count">{groups.length}</span>
      </div>
      <div className="evidence-badge-row" role="list">
        {groups.map((group) => {
          const location = group.location
          const status = group.status || statuses[location.id] || getDefaultEvidenceStatus(location)
          const displayLabel = getEvidenceDisplayLabel(location)
          const pageLabel = status.pageNumber || location.pageHint ? `Page ${status.pageNumber || location.pageHint}` : null
          const secondaryLabel = pageLabel && pageLabel !== displayLabel ? pageLabel : null
          const isActive = group.evidenceIds.includes(selectedEvidenceId)
          return (
            <button
              key={group.id}
              type="button"
              className={`evidence-badge evidence-badge-${status.status} ${isActive ? 'active' : ''}`}
              title={buildEvidenceTitle(location, status, group)}
              aria-pressed={isActive}
              onClick={() => onSelect(location)}
            >
              <span className={`evidence-status-dot evidence-status-dot-${status.status}`} aria-hidden="true" />
              <span className="evidence-badge-main">{displayLabel}</span>
              {secondaryLabel && <span className="evidence-badge-page">{secondaryLabel}</span>}
            </button>
          )
        })}
      </div>
    </div>
  )
}
