export default function HelpRequestModal({ note, setNote, onClose, onSubmit, saving }) {
  return (
    <div className="modal-backdrop">
      <form
        className="help-modal"
        onSubmit={(event) => {
          event.preventDefault()
          onSubmit()
        }}
      >
        <h2>Ask for Help</h2>
        <p>This sends the paper to Arciel with your current draft context.</p>
        <textarea
          value={note}
          placeholder="What is confusing?"
          onChange={(event) => setNote(event.target.value)}
          disabled={saving}
          autoFocus
        />
        <div className="modal-actions">
          <button type="button" className="btn btn-outline" onClick={onClose} disabled={saving}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={saving || !note.trim()} style={{ width: 'auto' }}>
            {saving ? 'Sending...' : 'Send Help Request'}
          </button>
        </div>
      </form>
    </div>
  )
}
