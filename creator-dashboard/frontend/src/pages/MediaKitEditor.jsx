import { useEffect, useMemo, useState } from 'react'
import { API, authFetch } from '../api.js'
import { FormField } from '../components/ui.jsx'

const EMPTY = {
  name: '',
  tagline: '',
  bio: '',
  location: '',
  contact_email: '',
  contact_phone: '',
  profile_image_url: '',
  cover_image_url: '',
  instagram_handle: '',
  youtube_handle: '',
  linkedin_handle: '',
  linkedin_followers: 0,
  linkedin_avg_impressions: 0,
  social_links: [],
  highlights: [],
  audience_insights: [],
  content_pillars: [],
  partner_reasons: [],
  rate_card: [],
  past_collabs: [],
  testimonials: [],
  gallery: [],
}

const STARTER = {
  name: 'Aarohi Dixit',
  tagline: 'Tech Content Creator | AI Tools | Productivity | Coding & Career Guidance',
  bio: "I'm Aarohi Dixit, a tech-focused content creator and Computer Science student helping students and early professionals simplify AI tools, productivity systems, coding concepts, and career growth. Through practical, relatable, and high-engagement content, I turn complex technology into actionable insights that help my audience learn faster and work smarter.",
  location: 'India',
  contact_email: 'aarohi.inframe@gmail.com',
  contact_phone: '+91 92175 30643',
  instagram_handle: 'aarohi.inframe',
  youtube_handle: '@aarohi.inframe',
  linkedin_handle: 'Aarohi Dixit',
  linkedin_followers: 3200,
  social_links: [
    { platform: 'Instagram', label: 'Instagram', handle: '@aarohi.inframe', url: 'https://instagram.com/aarohi.inframe', follower_count: 25360, secondary_stat: '2.7M+ recent views' },
    { platform: 'LinkedIn', label: 'LinkedIn', handle: 'Aarohi Dixit', url: 'https://www.linkedin.com/in/aarohi-dixit', follower_count: 3200, secondary_stat: 'Career-focused community' },
    { platform: 'YouTube', label: 'YouTube', handle: '@aarohi.inframe', url: 'https://youtube.com/@aarohi.inframe', follower_count: 350, secondary_stat: 'Growing' },
  ],
  highlights: [
    { label: 'Instagram views', value: '2.7M+', note: 'Recent performance' },
    { label: 'Interactions', value: '73K+', note: 'High-intent engagement' },
    { label: 'New followers', value: '5.1K+', note: 'Recent growth' },
    { label: 'Average reel reach', value: '10K+', note: 'Strong organic discovery' },
  ],
  audience_insights: [
    { label: 'Primary audience', value: 'Students, coding learners and early-career professionals' },
    { label: 'Top age group', value: '18-24 (72.5%)' },
    { label: 'Gender split', value: '52.3% women / 47.7% men' },
    { label: 'Top cities', value: 'Delhi, Bengaluru, Pune, Noida and Mumbai' },
  ],
  content_pillars: [
    'AI tools & real-world workflows',
    'Productivity systems for students',
    'Coding & DSA guidance',
    'Placement & career growth',
    'Tool and platform explainers',
  ],
  partner_reasons: [
    'Highly targeted 18-30 tech-focused audience',
    'Strong organic reach beyond the follower base',
    'Clear communication and professional workflow',
    'Native storytelling approach with quick turnaround',
  ],
  rate_card: [
    { deliverable: 'Instagram Reel', price: 8000, note: '' },
    { deliverable: 'Instagram Carousel Post', price: 4000, note: '' },
    { deliverable: 'Instagram Story (Link Integration)', price: 2000, note: '' },
    { deliverable: 'Reel + Story Package', price: 9000, note: '' },
    { deliverable: 'Instagram Reel + 30-day Meta Ads whitelisting', price: 10000, note: '' },
  ],
  past_collabs: [
    'GeeksforGeeks', 'Coding Ninjas', 'KPIT Sparkle', 'Chitkara University',
    'CareerRoadmap', 'Codeflix Labs', 'Code Monsters', 'SuperProfile',
    'Bits Pilani Hyderabad', 'E-cell IIT Ropar', 'upgrad',
  ].map((brand) => ({ brand, summary: '', logo_url: '', image_url: '', content_url: '' })),
}

