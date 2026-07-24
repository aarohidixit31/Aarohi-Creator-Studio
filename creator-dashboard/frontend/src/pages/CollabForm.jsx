import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button, Feedback, FormField } from '../components/ui.jsx'

const API = import.meta.env.VITE_API_URL || ''

const CAMPAIGN_TYPES = [
  'Instagram Reel',
  'Carousel / Static',
  'YouTube Integration',
  'LinkedIn Content',
  'UGC',
  'Other',
]

const EMPTY_FORM = {
  brand_name: '',
  contact_person: '',
  email: '',
  phone: '',
  budget: '',
  campaign_types: [],
  campaign_other: '',
  deliverables: '',
  deadline: '',
  brief: '',
}

export default function CollabForm() {
  const [form, setForm] = useState(EMPTY_FORM)
  const [status, setStatus] = useState('idle')
  const [result, setResult] = useState(null)
  const [campaignError, setCampaignError] = useState('')

  const completed = useMemo(() => {
    const fields = [
      form.brand_name,
      form.contact_person,
      form.email,
      form.campaign_types.length ? 'selected' : '',
      form.deliverables,
    ]
    return Math.round((fields.filter((value) => value.trim()).length / fields.length) * 100)
  }, [form])

  function patch(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function toggleCampaignType(type) {
    setCampaignError('')
    setForm((current) => ({
      ...current,
      campaign_types: current.campaign_types.includes(type)
        ? current.campaign_types.filter((item) => item !== type)
        : [...current.campaign_types, type],
    }))
  }

  async function submit(event) {
    event.preventDefault()
    if (!form.campaign_types.length) {
      setCampaignError('Select at least one campaign format.')
      document.querySelector('.campaign-type-grid')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      return
    }
    setStatus('sending')
    try {
      const campaignType = form.campaign_types
        .map((type) => (type === 'Other' ? form.campaign_other.trim() || 'Other' : type))
        .join(', ')
      const { campaign_types: _campaignTypes, campaign_other: _campaignOther, ...inquiryFields } = form
      const response = await fetch(`${API}/api/collabs/inquiry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...inquiryFields,
          campaign_type: campaignType,
          budget: form.budget ? Number(form.budget) : null,
          deadline: form.deadline ? new Date(`${form.deadline}T12:00:00`).toISOString() : null,
        }),
      })
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(body?.detail || 'We could not send your inquiry.')
      }
      setResult(await response.json())
      setStatus('done')
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (error) {
      setStatus('error')
    }
  }

  function startAgain() {
    setForm(EMPTY_FORM)
    setResult(null)
    setCampaignError('')
    setStatus('idle')
  }

  if (status === 'done') {
    return <SuccessState brandName={form.brand_name} inquiryId={result?.collab_id} onReset={startAgain} />
  }

  return (
    <div className="collab-intake-page">
      <header className="collab-intake-nav">
        <Link className="collab-intake-logo" to="/">
          <span>AI</span>
          <div><strong>Aarohi Inframe</strong><small>Creator collaborations</small></div>
        </Link>
        <Link className="collab-back-link" to="/">View media kit <span aria-hidden="true">-&gt;</span></Link>
      </header>

      <main className="collab-intake-shell">
        <aside className="collab-intake-aside">
          <div className="collab-aside-grid" />
          <div className="collab-aside-copy">
            <span className="collab-terminal-label">$ start_collaboration</span>
            <h1>Let’s build something <em>worth sharing.</em></h1>
            <p>Tell us about the campaign. Aarohi and her manager will review the fit, scope and timeline, then respond within 24–48 hours.</p>
          </div>

          <div className="collab-process">
            <ProcessItem number="01" title="Share the brief" text="Goals, platform and expected deliverables." />
            <ProcessItem number="02" title="We review the fit" text="Audience relevance, timeline and commercials." />
            <ProcessItem number="03" title="Get a clear response" text="Availability and next steps within 24–48 hours." />
          </div>

          <div className="collab-trust-note">
            <span className="collab-live-dot" />
            Currently accepting selected partnerships
          </div>
        </aside>

        <section className="collab-form-panel">
          <div className="collab-form-heading">
            <div>
              <span className="eyebrow">Partnership inquiry</span>
              <h2>Tell us about the campaign</h2>
              <p>Fields marked required help us respond with a useful answer.</p>
            </div>
            <div className="form-progress" aria-label={`${completed}% complete`}>
              <strong>{completed}%</strong>
              <span><i style={{ width: `${completed}%` }} /></span>
            </div>
          </div>

          <form className="collab-intake-form" onSubmit={submit}>
            <FormSection number="01" title="Your details" description="Who should we speak with?">
              <div className="collab-form-grid two">
                <FormField label="Brand name" required>
                  <input
                    value={form.brand_name}
                    onChange={(event) => patch('brand_name', event.target.value)}
                    placeholder="e.g. Notion"
                    autoComplete="organization"
                    required
                  />
                </FormField>
                <FormField label="Contact person" required>
                  <input
                    value={form.contact_person}
                    onChange={(event) => patch('contact_person', event.target.value)}
                    placeholder="Your full name"
                    autoComplete="name"
                    required
                  />
                </FormField>
                <FormField label="Work email" required>
                  <input
                    type="email"
                    value={form.email}
                    onChange={(event) => patch('email', event.target.value)}
                    placeholder="name@brand.com"
                    autoComplete="email"
                    required
                  />
                </FormField>
                <FormField label="Phone / WhatsApp">
                  <input
                    type="tel"
                    value={form.phone}
                    onChange={(event) => patch('phone', event.target.value)}
                    placeholder="+91 98765 43210"
                    autoComplete="tel"
                  />
                </FormField>
              </div>
            </FormSection>

            <FormSection number="02" title="Campaign scope" description="What kind of partnership are you planning?">
              <FormField label="Content format" required error={campaignError}>
                <div className="campaign-type-grid" role="group" aria-label="Campaign formats" aria-invalid={Boolean(campaignError)}>
                  {CAMPAIGN_TYPES.map((type) => (
                    <button
                      type="button"
                      key={type}
                      className={form.campaign_types.includes(type) ? 'active' : ''}
                      onClick={() => toggleCampaignType(type)}
                      aria-pressed={form.campaign_types.includes(type)}
                    >
                      <span />
                      {type}
                    </button>
                  ))}
                </div>
                {form.campaign_types.includes('Other') && (
                  <input
                    className="campaign-custom-input"
                    value={form.campaign_other}
                    onChange={(event) => patch('campaign_other', event.target.value)}
                    placeholder="Describe the other content format"
                  />
                )}
              </FormField>

              <div className="collab-form-grid two">
                <FormField label="Approximate budget">
                  <div className="input-prefix">
                    <span>₹</span>
                    <input
                      type="number"
                      min="0"
                      value={form.budget}
                      onChange={(event) => patch('budget', event.target.value)}
                      placeholder="25,000"
                    />
                  </div>
                </FormField>
                <FormField label="Preferred deadline">
                  <input
                    type="date"
                    value={form.deadline}
                    onChange={(event) => patch('deadline', event.target.value)}
                  />
                </FormField>
              </div>

              <FormField label="Expected deliverables" required hint="Include quantities, platforms and usage requirements.">
                <textarea
                  rows="3"
                  value={form.deliverables}
                  onChange={(event) => patch('deliverables', event.target.value)}
                  placeholder="e.g. 1 Instagram Reel + 2 Stories, 30-day organic usage"
                  required
                />
              </FormField>
            </FormSection>

            <FormSection number="03" title="The brief" description="Context helps us evaluate the idea properly.">
              <FormField label="Campaign goals and context">
                <textarea
                  rows="6"
                  maxLength="1200"
                  value={form.brief}
                  onChange={(event) => patch('brief', event.target.value)}
                  placeholder="Tell us about the product, audience, campaign goal, key message and anything Aarohi should know..."
                />
                <span className="character-count">{form.brief.length}/1200</span>
              </FormField>
            </FormSection>

            {status === 'error' && (
              <Feedback tone="error" title="The inquiry was not sent">
                Please check your connection and try again. Your form details are still here.
              </Feedback>
            )}

            <div className="collab-submit-row">
              <p>By submitting, you agree that Aarohi or her manager may contact you about this campaign.</p>
              <Button type="submit" loading={status === 'sending'} icon="->">
                {status === 'sending' ? 'Sending inquiry' : 'Send partnership inquiry'}
              </Button>
            </div>
          </form>
        </section>
      </main>
    </div>
  )
}

function FormSection({ number, title, description, children }) {
  return (
    <section className="collab-form-section">
      <header>
        <span>{number}</span>
        <div><h3>{title}</h3><p>{description}</p></div>
      </header>
      <div className="collab-form-section-body">{children}</div>
    </section>
  )
}

function ProcessItem({ number, title, text }) {
  return (
    <div className="collab-process-item">
      <span>{number}</span>
      <div><strong>{title}</strong><p>{text}</p></div>
    </div>
  )
}

function SuccessState({ brandName, inquiryId, onReset }) {
  return (
    <div className="collab-success-page">
      <header className="collab-intake-nav">
        <Link className="collab-intake-logo" to="/">
          <span>AI</span>
          <div><strong>Aarohi Inframe</strong><small>Creator collaborations</small></div>
        </Link>
      </header>
      <main className="collab-success-card">
        <div className="success-orbit"><span className="success-check" /></div>
        <span className="eyebrow">Inquiry received</span>
        <h1>Thank you, {brandName}.</h1>
        <p>Your collaboration is now in our review queue. A confirmation has been sent to your email, and we’ll respond within 24–48 hours.</p>
        {inquiryId && <code>request_id: COLLAB-{String(inquiryId).padStart(4, '0')}</code>}

        <div className="success-next-steps">
          <div><span>01</span><strong>Brief received</strong><small>Your campaign details are saved.</small></div>
          <div><span>02</span><strong>Fit review</strong><small>We check scope, audience and availability.</small></div>
          <div><span>03</span><strong>Personal reply</strong><small>Expect clear next steps within 24–48 hours.</small></div>
        </div>

        <div className="success-actions">
          <Button to="/" variant="primary" icon="->">Back to media kit</Button>
          <Button type="button" variant="secondary" onClick={onReset}>Submit another inquiry</Button>
        </div>
      </main>
    </div>
  )
}
