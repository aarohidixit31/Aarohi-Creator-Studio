import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authFetch } from '../api.js'
import { Button } from '../components/ui.jsx'

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

  useEffect(() => {
    authFetch('/api/brands/directory')
      .then((response) => {
        if (!response.ok) throw new Error('Could not load your brand directory')
        return response.json()
      })
      .then(setBrands)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

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
        <Button to="/admin?new_collab=1" icon="+">Add collaboration</Button>
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

                <footer>
                  <span>{brand.email || brand.phone || 'No contact details'}</span>
                  <time>{relativeDate(brand.last_activity_at)}</time>
                </footer>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  )
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
