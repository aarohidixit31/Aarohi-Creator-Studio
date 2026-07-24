import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authFetch } from '../api.js'
import { Button } from './ui.jsx'

const TYPES = [
  ['all', 'All'],
  ['inquiry', 'Inquiries'],
  ['follow_up', 'Follow-ups'],
  ['deadline', 'Deadlines'],
  ['payment', 'Payments'],
]

const TYPE_META = {
  inquiry: { code: 'IN', label: 'Inquiry' },
  follow_up: { code: 'FU', label: 'Follow-up' },
  deadline: { code: 'DL', label: 'Deadline' },
  payment: { code: '₹', label: 'Payment' },
}

const money = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

export default function AttentionQueue({ compact = false, onSummary }) {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [filter, setFilter] = useState('all')
  const [working, setWorking] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  async function load() {
    setError('')
    try {
      const response = await authFetch('/api/collabs/attention')
      if (!response.ok) throw new Error('Could not load your attention queue')
      const next = await response.json()
      setData(next)
      onSummary?.(next.summary)
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => { load() }, [])

  const visibleItems = useMemo(() => {
    const items = data?.items || []
    const filtered = filter === 'all' ? items : items.filter((item) => item.type === filter)
    return compact ? filtered.slice(0, 5) : filtered
  }, [compact, data, filter])

  async function performAction(item, action) {
    setWorking(`${item.key}-${action}`)
    setError('')
    setNotice('')
    try {
      let response
      if (action === 'contacted') {
        response = await authFetch(`/api/collabs/${item.source_id}/status`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: 'in_discussion' }),
        })
      } else {
        const followUpAt = action === 'snooze'
          ? new Date(Date.now() + 2 * 86400000).toISOString()
          : null
        response = await authFetch(`/api/collabs/${item.source_id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ follow_up_at: followUpAt }),
        })
      }
      if (!response.ok) throw new Error('Could not update this task')
      setNotice(action === 'contacted' ? `${item.brand_name} marked as contacted.` : action === 'snooze' ? 'Follow-up moved forward by 2 days.' : 'Follow-up completed.')
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setWorking('')
    }
  }

  const summary = data?.summary

  return (
    <section className={`attention-panel${compact ? ' compact' : ''}`}>
      <header className="attention-panel-header">
        <div>
          <span className="summary-kicker">Priority queue</span>
          <h2>{compact ? 'Needs attention' : 'Manager attention queue'}</h2>
          <p>{summary?.urgent ? `${summary.urgent} urgent item${summary.urgent === 1 ? '' : 's'} should be handled first.` : 'Everything urgent is under control.'}</p>
        </div>
        {compact && <Button variant="ghost" size="sm" to="/admin/attention">View all →</Button>}
      </header>

      {!compact && (
        <div className="attention-summary-strip">
          <SummaryItem label="All tasks" value={summary?.total || 0} />
          <SummaryItem label="Urgent" value={summary?.urgent || 0} tone="urgent" />
          <SummaryItem label="Inquiries" value={summary?.inquiries || 0} />
          <SummaryItem label="Follow-ups" value={summary?.follow_ups || 0} />
          <SummaryItem label="Deadlines" value={summary?.deadlines || 0} />
          <SummaryItem label="Payments" value={summary?.payments || 0} />
        </div>
      )}

      <div className="attention-toolbar">
        <div className="attention-tabs" role="tablist" aria-label="Filter attention queue">
          {TYPES.map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={filter === value ? 'active' : ''}
              onClick={() => setFilter(value)}
            >
              {label}
              {!compact && <span>{countFor(data, value)}</span>}
            </button>
          ))}
        </div>
        {!compact && <span className="attention-refresh">Updated from live workspace data</span>}
      </div>

      {(error || notice) && <div className={`attention-message ${error ? 'error' : 'success'}`}>{error || notice}</div>}

      {!data && !error ? (
        <div className="attention-empty">Checking what needs attention...</div>
      ) : visibleItems.length === 0 ? (
        <div className="attention-empty complete">
          <span>✓</span>
          <strong>All clear in this view</strong>
          <p>No overdue or upcoming items match this filter.</p>
        </div>
      ) : (
        <div className="attention-list">
          {visibleItems.map((item) => {
            const meta = TYPE_META[item.type]
            return (
              <article
                className={`attention-item urgency-${item.urgency}`}
                key={item.key}
                onClick={() => navigate(item.href)}
              >
                <div className={`attention-type-icon type-${item.type}`}>{meta.code}</div>
                <div className="attention-item-copy">
                  <div className="attention-item-topline">
                    <span>{meta.label}</span>
                    <time className={item.urgency === 'urgent' ? 'urgent' : ''}>{timeLabel(item)}</time>
                  </div>
                  <h3>{item.title}</h3>
                  <p><strong>{item.brand_name}</strong><span>·</span>{item.detail}</p>
                </div>
                {item.amount != null && <strong className="attention-amount">{money.format(item.amount)}</strong>}
                <div className="attention-actions" onClick={(event) => event.stopPropagation()}>
                  {item.type === 'inquiry' && (
                    <button
                      type="button"
                      disabled={working === `${item.key}-contacted`}
                      onClick={() => performAction(item, 'contacted')}
                    >
                      Mark contacted
                    </button>
                  )}
                  {item.type === 'follow_up' && (
                    <>
                      <button type="button" disabled={Boolean(working)} onClick={() => performAction(item, 'snooze')}>+2 days</button>
                      <button type="button" disabled={Boolean(working)} onClick={() => performAction(item, 'done')}>Done</button>
                    </>
                  )}
                  <Link to={item.href}>{item.type === 'payment' ? 'Open ledger' : 'Open'} <span>→</span></Link>
                </div>
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}

function SummaryItem({ label, value, tone = '' }) {
  return <div className={tone}><span>{label}</span><strong>{value}</strong></div>
}

function countFor(data, type) {
  if (!data) return 0
  if (type === 'all') return data.summary.total
  if (type === 'inquiry') return data.summary.inquiries
  if (type === 'follow_up') return data.summary.follow_ups
  if (type === 'deadline') return data.summary.deadlines
  return data.summary.payments
}

function timeLabel(item) {
  if (!item.due_at) return 'No date'
  const date = new Date(item.due_at)
  const now = new Date()
  const dayDifference = Math.ceil((date.getTime() - now.getTime()) / 86400000)

  if (item.type === 'inquiry') {
    const age = Math.max(0, Math.floor((now.getTime() - date.getTime()) / 86400000))
    return age === 0 ? 'Received today' : `${age}d waiting`
  }
  if (dayDifference < 0) return `${Math.abs(dayDifference)}d overdue`
  if (dayDifference === 0) return 'Due today'
  if (dayDifference === 1) return 'Due tomorrow'
  return `Due ${date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}`
}
