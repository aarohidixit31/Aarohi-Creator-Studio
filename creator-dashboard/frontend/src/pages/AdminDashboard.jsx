import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { authFetch } from '../api.js'
import { Button, Feedback, FormField, SegmentedControl } from '../components/ui.jsx'
import AttentionQueue from '../components/AttentionQueue.jsx'

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

const ACTIVE_STAGES = new Set(STAGES.map(([value]) => value).filter((value) => !['payment_received', 'closed'].includes(value)))
const PHASES = [
  ['sales', 'Sales', ['new', 'in_discussion', 'negotiating']],
  ['onboarding', 'Onboarding', ['confirmed', 'agreement_invoice']],
  ['production', 'Production', ['script_approved', 'shoot_done', 'draft_submitted']],
  ['completion', 'Completion', ['content_posted', 'payment_received', 'closed']],
]
const EMPTY_COLLAB = {
  brand_id: '',
  brand_name: '',
  contact_person: '',
  email: '',
  phone: '',
  status: 'new',
  campaign_type: '',
  deliverables: '',
  budget: '',
  deadline: '',
  brief: '',
  notes: '',
  priority: 'normal',
  assignee: 'unassigned',
  waiting_on: 'none',
  next_action: '',
}

export default function AdminDashboard() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [collabs, setCollabs] = useState(null)
  const [brands, setBrands] = useState([])
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('all')
  const [campaignFilter, setCampaignFilter] = useState('all')
  const [timingFilter, setTimingFilter] = useState('all')
  const [budgetFilter, setBudgetFilter] = useState('all')
  const [priorityFilter, setPriorityFilter] = useState('all')
  const [assigneeFilter, setAssigneeFilter] = useState('all')
  const [updating, setUpdating] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const [archiving, setArchiving] = useState(null)
  const [pipelineScope, setPipelineScope] = useState('active')
  const [phase, setPhase] = useState(() => localStorage.getItem('pipeline_phase') || 'sales')
  const [view, setView] = useState(() => localStorage.getItem('pipeline_view') || 'board')
  const [draggedId, setDraggedId] = useState(null)
  const [dropStage, setDropStage] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [brandMode, setBrandMode] = useState('existing')
  const [createForm, setCreateForm] = useState(EMPTY_COLLAB)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')

  useEffect(() => {
    load()
    authFetch('/api/brands/')
      .then((response) => response.ok ? response.json() : [])
      .then(setBrands)
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (searchParams.get('new_collab') !== '1') return
    const brandId = searchParams.get('brand_id') || ''
    setBrandMode('existing')
    setCreateForm((current) => ({ ...current, brand_id: brandId }))
    setShowCreate(true)
    setSearchParams({}, { replace: true })
  }, [searchParams, setSearchParams])

  useEffect(() => {
    if (!showCreate) return undefined
    document.body.classList.add('modal-open')
    const closeOnEscape = (event) => {
      if (event.key === 'Escape' && !creating) closeCreate()
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => {
      document.body.classList.remove('modal-open')
      window.removeEventListener('keydown', closeOnEscape)
    }
  }, [showCreate, creating])

  function load(scope = pipelineScope) {
    setError('')
    authFetch(`/api/collabs/?archived=${scope === 'archived'}`)
      .then((response) => {
        if (!response.ok) throw new Error('Could not load collaborations')
        return response.json()
      })
      .then(setCollabs)
      .catch((err) => setError(err.message))
  }

  async function updateStatus(id, status) {
    const previous = collabs
    setUpdating(id)
    setCollabs((current) => current?.map((item) => (
      item.id === id ? { ...item, status } : item
    )))
    try {
      const response = await authFetch(`/api/collabs/${id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      })
      if (!response.ok) throw new Error('Could not update status')
    } catch (err) {
      setCollabs(previous)
      setError(err.message)
    } finally {
      setUpdating(null)
    }
  }

  async function deleteCollaboration(collab) {
    const brandName = collab.brand?.name || `Collaboration #${collab.id}`
    if (!window.confirm(`Remove ${brandName} from the collaboration pipeline?\n\nInvoices, content records and the brand profile will be kept.`)) return

    setDeleting(collab.id)
    setError('')
    try {
      const response = await authFetch(`/api/collabs/${collab.id}`, { method: 'DELETE' })
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(body?.detail || 'Could not delete collaboration')
      }
      setCollabs((current) => current?.filter((item) => item.id !== collab.id))
    } catch (err) {
      setError(err.message)
    } finally {
      setDeleting(null)
    }
  }

  async function toggleArchive(collab) {
    const restoring = pipelineScope === 'archived'
    setArchiving(collab.id)
    setError('')
    try {
      const response = await authFetch(`/api/collabs/${collab.id}/archive?archived=${!restoring}`, { method: 'PATCH' })
      if (!response.ok) throw new Error(restoring ? 'Could not restore collaboration' : 'Could not archive collaboration')
      setCollabs((current) => current?.filter((item) => item.id !== collab.id))
    } catch (err) {
      setError(err.message)
    } finally {
      setArchiving(null)
    }
  }

  function changeScope(scope) {
    setPipelineScope(scope)
    setCollabs(null)
    load(scope)
  }

  function changePhase(nextPhase) {
    setPhase(nextPhase)
    localStorage.setItem('pipeline_phase', nextPhase)
  }

  function changeView(nextView) {
    setView(nextView)
    localStorage.setItem('pipeline_view', nextView)
  }

  function dropCollab(stage) {
    const collab = collabs?.find((item) => item.id === draggedId)
    if (collab && collab.status !== stage) updateStatus(collab.id, stage)
    setDraggedId(null)
    setDropStage(null)
  }

  function closeCreate() {
    setShowCreate(false)
    setCreateError('')
    setCreateForm(EMPTY_COLLAB)
    setBrandMode('existing')
  }

  function patchCreate(field, value) {
    setCreateForm((current) => ({ ...current, [field]: value }))
  }

  async function createCollaboration(event) {
    event.preventDefault()
    setCreating(true)
    setCreateError('')
    try {
      const payload = {
        ...createForm,
        brand_id: brandMode === 'existing' ? Number(createForm.brand_id) : null,
        brand_name: brandMode === 'new' ? createForm.brand_name : null,
        contact_person: brandMode === 'new' ? createForm.contact_person || null : null,
        email: brandMode === 'new' ? createForm.email || null : null,
        phone: brandMode === 'new' ? createForm.phone || null : null,
        budget: createForm.budget ? Number(createForm.budget) : null,
        deadline: createForm.deadline ? new Date(`${createForm.deadline}T12:00:00`).toISOString() : null,
        brief: createForm.brief || null,
        notes: createForm.notes || null,
      }
      const response = await authFetch('/api/collabs/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(body?.detail || 'Could not add collaboration')
      }
      const collaboration = await response.json()
      setCollabs((current) => [collaboration, ...(current || [])])
      setBrands((current) => (
        current.some((brand) => brand.id === collaboration.brand.id)
          ? current
          : [...current, collaboration.brand]
      ))
      closeCreate()
    } catch (err) {
      setCreateError(err.message)
    } finally {
      setCreating(false)
    }
  }

  const stats = useMemo(() => {
    const list = collabs || []
    return {
      total: list.length,
      newCount: list.filter((item) => item.status === 'new').length,
      active: list.filter((item) => ACTIVE_STAGES.has(item.status)).length,
      pipeline: list
        .filter((item) => ACTIVE_STAGES.has(item.status))
        .reduce((sum, item) => sum + Number(item.budget || 0), 0),
    }
  }, [collabs])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return (collabs || []).filter((item) => {
      const matchesFilter = filter === 'all' || item.status === filter
      const matchesCampaign = campaignFilter === 'all' || item.campaign_type === campaignFilter
      const deadline = item.deadline ? new Date(item.deadline) : null
      const daysUntilDeadline = deadline ? (deadline.getTime() - Date.now()) / 86400000 : null
      const matchesTiming = timingFilter === 'all'
        || (timingFilter === 'overdue' && daysUntilDeadline != null && daysUntilDeadline < 0)
        || (timingFilter === 'next_7_days' && daysUntilDeadline != null && daysUntilDeadline >= 0 && daysUntilDeadline <= 7)
        || (timingFilter === 'no_deadline' && !deadline)
      const budget = Number(item.budget || 0)
      const matchesBudget = budgetFilter === 'all'
        || (budgetFilter === 'with_budget' && budget > 0)
        || (budgetFilter === 'under_25k' && budget > 0 && budget < 25000)
        || (budgetFilter === 'over_25k' && budget >= 25000)
      const matchesPriority = priorityFilter === 'all' || item.priority === priorityFilter
      const matchesAssignee = assigneeFilter === 'all' || item.assignee === assigneeFilter
      const haystack = [
        item.brand?.name, item.brand?.contact_person, item.brand?.email,
        item.campaign_type, item.deliverables, item.brief, item.next_action,
      ].filter(Boolean).join(' ').toLowerCase()
      return matchesFilter && matchesCampaign && matchesTiming && matchesBudget && matchesPriority && matchesAssignee && (!needle || haystack.includes(needle))
    })
  }, [collabs, query, filter, campaignFilter, timingFilter, budgetFilter, priorityFilter, assigneeFilter])

  const visibleBoardStages = useMemo(() => (
    PHASES.find(([value]) => value === phase)?.[2] || PHASES[0][2]
  ), [phase])

  const campaignTypes = useMemo(() => (
    [...new Set((collabs || []).map((item) => item.campaign_type).filter(Boolean))].sort()
  ), [collabs])

  const brandOptions = useMemo(() => {
    const unique = new Map()
    brands.forEach((brand) => unique.set(brand.id, brand))
    ;(collabs || []).forEach((item) => {
      if (item.brand?.id) unique.set(item.brand.id, item.brand)
    })
    return [...unique.values()].sort((a, b) => a.name.localeCompare(b.name))
  }, [brands, collabs])

  return (
    <div className="admin-page">
      <header className="admin-page-header">
        <div>
          <div className="eyebrow">Manager workspace</div>
          <h1>Good to see you, Aarohi.</h1>
          <p>Here is what needs attention across your collaboration pipeline.</p>
        </div>
        <div className="header-actions">
          <Button variant="secondary" to="/admin/media-kit">Edit media kit</Button>
          <Button variant="secondary" to="/admin/invoices/new">New invoice</Button>
          <Button icon="+" onClick={() => setShowCreate(true)}>Add collaboration</Button>
        </div>
      </header>

      {error && <div className="admin-notice error">{error}</div>}

      <section className="metric-grid">
        <MetricCard label="Total collaborations" value={stats.total} note="All records" tone="blue" />
        <MetricCard label="Needs response" value={stats.newCount} note="New collaborations" tone="yellow" />
        <MetricCard label="Active collabs" value={stats.active} note="Currently in pipeline" />
        <MetricCard label="Pipeline value" value={money(stats.pipeline)} note="Based on shared budgets" />
      </section>

      <AttentionQueue compact />

      <section className={`manager-card ${view === 'board' ? 'board-mode' : ''}`}>
        <div className="manager-card-header">
          <div>
            <span className="summary-kicker">Collaborations</span>
            <h2>Collaboration pipeline</h2>
          </div>
          <div className="pipeline-tools">
            <SegmentedControl
              value={pipelineScope}
              onChange={changeScope}
              label="Pipeline records"
              options={[{ value: 'active', label: 'Active' }, { value: 'archived', label: 'Archive' }]}
            />
            <SegmentedControl
              value={view}
              onChange={changeView}
              label="Pipeline view"
              options={[{ value: 'board', label: 'Board' }, { value: 'list', label: 'List' }]}
            />
            <div className="search-box">
              <span className="search-icon" aria-hidden="true" />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search brand, contact or campaign" />
            </div>
            <select value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="all">All stages</option>
              {STAGES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <select value={campaignFilter} onChange={(e) => setCampaignFilter(e.target.value)}>
              <option value="all">All campaign types</option>
              {campaignTypes.map((type) => <option value={type} key={type}>{type}</option>)}
            </select>
            <select value={timingFilter} onChange={(e) => setTimingFilter(e.target.value)}>
              <option value="all">Any deadline</option>
              <option value="overdue">Deadline overdue</option>
              <option value="next_7_days">Due in 7 days</option>
              <option value="no_deadline">No deadline</option>
            </select>
            <select value={budgetFilter} onChange={(e) => setBudgetFilter(e.target.value)}>
              <option value="all">Any budget</option>
              <option value="with_budget">Budget provided</option>
              <option value="under_25k">Under ₹25K</option>
              <option value="over_25k">₹25K and above</option>
            </select>
            <select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)}>
              <option value="all">Any priority</option>
              <option value="urgent">Urgent</option><option value="high">High</option><option value="normal">Normal</option><option value="low">Low</option>
            </select>
            <select value={assigneeFilter} onChange={(e) => setAssigneeFilter(e.target.value)}>
              <option value="all">Anyone</option>
              <option value="aarohi">Aarohi</option><option value="manager">Manager</option><option value="unassigned">Unassigned</option>
            </select>
            {(campaignFilter !== 'all' || timingFilter !== 'all' || budgetFilter !== 'all' || priorityFilter !== 'all' || assigneeFilter !== 'all') && (
              <button className="pipeline-filter-clear" type="button" onClick={() => {
                setCampaignFilter('all')
                setTimingFilter('all')
                setBudgetFilter('all')
                setPriorityFilter('all')
                setAssigneeFilter('all')
              }}>Clear filters</button>
            )}
          </div>
        </div>

        {!collabs && !error && <div className="admin-loading"><span className="loading-dot" />Loading pipeline...</div>}

        {collabs && filtered.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-mark">AI</div>
            <h3>{collabs.length ? 'No matching collaborations' : 'Your pipeline is ready'}</h3>
            <p>{collabs.length ? 'Try a different search or stage.' : 'New brand inquiries will appear here automatically.'}</p>
          </div>
        )}

        {filtered.length > 0 && view === 'list' && (
          <div className="pipeline-list">
            {filtered.map((collab) => (
              <article className="pipeline-row clickable" key={collab.id} onClick={() => navigate(`/admin/collabs/${collab.id}`)}>
                <div className="brand-avatar">{initials(collab.brand?.name || 'Brand')}</div>
                <div className="pipeline-brand">
                  <strong>{collab.brand?.name || `Brand #${collab.brand_id}`}</strong>
                  <span>{collab.brand?.contact_person || 'No contact name'}{collab.brand?.email ? ` · ${collab.brand.email}` : ''}</span>
                </div>
                <div className="pipeline-campaign">
                  <strong>{collab.campaign_type || 'General collaboration'}</strong>
                  <span>{collab.next_action || collab.deliverables || collab.brief || 'No next action added'}</span>
                </div>
                <div className="pipeline-budget">
                  <span>Budget</span>
                  <strong>{collab.budget ? money(collab.budget) : 'Not shared'}</strong>
                </div>
                <select
                  className={`status-select status-${collab.status}`}
                  value={collab.status}
                  disabled={updating === collab.id}
                  onClick={(event) => event.stopPropagation()}
                  onChange={(e) => updateStatus(collab.id, e.target.value)}
                  aria-label={`Status for ${collab.brand?.name || 'collaboration'}`}
                >
                  {STAGES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
                <button className="collab-archive-button" type="button" disabled={archiving === collab.id} onClick={(event) => {
                  event.stopPropagation()
                  toggleArchive(collab)
                }}>{pipelineScope === 'archived' ? 'Restore' : 'Archive'}</button>
                <button
                  className="collab-delete-button"
                  type="button"
                  disabled={deleting === collab.id}
                  onClick={(event) => {
                    event.stopPropagation()
                    deleteCollaboration(collab)
                  }}
                  aria-label={`Delete collaboration with ${collab.brand?.name || 'brand'}`}
                  title="Remove collaboration"
                >{deleting === collab.id ? '...' : '\u00d7'}</button>
              </article>
            ))}
          </div>
        )}

        {filtered.length > 0 && view === 'board' && (
          <div className="kanban-scroll">
            <div className="pipeline-phase-tabs">
              {PHASES.map(([value, label, stages]) => (
                <button type="button" className={phase === value ? 'active' : ''} key={value} onClick={() => changePhase(value)}>
                  <span>{label}</span><em>{filtered.filter((item) => stages.includes(item.status)).length}</em>
                </button>
              ))}
            </div>
            <div className="kanban-board">
              {STAGES.filter(([stage]) => visibleBoardStages.includes(stage)).map(([stage, label]) => {
                const cards = filtered.filter((collab) => collab.status === stage)
                return (
                  <section
                    className={`kanban-column${dropStage === stage ? ' drag-over' : ''}`}
                    key={stage}
                    onDragOver={(event) => {
                      event.preventDefault()
                      setDropStage(stage)
                    }}
                    onDragLeave={(event) => {
                      if (!event.currentTarget.contains(event.relatedTarget)) setDropStage(null)
                    }}
                    onDrop={(event) => {
                      event.preventDefault()
                      dropCollab(stage)
                    }}
                  >
                    <header>
                      <span className={`stage-dot stage-${stage}`} />
                      <strong>{label}</strong>
                      <em>{cards.length}</em>
                    </header>
                    <div className="kanban-cards">
                      {cards.map((collab) => (
                        <article
                          className={`kanban-card${draggedId === collab.id ? ' dragging' : ''}`}
                          draggable
                          key={collab.id}
                          onDragStart={(event) => {
                            setDraggedId(collab.id)
                            event.dataTransfer.effectAllowed = 'move'
                            event.dataTransfer.setData('text/plain', String(collab.id))
                          }}
                          onDragEnd={() => {
                            setDraggedId(null)
                            setDropStage(null)
                          }}
                          onClick={() => {
                            if (!draggedId) navigate(`/admin/collabs/${collab.id}`)
                          }}
                        >
                          <div className="kanban-card-top">
                            <div className="brand-avatar">{initials(collab.brand?.name || 'Brand')}</div>
                            <div className="kanban-card-actions">
                              <span className={`priority-dot priority-${collab.priority}`} title={`${collab.priority || 'normal'} priority`} />
                              <span>#{collab.id}</span>
                              <button className="kanban-archive-action" type="button" draggable="false" disabled={archiving === collab.id} onMouseDown={(event) => event.stopPropagation()} onClick={(event) => {
                                event.stopPropagation()
                                toggleArchive(collab)
                              }}>{pipelineScope === 'archived' ? '↩' : '□'}</button>
                              <button
                                className="collab-delete-button"
                                type="button"
                                draggable="false"
                                disabled={deleting === collab.id}
                                onMouseDown={(event) => event.stopPropagation()}
                                onClick={(event) => {
                                  event.stopPropagation()
                                  deleteCollaboration(collab)
                                }}
                                aria-label={`Delete collaboration with ${collab.brand?.name || 'brand'}`}
                                title="Remove collaboration"
                              >{deleting === collab.id ? '...' : '\u00d7'}</button>
                            </div>
                          </div>
                          <strong>{collab.brand?.name || `Brand #${collab.brand_id}`}</strong>
                          <p>{collab.campaign_type || collab.deliverables || 'General collaboration'}</p>
                          <div className="kanban-command-row">
                            <span>{assigneeLabel(collab.assignee)}</span>
                            <span>{daysInStage(collab.stage_entered_at)}d in stage</span>
                          </div>
                          {collab.next_action && <div className="kanban-next-action"><b>Next</b>{collab.next_action}</div>}
                          <div className="kanban-record-flags">
                            <span className={collab.has_agreement ? 'complete' : ''}>{collab.has_agreement ? '✓' : '·'} Agreement</span>
                            <span className={collab.invoice_count ? 'complete' : ''}>{collab.invoice_count ? '✓' : '·'} Invoice</span>
                            {collab.waiting_on !== 'none' && <span className="waiting">Waiting: {assigneeLabel(collab.waiting_on)}</span>}
                          </div>
                          <div className="kanban-card-meta">
                            <span>{collab.budget ? money(collab.budget) : 'Budget not shared'}</span>
                            {collab.deadline && <time>{shortDate(collab.deadline)}</time>}
                          </div>
                          <select
                            value={collab.status}
                            disabled={updating === collab.id}
                            onClick={(event) => event.stopPropagation()}
                            onChange={(event) => updateStatus(collab.id, event.target.value)}
                            aria-label={`Move ${collab.brand?.name || 'collaboration'}`}
                          >
                            {STAGES.map(([value, stageLabel]) => <option key={value} value={value}>{stageLabel}</option>)}
                          </select>
                        </article>
                      ))}
                      {cards.length === 0 && <div className="kanban-empty">Drop a collaboration here</div>}
                    </div>
                  </section>
                )
              })}
            </div>
          </div>
        )}
      </section>

      {showCreate && createPortal(
        <div className="admin-modal-backdrop" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !creating) closeCreate()
        }}>
          <section className="admin-modal" role="dialog" aria-modal="true" aria-labelledby="create-collab-title">
            <header className="admin-modal-header">
              <div>
                <span className="eyebrow">Manager entry</span>
                <h2 id="create-collab-title">Add collaboration</h2>
                <p>Add partnerships received through email, WhatsApp, calls, or referrals.</p>
              </div>
              <button type="button" onClick={closeCreate} disabled={creating} aria-label="Close modal">×</button>
            </header>

            <form className="admin-modal-form" onSubmit={createCollaboration}>
              <div className="admin-form-section">
                <div className="admin-form-section-title"><span>01</span><strong>Brand</strong></div>
                <SegmentedControl
                  value={brandMode}
                  onChange={setBrandMode}
                  label="Brand type"
                  options={[
                    { value: 'existing', label: 'Existing brand' },
                    { value: 'new', label: 'New brand' },
                  ]}
                />

                {brandMode === 'existing' ? (
                  <FormField label="Choose brand" required>
                    <select value={createForm.brand_id} onChange={(event) => patchCreate('brand_id', event.target.value)} required>
                      <option value="">Select an existing brand...</option>
                      {brandOptions.map((brand) => <option value={brand.id} key={brand.id}>{brand.name}</option>)}
                    </select>
                  </FormField>
                ) : (
                  <div className="admin-form-grid two">
                    <FormField label="Brand name" required>
                      <input value={createForm.brand_name} onChange={(event) => patchCreate('brand_name', event.target.value)} required />
                    </FormField>
                    <FormField label="Contact person">
                      <input value={createForm.contact_person} onChange={(event) => patchCreate('contact_person', event.target.value)} />
                    </FormField>
                    <FormField label="Email">
                      <input type="email" value={createForm.email} onChange={(event) => patchCreate('email', event.target.value)} />
                    </FormField>
                    <FormField label="Phone / WhatsApp">
                      <input value={createForm.phone} onChange={(event) => patchCreate('phone', event.target.value)} />
                    </FormField>
                  </div>
                )}
              </div>

              <div className="admin-form-section">
                <div className="admin-form-section-title"><span>02</span><strong>Campaign</strong></div>
                <div className="admin-form-grid two">
                  <FormField label="Campaign type">
                    <input value={createForm.campaign_type} onChange={(event) => patchCreate('campaign_type', event.target.value)} placeholder="e.g. Instagram Reel" />
                  </FormField>
                  <FormField label="Pipeline stage">
                    <select value={createForm.status} onChange={(event) => patchCreate('status', event.target.value)}>
                      {STAGES.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
                    </select>
                  </FormField>
                  <FormField label="Budget">
                    <input type="number" min="0" value={createForm.budget} onChange={(event) => patchCreate('budget', event.target.value)} placeholder="Amount in INR" />
                  </FormField>
                  <FormField label="Deadline">
                    <input type="date" value={createForm.deadline} onChange={(event) => patchCreate('deadline', event.target.value)} />
                  </FormField>
                  <FormField label="Priority">
                    <select value={createForm.priority} onChange={(event) => patchCreate('priority', event.target.value)}>
                      <option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option>
                    </select>
                  </FormField>
                  <FormField label="Assigned to">
                    <select value={createForm.assignee} onChange={(event) => patchCreate('assignee', event.target.value)}>
                      <option value="unassigned">Unassigned</option><option value="aarohi">Aarohi</option><option value="manager">Manager</option>
                    </select>
                  </FormField>
                </div>
                <FormField label="Next action">
                  <input value={createForm.next_action} onChange={(event) => patchCreate('next_action', event.target.value)} placeholder="e.g. Send revised commercial proposal" />
                </FormField>
                <FormField label="Deliverables">
                  <textarea rows="3" value={createForm.deliverables} onChange={(event) => patchCreate('deliverables', event.target.value)} placeholder="e.g. 1 Reel + 2 Stories" />
                </FormField>
                <FormField label="Brief">
                  <textarea rows="4" value={createForm.brief} onChange={(event) => patchCreate('brief', event.target.value)} />
                </FormField>
                <FormField label="Private manager notes">
                  <textarea rows="3" value={createForm.notes} onChange={(event) => patchCreate('notes', event.target.value)} />
                </FormField>
              </div>

              {createError && <Feedback tone="error" title="Could not add collaboration">{createError}</Feedback>}

              <footer className="admin-modal-actions">
                <Button type="button" variant="secondary" onClick={closeCreate} disabled={creating}>Cancel</Button>
                <Button type="submit" loading={creating} icon="+">{creating ? 'Adding collaboration' : 'Add collaboration'}</Button>
              </footer>
            </form>
          </section>
        </div>,
        document.body,
      )}
    </div>
  )
}

function MetricCard({ label, value, note, tone = '' }) {
  return (
    <article className={`metric-card ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  )
}

function initials(value) {
  return value.split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase()
}

function money(value) {
  return `₹${Number(value || 0).toLocaleString('en-IN')}`
}

function shortDate(value) {
  return new Date(value).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

function daysInStage(value) {
  if (!value) return 0
  return Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 86400000))
}

function assigneeLabel(value) {
  if (value === 'aarohi') return 'Aarohi'
  if (value === 'manager') return 'Manager'
  if (value === 'brand') return 'Brand'
  return 'Unassigned'
}
