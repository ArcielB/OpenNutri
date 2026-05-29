import { useMemo } from 'react'
import {
  PIPELINE_RANGE_OPTIONS,
  buildPipelineSteps,
  formatCount,
  formatDate,
  formatPercent,
  getPipelineModelStageViews,
  toNumber,
} from '../utils/annotateHelpers'

export default function PipelineOpsView({
  snapshot,
  filters,
  onFilterChange,
  loading,
  error,
  onRefresh,
}) {
  const steps = useMemo(() => buildPipelineSteps(snapshot), [snapshot])
  const modelStages = useMemo(() => getPipelineModelStageViews(snapshot), [snapshot])
  const human = snapshot?.human_review || {}
  const papers = snapshot?.papers || {}
  const maxCount = Math.max(...steps.map((step) => step.count), 1)
  const queueCards = [
    ...modelStages.flatMap((modelStage) => [
      {
        key: `${modelStage.stageKey}-queued`,
        label: modelStage.label,
        detail: 'Waiting',
        value: modelStage.stage.queued,
        tone: 'blue',
      },
      {
        key: `${modelStage.stageKey}-processing`,
        label: modelStage.label,
        detail: 'Running',
        value: modelStage.stage.processing,
        tone: 'yellow',
      },
    ]),
    { key: 'human-ready', label: 'Ready for labelers', value: human.ready_current, tone: 'green' },
    { key: 'approval', label: 'Waiting approval', value: human.pending_approval_current, tone: 'yellow' },
    { key: 'failed', label: 'AI failed', value: papers.ai_failed_current, tone: 'red' },
  ]

  const handleFilterChange = (field, value) => {
    onFilterChange((previous) => ({ ...previous, [field]: value }))
  }

  return (
    <div className="dashboard-page pipeline-page">
      <div className="dashboard-header pipeline-header">
        <div>
          <h2>Pipeline</h2>
          <p>How many papers are waiting now, and how many made it through each step.</p>
        </div>
        <button className="btn btn-outline" onClick={onRefresh} disabled={loading}>
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {error && <div className="profile-warning pipeline-error">Pipeline snapshot failed: {error}</div>}

      <section className="pipeline-section">
        <div className="pipeline-section-title">
          <div>
            <h3>Right Now</h3>
            <p>Current queues and blockers.</p>
          </div>
          <span>{formatDate(snapshot?.generated_at)}</span>
        </div>
        <div className="pipeline-queue-grid">
          {queueCards.map((card) => (
            <div className={`pipeline-queue-card pipeline-queue-${card.tone}`} key={card.key}>
              <div>
                {card.detail && <span className="pipeline-queue-card-detail">{card.detail}</span>}
                <span>{card.label}</span>
              </div>
              <strong>{formatCount(card.value)}</strong>
            </div>
          ))}
        </div>
      </section>

      <section className="pipeline-section">
        <div className="pipeline-section-title">
          <div>
            <h3>Paper Funnel</h3>
            <p>Each row shows how many papers reached that step.</p>
          </div>
          <div className="pipeline-filter-simple">
            <label>
              Time
              <select value={filters.range} onChange={(event) => handleFilterChange('range', event.target.value)}>
                {PIPELINE_RANGE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
            {filters.range === 'custom' && (
              <>
                <label>
                  Start
                  <input
                    type="datetime-local"
                    value={filters.startAt}
                    onChange={(event) => handleFilterChange('startAt', event.target.value)}
                  />
                </label>
                <label>
                  End
                  <input
                    type="datetime-local"
                    value={filters.endAt}
                    onChange={(event) => handleFilterChange('endAt', event.target.value)}
                  />
                </label>
              </>
            )}
          </div>
        </div>

        <div className="pipeline-funnel">
          {steps.map((step, index) => {
            const previous = index > 0 ? steps[index - 1] : null
            const width = step.count > 0 ? Math.max(5, Math.round((step.count / maxCount) * 100)) : 0
            const retained = previous ? formatPercent(step.count, previous.count) : '100%'
            const dropped = previous ? Math.max(0, toNumber(previous.count) - toNumber(step.count)) : 0
            return (
              <div className="pipeline-funnel-row" key={step.key}>
                <div className="pipeline-funnel-label">
                  <span className="pipeline-step-index">{index + 1}</span>
                  <div>
                    <strong>{step.label}</strong>
                    <span>{step.note}</span>
                  </div>
                </div>
                <div className="pipeline-funnel-bar-wrap">
                  <div className={`pipeline-funnel-bar ${step.count <= 0 ? 'pipeline-funnel-bar-empty' : ''}`} style={{ width: `${width}%` }}>
                    {step.count > 0 && <span>{formatCount(step.count)}</span>}
                  </div>
                </div>
                <div className="pipeline-funnel-meta">
                  <strong>{formatCount(step.count)}</strong>
                  <span>{index === 0 ? 'start' : `${retained} kept`}</span>
                  {index > 0 && (
                    <span>{formatCount(dropped)} did not reach this step</span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </section>

      <div className="pipeline-generated-at">
        Showing {filters.range === 'all' ? 'all time' : PIPELINE_RANGE_OPTIONS.find((option) => option.value === filters.range)?.label.toLowerCase()}.
      </div>
    </div>
  )
}
