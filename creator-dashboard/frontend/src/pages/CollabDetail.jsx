import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { API, authFetch } from '../api.js'
import { Button, FormField } from '../components/ui.jsx'
import AgreementCenter from '../components/AgreementCenter.jsx'

const STAGES = [
  ['new', 'New'],
  ['in_discussion', 'In discussion'],
  ['negotiating', 'Negotiating'],
  ['confirmed', 'Confirmed'],
  ['agreement_invoice', 'Agreement & Invoice'],
  ['script_approved', 'Script Approved'],
  ['shoot_done', 'Shoot Done'],
  ['draft_submitted', 'Draft Submitted'],
  ['content_posted', 'Content Posted'],
  ['payment_received', 'Payment Received'],
  ['closed', 'Closed'],
]

const TABS = [
  ['overview', 'Overview'],
  ['agreement', 'Agreement'],
  ['finance', 'Finance'],
  ['deliverables', 'Deliverables'],
  ['resources', 'Files & links'],
  ['results', 'Content results'],
  ['notes', 'Notes & activity'],
]
const FINANCE_FIELDS = new Set(['amount_received', 'payment_date', 'payment_method', 'tds_deduction', 'other_deductions', 'finance_notes'])
const DELIVERY_COMPLETE_STATUSES = new Set(['content_posted', 'payment_received', 'closed'])

