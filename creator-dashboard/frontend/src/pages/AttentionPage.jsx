import { useEffect, useState } from 'react'
import AttentionQueue from '../components/AttentionQueue.jsx'
import { authFetch } from '../api.js'

export default function AttentionPage() {
  const [automation, setAutomation] = useState(null)
  const [running, setRunning] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    authFetch('/api/automation/status')
      .then((response) => response.ok ? response.json() : null)
      .then(setAutomation)
      .catch(() => setAutomation(null))
  }, [])

  async function runAutomation() {
    if (!window.confirm('Run invoice reminders and the manager follow-up digest now?')) return
    setRunning(true)
    setError('')
    setFeedback('')
    try {
      const response = await authFetch('/api/automation/run', { method: 'POST' })
      const body = await response.json().catch(() => null)
      if (!response.ok) throw new Error(body?.detail || 'Daily automation could not run')
      setFeedback(
        `${body.invoice_reminders_sent} payment reminder${body.invoice_reminders_sent === 1 ? '' : 's'} sent · `
        + `${body.collaboration_follow_ups} collaboration follow-up${body.collaboration_follow_ups === 1 ? '' : 's'} found`,
      )
      if (body.errors?.length) setError(body.errors.join(' · '))
    } catch (err) {
      setError(err.message)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="admin-page attention-page">
      <header className="admin-page-header">
        <div>
          <span className="eyebrow">Manager command centre</span>
          <h1>What needs attention</h1>
          <p>A prioritized working list so nothing gets lost between messages, deadlines, and payments.</p>
        </div>
      </header>
      <section className="automation-card">
        <div className="automation-card-copy">
          <span className="eyebrow">Daily automation</span>
          <h2>Reminder engine</h2>
          <p>
            Sends overdue invoice reminders every {automation?.reminder_interval_days || 3} days and emails the manager a digest of unanswered collaborations.
          </p>
        </div>
        <div className="automation-health">
          <Status label="Automation" ready={automation?.enabled} />
          <Status label="Resend email" ready={automation?.email_configured} />
          <Status label="Scheduled trigger" ready={automation?.cron_secret_configured} />
        </div>
        <button
          className="button primary"
          type="button"
          disabled={running || !automation?.enabled || !automation?.email_configured}
          onClick={runAutomation}
        >
          {running ? 'Running checks...' : 'Run now'}
        </button>
      </section>
      {(feedback || error) && <div className={`admin-notice ${error ? 'error' : 'success'}`}>{error || feedback}</div>}
      <AttentionQueue />
    </div>
  )
}

function Status({ label, ready }) {
  return <div className={ready ? 'ready' : ''}><i /><span>{label}</span><strong>{ready ? 'Ready' : 'Setup needed'}</strong></div>
}
