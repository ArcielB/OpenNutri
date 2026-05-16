export default function ReviewerAdminView({ cockpitData, reviewerDrafts, onChangeDraft, onSaveDraft, savingReviewerTarget }) {
  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <div>
          <h2>Reviewer Admin</h2>
          <p>Manage reviewer access, read-only tester mode, cockpit visibility, and approval authority.</p>
        </div>
      </div>
      <div className="dashboard-card dashboard-card-table">
        <div className="table-scroll">
          <table className="dashboard-table">
            <thead>
              <tr>
                <th>Reviewer</th>
                <th>Languages</th>
                <th>Active</th>
                <th>Tester</th>
                <th>Cockpit</th>
                <th>Can Approve</th>
                <th>Save</th>
              </tr>
            </thead>
            <tbody>
              {(cockpitData.reviewerProfiles || []).map((profile) => {
                const draft = reviewerDrafts[profile.id] || profile
                return (
                  <tr key={profile.id}>
                    <td className="table-title-cell">
                      <div className="table-primary-line">{profile.display_name || profile.email}</div>
                      <div className="table-secondary-line">{profile.email}</div>
                    </td>
                    <td>
                      <div className="reviewer-toggle-row">
                        <label className="reviewer-toggle">
                          <input
                            type="checkbox"
                            checked={Boolean(draft.can_review_en)}
                            onChange={(event) => onChangeDraft(profile.id, 'can_review_en', event.target.checked)}
                          />
                          EN
                        </label>
                        <label className="reviewer-toggle">
                          <input
                            type="checkbox"
                            checked={Boolean(draft.can_review_tr)}
                            onChange={(event) => onChangeDraft(profile.id, 'can_review_tr', event.target.checked)}
                          />
                          TR
                        </label>
                      </div>
                    </td>
                    {['active', 'tester_access', 'cockpit_access', 'can_approve_labels'].map((field) => (
                      <td key={field}>
                        <input
                          type="checkbox"
                          checked={Boolean(draft[field])}
                          onChange={(event) => onChangeDraft(profile.id, field, event.target.checked)}
                        />
                      </td>
                    ))}
                    <td>
                      <button
                        className="btn btn-primary"
                        onClick={() => onSaveDraft(profile.id)}
                        disabled={savingReviewerTarget === profile.id}
                      >
                        {savingReviewerTarget === profile.id ? 'Saving...' : 'Save'}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
