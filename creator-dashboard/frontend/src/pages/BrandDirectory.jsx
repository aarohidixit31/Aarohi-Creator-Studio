import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { authFetch } from '../api.js'
import { Button, Feedback, FormField } from '../components/ui.jsx'

const EMPTY_BRAND = { name: '', contact_person: '', email: '', phone: '', notes: '' }

const money = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

export default function BrandDirectory() {
  const navigate = useNavigate()
  const [brands, setBrands] = useState([])
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showImport, setShowImport] = useState(false)
  const [importFile, setImportFile] = useState(null)
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState(null)
  const [showAddBrand, setShowAddBrand] = useState(false)
  const [brandForm, setBrandForm] = useState(EMPTY_BRAND)
  const [savingBrand, setSavingBrand] = useState(false)

  function loadBrands() {
    authFetch('/api/brands/directory')
      .then((response) => {
        if (!response.ok) throw new Error('Could not load your brand directory')
        return response.json()
      })
      .then(setBrands)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(loadBrands, [])

  useEffect(() => {
    if (!showImport && !showAddBrand) return undefined
    document.body.classList.add('modal-open')
    return () => document.body.classList.remove('modal-open')
  }, [showImport, showAddBrand])

  async function addBrand(event) {
    event.preventDefault()
    setSavingBrand(true)
    setError('')
    try {
      const response = await authFetch('/api/brands/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(Object.fromEntries(Object.entries(brandForm).map(([key, value]) => [key, value.trim() || null]))),
      })
      const data = await response.json().catch(() => null)
      if (!response.ok) throw new Error(data?.detail || 'Could not save brand')
      setShowAddBrand(false)
      setBrandForm(EMPTY_BRAND)
      setLoading(true)
      loadBrands()
      navigate(`/admin/brands/${data.id}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setSavingBrand(false)
    }
  }

  async function importHistory(event) {
    event.preventDefault()
    if (!importFile) return
    setImporting(true)
    setError('')
    try {
      const body = new FormData()
      body.append('file', importFile)
      const response = await authFetch('/api/brands/import-history', { method: 'POST', body })
      const data = await response.json().catch(() => null)
      if (!response.ok) throw new Error(data?.detail || 'Could not import collaboration history')
      setImportResult(data)
      setLoading(true)
      loadBrands()
    } catch (err) {
      setError(err.message)
    } finally {
      setImporting(false)
    }
  }

  function downloadTemplate() {
    const csv = [
      'source_id,brand_name,contact_person,email,phone,campaign_type,status,budget,deadline,deliverables,content_link,created_at,brand_notes,notes,priority,assignee,next_action,show_on_media_kit,media_kit_summary,media_kit_image_url,media_kit_logo_url',
      'notion-2025,Notion,Maya Singh,maya@notion.com,+91 98765 43210,Instagram Reel,Payment Received,25000,2025-06-15,1 Reel + 2 Stories,https://instagram.com/reel/example,2025-05-01,Repeat partner,Campaign completed successfully,normal,manager,,yes,Productivity campaign for students,https://example.com/campaign.jpg,https://example.com/logo.png',
    ].join('\n')
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = 'aarohi-collaboration-history-template.csv'
    link.click()
    URL.revokeObjectURL(url)
  }

  function closeImport() {
    if (importing) return
    setShowImport(false)
    setImportFile(null)
    setImportResult(null)
  }

  const totals = useMemo(() => ({
    brands: brands.length,
    repeat: brands.filter((brand) => brand.collaboration_count > 1).length,
    active: brands.filter((brand) => brand.active_collaboration_count > 0).length,
    received: brands.reduce((sum, brand) => sum + brand.total_received, 0),
  }), [brands])

  const visibleBrands = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return brands.filter((brand) => {
      const matchesFilter = filter === 'all'
        || (filter === 'active' && brand.active_collaboration_count > 0)
        || (filter === 'repeat' && brand.collaboration_count > 1)
        || (filter === 'outstanding' && brand.outstanding_amount > 0)
      const searchable = [
        brand.name, brand.contact_person, brand.email, brand.phone, brand.notes,
      ].filter(Boolean).join(' ').toLowerCase()
      return matchesFilter && (!needle || searchable.includes(needle))
    })
  }, [brands, filter, query])

  return (
    <div className="admin-page brand-directory-page">
      <header className="admin-page-header">
        <div>
          <span className="eyebrow">Relationship desk</span>
          <h1>Brand CRM</h1>
          <p>Every contact, collaboration, invoice, and relationship in one place.</p>
        </div>
        <div className="header-actions">
          <Button size="sm" variant="secondary" onClick={() => setShowImport(true)}>Import CSV</Button>
          <Button size="sm" variant="secondary" onClick={() => setShowAddBrand(true)}>Add brand</Button>
          <Button size="sm" to="/admin?new_collab=1" icon="+">Add collaboration</Button>
        </div>
      </header>

      <section className="brand-metric-grid" aria-label="Brand relationship summary">
        <Metric label="Brand partners" value={totals.brands} note="All contacts" tone="blue" />
        <Metric label="Active relationships" value={totals.active} note="In your pipeline" tone="yellow" />
        <Metric label="Repeat partners" value={totals.repeat} note="2+ collaborations" />
        <Metric label="Revenue received" value={money.format(totals.received)} note="From all brands" />
      </section>

      <section className="brand-directory-panel">
        <div className="brand-directory-toolbar">
          <div className="brand-filter-tabs" role="tablist" aria-label="Filter brands">
            {[
              ['all', 'All'],
              ['active', 'Active'],
              ['repeat', 'Repeat'],
              ['outstanding', 'Payment due'],
            ].map(([value, label]) => (
              <button
                type="button"
                key={value}
                className={filter === value ? 'active' : ''}
                onClick={() => setFilter(value)}
              >
                {label}
              </button>
            ))}
          </div>
          <label className="brand-search">
            <span className="sr-only">Search brands</span>
            <i aria-hidden="true" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search brand, contact, email..."
            />
          </label>
        </div>

        {error && <div className="admin-notice error">{error}</div>}

        {loading ? (
          <div className="brand-directory-empty">Loading brand relationships...</div>
        ) : visibleBrands.length === 0 ? (
          <div className="brand-directory-empty">
            <span>CRM</span>
            <h2>{brands.length ? 'No matching brands' : 'Your brand directory is ready'}</h2>
            <p>{brands.length ? 'Try another search or filter.' : 'Brands are added automatically from inquiries and manager entries.'}</p>
          </div>
        ) : (
          <div className="brand-card-grid">
            {visibleBrands.map((brand) => (
              <article
                className="brand-crm-card"
                key={brand.id}
                tabIndex="0"
                role="link"
                onClick={() => navigate(`/admin/brands/${brand.id}`)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') navigate(`/admin/brands/${brand.id}`)
                }}
              >
                <div className="brand-card-heading">
                  <div className="brand-avatar brand-avatar-large">{initials(brand.name)}</div>
                  <div>
                    <h2>{brand.name}</h2>
                    <p>{brand.contact_person || 'Contact not added'}</p>
                  </div>
                  <span className="brand-card-arrow" aria-hidden="true">↗</span>
                </div>

                <div className="brand-health-row">
                  {brand.active_collaboration_count > 0
                    ? <span className="brand-health active"><i />Active partner</span>
                    : <span className="brand-health"><i />In directory</span>}
                  {brand.collaboration_count > 1 && <span className="repeat-chip">Repeat ×{brand.collaboration_count}</span>}
                </div>

                <div className="brand-card-stats">
                  <div><span>Collabs</span><strong>{brand.collaboration_count}</strong></div>
                  <div><span>Invoiced</span><strong>{money.format(brand.total_invoiced)}</strong></div>
                  <div><span>Received</span><strong>{money.format(brand.total_received)}</strong></div>
                </div>

                <footer className="brand-card-footer">
                  <span>{brand.email || brand.phone || 'No contact details'}</span>
                  <div>
                    <button type="button" onClick={(event) => {
                      event.stopPropagation()
                      navigate(`/admin?new_collab=1&brand_id=${brand.id}`)
                    }}>+ Collab</button>
                    <time>{relativeDate(brand.last_activity_at)}</time>
                  </div>
                </footer>
              </article>
            ))}
          </div>
        )}
      </section>

      {showImport && createPortal(
        <div className="admin-modal-backdrop" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget) closeImport()
        }}>
          <section className="admin-modal history-import-modal" role="dialog" aria-modal="true" aria-labelledby="history-import-title">
            <header className="admin-modal-header">
              <div>
                <span className="eyebrow">Historical records</span>
                <h2 id="history-import-title">Import brands & collaborations</h2>
                <p>One row creates or reuses a brand and adds its collaboration record.</p>
              </div>
              <button type="button" onClick={closeImport} disabled={importing} aria-label="Close import">×</button>
            </header>

            <form className="admin-modal-form" onSubmit={importHistory}>
              <div className="admin-form-section history-import-intro">
                <div className="admin-form-section-title"><span>01</span><strong>Prepare your sheet</strong></div>
                <p><code>brand_name</code> is required. Set <code>show_on_media_kit</code> to <code>yes</code> and the row will also be added to the Media Kit draft with its link, summary and images.</p>
                <Button type="button" size="sm" variant="secondary" onClick={downloadTemplate}>Download CSV template</Button>
              </div>

              <div className="admin-form-section">
                <div className="admin-form-section-title"><span>02</span><strong>Choose CSV file</strong></div>
                <label className="history-file-picker">
                  <input type="file" accept=".csv,text/csv" onChange={(event) => {
                    setImportFile(event.target.files?.[0] || null)
                    setImportResult(null)
                  }} />
                  <span>{importFile ? importFile.name : 'Select collaboration history CSV'}</span>
                  <small>Maximum 2 MB · UTF-8 CSV</small>
                </label>
              </div>

              {importResult && (
                <div className="admin-form-section history-import-result">
                  <Feedback tone={importResult.rows_failed ? 'info' : 'success'} title="Import complete">
                    {importResult.collabs_created} collaborations added and {importResult.duplicates_skipped} duplicates safely skipped.
                  </Feedback>
                  <div className="history-result-grid">
                    <Result label="Brands created" value={importResult.brands_created} />
                    <Result label="Brands reused" value={importResult.brands_reused} />
                    <Result label="Collabs added" value={importResult.collabs_created} />
                    <Result label="Media-kit entries" value={importResult.media_kit_added || 0} />
                    <Result label="Rows needing fixes" value={importResult.rows_failed} />
                  </div>
                  {importResult.errors?.length > 0 && (
                    <div className="history-import-errors">
                      {importResult.errors.map((item) => <p key={`${item.row}-${item.message}`}><strong>Row {item.row}</strong>{item.message}</p>)}
                    </div>
                  )}
                </div>
              )}

              <footer className="admin-modal-actions">
                <Button type="button" variant="secondary" onClick={closeImport} disabled={importing}>{importResult ? 'Done' : 'Cancel'}</Button>
                {!importResult && <Button type="submit" loading={importing} disabled={!importFile}>Import history</Button>}
              </footer>
            </form>
          </section>
        </div>,
        document.body,
      )}

      {showAddBrand && createPortal(
        <div className="admin-modal-backdrop" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !savingBrand) setShowAddBrand(false)
        }}>
          <section className="admin-modal quick-brand-modal" role="dialog" aria-modal="true" aria-labelledby="quick-brand-title">
            <header className="admin-modal-header">
              <div>
                <span className="eyebrow">Relationship desk</span>
                <h2 id="quick-brand-title">Add a brand</h2>
                <p>Save the contact once, then reuse it in collaborations, invoices and content records.</p>
              </div>
              <button type="button" onClick={() => setShowAddBrand(false)} disabled={savingBrand} aria-label="Close add brand">×</button>
            </header>
            <form className="admin-modal-form" onSubmit={addBrand}>
              <div className="admin-form-section">
                <div className="admin-form-grid two">
                  <FormField label="Brand name" required><input required value={brandForm.name} onChange={(event) => setBrandForm({ ...brandForm, name: event.target.value })} /></FormField>
                  <FormField label="Contact person"><input value={brandForm.contact_person} onChange={(event) => setBrandForm({ ...brandForm, contact_person: event.target.value })} /></FormField>
                  <FormField label="Work email"><input type="email" value={brandForm.email} onChange={(event) => setBrandForm({ ...brandForm, email: event.target.value })} /></FormField>
                  <FormField label="Phone / WhatsApp"><input value={brandForm.phone} onChange={(event) => setBrandForm({ ...brandForm, phone: event.target.value })} /></FormField>
                </div>
                <FormField label="Private relationship notes"><textarea rows="4" value={brandForm.notes} onChange={(event) => setBrandForm({ ...brandForm, notes: event.target.value })} placeholder="Past conversations, preferences, negotiation context..." /></FormField>
              </div>
              <footer className="admin-modal-actions">
                <Button type="button" variant="secondary" onClick={() => setShowAddBrand(false)} disabled={savingBrand}>Cancel</Button>
                <Button type="submit" loading={savingBrand}>Save brand</Button>
              </footer>
            </form>
          </section>
        </div>,
        document.body,
      )}
    </div>
  )
}

function Result({ label, value }) {
  return <div><span>{label}</span><strong>{value}</strong></div>
}

function Metric({ label, value, note, tone = '' }) {
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

function relativeDate(value) {
  if (!value) return 'No activity yet'
  const days = Math.floor((Date.now() - new Date(value).getTime()) / 86400000)
  if (days <= 0) return 'Active today'
  if (days === 1) return 'Active yesterday'
  if (days < 30) return `Active ${days} days ago`
  return `Active ${new Date(value).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' })}`
}
