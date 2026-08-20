import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { API } from '../api.js'

const DEFAULT_PILLARS = ['Technology', 'AI & tools', 'Career growth', 'Student life', 'Creator stories']
const DEFAULT_REASONS = [
  'Ideas translated into clear, audience-first stories',
  'A trusted student and early-career technology community',
  'Concept, scripting, production and delivery in one workflow',
  'Professional communication from brief to performance recap',
]
const DEFAULT_AUDIENCE = [
  { label: 'Primary audience', value: 'Students, coding learners and early-career professionals' },
  { label: 'Top age group', value: '18–24 (72.5%)' },
  { label: 'Gender split', value: '52.3% women / 47.7% men' },
  { label: 'Top cities', value: 'Delhi, Bengaluru, Pune, Noida and Mumbai' },
  { label: 'Primary country', value: 'India' },
]
const DEFAULT_BRANDS = [
  'Motorola', 'GeeksforGeeks', 'KPIT Sparkle', 'Coding Ninjas', 'SuperProfile',
  'Unstop', 'Aakash Institute', 'BITS Pilani Hyderabad', 'Chitkara University', 'Code Monsters',
].map((brand) => ({ brand }))

const BRAND_STORIES = {
  'aakash institute': 'Student-focused education campaign translating academic ambition into an engaging social story.',
  'bits pilani hyderabad': 'On-site Launchpad 26 coverage capturing student innovation, founders and campus energy.',
  'brand bikega': 'UGSOT campaign delivered through Brand Bikega for a student-first social audience.',
  'career roadmap': 'Career guidance series helping students navigate skills, opportunities and early-career decisions.',
  'chitkara university': 'Campus storytelling highlighting student opportunities, technology culture and university life.',
  'code monsters': 'Hackathon awareness campaign motivating student developers to participate, build and showcase their skills.',
  'codeflix labs': 'Coding-education story designed to make technical learning feel approachable and actionable.',
  'coding ninjas': 'Community-led collaboration connecting coding learners with the Coding Ninjas ecosystem.',
  'dpu online': 'Online-education campaign focused on flexible learning and career advancement.',
  'finalround ai': 'AI interview-preparation campaign turning a technical product into a practical career story.',
  'flipkart x netflix': 'Entertainment-commerce collaboration built around a culturally relevant, social-first moment.',
  'ganpat university': 'University campaign highlighting campus experience and opportunity through relatable creator content.',
  'geeksforgeeks': 'Developer-learning campaign translating a technical opportunity into clear, relatable content.',
  'golzza': 'Multi-month campus activation at Chitkara University, creating student-focused promotional content.',
  'interview cue': 'Career-tech collaboration helping young professionals discover smarter interview preparation.',
  'kpit': 'Innovation-led storytelling connecting student builders with KPIT Sparkle’s national mobility challenge.',
  'kpit sparkle': 'Innovation-led storytelling connecting student builders with KPIT Sparkle’s national mobility challenge.',
  'linkedin': 'Career-focused collaboration for students and early professionals building their professional identity.',
  'motorola': 'Three-Reel smartphone launch campaign turning product features into creator-led stories.',
  'stanford university': 'Education-focused collaboration bringing a global academic story to an ambitious student audience.',
  'superprofile': 'Creator-economy campaign presenting a practical digital product through native social storytelling.',
  'unstop': 'IPL-themed campaign connecting Unstop with ambitious students through timely cultural storytelling.',
  'upgrad': 'Higher-education campaign translating upskilling opportunities into clear, audience-first content.',
  'vgu rajasthan': 'Campus campaign showcasing VGU Jaipur through student-focused, social-first storytelling.',
  'wise monk journals': 'Mindful-productivity collaboration presented through authentic lifestyle storytelling.',
}

