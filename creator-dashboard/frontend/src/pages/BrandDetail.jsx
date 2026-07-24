import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { authFetch } from '../api.js'
import { Button, Feedback, FormField } from '../components/ui.jsx'

const money = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

const STAGE_LABELS = {
  new_inquiry: 'New inquiry',
  in_discussion: 'In discussion',
  negotiating: 'Negotiating',
  confirmed: 'Confirmed',
  content_live: 'Content live',
  invoiced: 'Invoiced',
  paid: 'Paid',
  closed: 'Closed',
}

export default function BrandDetail() {
  const { brandId } = useParams()
  const [brand, setBrand] = useState(null)
  const [form, setForm] = useState(null)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    authFetch(`/api/brands/${brandId}`)
      .then((response) => {
        if (!response.ok) throw new Error(response.status === 404 ? 'Brand not found' : 'Could not load this brand')
        return response.json()
      })
      .then((data) => {
        setBrand(data)
        setForm(editableFields(data))
      })
      .catch((err) => setError(err.message))
  }, [brandId])

  const averageDeal = useMemo(() => {
    if (!brand?.collaboration_count) return 0
    const budgetTotal = brand.collabs.reduce((sum, collab) => sum + Number(collab.budget || 0), 0)
    return budgetTotal / brand.collaboration_count
  }, [brand])

  async function saveBrand(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setSaved(false)
    try {
      const response = await authFetch(`/api/brands/${brandId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...form,
          contact_person: form.contact_person.trim() || null,
          email: form.email.trim() || null,
          phone: form.phone.trim() || null,
          notes: form.notes.trim() || null,
        }),
      })
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(body?.detail || 'Could not save brand details')
      }
      const updated = await response.json()
      setBrand((current) => ({ ...current, ...updated }))
      setForm(editableFields(updated))
      setEditing(false)
      setSaved(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (!brand) {
    return (
      <div className="admin-page brand-profile-page">
        <Link className="brand-back-link" to="/admin/brands">← Brand CRM</Link>
        {error ? <Feedback tone="error" title="Could not open profile">{error}</Feedback> : <div className="admin-loading"><span className="loading-dot" />Loading brand profile...</div>}
      </div>
    )
  }

  return (
    <div className="admin-page brand-profile-page">
      <Link className="brand-back-link" to="/admin/brands">← Brand CRM</Link>

      <header className="brand-profile-header">
        <div className="brand-avatar brand-profile-avatar">{initials(brand.name)}</div>
        <div className="brand-profile-title">
          <span className="eyebrow">Brand relationship</span>
          <h1>{brand.name}</h1>
          <p>{brand.contact_person || 'No contact person'}{brand.email ? ` · ${brand.email}` : ''}</p>
        </div>
        <div className="header-actions">
          <Button variant="secondary" onClick={() => setEditing((current) => !current)}>
            {editing ? 'Cancel editing' : 'Edit profile'}
          </Button>
          <Button to={`/admin?new_collab=1&brand_id=${brand.id}`} icon="+">Start collaboration</Button>
        </div>
      </header>

      {saved && <Feedback tone="success" title="Brand profile saved">The latest contact details and notes are now available to your manager.</Feedback>}
      {error && <Feedback tone="error" title="Something went wrong">{error}</Feedback>}

      <section className="brand-profile-metrics">
        <article><span>Total collaborations</span><strong>{brand.collaboration_count}</strong><small>{brand.active_collaboration_count} currently active</small></article>
        <article><span>Total invoiced</span><strong>{money.format(brand.total_invoiced)}</strong><small>{brand.invoice_count} invoices</small></article>
        <article><span>Revenue received</span><strong>{money.format(brand.total_received)}</strong><small>{brand.outstanding_amount ? `${money.format(brand.outstanding_amount)} pending` : 'Nothing pending'}</small></article>
        <article><span>Average collab budget</span><strong>{money.format(averageDeal)}</strong><small>Based on shared budgets</small></article>
      </section>

      <div className="brand-profile-layout">
        <aside className="brand-profile-sidebar">
          <section className="brand-profile-card">
            <div className="brand-profile-card-heading">
              <div><span className="summary-kicker">Contact card</span><h2>Brand details</h2></div>
            </div>
            {editing ? (
              <form className="brand-edit-form" onSubmit={saveBrand}>
                <FormField label="Brand name" required>
                  <input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
                </FormField>
                <FormField label="Contact person">
                  <input value={form.contact_person} onChange={(event) => setForm({ ...form, contact_person: event.target.value })} />
                </FormField>
                <FormField label="Work email">
                  <input type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
                </FormField>
                <FormField label="Phone / WhatsApp">
                  <input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} />
                </FormField>
                <FormField label="Private relationship notes">
                  <textarea rows="6" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} placeholder="Preferences, negotiation history, follow-up context..." />
                </FormField>
                <Button type="submit" loading={saving}>{saving ? 'Saving profile' : 'Save changes'}</Button>
              </form>
            ) : (
              <>
                <dl className="brand-contact-list">
                  <div><dt>Contact</dt><dd>{brand.contact_person || 'Not added'}</dd></div>
                  <div><dt>Email</dt><dd>{brand.email ? <a href={`mailto:${brand.email}`}>{brand.email}</a> : 'Not added'}</dd></div>
                  <div><dt>Phone</dt><dd>{brand.phone ? <a href={`tel:${brand.phone}`}>{brand.phone}</a> : 'Not added'}</dd></div>
                  <div><dt>Partner since</dt><dd>{formatDate(brand.created_at)}</dd></div>
                </dl>
                <div className="brand-notes">
                  <span>Manager notes</span>
                  <p>{brand.notes || 'No relationship notes added yet.'}</p>
                </div>
              </>
            )}
          </section>
        </aside>

        <div className="brand-profile-main">
          <section className="brand-profile-card">
            <div className="brand-profile-card-heading">
              <div><span className="summary-kicker">Partnership history</span><h2>Collaborations</h2></div>
              <span className="record-count">{brand.collabs.length} records</span>
            </div>
            {brand.collabs.length ? (
              <div className="brand-history-list">
                {brand.collabs.map((collab) => (
                  <Link className="brand-history-row" to={`/admin/collabs/${collab.id}`} key={collab.id}>
                    <span className={`brand-history-status status-${collab.status}`} />
                    <div>
                      <strong>{collab.campaign_type || collab.deliverables || 'General collaboration'}</strong>
                      <p>{collab.deliverables || collab.brief || 'No scope added'}</p>
                    </div>
                    <div className="brand-history-budget">
                      <strong>{collab.budget ? money.format(collab.budget) : 'No budget'}</strong>
                      <span>{formatDate(collab.created_at)}</span>
                    </div>
                    <span className={`status-pill status-${collab.status}`}>{STAGE_LABELS[collab.status] || collab.status}</span>
                    <i aria-hidden="true">→</i>
                  </Link>
                ))}
              </div>
            ) : <EmptyRecord title="No collaborations yet" text="Start one from this profile and it will appear here." />}
          </section>

          <section className="brand-profile-card">
            <div className="brand-profile-card-heading">
              <div><span className="summary-kicker">Financial history</span><h2>Invoices</h2></div>
              <Button variant="ghost" size="sm" to={`/admin/invoices/new?brand_id=${brand.id}`}>Create invoice</Button>
            </div>
            {brand.invoices.length ? (
              <div className="brand-invoice-list">
                {brand.invoices.map((invoice) => (
                  <div className="brand-invoice-row" key={invoice.id}>
                    <div><strong>{invoice.invoice_number}</strong><span>{formatDate(invoice.created_at)}</span></div>
                    <strong>{money.format(invoice.total)}</strong>
                    <span className={`status-pill invoice-${invoice.status}`}>{invoice.status}</span>
                  </div>
                ))}
              </div>
            ) : <EmptyRecord title="No invoices yet" text="Invoices created for this brand will build its financial history." />}
          </section>
        </div>
      </div>
    </div>
  )
}

function EmptyRecord({ title, text }) {
  return <div className="brand-record-empty"><span>—</span><strong>{title}</strong><p>{text}</p></div>
}

function editableFields(brand) {
  return {
    name: brand.name || '',
    contact_person: brand.contact_person || '',
    email: brand.email || '',
    phone: brand.phone || '',
    notes: brand.notes || '',
  }
}

function initials(value) {
  return value.split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase()
}

function formatDate(value) {
  if (!value) return 'Not set'
  return new Intl.DateTimeFormat('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric',
  }).format(new Date(value))
}