export default function CollabDetail() {
  const { collabId } = useParams()
  const navigate = useNavigate()
  const [form, setForm] = useState(null)
  const [baseline, setBaseline] = useState('')
  const [activeTab, setActiveTab] = useState('overview')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [resourceKind, setResourceKind] = useState('Brief')
  const [resourceLabel, setResourceLabel] = useState('')
  const [resourceFile, setResourceFile] = useState(null)
  const [resourceUploading, setResourceUploading] = useState(false)

  useEffect(() => {
    authFetch(`/api/collabs/${collabId}`)
      .then((response) => {
        if (!response.ok) throw new Error('Could not load collaboration')
        return response.json()
      })
      .then((data) => {
        const normalized = normalize(data)
        setForm(normalized)
        setBaseline(JSON.stringify(normalized))
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [collabId])

  const checklistProgress = useMemo(() => {
    if (!form?.deliverable_checklist.length) return 0
    const complete = form.deliverable_checklist.filter((item) => item.completed).length
    return Math.round((complete / form.deliverable_checklist.length) * 100)
  }, [form])

  const pipelineProgress = useMemo(() => {
    const index = STAGES.findIndex(([value]) => value === form?.status)
    return index < 0 ? 0 : Math.round((index / (STAGES.length - 1)) * 100)
  }, [form?.status])

  const dirty = Boolean(form && baseline && JSON.stringify(form) !== baseline)

  useEffect(() => {
    const protectChanges = (event) => {
      if (!dirty) return
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', protectChanges)
    return () => window.removeEventListener('beforeunload', protectChanges)
  }, [dirty])

  function patch(field, value) {
    setForm((current) => ({
      ...current,
      [field]: value,
      ...(FINANCE_FIELDS.has(field) ? { finance_tracking_enabled: true } : {}),
    }))
    setNotice('')
  }

  function patchList(field, index, key, value) {
    patch(field, form[field].map((item, itemIndex) => (
      itemIndex === index ? { ...item, [key]: value } : item
    )))
  }

  function removeListItem(field, index) {
    patch(field, form[field].filter((_, itemIndex) => itemIndex !== index))
  }

  async function save() {
    setSaving(true)
    setError('')
    setNotice('')
    try {
      const response = await authFetch(`/api/collabs/${collabId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(toPayload(form)),
      })
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(body?.detail || 'Could not save collaboration')
      }
      const normalized = normalize(await response.json())
      setForm(normalized)
      setBaseline(JSON.stringify(normalized))
      setNotice('Collaboration saved.')
      return true
    } catch (err) {
      setError(err.message)
      return false
    } finally {
      setSaving(false)
    }
  }

  function discardChanges() {
    if (!baseline) return
    setForm(JSON.parse(baseline))
    setError('')
    setNotice('Unsaved changes discarded.')
  }

  async function uploadResource(file = resourceFile) {
    if (!file) return
    if (dirty && !(await save())) return
    setResourceUploading(true)
    setError('')
    setNotice('')
    const body = new FormData()
    body.append('file', file)
    body.append('kind', resourceKind)
    if (resourceLabel.trim()) body.append('label', resourceLabel.trim())
    try {
      const response = await authFetch(`/api/collabs/${collabId}/resources`, { method: 'POST', body })
      const payload = await response.json().catch(() => null)
      if (!response.ok) throw new Error(payload?.detail || 'Could not upload campaign file')
      const normalized = normalize(payload)
      setForm(normalized)
      setBaseline(JSON.stringify(normalized))
      setResourceFile(null)
      setResourceLabel('')
      setNotice(`${file.name} uploaded to campaign resources.`)
    } catch (err) {
      setError(err.message)
    } finally {
      setResourceUploading(false)
    }
  }

  if (loading) return <div className="admin-loading"><span className="loading-dot" />Loading collaboration...</div>
  if (!form) {
    return (
      <div className="admin-page">
        <div className="admin-notice error">{error || 'Collaboration not found'}</div>
        <Link className="button secondary" to="/admin">Back to dashboard</Link>
      </div>
    )
  }

  const scheduleSummary = collaborationScheduleSummary(form)

  return (
    <div className="admin-page collab-detail-page">
      <div className="detail-breadcrumb">
        <Link to="/admin">Collaborations</Link><span>/</span><strong>{form.brand.name}</strong>
      </div>

      <header className="admin-page-header collab-detail-header">
        <div>
          <div className="detail-title-line">
            <div className="brand-avatar large">{initials(form.brand.name)}</div>
            <div>
              <div className="eyebrow">Collaboration #{form.id}</div>
              <h1>{form.brand.name}</h1>
            </div>
          </div>
          <p>{form.campaign_type || 'General collaboration'} · Opened {formatDate(form.created_at)}</p>
        </div>
        <div className="header-actions">
          {dirty && <span className="unsaved-indicator"><i />Unsaved changes</span>}
          <select className={`detail-status status-${form.status}`} value={form.status} onChange={(event) => patch('status', event.target.value)}>
            {STAGES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <Button variant="secondary" onClick={() => navigate(`/admin/invoices/new?brand_id=${form.brand_id}&collab_id=${form.id}`)}>
            Generate invoice
          </Button>
          {dirty && <Button size="sm" variant="ghost" onClick={discardChanges} disabled={saving}>Discard</Button>}
          <Button size="sm" onClick={save} loading={saving} disabled={!dirty}>{saving ? 'Saving' : 'Save changes'}</Button>
        </div>
      </header>

      {(error || notice) && <div className={`admin-notice ${error ? 'error' : 'success'}`}>{error || notice}</div>}

      <section className="campaign-progress-card">
        <div className="campaign-progress-copy">
          <span>Campaign progress</span>
          <strong>{stageLabel(form.status)}</strong>
        </div>
        <div className="campaign-progress-track"><span style={{ width: `${pipelineProgress}%` }} /></div>
        <em>{pipelineProgress}%</em>
      </section>

      <CampaignWarnings form={form} />

      <div className="detail-summary-grid">
        <SummaryCard label="Budget" value={form.budget ? money(form.budget) : 'Not shared'} />
        <SummaryCard label={scheduleSummary.label} value={scheduleSummary.value} tone={scheduleSummary.tone} />
        <SummaryCard label="Days in stage" value={`${daysInStage(form.stage_entered_at)} days`} tone={daysInStage(form.stage_entered_at) > 7 ? 'yellow' : ''} />
        <SummaryCard label="Deliverables complete" value={`${checklistProgress}%`} tone={checklistProgress === 100 ? 'green' : ''} />
      </div>

      <nav className="detail-tabs" aria-label="Collaboration workspace sections">
        {TABS.map(([value, label]) => (
          <button type="button" key={value} className={activeTab === value ? 'active' : ''} onClick={() => setActiveTab(value)}>
            {label}
            {value === 'deliverables' && form.deliverable_checklist.length > 0 && <span>{form.deliverable_checklist.length}</span>}
            {value === 'resources' && form.resource_links.length > 0 && <span>{form.resource_links.length}</span>}
            {value === 'finance' && form.invoice_count > 0 && <span>{form.invoice_count}</span>}
          </button>
        ))}
      </nav>

      <div className="detail-tab-panel">
        {activeTab === 'overview' && (
          <div className="detail-layout">
            <div className="detail-main">
              <DetailSection title="Campaign overview" description="The commercial and creative context for this partnership.">
                <div className="editor-grid two">
                  <Field label="Campaign type"><input value={form.campaign_type || ''} onChange={(event) => patch('campaign_type', event.target.value)} /></Field>
                  <Field label="Budget (INR)"><input type="number" min="0" value={form.budget ?? ''} onChange={(event) => patch('budget', event.target.value)} /></Field>
                  <Field label={DELIVERY_COMPLETE_STATUSES.has(form.status) ? 'Original campaign deadline' : 'Campaign deadline'}><input type="date" value={dateInput(form.deadline)} onChange={(event) => patch('deadline', event.target.value)} /></Field>
                  <Field label="Next follow-up"><input type="datetime-local" value={dateTimeInput(form.follow_up_at)} onChange={(event) => patch('follow_up_at', event.target.value)} /></Field>
                  <Field label="Priority">
                    <select value={form.priority} onChange={(event) => patch('priority', event.target.value)}>
                      <option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option>
                    </select>
                  </Field>
                  <Field label="Assigned to">
                    <select value={form.assignee} onChange={(event) => patch('assignee', event.target.value)}>
                      <option value="unassigned">Unassigned</option><option value="aarohi">Aarohi</option><option value="manager">Manager</option>
                    </select>
                  </Field>
                  <Field label="Waiting on">
                    <select value={form.waiting_on} onChange={(event) => patch('waiting_on', event.target.value)}>
                      <option value="none">No one</option><option value="brand">Brand</option><option value="aarohi">Aarohi</option><option value="manager">Manager</option>
                    </select>
                  </Field>
                </div>
                <Field label="Next action"><input value={form.next_action || ''} onChange={(event) => patch('next_action', event.target.value)} placeholder="What should happen next?" /></Field>
                <Field label="Deliverables"><textarea rows="3" value={form.deliverables || ''} onChange={(event) => patch('deliverables', event.target.value)} /></Field>
                <Field label="Campaign brief"><textarea rows="6" value={form.brief || ''} onChange={(event) => patch('brief', event.target.value)} /></Field>
              </DetailSection>
            </div>
            <aside className="detail-sidebar">
              <DetailSection title="Brand contact" description="Reach the primary contact without leaving this workspace.">
                <Field label="Brand name"><input value={form.brand.name || ''} onChange={(event) => patch('brand', { ...form.brand, name: event.target.value })} /></Field>
                <Field label="Contact person"><input value={form.brand.contact_person || ''} onChange={(event) => patch('brand', { ...form.brand, contact_person: event.target.value })} /></Field>
                <Field label="Email"><input type="email" value={form.brand.email || ''} onChange={(event) => patch('brand', { ...form.brand, email: event.target.value })} /></Field>
                <Field label="Phone"><input value={form.brand.phone || ''} onChange={(event) => patch('brand', { ...form.brand, phone: event.target.value })} /></Field>
                <div className="contact-quick-actions">
                  {form.brand.email && <a href={`mailto:${form.brand.email}`}>Email contact</a>}
                  {form.brand.phone && <a href={`https://wa.me/${form.brand.phone.replace(/\D/g, '')}`} target="_blank" rel="noreferrer">Open WhatsApp</a>}
                </div>
              </DetailSection>
            </aside>
          </div>
        )}

        {activeTab === 'deliverables' && (
          <DetailSection title="Deliverable checklist" description="A clear execution plan shared by Aarohi and her manager.">
            <div className="checklist-heading"><strong>{checklistProgress}% complete</strong><span>{form.deliverable_checklist.filter((item) => item.completed).length} of {form.deliverable_checklist.length} finished</span></div>
            <div className="checklist-progress"><span style={{ width: `${checklistProgress}%` }} /></div>
            <div className="deliverable-checklist">
              {form.deliverable_checklist.map((item, index) => (
                <div className={item.completed ? 'completed' : ''} key={index}>
                  <input type="checkbox" checked={item.completed} onChange={(event) => patchList('deliverable_checklist', index, 'completed', event.target.checked)} />
                  <input value={item.text} onChange={(event) => patchList('deliverable_checklist', index, 'text', event.target.value)} placeholder="Deliverable or action" />
                  <button type="button" aria-label="Remove item" onClick={() => removeListItem('deliverable_checklist', index)}>×</button>
                </div>
              ))}
              {!form.deliverable_checklist.length && <div className="empty-inline">No deliverables added yet.</div>}
            </div>
            <button className="small-button" type="button" onClick={() => patch('deliverable_checklist', [...form.deliverable_checklist, { text: '', completed: false }])}>+ Add checklist item</button>
          </DetailSection>
        )}

        {activeTab === 'agreement' && <AgreementCenter collab={form} />}

        {activeTab === 'finance' && (
          <div className="collab-finance-workspace">
            <section className="collab-finance-summary">
              <SummaryCard label="Agreed amount" value={money(form.budget || 0)} />
              <SummaryCard label="Invoiced" value={money(form.invoiced_amount || 0)} />
              <SummaryCard label="Cash received" value={money(form.amount_received || 0)} tone="green" />
              <SummaryCard label="Balance remaining" value={money(financeRemaining(form))} tone={financeRemaining(form) > 0 ? 'yellow' : 'green'} />
            </section>
            <div className="detail-layout finance-detail-layout">
              <div className="detail-main">
                <DetailSection title="Payment tracking" description="Record the actual amount received. TDS and other deductions are included when calculating the remaining balance.">
                  <div className="editor-grid two">
                    <Field label="Amount received (INR)"><input type="number" min="0" value={form.amount_received ?? ''} onChange={(event) => patch('amount_received', event.target.value)} /></Field>
                    <Field label="Payment date"><input type="date" value={dateInput(form.payment_date)} onChange={(event) => patch('payment_date', event.target.value)} /></Field>
                    <Field label="Payment method">
                      <select value={form.payment_method || ''} onChange={(event) => patch('payment_method', event.target.value)}>
                        <option value="">Not recorded</option><option value="Bank transfer">Bank transfer</option><option value="UPI">UPI</option><option value="PayPal">PayPal</option><option value="Other">Other</option>
                      </select>
                    </Field>
                    <Field label="TDS deducted (INR)"><input type="number" min="0" value={form.tds_deduction ?? ''} onChange={(event) => patch('tds_deduction', event.target.value)} /></Field>
                    <Field label="Other deductions (INR)"><input type="number" min="0" value={form.other_deductions ?? ''} onChange={(event) => patch('other_deductions', event.target.value)} /></Field>
                  </div>
                  <Field label="Finance notes"><textarea rows="4" value={form.finance_notes || ''} onChange={(event) => patch('finance_notes', event.target.value)} placeholder="Payment reference, partial-payment plan, deduction reason..." /></Field>
                  <div className="finance-formula-note">
                    <strong>Balance calculation</strong>
                    <span>Agreed amount − cash received − TDS − other deductions</span>
                  </div>
                </DetailSection>
              </div>
              <aside className="detail-sidebar">
                <DetailSection title="Invoice connection" description="Invoices remain linked to this collaboration and are protected against accidental duplicates.">
                  <div className="finance-invoice-status">
                    <span>{form.invoice_count ? `${form.invoice_count} invoice${form.invoice_count === 1 ? '' : 's'} created` : 'No invoice created'}</span>
                    <strong>{money(form.invoiced_amount || 0)}</strong>
                    <small>{form.paid_invoice_count ? `${form.paid_invoice_count} marked paid` : 'No paid invoice yet'}</small>
                  </div>
                  <Button size="sm" to={`/admin/invoices/new?brand_id=${form.brand_id}&collab_id=${form.id}`}>
                    {form.invoice_count ? 'Review or create another' : 'Create invoice'}
                  </Button>
                  {form.invoice_count > 0 && <Button size="sm" variant="secondary" to="/admin/invoices">Open earnings center</Button>}
                </DetailSection>
              </aside>
            </div>
          </div>
        )}

        {activeTab === 'resources' && (
          <DetailSection title="Campaign resource hub" description="Upload campaign files or save important working links in one place.">
            <div
              className="resource-upload-zone"
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault()
                const file = event.dataTransfer.files?.[0]
                if (file) setResourceFile(file)
              }}
            >
              <div className="resource-upload-mark" aria-hidden="true">&#8593;</div>
              <div className="resource-upload-copy">
                <strong>{resourceFile ? resourceFile.name : 'Drop a campaign file here'}</strong>
                <span>{resourceFile ? formatBytes(resourceFile.size) : 'PDF, Word, Excel, PowerPoint, ZIP, text or image · up to 15 MB'}</span>
              </div>
              <label className="resource-file-picker">
                {resourceFile ? 'Choose another' : 'Browse files'}
                <input type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.zip,.txt,.jpg,.jpeg,.png,.webp" onChange={(event) => setResourceFile(event.target.files?.[0] || null)} />
              </label>
            </div>
            <div className="resource-upload-controls">
              <select value={resourceKind} onChange={(event) => setResourceKind(event.target.value)}>{resourceKindOptions()}</select>
              <input value={resourceLabel} onChange={(event) => setResourceLabel(event.target.value)} placeholder="Display name (uses filename if blank)" />
              <Button onClick={() => uploadResource()} loading={resourceUploading} disabled={!resourceFile}>Upload file</Button>
            </div>

            <div className="resource-section-label"><span>Saved resources</span><em>{form.resource_links.length}</em></div>
            <div className="detail-repeat-list resource-library">
              {form.resource_links.map((item, index) => (
                <div className={`resource-row ${item.source === 'upload' ? 'uploaded' : ''}`} key={`${item.url}-${index}`}>
                  <select value={item.kind || 'Brief'} onChange={(event) => patchList('resource_links', index, 'kind', event.target.value)}>{resourceKindOptions()}</select>
                  <div className="resource-name-cell">
                    <input value={item.label} onChange={(event) => patchList('resource_links', index, 'label', event.target.value)} placeholder="Label" />
                    {item.source === 'upload' && <small>{item.filename} · {formatBytes(item.size)}</small>}
                  </div>
                  {item.source === 'upload'
                    ? <span className="resource-stored-badge">Cloud file</span>
                    : <input type="url" value={item.url} onChange={(event) => patchList('resource_links', index, 'url', event.target.value)} placeholder="https://..." />}
                  {item.url && <a href={absoluteResourceUrl(item.url)} target="_blank" rel="noreferrer" title="Open resource">&#8599;</a>}
                  <button type="button" aria-label="Remove resource" onClick={() => removeListItem('resource_links', index)}>×</button>
                </div>
              ))}
              {!form.resource_links.length && <div className="empty-inline">No campaign files or links added yet.</div>}
            </div>
            <button className="small-button" type="button" onClick={() => patch('resource_links', [...form.resource_links, { label: '', url: '', kind: 'Brief', source: 'link' }])}>+ Add external link</button>
          </DetailSection>
        )}

        {activeTab === 'results' && (
          <DetailSection title="Live content & performance" description="Capture results so strong campaigns can become case studies.">
            <Field label="Published content URL"><input type="url" value={form.content_link || ''} onChange={(event) => patch('content_link', event.target.value)} placeholder="https://instagram.com/..." /></Field>
            <div className="performance-grid">
              {form.performance_metrics.map((item, index) => (
                <div key={index}>
                  <input value={item.label} onChange={(event) => patchList('performance_metrics', index, 'label', event.target.value)} placeholder="Metric, e.g. Views" />
                  <input value={item.value} onChange={(event) => patchList('performance_metrics', index, 'value', event.target.value)} placeholder="Value, e.g. 250K" />
                  <button type="button" aria-label="Remove metric" onClick={() => removeListItem('performance_metrics', index)}>×</button>
                </div>
              ))}
            </div>
            {!form.performance_metrics.length && <div className="empty-inline">Add views, reach, engagement, clicks, or conversions after publishing.</div>}
            <button className="small-button" type="button" onClick={() => patch('performance_metrics', [...form.performance_metrics, { label: '', value: '' }])}>+ Add performance metric</button>
          </DetailSection>
        )}

        {activeTab === 'notes' && (
          <div className="detail-notes-layout">
            <DetailSection title="Private manager notes" description="Negotiation context and next actions visible only inside admin.">
              <textarea className="manager-notes" rows="16" value={form.notes || ''} onChange={(event) => patch('notes', event.target.value)} placeholder="Negotiation notes, preferences, next action..." />
            </DetailSection>
            <DetailSection title="Activity" description="Recent changes to this collaboration.">
              <div className="activity-list">
                {[...form.activity_log].reverse().slice(0, 20).map((event, index) => (
                  <div key={`${event.timestamp}-${index}`}>
                    <span className="activity-dot" />
                    <div>
                      <strong>{activityTitle(event)}</strong>
                      {event.detail && <p>{event.detail}</p>}
                      <time>{formatDateTime(event.timestamp)}</time>
                    </div>
                  </div>
                ))}
                {!form.activity_log.length && <div className="empty-inline">Activity will appear after the first update.</div>}
              </div>
            </DetailSection>
          </div>
        )}
      </div>
    </div>
  )
}

function CampaignWarnings({ form }) {
  const warnings = []
  const now = new Date()
  if (form.deadline && !DELIVERY_COMPLETE_STATUSES.has(form.status)) {
    const deadline = new Date(form.deadline)
    const days = Math.ceil((deadline.getTime() - now.getTime()) / 86400000)
    if (days < 0) warnings.push({ tone: 'danger', text: `Campaign deadline passed ${Math.abs(days)} day${Math.abs(days) === 1 ? '' : 's'} ago.` })
    else if (days <= 3) warnings.push({ tone: 'warning', text: days === 0 ? 'Campaign deadline is today.' : `Campaign deadline is in ${days} day${days === 1 ? '' : 's'}.` })
  }
  if (form.follow_up_at && !['payment_received', 'closed'].includes(form.status) && new Date(form.follow_up_at) <= now) warnings.push({ tone: 'danger', text: 'The scheduled brand follow-up is overdue.' })
  if (!warnings.length) return null
  return (
    <div className="campaign-warning-list">
      {warnings.map((warning, index) => <div className={warning.tone} key={index}><span>!</span>{warning.text}</div>)}
    </div>
  )
}

function collaborationScheduleSummary(form) {
  if (form.status === 'content_posted') return { label: 'Delivery status', value: 'Content posted', tone: 'green' }
  if (form.status === 'payment_received') return { label: 'Payment status', value: 'Payment received', tone: 'green' }
  if (form.status === 'closed') return { label: 'Campaign status', value: 'Closed', tone: 'green' }
  return { label: 'Campaign deadline', value: form.deadline ? formatDate(form.deadline) : 'Not scheduled', tone: '' }
}

function normalize(data) {
  return {
    ...data,
    brand: data.brand || {},
    deliverable_checklist: data.deliverable_checklist || [],
    resource_links: data.resource_links || [],
    performance_metrics: data.performance_metrics || [],
    activity_log: data.activity_log || [],
    priority: data.priority || 'normal',
    assignee: data.assignee || 'unassigned',
    waiting_on: data.waiting_on || 'none',
    next_action: data.next_action || '',
    amount_received: data.amount_received ?? 0,
    tds_deduction: data.tds_deduction ?? 0,
    other_deductions: data.other_deductions ?? 0,
    payment_method: data.payment_method || '',
    finance_notes: data.finance_notes || '',
    finance_tracking_enabled: Boolean(data.finance_tracking_enabled),
  }
}

function toPayload(form) {
  const payload = {
    brand_name: form.brand.name || '',
    brand_contact_person: form.brand.contact_person || null,
    brand_email: form.brand.email || null,
    brand_phone: form.brand.phone || null,
    campaign_type: form.campaign_type || null,
    deliverables: form.deliverables || null,
    budget: form.budget === '' || form.budget == null ? null : Number(form.budget),
    deadline: form.deadline ? new Date(form.deadline).toISOString() : null,
    status: form.status,
    brief: form.brief || null,
    content_link: form.content_link || null,
    notes: form.notes || null,
    follow_up_at: form.follow_up_at ? new Date(form.follow_up_at).toISOString() : null,
    deliverable_checklist: form.deliverable_checklist.filter((item) => item.text.trim()),
    resource_links: form.resource_links.filter((item) => item.label.trim() && item.url.trim()),
    performance_metrics: form.performance_metrics.filter((item) => item.label.trim() && item.value.trim()),
    priority: form.priority,
    assignee: form.assignee,
    waiting_on: form.waiting_on,
    next_action: form.next_action || null,
  }
  if (form.finance_tracking_enabled) Object.assign(payload, {
    amount_received: form.amount_received === '' || form.amount_received == null ? null : Number(form.amount_received),
    payment_date: form.payment_date ? new Date(form.payment_date).toISOString() : null,
    payment_method: form.payment_method || null,
    tds_deduction: form.tds_deduction === '' || form.tds_deduction == null ? 0 : Number(form.tds_deduction),
    other_deductions: form.other_deductions === '' || form.other_deductions == null ? 0 : Number(form.other_deductions),
    finance_notes: form.finance_notes || null,
  })
  return payload
}

function DetailSection({ title, description, children }) {
  return (
    <section className="detail-card">
      <header><h2>{title}</h2>{description && <p>{description}</p>}</header>
      <div className="detail-card-body">{children}</div>
    </section>
  )
}

function Field({ label, children }) {
  return <FormField label={label}>{children}</FormField>
}

function SummaryCard({ label, value, tone = '' }) {
  return <article className={`detail-summary-card ${tone}`}><span>{label}</span><strong>{value}</strong></article>
}

function financeRemaining(form) {
  return Math.max(
    Number(form.budget || 0)
      - Number(form.amount_received || 0)
      - Number(form.tds_deduction || 0)
      - Number(form.other_deductions || 0),
    0,
  )
}

function stageLabel(status) {
  return STAGES.find(([value]) => value === status)?.[1] || 'In progress'
}

function initials(value) {
  return value.split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase()
}

function money(value) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(Number(value || 0))
}

function dateInput(value) {
  return value ? new Date(value).toISOString().slice(0, 10) : ''
}

function dateTimeInput(value) {
  if (!value) return ''
  const date = new Date(value)
  const offset = date.getTimezoneOffset()
  return new Date(date.getTime() - offset * 60000).toISOString().slice(0, 16)
}

function formatDate(value) {
  return new Date(value).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

function formatDateTime(value) {
  return new Date(value).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })
}

function activityTitle(event) {
  if (event.action === 'status_changed') return 'Status changed'
  if (event.action === 'inquiry_received') return 'Inquiry received'
  if (event.action === 'collaboration_added') return 'Collaboration added'
  if (event.action === 'resource_uploaded') return 'Campaign file uploaded'
  if (event.action === 'finance_updated') return 'Payment details updated'
  return 'Workspace updated'
}

function resourceKindOptions() {
  return ['Brief', 'Script', 'Contract', 'Draft', 'Reference', 'Brand assets', 'Drive folder', 'Live content', 'Other']
    .map((kind) => <option key={kind}>{kind}</option>)
}

function formatBytes(value) {
  const bytes = Number(value || 0)
  if (!bytes) return 'File size unavailable'
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function absoluteResourceUrl(value) {
  return /^https?:\/\//i.test(value) ? value : `${API}${value}`
}

function daysInStage(value) {
  if (!value) return 0
  return Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 86400000))
}