export default function MediaKit({ initialData = null, previewMode = false }) {
  const [data, setData] = useState(initialData)
  const [error, setError] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [scrollProgress, setScrollProgress] = useState(0)
  const [featuredContent, setFeaturedContent] = useState([])
  const siteRef = useRef(null)

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
  }, [initialData])

  useEffect(() => {
    fetch(`${API}/api/content/case-studies`)
      .then((response) => response.ok ? response.json() : [])
      .then(setFeaturedContent)
      .catch(() => setFeaturedContent([]))
  }, [])

  useEffect(() => {
    if (!data) return undefined
    const elements = [...document.querySelectorAll('.mk-reveal')]
    if (!('IntersectionObserver' in window) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      elements.forEach((element) => element.classList.add('is-visible'))
      return undefined
    }
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return
        entry.target.classList.add('is-visible')
        observer.unobserve(entry.target)
      })
    }, { threshold: 0.1, rootMargin: '0px 0px -6% 0px' })
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
    const close = (event) => event.key === 'Escape' && setMenuOpen(false)
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [menuOpen])

  function moveSpotlight(event) {
    if (!siteRef.current || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    siteRef.current.style.setProperty('--pointer-x', `${event.clientX}px`)
    siteRef.current.style.setProperty('--pointer-y', `${event.clientY}px`)
  }

  if (error) return <Centered error>Could not load the media kit right now. Please refresh.</Centered>
  if (!data) return <Centered><span className="loading-dot" />Loading Aarohi's creator world...</Centered>

  const visibleItems = (items) => (items || []).filter((item) => item?.visible !== false)
  const hiddenSections = new Set(data.hidden_sections || [])
  const sectionOrder = data.section_order || []
  const socials = visibleItems(data.social_links).length ? visibleItems(data.social_links) : legacySocials(data)
  const highlights = visibleItems(data.highlights)
  const audienceInsights = visibleItems(data.audience_insights)
  const gallery = visibleItems(data.gallery)
  const rates = visibleItems(data.rate_card)
  const pastCollabs = visibleItems(data.past_collabs)
  const displayCollabs = dedupeCollabs(pastCollabs.length ? pastCollabs : DEFAULT_BRANDS)
  const testimonials = visibleItems(data.testimonials)
  const pillars = data.content_pillars?.length ? data.content_pillars : DEFAULT_PILLARS
  const partnerReasons = data.partner_reasons?.length ? data.partner_reasons : DEFAULT_REASONS
  const followerPeak = primaryFollowers(socials)
  const uniqueBrands = new Set(displayCollabs.map((item) => item.brand?.trim()).filter(Boolean)).size
  const proofCards = buildProofCards(highlights, socials, uniqueBrands)
  const availableSections = {
    pillars: !hiddenSections.has('pillars'),
    proof: !hiddenSections.has('proof'),
    audience: !hiddenSections.has('audience'),
    gallery: !hiddenSections.has('gallery') && (gallery.length > 0 || featuredContent.length > 0),
    services: !hiddenSections.has('services') && rates.length > 0,
    collaborations: !hiddenSections.has('collaborations') && displayCollabs.length > 0,
    partner_reasons: !hiddenSections.has('partner_reasons'),
    testimonials: !hiddenSections.has('testimonials') && testimonials.length > 0,
  }
  const defaultSectionOrder = ['pillars', 'proof', 'audience', 'gallery', 'services', 'collaborations', 'partner_reasons', 'testimonials']
  const orderedSections = [...new Set([...sectionOrder, ...defaultSectionOrder])].filter((section) => availableSections[section])
  const sectionStyle = (section) => ({ order: orderedSections.indexOf(section) })
  const sectionIndex = (section) => String(orderedSections.indexOf(section) + 1).padStart(2, '0')
  const portraitStyle = data.portrait_style === 'framed' ? 'framed' : 'cutout'
  const profileImageSrc = portraitMediaUrl(data.profile_image_url, portraitStyle)
  const audienceProfile = audienceInsights.length ? audienceInsights : DEFAULT_AUDIENCE

  return (
    <div className="media-site mk-site" ref={siteRef} onPointerMove={moveSpotlight}>
      {previewMode && (
        <div className="draft-preview-banner">
          <div><strong>Draft preview</strong><span>Only you can see these unpublished changes.</span></div>
          <button type="button" onClick={() => window.close()}>Close preview</button>
        </div>
      )}

      <nav className={`media-nav mk-nav${menuOpen ? ' menu-open' : ''}`} aria-label="Media kit navigation">
        <a href="#top" className="media-logo mk-logo" aria-label="Aarohi Inframe home">
          <span>AI</span>
          <span className="mk-logo-copy"><strong>@aarohi.inframe</strong><small> by Aarohi Dixit</small></span>
        </a>
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
          <a href="#story">About</a>
          <a href="#proof">Results</a>
          {(gallery.length > 0 || featuredContent.length > 0) && <a href="#work">Work</a>}
          {availableSections.collaborations && <a href="#brands">Collaborations</a>}
          <Link className="media-nav-cta" to="/collab">Start a project <Icon name="arrow" /></Link>
        </div>
        <span className="media-scroll-progress" style={{ width: `${scrollProgress}%` }} />
      </nav>

      <main id="top">
        <section className={`mk-hero${data.cover_image_url ? ' has-cover' : ''}`}>
          {data.cover_image_url && <img className="mk-cover" src={mediaUrl(data.cover_image_url)} alt="" />}
          <div className="mk-noise" />
          <div className="mk-editorial-word" aria-hidden="true">aarohi.inframe</div>

          <div className="mk-editorial-meta">
            <span>Tech · Career · Student life</span>
            <div className="mk-availability"><span /> Available for collaborations <em>2026</em></div>
          </div>

          <div className="mk-hero-copy mk-editorial-intro">
            <p className="mk-editorial-kicker">Hello, I’m</p>
            <h1>{data.name || 'Aarohi Dixit'}</h1>
            <strong>{data.tagline || 'Tech content creator & digital storyteller'}</strong>
            <p className="mk-intro">{data.bio || 'I turn complex technology into clear, useful stories people genuinely want to save and share.'}</p>
            <div className="mk-hero-actions">
              <Link className="mk-button mk-button-primary" to="/collab">Work with me <Icon name="arrow" /></Link>
              <a className="mk-editorial-text-link" href={(gallery.length || featuredContent.length) ? '#work' : '#proof'}>View selected work</a>
            </div>
            {socials.some((social) => social.url) && (
              <div className="mk-hero-socials" aria-label="Aarohi's social profiles">
                <span>Find me online</span>
                <div>
                  {socials.filter((social) => social.url).map((social, index) => (
                    <a href={social.url} target="_blank" rel="noreferrer" key={`hero-social-${social.platform}-${index}`} aria-label={`Open ${social.platform}`}>
                      <SocialIcon platform={social.platform} /><span>{social.platform}</span>
                    </a>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className={`mk-portrait-stage is-${portraitStyle}`} aria-label={`${data.name} creator profile`}>
            <div className="mk-portrait-aura" aria-hidden="true" />
            <div className="mk-orbit mk-orbit-outer" aria-hidden="true">
              <div className="mk-orbit-particles">{Array.from({ length: 9 }, (_, index) => <i key={index} />)}</div>
            </div>
            <div className="mk-orbit mk-orbit-inner" aria-hidden="true"><i /><i /></div>
            <div className="mk-orbit mk-orbit-signal" aria-hidden="true" />
            <div className="mk-portrait-card">
              {profileImageSrc ? (
                <img src={profileImageSrc} alt={data.name} />
              ) : (
                <div className="hero-photo-placeholder"><span>AD</span><small>Add profile photo</small></div>
              )}
              <span className="mk-photo-scan" />
              <span className="mk-frame-corner corner-one" /><span className="mk-frame-corner corner-two" />
              <div className="mk-portrait-label"><span>the human behind the handle</span><strong>{data.name}</strong></div>
            </div>
          </div>

          <aside className="mk-editorial-stats" aria-label="Creator highlights">
            {proofCards.slice(0, 3).map((item, index) => (
              <div key={`hero-${item.label}`}>
                <span>{String(index + 1).padStart(2, '0')} · {item.label}</span>
                <strong>{item.value}</strong>
                <small>{item.note}</small>
              </div>
            ))}
          </aside>

        </section>

        {!hiddenSections.has('pillars') && (
          <div className="mk-marquee" aria-label="Content themes">
            <div>{[...pillars, ...pillars].map((pillar, index) => <span key={`${pillar}-${index}`}><i>✦</i>{pillar}</span>)}</div>
          </div>
        )}

        <div className="media-reorderable mk-reorderable">
          {!hiddenSections.has('pillars') && (
            <section className="mk-manifesto mk-reveal" id="story" style={sectionStyle('pillars')}>
              <span className="mk-index">{sectionIndex('pillars')} / ABOUT AAROHI</span>
              <p>I don't just post about technology.</p>
              <h2>I translate the future into stories that feel like a conversation with your smartest friend.</h2>
              <div><span>Clear thinking</span><span>Native storytelling</span><span>Real community</span></div>
            </section>
          )}

          {!hiddenSections.has('proof') && (
            <section className="mk-section mk-proof mk-reveal" id="proof" style={sectionStyle('proof')}>
              <SectionIntro index={sectionIndex('proof')} eyebrow="Reach & results" title="Performance brands can act on." body="A concise snapshot of audience scale, engagement and consistent content discovery." />
              <div className="mk-bento">
                {proofCards.map((item, index) => (
                  <article className={`mk-proof-card proof-${index + 1}`} key={`${item.label}-${index}`}>
                    <span>{String(index + 1).padStart(2, '0')} / {item.label}</span>
                    <strong><AnimatedStat value={item.value} /></strong>
                    <p>{item.note}</p>
                    <i><Icon name={index === 0 ? 'pulse' : index === 1 ? 'people' : index === 2 ? 'play' : 'spark'} /></i>
                  </article>
                ))}
              </div>
            </section>
          )}

          {!hiddenSections.has('audience') && (
            <section className="mk-audience mk-reveal" id="audience" style={sectionStyle('audience')}>
              <div className="mk-audience-copy">
                <SectionIntro index={sectionIndex('audience')} eyebrow="Audience intelligence" title="The people behind the numbers." body="Age, gender, geography and interests. The context a brand needs to judge campaign fit before the first conversation." />
                <div className="mk-audience-fit"><span>Audience fit</span><strong>Tech-curious, career-focused and ready to act.</strong><p>Built around useful content people save, share and return to when they are making education, career and technology decisions.</p></div>
              </div>
              <div className="mk-audience-dashboard">
                {audienceProfile.map((item, index) => <AudienceInsightCard item={item} index={index} key={`${item.label}-${index}`} />)}
              </div>
              <div className="mk-audience-note"><span>Why this audience matters</span><strong>High-intent attention at the moment choices are being made.</strong><small>Education · software · consumer tech · careers · student culture</small></div>
              {socials.length > 0 && (
                <div className="mk-social-rail">
                  {socials.map((social, index) => <SocialLink key={`${social.platform}-${index}`} social={social} />)}
                </div>
              )}
            </section>
          )}

          {!hiddenSections.has('gallery') && (gallery.length > 0 || featuredContent.length > 0) && (
            <section className="mk-section mk-work mk-reveal" id="work" style={sectionStyle('gallery')}>
              <SectionIntro index={sectionIndex('gallery')} eyebrow="Featured content" title="Reels and videos that performed." body="Selected work with live links and performance proof, chosen specifically for brands reviewing this media kit." />
              {featuredContent.length > 0 && (
                <div className="mk-featured-content-grid">
                  {featuredContent.slice(0, 6).map((item, index) => <FeaturedContentCard item={item} index={index} key={item.id} />)}
                </div>
              )}
              {gallery.length > 0 && (
                <>
                  {featuredContent.length > 0 && <div className="mk-gallery-divider"><span>Campaign gallery</span><i /></div>}
                  <div className="mk-work-grid">
                    {gallery.map((item, index) => <GalleryCard item={item} index={index} key={`${item.title}-${index}`} />)}
                  </div>
                </>
              )}
            </section>
          )}

          {!hiddenSections.has('services') && rates.length > 0 && (
            <section className="mk-section mk-services mk-reveal" id="services" style={sectionStyle('services')}>
              <SectionIntro index={sectionIndex('services')} eyebrow="Collaboration formats" title="Ways we can work together." body="Each partnership starts with the campaign goal, not a copy-and-paste package." />
              <div className="mk-service-stack">
                {rates.map((item, index) => (
                  <div key={`${item.deliverable}-${index}`}>
                    <span>{String(index + 1).padStart(2, '0')}</span>
                    <strong>{item.deliverable}</strong>
                    <em>{item.price ? `₹${Number(item.price).toLocaleString('en-IN')}` : item.note || 'Custom quote'}</em>
                    <Icon name="arrow" />
                  </div>
                ))}
              </div>
            </section>
          )}

          {availableSections.collaborations && (
            <section className="mk-brands mk-reveal" id="brands" style={sectionStyle('collaborations')}>
              <div className="mk-brands-heading">
                <span className="mk-index">{sectionIndex('collaborations')} / PAST COLLABORATIONS</span>
                <h2>Stories built with<br /><em>ambitious brands.</em></h2>
                <p>One selected campaign per brand, spanning technology, education, careers, campuses and culture.</p>
              </div>
              <div className="mk-brand-wall">
                {displayCollabs.map((collab, index) => <BrandCard collab={collab} index={index} key={`${collab.brand}-${index}`} />)}
              </div>
            </section>
          )}

          {!hiddenSections.has('partner_reasons') && (
            <section className="mk-section mk-why mk-reveal" style={sectionStyle('partner_reasons')}>
              <SectionIntro index={sectionIndex('partner_reasons')} eyebrow="Why partner with Aarohi" title="Creative work with a professional process." />
              <div className="mk-reason-grid">
                {partnerReasons.map((reason, index) => (
                  <article key={reason}><span>0{index + 1}</span><strong>{reason}</strong><i /></article>
                ))}
              </div>
            </section>
          )}

          {!hiddenSections.has('testimonials') && testimonials.length > 0 && (
            <section className="mk-section mk-testimonials mk-reveal" style={sectionStyle('testimonials')}>
              <SectionIntro index={sectionIndex('testimonials')} eyebrow="Brand feedback" title="What partners say." />
              <div className="mk-quote-grid">
                {testimonials.map((item, index) => (
                  <blockquote key={index}>
                    <span>“</span><p>{item.quote}</p>
                    <footer><strong>{item.author || item.brand}</strong>{item.author && <small>{item.brand}</small>}</footer>
                  </blockquote>
                ))}
              </div>
            </section>
          )}
        </div>

        <section className="mk-cta mk-reveal">
          <div className="mk-cta-grid" />
          <span className="mk-cta-kicker">Your campaign could be the next frame.</span>
          <h2>Let's make the internet<br /><em>pause for a second.</em></h2>
          <p>Tell me what you are building, who it is for and why it matters. We will shape the format together.</p>
          <Link className="mk-button mk-button-primary" to="/collab">Build something memorable <Icon name="arrow" /></Link>
          <div className="mk-cta-contact">
            {data.contact_email && <a href={`mailto:${data.contact_email}`}>{data.contact_email}</a>}
            {data.contact_phone && <a href={`tel:${data.contact_phone.replace(/\s/g, '')}`}>{data.contact_phone}</a>}
          </div>
        </section>
      </main>

      <footer className="mk-footer">
        <div className="mk-footer-main">
          <div className="mk-footer-brand">
            <a href="#top" className="media-logo mk-logo" aria-label="Back to the top">
              <span>AI</span>
              <span className="mk-logo-copy"><strong>Aarohi Inframe</strong><small>by Aarohi Dixit</small></span>
            </a>
            <p>Technology, careers and student life, explained through clear, human-first stories.</p>
            <span className="mk-footer-availability"><i /> Available for select collaborations</span>
          </div>

          <div className="mk-footer-links">
            <div>
              <span>Explore</span>
              <a href="#story">About Aarohi</a>
              <a href="#proof">Audience & results</a>
              {(gallery.length > 0 || featuredContent.length > 0) && <a href="#work">Selected work</a>}
              {availableSections.collaborations && <a href="#brands">Past collaborations</a>}
            </div>
            <div>
              <span>Connect</span>
              {socials.filter((social) => social.url).slice(0, 4).map((social, index) => (
                <a className="mk-footer-social-link" href={social.url} target="_blank" rel="noreferrer" key={`footer-${social.platform}-${index}`}>
                  <SocialIcon platform={social.platform} />{social.label || social.platform}
                </a>
              ))}
              {data.contact_email && <a className="mk-footer-social-link" href={`mailto:${data.contact_email}`}><SocialIcon platform="Email" />Email</a>}
              {data.contact_phone && <a className="mk-footer-social-link" href={`tel:${data.contact_phone.replace(/\s/g, '')}`}><SocialIcon platform="Phone" />{data.contact_phone}</a>}
            </div>
          </div>

          <div className="mk-footer-project">
            <span>Brand partnerships</span>
            <strong>Have a campaign in mind?</strong>
            <p>Share the idea, goal and timeline. We’ll shape the right format together.</p>
            <Link to="/collab">Start a conversation <Icon name="arrow" /></Link>
          </div>
        </div>
        <div className="mk-footer-bottom">
          <span>© {new Date().getFullYear()} {data.name}. All rights reserved.</span>
          <span>Creator · Engineer · Storyteller</span>
          <a href="#top">Back to top ↑</a>
        </div>
      </footer>
      <Link className="mobile-collab-cta" to="/collab">Build a campaign <Icon name="arrow" /></Link>
    </div>
  )
}

function buildProofCards(highlights, socials, uniqueBrands) {
  if (highlights.length) return highlights.slice(0, 4)
  const socialCards = socials.filter((item) => item.follower_count).map((item) => ({
    label: item.platform,
    value: formatCount(item.follower_count),
    note: item.secondary_stat || 'An active, platform-native community.',
  }))
  const fallbacks = [
    { label: 'Instagram views', value: '2.7M+', note: 'Recent content performance.' },
    { label: 'Interactions', value: '73K+', note: 'High-intent engagement across content.' },
    { label: 'New followers', value: '5.1K+', note: 'Recent community growth.' },
    { label: 'Average reel reach', value: '10K+', note: uniqueBrands ? `Across ${uniqueBrands}+ brand relationships.` : 'Strong organic discovery.' },
  ]
  return [...socialCards, ...fallbacks].slice(0, 4)
}

function AudienceInsightCard({ item, index }) {
  const value = String(item.value || '')
  const percentages = [...value.matchAll(/(\d+(?:\.\d+)?)%/g)].map((match) => Math.min(100, Number(match[1])))
  return (
    <article className="mk-audience-insight">
      <span>{String(index + 1).padStart(2, '0')} / {item.label}</span>
      <strong>{value}</strong>
      {percentages.length > 0 && <div className="mk-audience-bars">{percentages.map((percentage, barIndex) => <i key={`${percentage}-${barIndex}`} style={{ '--audience-value': `${percentage}%` }} />)}</div>}
    </article>
  )
}

function FeaturedContentCard({ item, index }) {
  const metrics = item.metrics || {}
  const primaryValue = metrics.views || metrics.reach || 0
  const primaryLabel = metrics.views ? 'views' : metrics.reach ? 'reach' : 'published'
  const engagement = item.calculated_engagement_rate || metrics.engagement_rate
  const content = (
    <>
      <div className="mk-featured-media">
        {item.thumbnail_url
          ? <img src={mediaUrl(item.thumbnail_url)} alt="" loading="lazy" />
          : <span>{item.platform?.slice(0, 2) || 'AD'}</span>}
        <i>{item.platform}</i>
        <b>{String(index + 1).padStart(2, '0')}</b>
      </div>
      <div className="mk-featured-copy">
        <span>{item.brand?.name || item.collab_label || 'Creator content'}</span>
        <strong>{item.title}</strong>
        <div>
          <p><b>{primaryValue ? formatCount(primaryValue) : 'Live'}</b><small>{primaryLabel}</small></p>
          {engagement ? <p><b>{Number(engagement).toFixed(1)}%</b><small>engagement</small></p> : null}
          {metrics.likes ? <p><b>{formatCount(metrics.likes)}</b><small>likes</small></p> : null}
        </div>
      </div>
      {item.content_url && <em><Icon name="arrow" /></em>}
    </>
  )
  return item.content_url
    ? <a className="mk-featured-card" href={item.content_url} target="_blank" rel="noreferrer">{content}</a>
    : <article className="mk-featured-card">{content}</article>
}

function GalleryCard({ item, index }) {
  const content = (
    <>
      <img src={mediaUrl(item.image_url)} alt={item.title} loading="lazy" />
      <div className="mk-work-shade" />
      <span className="mk-work-number">0{index + 1}</span>
      <div className="mk-work-copy"><small>{item.category || 'Selected work'}</small><strong>{item.title}</strong>{item.caption && <p>{item.caption}</p>}</div>
      {item.link_url && <i><Icon name="arrow" /></i>}
    </>
  )
  return item.link_url
    ? <a href={item.link_url} target="_blank" rel="noreferrer">{content}</a>
    : <article>{content}</article>
}

function BrandCard({ collab, index }) {
  const brand = displayBrandName(collab.brand)
  const story = campaignStory(collab)
  const logoUrl = collab.logo_url || collab.image_url
  return (
    <article className="mk-brand-story">
      <header className="mk-brand-story-heading">
        <span className={`mk-brand-heading-mark${logoUrl ? ' has-logo' : ''}`}>
          {logoUrl ? <img src={mediaUrl(logoUrl)} alt={`${brand} logo`} loading="lazy" /> : initials(brand)}
        </span>
        <div><strong>{brand}</strong><small>Campaign collaboration</small></div>
        <span className="mk-brand-heading-index">{String(index + 1).padStart(2, '0')}</span>
      </header>
      <div className="mk-brand-story-copy">
        <p>{story}</p>
        {collab.content_url && <a href={collab.content_url} target="_blank" rel="noreferrer">View on Instagram <Icon name="arrow" /></a>}
      </div>
    </article>
  )
}

function normalizedBrandKey(brand = '') {
  return String(brand).toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()
}

function collabViews(collab = {}) {
  return Number(collab.views || collab.metrics?.views || collab.performance?.views || 0) || 0
}

function dedupeCollabs(collabs) {
  const selected = new Map()
  collabs.forEach((collab, position) => {
    const key = normalizedBrandKey(collab.brand)
    if (!key) return
    const candidate = { ...collab, _position: position }
    const current = selected.get(key)
    const candidateViews = collabViews(candidate)
    const currentViews = collabViews(current)
    if (!current || candidateViews > currentViews || (candidateViews === currentViews && position > current._position)) selected.set(key, candidate)
  })
  return [...selected.values()]
    .sort((a, b) => Number(Boolean(b.content_url)) - Number(Boolean(a.content_url)) || a._position - b._position)
    .map(({ _position, ...collab }) => collab)
}

function displayBrandName(brand = '') {
  const key = normalizedBrandKey(brand)
  if (key === 'kpit') return 'KPIT Sparkle'
  if (key === 'dpu online') return 'DPU Online'
  if (key === 'upgrad') return 'upGrad'
  if (key === 'wise monk jorunals' || key === 'wise monk journals') return 'Wise Monk Journals'
  return brand
}

function campaignStory(collab) {
  const key = normalizedBrandKey(displayBrandName(collab.brand))
  return BRAND_STORIES[key] || collab.summary || 'A creator-led campaign shaped around the brand’s objective and Aarohi’s audience.'
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
        const number = (target * eased).toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
        setDisplay(`${match[1]}${number}${match[3]}`)
        if (progress < 1) frame = requestAnimationFrame(tick)
      }
      frame = requestAnimationFrame(tick)
    }, { threshold: 0.5 })
    observer.observe(ref.current)
    return () => { observer.disconnect(); if (frame) cancelAnimationFrame(frame) }
  }, [value])

  return <span ref={ref}>{display}</span>
}

