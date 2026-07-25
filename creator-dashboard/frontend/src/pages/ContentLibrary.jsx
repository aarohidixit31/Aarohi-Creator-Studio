import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { API, authFetch } from '../api.js'
import { Button, Feedback, FormField } from '../components/ui.jsx'

const PLATFORMS = ['Instagram', 'YouTube', 'LinkedIn', 'Other']
const EMPTY_METRICS = { views: '', reach: '', likes: '', comments: '', saves: '', shares: '', conversions: '', engagement_rate: '' }
const EMPTY_FORM = {
  brand_id: '',
  collab_id: '',
  platform: 'Instagram',
  title: '',
  content_url: '',
  thumbnail_url: '',
  published_at: '',
  objective: '',
  results: '',
  notes: '',
  metrics: { ...EMPTY_METRICS },
  featured: false,
}

export default function ContentLibrary() {
  const [items, setItems] = useState([])
  const [summary, setSummary] = useState(null)
  const [brands, setBrands] = useState([])
  const [collabs, setCollabs] = useState([])
  const [query, setQuery] = useState('')
  const [platform, setPlatform] = useState('all')
  const [featuredOnly, setFeaturedOnly] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [formError, setFormError] = useState('')

  async function load() {
    setError('')
    try {
      const [itemsResponse, summaryResponse, brandsResponse, collabsResponse] = await Promise.all([
        authFetch('/api/content/'),
        authFetch('/api/content/summary'),
        authFetch('/api/brands/'),
        authFetch('/api/collabs/'),
      ])
      if (!itemsResponse.ok || !summaryResponse.ok) throw new Error('Could not load the content library')
      const [itemData, summaryData] = await Promise.all([itemsResponse.json(), summaryResponse.json()])
      setItems(itemData)
      setSummary(summaryData)
      if (brandsResponse.ok) setBrands(await brandsResponse.json())
      if (collabsResponse.ok) setCollabs(await collabsResponse.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  useEffect(() => {
    if (!showForm) return undefined
    document.body.classList.add('modal-open')
    const closeOnEscape = (event) => {
      if (event.key === 'Escape' && !saving) closeForm()
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => {
      document.body.classList.remove('modal-open')
      window.removeEventListener('keydown', closeOnEscape)
    }
  }, [showForm, saving])

  const visibleItems = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return items.filter((item) => {
      const matchesPlatform = platform === 'all' || item.platform === platform
      const matchesFeatured = !featuredOnly || item.featured
      const searchable = [
        item.title, item.platform, item.brand?.name, item.collab_label,
        item.objective, item.results,
      ].filter(Boolean).join(' ').toLowerCase()
      return matchesPlatform && matchesFeatured && (!needle || searchable.includes(needle))
    })
  }, [featuredOnly, items, platform, query])

  const availableCollabs = useMemo(() => (
    form.brand_id
      ? collabs.filter((collab) => String(collab.brand_id) === String(form.brand_id))
      : collabs
  ), [collabs, form.brand_id])

  function openCreate() {
    setEditingId(null)
    setForm({ ...EMPTY_FORM, metrics: { ...EMPTY_METRICS } })
    setFormError('')
    setShowForm(true)
  }

  function openEdit(item) {
    setEditingId(item.id)
    setForm({
      brand_id: item.brand_id ? String(item.brand_id) : '',
      collab_id: item.collab_id ? String(item.collab_id) : '',
      platform: item.platform,
      title: item.title || '',
      content_url: item.content_url || '',
      thumbnail_url: item.thumbnail_url || '',
      published_at: dateInput(item.published_at),
      objective: item.objective || '',
      results: item.results || '',
      notes: item.notes || '',
      metrics: { ...EMPTY_METRICS, ...(item.metrics || {}) },
      featured: Boolean(item.featured),
    })
    setFormError('')
    setShowForm(true)
  }

  function closeForm() {
    setShowForm(false)
    setEditingId(null)
    setFormError('')
  }

  function patch(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function patchMetric(field, value) {
    setForm((current) => ({ ...current, metrics: { ...current.metrics, [field]: value } }))
  }

  async function uploadThumbnail(event) {
    const file = event.target.files?.[0]
    if (!file) return
    setUploading(true)
    setFormError('')
    try {
      const body = new FormData()
      body.append('file', file)
      const response = await authFetch('/api/media-kit/upload', { method: 'POST', body })
      if (!response.ok) {
        const detail = await response.json().catch(() => null)
        throw new Error(detail?.detail || 'Could not upload thumbnail')
      }
      patch('thumbnail_url', (await response.json()).url)
    } catch (err) {
      setFormError(err.message)
    } finally {
      setUploading(false)
      event.target.value = ''
    }
  }

  async function saveContent(event) {
    event.preventDefault()
    setSaving(true)
    setFormError('')
    try {
      const response = await authFetch(editingId ? `/api/content/${editingId}` : '/api/content/', {
        method: editingId ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(toPayload(form)),
      })
      if (!response.ok) {
        const detail = await response.json().catch(() => null)
        throw new Error(detail?.detail || 'Could not save content')
      }
      closeForm()
      await load()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function toggleFeatured(item) {
    setError('')
    try {
      const response = await authFetch(`/api/content/${item.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ featured: !item.featured }),
      })
      if (!response.ok) throw new Error('Could not update case-study visibility')
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  async function removeContent(item) {
    if (!window.confirm(`Delete “${item.title}” from the content library?`)) return
    setError('')
    try {
      const response = await authFetch(`/api/content/${item.id}`, { method: 'DELETE' })
      if (!response.ok) throw new Error('Could not delete content')
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="admin-page content-library-page">
      <header className="admin-page-header">
        <div>
          <span className="eyebrow">Content intelligence</span>
          <h1>Content & case studies</h1>
          <p>Build a searchable performance history and turn your strongest work into brand proof.</p>
        </div>
        <Button icon="+" onClick={openCreate}>Add published content</Button>
      </header>

      <section className="content-summary-grid">
        <SummaryCard label="Published content" value={summary?.content_count || 0} note="Saved performance records" tone="blue" />
        <SummaryCard label="Total views" value={compactNumber(summary?.total_views)} note="Across tracked content" />
        <SummaryCard label="Total reach" value={compactNumber(summary?.total_reach)} note="Recorded audience reach" />
        <SummaryCard label="Average engagement" value={`${Number(summary?.average_engagement_rate || 0).toFixed(1)}%`} note={`${summary?.featured_count || 0} public case studies`} tone="yellow" />
      </section>

      <section className="content-library-panel">
        <div className="content-library-toolbar">
          <div className="content-platform-tabs">
            {['all', ...PLATFORMS].map((value) => (
              <button type="button" key={value} className={platform === value ? 'active' : ''} onClick={() => setPlatform(value)}>
                {value === 'all' ? 'All platforms' : value}
              </button>
            ))}
          </div>
          <div className="content-toolbar-right">
            <label className="content-featured-filter">
              <input type="checkbox" checked={featuredOnly} onChange={(event) => setFeaturedOnly(event.target.checked)} />
              Public case studies
            </label>
            <label className="content-search">
              <span className="sr-only">Search content</span>
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search title, brand, campaign..." />
            </label>
          </div>
        </div>

        {error && <div className="admin-notice error">{error}</div>}

        {loading ? (
          <div className="content-empty">Loading your content history...</div>
        ) : visibleItems.length === 0 ? (
          <div className="content-empty">
            <span>▶</span>
            <h2>{items.length ? 'No matching content' : 'Build your performance library'}</h2>
            <p>{items.length ? 'Try another platform or search.' : 'Add published work once, then reuse the proof in future pitches and case studies.'}</p>
            {!items.length && <Button variant="secondary" onClick={openCreate}>Add first content</Button>}
          </div>
        ) : (
          <div className="content-card-grid">
            {visibleItems.map((item) => (
              <article className="content-record-card" key={item.id}>
                <div className="content-record-media">
                  {item.thumbnail_url
                    ? <img src={mediaUrl(item.thumbnail_url)} alt="" />
                    : <div className={`content-thumbnail-placeholder platform-${item.platform.toLowerCase()}`}><span>{platformCode(item.platform)}</span></div>}
                  <span className={`content-platform-badge platform-${item.platform.toLowerCase()}`}>{item.platform}</span>
                  <button className={`case-study-toggle${item.featured ? ' active' : ''}`} type="button" onClick={() => toggleFeatured(item)}>
                    <span>★</span>{item.featured ? 'Published case study' : 'Feature publicly'}
                  </button>
                </div>
                <div className="content-record-body">
                  <div className="content-record-heading">
                    <div>
                      <span>{item.brand?.name || item.collab_label || 'Independent content'}</span>
                      <h2>{item.title}</h2>
                    </div>
                    <button type="button" onClick={() => openEdit(item)} aria-label={`Edit ${item.title}`}>•••</button>
                  </div>
                  <div className="content-performance-row">
                    <Metric label="Views" value={compactNumber(item.metrics?.views)} />
                    <Metric label="Reach" value={compactNumber(item.metrics?.reach)} />
                    {item.metrics?.conversions != null && <Metric label="Conv." value={compactNumber(item.metrics.conversions)} />}
                    <Metric label="Eng." value={item.metrics?.engagement_rate != null ? `${item.metrics.engagement_rate}%` : '—'} />
                  </div>
                  <div className="content-record-result">
                    <span>Result</span>
                    <p>{item.results || item.objective || 'Add the campaign result to make this record pitch-ready.'}</p>
                  </div>
                  <footer>
                    <time>{item.published_at ? formatDate(item.published_at) : 'Publish date not added'}</time>
                    <div>
                      {item.content_url && <a href={item.content_url} target="_blank" rel="noreferrer">View live ↗</a>}
                      <button type="button" onClick={() => removeContent(item)}>Delete</button>
                    </div>
                  </footer>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {showForm && createPortal(
        <div className="admin-modal-backdrop" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !saving) closeForm()
        }}>
          <section className="admin-modal content-editor-modal" role="dialog" aria-modal="true" aria-labelledby="content-editor-title">
            <header className="admin-modal-header">
              <div>
                <span className="eyebrow">{editingId ? 'Update performance' : 'Content record'}</span>
                <h2 id="content-editor-title">{editingId ? 'Edit published content' : 'Add published content'}</h2>
                <p>Capture the work, campaign context and performance once.</p>
              </div>
              <button type="button" onClick={closeForm} disabled={saving} aria-label="Close modal">×</button>
            </header>

            <form className="admin-modal-form content-editor-form" onSubmit={saveContent}>
              <div className="admin-form-section">
                <div className="admin-form-section-title"><span>01</span><strong>Content details</strong></div>
                <div className="admin-form-grid two">
                  <FormField label="Platform" required>
                    <select value={form.platform} onChange={(event) => patch('platform', event.target.value)}>
                      {PLATFORMS.map((item) => <option key={item}>{item}</option>)}
                    </select>
                  </FormField>
                  <FormField label="Publish date">
                    <input type="date" value={form.published_at} onChange={(event) => patch('published_at', event.target.value)} />
                  </FormField>
                </div>
                <FormField label="Content title" required>
                  <input required value={form.title} onChange={(event) => patch('title', event.target.value)} placeholder="e.g. 5 AI tools every student should know" />
                </FormField>
                <FormField label="Live content URL">
                  <input type="url" value={form.content_url} onChange={(event) => patch('content_url', event.target.value)} placeholder="https://instagram.com/..." />
                </FormField>
                <div className="content-thumbnail-field">
                  <span>Thumbnail</span>
                  <div>
                    {form.thumbnail_url
                      ? <img src={mediaUrl(form.thumbnail_url)} alt="Content thumbnail preview" />
                      : <span className="content-upload-placeholder">Upload a campaign cover or post thumbnail</span>}
                    <label className="small-button">
                      {uploading ? 'Uploading...' : 'Upload image'}
                      <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={uploadThumbnail} disabled={uploading} />
                    </label>
                    {form.thumbnail_url && <button className="text-button danger-text" type="button" onClick={() => patch('thumbnail_url', '')}>Remove</button>}
                  </div>
                </div>
              </div>

              <div className="admin-form-section">
                <div className="admin-form-section-title"><span>02</span><strong>Campaign relationship</strong></div>
                <div className="admin-form-grid two">
                  <FormField label="Brand">
                    <select value={form.brand_id} onChange={(event) => {
                      setForm((current) => ({ ...current, brand_id: event.target.value, collab_id: '' }))
                    }}>
                      <option value="">Independent content</option>
                      {brands.map((brand) => <option value={brand.id} key={brand.id}>{brand.name}</option>)}
                    </select>
                  </FormField>
                  <FormField label="Collaboration">
                    <select value={form.collab_id} onChange={(event) => {
                      const selected = collabs.find((collab) => String(collab.id) === event.target.value)
                      setForm((current) => ({
                        ...current,
                        collab_id: event.target.value,
                        brand_id: selected ? String(selected.brand_id) : current.brand_id,
                      }))
                    }}>
                      <option value="">Not linked to a campaign</option>
                      {availableCollabs.map((collab) => <option value={collab.id} key={collab.id}>{collab.brand?.name} — {collab.campaign_type || collab.deliverables || `Collab #${collab.id}`}</option>)}
                    </select>
                  </FormField>
                </div>
                <FormField label="Campaign objective">
                  <textarea rows="3" value={form.objective} onChange={(event) => patch('objective', event.target.value)} placeholder="What did the brand want this content to achieve?" />
                </FormField>
                <FormField label="Result / case-study summary">
                  <textarea rows="4" value={form.results} onChange={(event) => patch('results', event.target.value)} placeholder="Explain the outcome in a pitch-friendly way." />
                </FormField>
              </div>

              <div className="admin-form-section">
                <div className="admin-form-section-title"><span>03</span><strong>Performance snapshot</strong></div>
                <div className="content-metric-form-grid">
                  {[
                    ['views', 'Views'], ['reach', 'Reach'], ['likes', 'Likes'], ['comments', 'Comments'],
                    ['saves', 'Saves'], ['shares', 'Shares'], ['conversions', 'Conversions'], ['engagement_rate', 'Engagement %'],
                  ].map(([field, label]) => (
                    <FormField label={label} key={field}>
                      <input type="number" min="0" step={field === 'engagement_rate' ? '0.1' : '1'} value={form.metrics[field]} onChange={(event) => patchMetric(field, event.target.value)} />
                    </FormField>
                  ))}
                </div>
                <label className="content-feature-switch">
                  <input type="checkbox" checked={form.featured} onChange={(event) => patch('featured', event.target.checked)} />
                  <span><strong>Show as a public case study</strong><small>Selected content will automatically appear on your media kit.</small></span>
                </label>
                <FormField label="Private manager notes">
                  <textarea rows="3" value={form.notes} onChange={(event) => patch('notes', event.target.value)} />
                </FormField>
              </div>

              {formError && <Feedback tone="error" title="Could not save content">{formError}</Feedback>}
              <footer className="admin-modal-actions">
                <Button type="button" variant="secondary" onClick={closeForm} disabled={saving}>Cancel</Button>
                <Button type="submit" loading={saving}>{saving ? 'Saving content' : editingId ? 'Save changes' : 'Add to library'}</Button>
              </footer>
            </form>
          </section>
        </div>,
        document.body,
      )}
    </div>
  )
}

function SummaryCard({ label, value, note, tone = '' }) {
  return <article className={`metric-card ${tone}`}><span>{label}</span><strong>{value}</strong><small>{note}</small></article>
}

function Metric({ label, value }) {
  return <div><span>{label}</span><strong>{value || '—'}</strong></div>
}

function toPayload(form) {
  const metrics = {}
  Object.entries(form.metrics).forEach(([field, value]) => {
    metrics[field] = value === '' || value == null ? null : Number(value)
  })
  return {
    ...form,
    brand_id: form.brand_id ? Number(form.brand_id) : null,
    collab_id: form.collab_id ? Number(form.collab_id) : null,
    published_at: form.published_at ? new Date(`${form.published_at}T12:00:00`).toISOString() : null,
    content_url: form.content_url || null,
    thumbnail_url: form.thumbnail_url || null,
    objective: form.objective || null,
    results: form.results || null,
    notes: form.notes || null,
    metrics,
  }
}

function compactNumber(value) {
  const number = Number(value || 0)
  if (number >= 1000000) return `${(number / 1000000).toFixed(number >= 10000000 ? 0 : 1)}M`
  if (number >= 1000) return `${(number / 1000).toFixed(number >= 10000 ? 0 : 1)}K`
  return number.toLocaleString('en-IN')
}

function dateInput(value) {
  return value ? new Date(value).toISOString().slice(0, 10) : ''
}

function formatDate(value) {
  return new Date(value).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

function mediaUrl(url) {
  if (!url) return ''
  if (/^https?:\/\//i.test(url)) return url
  return `${API}${url}`
}

function platformCode(value) {
  if (value === 'Instagram') return 'IG'
  if (value === 'YouTube') return 'YT'
  if (value === 'LinkedIn') return 'IN'
  return 'WEB'
}
