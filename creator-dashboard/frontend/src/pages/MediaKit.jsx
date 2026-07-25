import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { API } from '../api.js'

export default function MediaKit({ initialData = null, previewMode = false }) {
  const [data, setData] = useState(initialData)
  const [caseStudies, setCaseStudies] = useState([])
  const [error, setError] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [scrollProgress, setScrollProgress] = useState(0)

  useEffect(() => {
    if (!initialData) {
      fetch(`${API}/api/media-kit/`)
        .then((response) => {
          if (!response.ok) throw new Error('Could not load media kit')
          return response.json()
        })
        .then(setData)
        .catch(() => setError(true))
    }
    fetch(`${API}/api/content/case-studies`)
      .then((response) => response.ok ? response.json() : [])
      .then(setCaseStudies)
      .catch(() => setCaseStudies([]))
  }, [initialData])

  useEffect(() => {
    if (!data) return undefined
    const elements = [...document.querySelectorAll('.media-reveal')]
    if (!('IntersectionObserver' in window) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      elements.forEach((element) => element.classList.add('is-visible'))
      return undefined
    }
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible')
          observer.unobserve(entry.target)
        }
      })
    }, { threshold: 0.12, rootMargin: '0px 0px -7% 0px' })
    elements.forEach((element) => observer.observe(element))
    return () => observer.disconnect()
  }, [data])

  useEffect(() => {
    const updateProgress = () => {
      const available = document.documentElement.scrollHeight - window.innerHeight
      setScrollProgress(available > 0 ? Math.min(100, (window.scrollY / available) * 100) : 0)
    }
    updateProgress()
    window.addEventListener('scroll', updateProgress, { passive: true })
    return () => window.removeEventListener('scroll', updateProgress)
  }, [])

  useEffect(() => {
    if (!menuOpen) return undefined
    const close = (event) => {
      if (event.key === 'Escape') setMenuOpen(false)
    }
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [menuOpen])

  if (error) return <Centered>Could not load the media kit right now. Please refresh.</Centered>
  if (!data) return <Centered><span className="loading-dot" />Loading media kit...</Centered>

  const visibleItems = (items) => (items || []).filter((item) => item?.visible !== false)
  const hiddenSections = new Set(data.hidden_sections || [])
  const sectionOrder = data.section_order || []
  const sectionStyle = (section) => ({ order: Math.max(0, sectionOrder.indexOf(section)) })
  const socials = visibleItems(data.social_links).length
    ? visibleItems(data.social_links)
    : legacySocials(data)
  const highlights = visibleItems(data.highlights)
  const audienceInsights = visibleItems(data.audience_insights)
  const gallery = visibleItems(data.gallery)
  const rates = visibleItems(data.rate_card)
  const pastCollabs = visibleItems(data.past_collabs)
  const testimonials = visibleItems(data.testimonials)

  return (
    <div className="media-site">
      {previewMode && (
        <div className="draft-preview-banner">
          <div><strong>Draft preview</strong><span>Only you can see these unsaved or unpublished changes.</span></div>
          <button type="button" onClick={() => window.close()}>Close preview</button>
        </div>
      )}
      <nav className={`media-nav${menuOpen ? ' menu-open' : ''}`}>
        <a href="#top" className="media-logo"><span>AI</span>Aarohi Inframe</a>
        <button
          className="media-menu-button"
          type="button"
          aria-label={menuOpen ? 'Close navigation' : 'Open navigation'}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((current) => !current)}
        >
          <span /><span /><span />
        </button>
        <div className="media-nav-links" onClick={() => setMenuOpen(false)}>
          <a href={gallery.length || caseStudies.length ? '#work' : '#proof'}>Work</a>
          <a href={rates.length && !hiddenSections.has('services') ? '#services' : '#audience'}>Services</a>
          {!hiddenSections.has('audience') && <a href="#audience">Audience</a>}
          <Link className="media-nav-cta" to="/collab">Work with me</Link>
        </div>
        <span className="media-scroll-progress" style={{ width: `${scrollProgress}%` }} />
      </nav>

      <main id="top">
        <section className={`media-hero${data.cover_image_url ? ' with-cover' : ''}`}>
          {data.cover_image_url && <img className="media-cover" src={mediaUrl(data.cover_image_url)} alt="" />}
          <div className="hero-grid-pattern" />
          <div className="media-hero-copy">
            <div className="hero-badge"><span /> Available for brand partnerships</div>
            <p className="hero-kicker">Tech creator · Student · Digital storyteller</p>
            <h1>Making tech feel <em>simple, useful</em> and worth sharing.</h1>
            <p className="hero-intro">{data.bio || data.tagline}</p>
            <div className="hero-actions">
              <Link className="button media-primary" to="/collab">Start a collaboration <span>↗</span></Link>
              <a className="button media-secondary" href="#proof">Explore my reach</a>
            </div>
            <div className="hero-social-row">
              {socials.map((social, index) => (
                <SocialLink key={`${social.platform}-${index}`} social={social} compact />
              ))}
            </div>
          </div>
          <div className="media-hero-visual">
            <div className="hero-yellow-card">
              <span className="hero-code">&lt;creator /&gt;</span>
              <strong>{data.name}</strong>
              <span>{data.tagline}</span>
            </div>
            <div className="hero-photo-wrap">
              {data.profile_image_url ? (
                <img src={mediaUrl(data.profile_image_url)} alt={data.name} />
              ) : (
                <div className="hero-photo-placeholder"><span>AD</span><small>Add profile photo</small></div>
              )}
            </div>
            <div className="hero-floating-stat">
              <span>Community</span>
              <strong><AnimatedStat value={`${formatCount(primaryFollowers(socials))}+`} /></strong>
              <small>and growing</small>
            </div>
          </div>
        </section>

        <div className="media-reorderable">
        {!hiddenSections.has('pillars') && data.content_pillars?.length > 0 && (
          <div className="pillar-strip media-reveal" style={sectionStyle('pillars')}>
            <span>Creating around</span>
            {data.content_pillars.map((pillar) => <strong key={pillar}>{pillar}</strong>)}
          </div>
        )}

        {!hiddenSections.has('proof') && (
        <section className="media-section media-proof media-reveal" id="proof" style={sectionStyle('proof')}>
          <SectionIntro
            eyebrow="Performance at a glance"
            title="Numbers that tell a stronger story."
            body="Clear, manager-updated proof of reach, engagement and audience quality."
          />
          <div className="media-metric-grid">
            {highlights.map((item, index) => (
              <article className={`media-metric-card ${index === 0 ? 'featured' : ''}`} key={`${item.label}-${index}`}>
                <span>{item.label}</span>
                <strong><AnimatedStat value={item.value} /></strong>
                {item.note && <small>{item.note}</small>}
              </article>
            ))}
            {!highlights.length && socials.map((social, index) => (
              <article className={`media-metric-card ${index === 0 ? 'featured' : ''}`} key={social.platform}>
                <span>{social.platform}</span>
                <strong><AnimatedStat value={formatCount(social.follower_count)} /></strong>
                <small>{social.secondary_stat || 'Community size'}</small>
              </article>
            ))}
          </div>
        </section>
        )}

        {!hiddenSections.has('audience') && (
        <section className="media-section media-split media-reveal" id="audience" style={sectionStyle('audience')}>
          <div>
            <SectionIntro
              eyebrow="Audience"
              title="Built for curious people moving forward."
              body="A focused community of students, developers and early-career professionals who want practical tools and honest guidance."
            />
            <div className="audience-list">
              {audienceInsights.map((item) => (
                <div key={item.label}><span>{item.label}</span><strong>{item.value}</strong></div>
              ))}
            </div>
          </div>
          <div className="social-stack">
            <span className="section-eyebrow">Find me online</span>
            {socials.map((social, index) => <SocialLink key={`${social.platform}-${index}`} social={social} />)}
          </div>
        </section>
        )}

        {!hiddenSections.has('gallery') && gallery.length > 0 && (
          <section className="media-section media-reveal" id="work" style={sectionStyle('gallery')}>
            <SectionIntro
              eyebrow="Selected proof"
              title="Campaigns, content and performance."
              body="A visual snapshot of the work and outcomes behind the numbers."
            />
            <div className="media-gallery">
              {gallery.map((item, index) => {
                const content = (
                  <>
                    <img src={mediaUrl(item.image_url)} alt={item.title} />
                    <div><span>{item.category || 'Media'}</span><strong>{item.title}</strong>{item.caption && <p>{item.caption}</p>}</div>
                  </>
                )
                return item.link_url
                  ? <a key={index} href={item.link_url} target="_blank" rel="noreferrer">{content}</a>
                  : <article key={index}>{content}</article>
              })}
            </div>
          </section>
        )}

        {!hiddenSections.has('case_studies') && caseStudies.length > 0 && (
          <section className="media-section public-case-studies media-reveal" id={gallery.length ? 'case-studies' : 'work'} style={sectionStyle('case_studies')}>
            <SectionIntro
              eyebrow="Performance case studies"
              title="Creative work backed by results."
              body="Selected campaigns with the context and numbers brands need to evaluate a partnership."
            />
            <div className="public-case-study-grid">
              {caseStudies.map((item) => (
                <article className="public-case-study-card" key={item.id}>
                  <div className="public-case-study-media">
                    {item.thumbnail_url
                      ? <img src={mediaUrl(item.thumbnail_url)} alt="" />
                      : <div><span>{item.platform.slice(0, 2)}</span></div>}
                    <span>{item.platform}</span>
                  </div>
                  <div className="public-case-study-body">
                    <span>{item.brand?.name || 'Creator original'}</span>
                    <h3>{item.title}</h3>
                    <p>{item.results || item.objective || 'Performance snapshot available for this content.'}</p>
                    <div>
                      <CaseMetric label="Views" value={formatCount(item.metrics?.views)} />
                      <CaseMetric label="Reach" value={formatCount(item.metrics?.reach)} />
                      {item.metrics?.conversions != null
                        ? <CaseMetric label="Conversions" value={formatCount(item.metrics.conversions)} />
                        : <CaseMetric label="Engagement" value={item.metrics?.engagement_rate != null ? `${item.metrics.engagement_rate}%` : '—'} />}
                    </div>
                    {item.content_url && <a href={item.content_url} target="_blank" rel="noreferrer">View live content <span>↗</span></a>}
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}

        {!hiddenSections.has('services') && rates.length > 0 && (
          <section className="media-section services-section media-reveal" id="services" style={sectionStyle('services')}>
            <SectionIntro
              eyebrow="Services & investment"
              title="Flexible formats, professional execution."
              body="Every partnership is shaped around the campaign goal, audience and creative fit."
            />
            <div className="service-list">
              {rates.map((item, index) => (
                <div key={`${item.deliverable}-${index}`}>
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <strong>{item.deliverable}</strong>
                  <em>{item.price ? `₹${Number(item.price).toLocaleString('en-IN')}` : item.note || 'Custom quote'}</em>
                </div>
              ))}
            </div>
          </section>
        )}

        {!hiddenSections.has('collaborations') && pastCollabs.length > 0 && (
          <section className="media-section collab-section media-reveal" style={sectionStyle('collaborations')}>
            <SectionIntro
              eyebrow="Trusted by"
              title="Previous brand collaborations."
              body="Partnership experience across technology, education and career-focused brands."
            />
            <div className="brand-grid">
              {pastCollabs.map((collab, index) => {
                const card = (
                  <>
                    {collab.image_url || collab.logo_url
                      ? <img src={mediaUrl(collab.image_url || collab.logo_url)} alt="" />
                      : <span>{initials(collab.brand)}</span>}
                    <div><strong>{collab.brand}</strong>{collab.summary && <small>{collab.summary}</small>}</div>
                  </>
                )
                return collab.content_url
                  ? <a key={index} href={collab.content_url} target="_blank" rel="noreferrer">{card}</a>
                  : <article key={index}>{card}</article>
              })}
            </div>
          </section>
        )}

        {!hiddenSections.has('partner_reasons') && data.partner_reasons?.length > 0 && (
          <section className="media-section partner-section media-reveal" style={sectionStyle('partner_reasons')}>
            <div>
              <span className="section-eyebrow">The partnership advantage</span>
              <h2>Why brands work with me.</h2>
            </div>
            <div className="partner-reasons">
              {data.partner_reasons.map((reason, index) => (
                <div key={reason}><span>0{index + 1}</span><strong>{reason}</strong></div>
              ))}
            </div>
          </section>
        )}

        {!hiddenSections.has('testimonials') && testimonials.length > 0 && (
          <section className="media-section media-reveal" style={sectionStyle('testimonials')}>
            <SectionIntro eyebrow="Partner notes" title="What brands say." />
            <div className="testimonial-grid">
              {testimonials.map((item, index) => (
                <blockquote key={index}>
                  <p>“{item.quote}”</p>
                  <footer><strong>{item.author || item.brand}</strong>{item.author && <span>{item.brand}</span>}</footer>
                </blockquote>
              ))}
            </div>
          </section>
        )}

        </div>

        <section className="media-cta media-reveal">
          <div>
            <span>Have a campaign in mind?</span>
            <h2>Let’s create something useful together.</h2>
          </div>
          <div>
            <Link className="button media-primary" to="/collab">Start a conversation ↗</Link>
            {data.contact_email && <a href={`mailto:${data.contact_email}`}>{data.contact_email}</a>}
            {data.contact_phone && <a href={`tel:${data.contact_phone.replace(/\s/g, '')}`}>{data.contact_phone}</a>}
          </div>
        </section>
      </main>

      <footer className="media-footer">
        <span>© {new Date().getFullYear()} {data.name}</span>
        <span>Tech, but human.</span>
      </footer>
      <Link className="mobile-collab-cta" to="/collab">Work with me <span>↗</span></Link>
    </div>
  )
}

function AnimatedStat({ value }) {
  const ref = useRef(null)
  const [display, setDisplay] = useState(value)

  useEffect(() => {
    const text = String(value ?? '')
    const match = text.match(/^([^\d]*)([\d,.]+)(.*)$/)
    if (!match || !ref.current || !('IntersectionObserver' in window) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setDisplay(text)
      return undefined
    }
    const target = Number(match[2].replace(/,/g, ''))
    if (!Number.isFinite(target)) return undefined
    const decimals = match[2].includes('.') ? match[2].split('.')[1].length : 0
    let frame
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return
      observer.disconnect()
      const started = performance.now()
      const tick = (now) => {
        const progress = Math.min(1, (now - started) / 900)
        const eased = 1 - (1 - progress) ** 3
        const number = (target * eased).toLocaleString('en-IN', {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        })
        setDisplay(`${match[1]}${number}${match[3]}`)
        if (progress < 1) frame = requestAnimationFrame(tick)
      }
      frame = requestAnimationFrame(tick)
    }, { threshold: 0.5 })
    observer.observe(ref.current)
    return () => {
      observer.disconnect()
      if (frame) cancelAnimationFrame(frame)
    }
  }, [value])

  return <span ref={ref}>{display}</span>
}

function SectionIntro({ eyebrow, title, body }) {
  return (
    <header className="section-intro">
      <span className="section-eyebrow">{eyebrow}</span>
      <h2>{title}</h2>
      {body && <p>{body}</p>}
    </header>
  )
}

function CaseMetric({ label, value }) {
  return <div><span>{label}</span><strong>{value || '—'}</strong></div>
}

function SocialLink({ social, compact }) {
  const content = (
    <>
      <span className={`social-icon social-${social.platform?.toLowerCase()}`}>{social.platform?.slice(0, 2)}</span>
      <div>
        <strong>{social.label || social.platform}{social.live && <span className="social-live-label">Live</span>}</strong>
        <small>
          {social.handle || social.secondary_stat}
          {!compact && social.handle && social.secondary_stat ? ` · ${social.secondary_stat}` : ''}
        </small>
      </div>
      {!compact && <em>{social.follower_count ? formatCount(social.follower_count) : '↗'}</em>}
    </>
  )
  return social.url
    ? <a className={`social-link${compact ? ' compact' : ''}`} href={social.url} target="_blank" rel="noreferrer">{content}</a>
    : <span className={`social-link${compact ? ' compact' : ''}`}>{content}</span>
}

function legacySocials(data) {
  return [
    data.instagram_handle && { platform: 'Instagram', handle: `@${data.instagram_handle}`, url: `https://instagram.com/${data.instagram_handle}` },
    data.youtube_handle && { platform: 'YouTube', handle: data.youtube_handle, url: `https://youtube.com/${data.youtube_handle}` },
    data.linkedin_handle && {
      platform: 'LinkedIn',
      handle: data.linkedin_handle,
      url: `https://linkedin.com/in/${data.linkedin_handle}`,
      follower_count: data.linkedin_followers,
      secondary_stat: data.linkedin_avg_impressions ? `${formatCount(data.linkedin_avg_impressions)} avg impressions` : '',
    },
  ].filter(Boolean)
}

function primaryFollowers(socials) {
  return Math.max(0, ...socials.map((item) => Number(item.follower_count || 0)))
}

function formatCount(value) {
  const number = Number(value || 0)
  if (number >= 1000000) return `${(number / 1000000).toFixed(number >= 10000000 ? 0 : 1)}M`
  if (number >= 1000) return `${(number / 1000).toFixed(number >= 10000 ? 0 : 1)}K`
  return number.toLocaleString('en-IN')
}

function mediaUrl(url) {
  if (!url) return ''
  if (/^https?:\/\//i.test(url)) return url
  return `${API}${url}`
}

function initials(value) {
  return value.split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase()
}

function Centered({ children }) {
  return <div className="media-centered">{children}</div>
}