function SectionIntro({ index, eyebrow, title, body }) {
  return (
    <header className="mk-section-intro">
      <span className="mk-index">{index} / {eyebrow}</span>
      <h2>{title}</h2>
      {body && <p>{body}</p>}
    </header>
  )
}

function SocialLink({ social }) {
  const content = (
    <>
      <span className="mk-social-monogram"><SocialIcon platform={social.platform} /></span>
      <div><strong>{social.label || social.platform}{social.live && <i>Live</i>}</strong><small>{social.handle || social.secondary_stat}</small></div>
      <em>{social.follower_count ? formatCount(social.follower_count) : <Icon name="arrow" />}</em>
    </>
  )
  return social.url
    ? <a className="mk-social-link" href={social.url} target="_blank" rel="noreferrer">{content}</a>
    : <span className="mk-social-link">{content}</span>
}

function SocialIcon({ platform = '' }) {
  const name = platform.toLowerCase()
  if (name.includes('instagram')) return <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5" /><circle cx="12" cy="12" r="4" /><circle cx="17.4" cy="6.7" r=".8" className="is-filled" /></svg>
  if (name.includes('youtube')) return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 8.2a3 3 0 0 0-2.1-2.1C17 5.6 14.4 5.5 12 5.5s-5 .1-6.9.6A3 3 0 0 0 3 8.2 16 16 0 0 0 2.5 12 16 16 0 0 0 3 15.8a3 3 0 0 0 2.1 2.1c1.9.5 4.5.6 6.9.6s5-.1 6.9-.6a3 3 0 0 0 2.1-2.1 16 16 0 0 0 .5-3.8 16 16 0 0 0-.5-3.8Z" /><path d="m10 9 5 3-5 3V9Z" /></svg>
  if (name.includes('linkedin')) return <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M8 10v7M8 7v.1M12 17v-4a3 3 0 0 1 6 0v4M12 10v7" /></svg>
  if (name.includes('mail')) return <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m4 7 8 6 8-6" /></svg>
  if (name.includes('phone')) return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3H4.5A1.5 1.5 0 0 0 3 4.5C3 13.6 10.4 21 19.5 21a1.5 1.5 0 0 0 1.5-1.5V17l-4-1-1.2 2a14.5 14.5 0 0 1-9.8-9.8L8 7 7 3Z" /></svg>
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 14a5 5 0 0 0 7.5.5l2-2a5 5 0 0 0-7-7l-1.2 1.2M14 10a5 5 0 0 0-7.5-.5l-2 2a5 5 0 0 0 7 7l1.2-1.2" /></svg>
}

