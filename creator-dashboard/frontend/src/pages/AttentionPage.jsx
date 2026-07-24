import AttentionQueue from '../components/AttentionQueue.jsx'

export default function AttentionPage() {
  return (
    <div className="admin-page attention-page">
      <header className="admin-page-header">
        <div>
          <span className="eyebrow">Manager command centre</span>
          <h1>What needs attention</h1>
          <p>A prioritized working list so nothing gets lost between messages, deadlines, and payments.</p>
        </div>
      </header>
      <AttentionQueue />
    </div>
  )
}