export default function MediaKitEditor() {
  const [form, setForm] = useState(EMPTY)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [active, setActive] = useState('profile')

  useEffect(() => {
    fetch(`${API}/api/media-kit/`)
      .then((response) => {
        if (!response.ok) throw new Error('Could not load media kit')
        return response.json()
      })
      .then((data) => setForm(normalize(data)))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const completion = useMemo(() => {
    const checks = [
      form.name, form.tagline, form.bio, form.contact_email,
      form.social_links.length, form.highlights.length, form.rate_card.length,
      form.past_collabs.length, form.cover_image_url || form.profile_image_url,
    ]
    return Math.round((checks.filter(Boolean).length / checks.length) * 100)
  }, [form])

  function patch(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function patchItem(field, index, key, value) {
    patch(field, form[field].map((item, itemIndex) => (
      itemIndex === index ? { ...item, [key]: value } : item
    )))
  }

  function addItem(field, item) {
    patch(field, [...form[field], item])
  }

  function removeItem(field, index) {
    patch(field, form[field].filter((_, itemIndex) => itemIndex !== index))
  }

  function moveItem(field, index, direction) {
    const target = index + direction
    if (target < 0 || target >= form[field].length) return
    const next = [...form[field]]
    ;[next[index], next[target]] = [next[target], next[index]]
    patch(field, next)
  }

  function loadStarter() {
    setForm((current) => normalize({ ...current, ...STARTER }))
    setNotice('Starter content loaded. Review it, then click Save changes.')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function save() {
    setSaving(true)
    setError('')
    setNotice('')
    try {
      const response = await authFetch('/api/media-kit/', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(clean(form)),
      })
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(body?.detail || 'Could not save media kit')
      }
      setNotice('Media kit saved and published.')
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <AdminLoading label="Loading your media kit..." />

  return (
    <div className="admin-page">
      <header className="admin-page-header">
        <div>
          <div className="eyebrow">Public profile</div>
          <h1>Media kit studio</h1>
          <p>Manage everything brands see from one polished workspace.</p>
        </div>
        <div className="header-actions">
          <a className="button secondary" href="/" target="_blank" rel="noreferrer">Preview live ↗</a>
          <button className="button primary" onClick={save} disabled={saving}>
            {saving ? 'Saving...' : 'Save changes'}
          </button>
        </div>
      </header>

      {(notice || error) && (
        <div className={`admin-notice ${error ? 'error' : 'success'}`}>{error || notice}</div>
      )}

      <div className="media-editor-summary">
        <div>
          <span className="summary-kicker">Profile strength</span>
          <strong>{completion}% complete</strong>
        </div>
        <div className="completion-track"><span style={{ width: `${completion}%` }} /></div>
        <button className="text-button" onClick={loadStarter}>Load content from current PDF kit</button>
      </div>

      <div className="media-editor-layout">
        <nav className="editor-tabs" aria-label="Media kit sections">
          {[
            ['profile', 'Profile & contact'],
            ['social', 'Social presence'],
            ['proof', 'Performance proof'],
            ['services', 'Services & rates'],
            ['collabs', 'Past collaborations'],
            ['testimonials', 'Testimonials'],
            ['gallery', 'Photos & gallery'],
          ].map(([id, label]) => (
            <button key={id} className={active === id ? 'active' : ''} onClick={() => setActive(id)}>
              {label}
            </button>
          ))}
        </nav>

        <div className="editor-panel">
          {active === 'profile' && (
            <EditorSection title="Profile & contact" description="Your public positioning and the fastest way for brands to reach you.">
              <div className="editor-grid two">
                <Field label="Name"><input value={form.name} onChange={(e) => patch('name', e.target.value)} /></Field>
                <Field label="Location"><input value={form.location} onChange={(e) => patch('location', e.target.value)} /></Field>
              </div>
              <Field label="Professional tagline" hint="Keep it specific and searchable.">
                <input value={form.tagline} onChange={(e) => patch('tagline', e.target.value)} />
              </Field>
              <Field label="About you">
                <textarea rows="7" value={form.bio} onChange={(e) => patch('bio', e.target.value)} />
              </Field>
              <div className="editor-grid two">
                <Field label="Contact email"><input type="email" value={form.contact_email || ''} onChange={(e) => patch('contact_email', e.target.value)} /></Field>
                <Field label="Contact phone"><input value={form.contact_phone || ''} onChange={(e) => patch('contact_phone', e.target.value)} /></Field>
              </div>
              <div className="editor-grid two">
                <ImageField label="Profile photo" value={form.profile_image_url} onChange={(url) => patch('profile_image_url', url)} />
                <ImageField label="Cover/banner image" value={form.cover_image_url} onChange={(url) => patch('cover_image_url', url)} wide />
              </div>
              <StringList
                title="Content pillars"
                items={form.content_pillars}
                placeholder="e.g. AI tools & workflows"
                onChange={(items) => patch('content_pillars', items)}
              />
            </EditorSection>
          )}

          {active === 'social' && (
            <EditorSection title="Social presence" description="Add direct profile links, handles and manager-updatable audience numbers.">
              <div className="editor-grid three">
                <Field label="Instagram handle"><input value={form.instagram_handle} onChange={(e) => patch('instagram_handle', e.target.value)} /></Field>
                <Field label="YouTube handle"><input value={form.youtube_handle} onChange={(e) => patch('youtube_handle', e.target.value)} /></Field>
                <Field label="LinkedIn name/handle"><input value={form.linkedin_handle} onChange={(e) => patch('linkedin_handle', e.target.value)} /></Field>
              </div>
              <RepeatList
                title="Public social cards"
                items={form.social_links}
                onAdd={() => addItem('social_links', { platform: 'Instagram', label: '', handle: '', url: '', follower_count: '', secondary_stat: '' })}
                onRemove={(index) => removeItem('social_links', index)}
                onMove={(index, direction) => moveItem('social_links', index, direction)}
                render={(item, index) => (
                  <div className="editor-grid two">
                    <Field label="Platform">
                      <select value={item.platform} onChange={(e) => patchItem('social_links', index, 'platform', e.target.value)}>
                        <option>Instagram</option><option>YouTube</option><option>LinkedIn</option><option>Other</option>
                      </select>
                    </Field>
                    <Field label="Display label"><input value={item.label || ''} onChange={(e) => patchItem('social_links', index, 'label', e.target.value)} /></Field>
                    <Field label="Handle"><input value={item.handle || ''} onChange={(e) => patchItem('social_links', index, 'handle', e.target.value)} /></Field>
                    <Field label="Full profile URL"><input type="url" value={item.url || ''} onChange={(e) => patchItem('social_links', index, 'url', e.target.value)} /></Field>
                    <Field label="Followers / subscribers"><input type="number" min="0" value={item.follower_count ?? ''} onChange={(e) => patchItem('social_links', index, 'follower_count', e.target.value)} /></Field>
                    <Field label="Secondary stat"><input placeholder="e.g. 2.7M+ recent views" value={item.secondary_stat || ''} onChange={(e) => patchItem('social_links', index, 'secondary_stat', e.target.value)} /></Field>
                  </div>
                )}
              />
            </EditorSection>
          )}

          {active === 'proof' && (
            <EditorSection title="Performance proof" description="Turn analytics into quick, brand-friendly evidence.">
              <RepeatList
                title="Headline metrics"
                items={form.highlights}
                onAdd={() => addItem('highlights', { label: '', value: '', note: '' })}
                onRemove={(index) => removeItem('highlights', index)}
                onMove={(index, direction) => moveItem('highlights', index, direction)}
                render={(item, index) => (
                  <div className="editor-grid three">
                    <Field label="Metric"><input value={item.label} onChange={(e) => patchItem('highlights', index, 'label', e.target.value)} /></Field>
                    <Field label="Value"><input value={item.value} onChange={(e) => patchItem('highlights', index, 'value', e.target.value)} /></Field>
                    <Field label="Context"><input value={item.note || ''} onChange={(e) => patchItem('highlights', index, 'note', e.target.value)} /></Field>
                  </div>
                )}
              />
              <RepeatList
                title="Audience insights"
                items={form.audience_insights}
                onAdd={() => addItem('audience_insights', { label: '', value: '' })}
                onRemove={(index) => removeItem('audience_insights', index)}
                onMove={(index, direction) => moveItem('audience_insights', index, direction)}
                render={(item, index) => (
                  <div className="editor-grid two">
                    <Field label="Insight"><input value={item.label} onChange={(e) => patchItem('audience_insights', index, 'label', e.target.value)} /></Field>
                    <Field label="Detail"><input value={item.value} onChange={(e) => patchItem('audience_insights', index, 'value', e.target.value)} /></Field>
                  </div>
                )}
              />
              <StringList
                title="Why brands partner with me"
                items={form.partner_reasons}
                placeholder="e.g. Strong organic reach beyond followers"
                onChange={(items) => patch('partner_reasons', items)}
              />
            </EditorSection>
          )}

          {active === 'services' && (
            <EditorSection title="Services & rates" description="Keep investment information current without editing code.">
              <RepeatList
                title="Rate card"
                items={form.rate_card}
                onAdd={() => addItem('rate_card', { deliverable: '', price: '', note: '' })}
                onRemove={(index) => removeItem('rate_card', index)}
                onMove={(index, direction) => moveItem('rate_card', index, direction)}
                render={(item, index) => (
                  <div className="editor-grid three">
                    <Field label="Deliverable"><input value={item.deliverable} onChange={(e) => patchItem('rate_card', index, 'deliverable', e.target.value)} /></Field>
                    <Field label="Price (INR)"><input type="number" min="0" value={item.price ?? ''} onChange={(e) => patchItem('rate_card', index, 'price', e.target.value)} /></Field>
                    <Field label="Note"><input placeholder="Optional" value={item.note || ''} onChange={(e) => patchItem('rate_card', index, 'note', e.target.value)} /></Field>
                  </div>
                )}
              />
            </EditorSection>
          )}

          {active === 'collabs' && (
            <EditorSection title="Past collaborations" description="Add brand proof, campaign summaries and links to live work.">
              <RepeatList
                title="Brand collaborations"
                items={form.past_collabs}
                onAdd={() => addItem('past_collabs', { brand: '', summary: '', logo_url: '', image_url: '', content_url: '' })}
                onRemove={(index) => removeItem('past_collabs', index)}
                onMove={(index, direction) => moveItem('past_collabs', index, direction)}
                render={(item, index) => (
                  <>
                    <div className="editor-grid two">
                      <Field label="Brand"><input value={item.brand} onChange={(e) => patchItem('past_collabs', index, 'brand', e.target.value)} /></Field>
                      <Field label="Live content URL"><input type="url" value={item.content_url || ''} onChange={(e) => patchItem('past_collabs', index, 'content_url', e.target.value)} /></Field>
                    </div>
                    <Field label="Campaign summary"><input value={item.summary || ''} onChange={(e) => patchItem('past_collabs', index, 'summary', e.target.value)} /></Field>
                    <ImageField compact label="Campaign photo or logo" value={item.image_url || item.logo_url || ''} onChange={(url) => patchItem('past_collabs', index, 'image_url', url)} />
                  </>
                )}
              />
            </EditorSection>
          )}

          {active === 'testimonials' && (
            <EditorSection title="Testimonials" description="Publish concise social proof from brand partners.">
              <RepeatList
                title="Brand feedback"
                items={form.testimonials}
                onAdd={() => addItem('testimonials', { brand: '', quote: '', author: '' })}
                onRemove={(index) => removeItem('testimonials', index)}
                onMove={(index, direction) => moveItem('testimonials', index, direction)}
                render={(item, index) => (
                  <>
                    <div className="editor-grid two">
                      <Field label="Brand"><input value={item.brand} onChange={(e) => patchItem('testimonials', index, 'brand', e.target.value)} /></Field>
                      <Field label="Author"><input value={item.author || ''} onChange={(e) => patchItem('testimonials', index, 'author', e.target.value)} /></Field>
                    </div>
                    <Field label="Quote"><textarea rows="3" value={item.quote} onChange={(e) => patchItem('testimonials', index, 'quote', e.target.value)} /></Field>
                  </>
                )}
              />
            </EditorSection>
          )}

          {active === 'gallery' && (
            <EditorSection title="Photos & gallery" description="Upload analytics screenshots, campaign images and other visual proof.">
              <RepeatList
                title="Media gallery"
                items={form.gallery}
                onAdd={() => addItem('gallery', { title: '', image_url: '', category: 'Performance', caption: '', link_url: '' })}
                onRemove={(index) => removeItem('gallery', index)}
                onMove={(index, direction) => moveItem('gallery', index, direction)}
                render={(item, index) => (
                  <>
                    <ImageField compact label="Image" value={item.image_url} onChange={(url) => patchItem('gallery', index, 'image_url', url)} />
                    <div className="editor-grid two">
                      <Field label="Title"><input value={item.title} onChange={(e) => patchItem('gallery', index, 'title', e.target.value)} /></Field>
                      <Field label="Category"><input value={item.category || ''} onChange={(e) => patchItem('gallery', index, 'category', e.target.value)} /></Field>
                      <Field label="Caption"><input value={item.caption || ''} onChange={(e) => patchItem('gallery', index, 'caption', e.target.value)} /></Field>
                      <Field label="Optional link"><input type="url" value={item.link_url || ''} onChange={(e) => patchItem('gallery', index, 'link_url', e.target.value)} /></Field>
                    </div>
                  </>
                )}
              />
            </EditorSection>
          )}
        </div>
      </div>
    </div>
  )
}

function normalize(data) {
  return {
    ...EMPTY,
    ...data,
    social_links: data.social_links || [],
    highlights: data.highlights || [],
    audience_insights: data.audience_insights || [],
    content_pillars: data.content_pillars || [],
    partner_reasons: data.partner_reasons || [],
    rate_card: data.rate_card || [],
    past_collabs: data.past_collabs || [],
    testimonials: data.testimonials || [],
    gallery: data.gallery || [],
  }
}

function clean(data) {
  const numericSocials = data.social_links
    .filter((item) => item.url && item.platform)
    .map((item) => ({
      ...item,
      follower_count: item.follower_count === '' || item.follower_count == null
        ? null
        : Number(item.follower_count),
    }))
  return {
    ...data,
    linkedin_followers: Number(data.linkedin_followers || 0),
    linkedin_avg_impressions: Number(data.linkedin_avg_impressions || 0),
    social_links: numericSocials,
    rate_card: data.rate_card
      .filter((item) => item.deliverable)
      .map((item) => ({ ...item, price: item.price === '' ? null : Number(item.price) })),
    highlights: data.highlights.filter((item) => item.label && item.value),
    audience_insights: data.audience_insights.filter((item) => item.label && item.value),
    past_collabs: data.past_collabs.filter((item) => item.brand),
    testimonials: data.testimonials.filter((item) => item.brand && item.quote),
    gallery: data.gallery.filter((item) => item.title && item.image_url),
    content_pillars: data.content_pillars.filter(Boolean),
    partner_reasons: data.partner_reasons.filter(Boolean),
    contact_email: data.contact_email || null,
  }
}

function EditorSection({ title, description, children }) {
  return (
    <section>
      <div className="editor-section-heading">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
      </div>
      <div className="editor-section-body">{children}</div>
    </section>
  )
}

function Field({ label, hint, children }) {
  return <FormField label={label} hint={hint}>{children}</FormField>
}

function RepeatList({ title, items, onAdd, onRemove, onMove, render }) {
  return (
    <div className="repeat-list">
      <div className="repeat-list-heading">
        <h3>{title}</h3>
        <button type="button" className="small-button" onClick={onAdd}>+ Add</button>
      </div>
      {items.length === 0 && <div className="empty-inline">Nothing added yet.</div>}
      {items.map((item, index) => (
        <div className="repeat-card" key={index}>
          <div className="repeat-card-toolbar">
            <span>{String(index + 1).padStart(2, '0')}</span>
            <div>
              <button type="button" onClick={() => onMove(index, -1)} aria-label="Move up">↑</button>
              <button type="button" onClick={() => onMove(index, 1)} aria-label="Move down">↓</button>
              <button type="button" className="danger" onClick={() => onRemove(index)}>Remove</button>
            </div>
          </div>
          {render(item, index)}
        </div>
      ))}
    </div>
  )
}

function StringList({ title, items, placeholder, onChange }) {
  return (
    <div className="repeat-list">
      <div className="repeat-list-heading">
        <h3>{title}</h3>
        <button type="button" className="small-button" onClick={() => onChange([...items, ''])}>+ Add</button>
      </div>
      {items.map((item, index) => (
        <div className="string-row" key={index}>
          <input
            placeholder={placeholder}
            value={item}
            onChange={(e) => onChange(items.map((value, i) => i === index ? e.target.value : value))}
          />
          <button type="button" onClick={() => onChange(items.filter((_, i) => i !== index))}>×</button>
        </div>
      ))}
    </div>
  )
}

function ImageField({ label, value, onChange, wide, compact }) {
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const src = absoluteMediaUrl(value)

  async function upload(file) {
    if (!file) return
    setUploading(true)
    setError('')
    try {
      const body = new FormData()
      body.append('file', file)
      const response = await authFetch('/api/media-kit/upload', { method: 'POST', body })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Upload failed')
      onChange(data.url)
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className={`image-field${wide ? ' wide' : ''}${compact ? ' compact' : ''}`}>
      <span className="image-field-label">{label}</span>
      <div className="image-preview">
        {src ? <img src={src} alt="" /> : <span>No image uploaded</span>}
      </div>
      <div className="image-actions">
        <label className="small-button">
          {uploading ? 'Uploading...' : 'Upload image'}
          <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden disabled={uploading} onChange={(e) => upload(e.target.files?.[0])} />
        </label>
        {value && <button type="button" className="text-button danger-text" onClick={() => onChange('')}>Remove</button>}
      </div>
      {error && <small className="field-error">{error}</small>}
    </div>
  )
}

function absoluteMediaUrl(url) {
  if (!url) return ''
  if (/^https?:\/\//i.test(url)) return url
  return `${API}${url}`
}

function AdminLoading({ label }) {
  return <div className="admin-loading"><span className="loading-dot" />{label}</div>
}