function Icon({ name }) {
  const paths = {
    arrow: <><path d="M5 12h13M13 6l6 6-6 6" /></>,
    down: <><path d="M12 4v15M6 13l6 6 6-6" /></>,
    pin: <><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z" /><circle cx="12" cy="10" r="2.5" /></>,
    spark: <><path d="m12 2 1.5 6.5L20 10l-6.5 1.5L12 18l-1.5-6.5L4 10l6.5-1.5L12 2Z" /><path d="m19 17 .5 2 2 .5-2 .5-.5 2-.5-2-2-.5 2-.5.5-2Z" /></>,
    pulse: <><path d="M3 12h4l2-7 4 14 2-7h6" /></>,
    people: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></>,
    play: <><circle cx="12" cy="12" r="9" /><path d="m10 8 6 4-6 4V8Z" /></>,
  }
  return <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name] || paths.spark}</svg>
}

function legacySocials(data) {
  return [
    data.instagram_handle && { platform: 'Instagram', handle: `@${data.instagram_handle}`, url: `https://instagram.com/${data.instagram_handle}` },
    data.youtube_handle && { platform: 'YouTube', handle: data.youtube_handle, url: `https://youtube.com/${data.youtube_handle}` },
    data.linkedin_handle && {
      platform: 'LinkedIn', handle: data.linkedin_handle, url: `https://linkedin.com/in/${data.linkedin_handle}`,
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

function portraitMediaUrl(url, portraitStyle) {
  const resolved = mediaUrl(url)
  if (portraitStyle !== 'cutout' || !resolved.includes('/ygp2zvbxjigpjs72myne')) return resolved
  return resolved
    .replace('/image/upload/', '/image/upload/e_background_removal/c_crop,x_280,y_260,w_1200,h_1740/f_png/')
    .replace(/\.webp(?=\?|$)/i, '.png')
}

function initials(value = '') {
  return value.split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase()
}

function Centered({ children, error = false }) {
  return <div className={`media-centered mk-centered${error ? ' is-error' : ''}`}><div className="mk-loader-mark">AI</div>{children}</div>
}
