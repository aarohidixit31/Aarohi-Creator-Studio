import { useEffect, useMemo, useState } from 'react'
import { authFetch } from '../api.js'
import { Button, Feedback } from '../components/ui.jsx'

const PLATFORM_META = {
  instagram: {
    label: 'Instagram',
    code: 'IG',
    description: 'Professional-account followers and published media count',
    variables: ['META_ACCESS_TOKEN', 'INSTAGRAM_ACCOUNT_ID'],
  },
  youtube: {
    label: 'YouTube',
    code: 'YT',
    description: 'Subscribers, total channel views and public video count',
    variables: ['YOUTUBE_API_KEY', 'YOUTUBE_CHANNEL_ID or YOUTUBE_HANDLE'],
  },
}

export default function SocialStats() {
  const [stats, setStats] = useState([])
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  async function load() {
    setError('')
    try {
      const [response, historyResponse] = await Promise.all([
        authFetch('/api/social-stats/'),
        authFetch('/api/social-stats/history?days=365'),
      ])
      if (!response.ok || !historyResponse.ok) throw new Error('Could not load social connections')
      const [current, snapshots] = await Promise.all([response.json(), historyResponse.json()])
      setStats(current)
      setHistory(snapshots)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function refresh(platform = 'all') {
    setRefreshing(platform)
    setError('')
    setNotice('')
    try {
      const response = await authFetch(`/api/social-stats/refresh?platform=${platform}`, { method: 'POST' })
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(body?.detail || 'Could not refresh platform statistics')
      }
      const refreshed = await response.json()
      setStats((current) => {
        const updates = new Map(refreshed.map((item) => [item.platform, item]))
        return current.map((item) => updates.get(item.platform) || item)
      })
      const failures = refreshed.filter((item) => item.status !== 'synced')
      setNotice(failures.length ? 'Refresh finished. Check the connection messages below.' : 'Live statistics refreshed successfully.')
      const historyResponse = await authFetch('/api/social-stats/history?days=365')
      if (historyResponse.ok) setHistory(await historyResponse.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setRefreshing('')
    }
  }

  const summary = useMemo(() => ({
    connected: stats.filter((item) => item.status === 'synced').length,
    followers: stats.reduce((sum, item) => sum + Number(item.data?.followers || 0), 0),
    views: stats.reduce((sum, item) => sum + Number(item.data?.total_views || 0), 0),
  }), [stats])

  return (
    <div className="admin-page social-stats-page">
      <header className="admin-page-header">
        <div>
          <span className="eyebrow">Audience connections</span>
          <h1>Live social statistics</h1>
          <p>Cached platform numbers for the public media kit, with manual values preserved as fallback.</p>
        </div>
        <Button onClick={() => refresh('all')} loading={refreshing === 'all'} disabled={!stats.some((item) => item.configured)}>
          {refreshing === 'all' ? 'Refreshing platforms' : 'Refresh all'}
        </Button>
      </header>

      {(error || notice) && <Feedback tone={error ? 'error' : 'success'} title={error ? 'Could not refresh statistics' : 'Sync complete'}>{error || notice}</Feedback>}

      <section className="social-sync-summary">
        <article><span>Connected platforms</span><strong>{summary.connected} / 2</strong><small>Instagram and YouTube</small></article>
        <article><span>Live audience</span><strong>{compactNumber(summary.followers)}</strong><small>Combined cached followers</small></article>
        <article><span>YouTube channel views</span><strong>{compactNumber(summary.views)}</strong><small>Official channel statistic</small></article>
        <article><span>Refresh policy</span><strong>{stats[0]?.cache_hours || 6}h</strong><small>Public pages use cached values</small></article>
      </section>

      {loading ? (
        <div className="admin-loading"><span className="loading-dot" />Checking platform connections...</div>
      ) : (
        <section className="social-connection-grid">
          {stats.map((item) => {
            const meta = PLATFORM_META[item.platform]
            return (
              <article className={`social-connection-card status-${item.status}`} key={item.platform}>
                <header>
                  <div className={`social-connection-icon platform-${item.platform}`}>{meta.code}</div>
                  <div>
                    <h2>{meta.label}</h2>
                    <p>{meta.description}</p>
                  </div>
                  <span className={`social-connection-status status-${item.status}`}><i />{statusLabel(item)}</span>
                </header>

                {item.status === 'synced' ? (
                  <>
                    <div className="social-live-metrics">
                      <LiveMetric label={item.platform === 'youtube' ? 'Subscribers' : 'Followers'} value={compactNumber(item.data?.followers)} />
                      <LiveMetric label={item.platform === 'youtube' ? 'Channel views' : 'Published posts'} value={compactNumber(item.platform === 'youtube' ? item.data?.total_views : item.data?.media_count)} />
                      <LiveMetric label={item.platform === 'youtube' ? 'Public videos' : 'Account'} value={item.platform === 'youtube' ? compactNumber(item.data?.media_count) : item.data?.username ? `@${item.data.username}` : 'Connected'} />
                    </div>
                    <div className="social-sync-meta">
                      <span>Last synced</span>
                      <strong>{formatDateTime(item.last_synced_at)}</strong>
                    </div>
                  </>
                ) : (
                  <div className="social-setup-state">
                    <strong>{item.configured ? 'The API returned an error' : 'Credentials not added yet'}</strong>
                    <p>{item.error || 'Add the environment variables below, restart the backend, then refresh.'}</p>
                    <div>
                      {meta.variables.map((variable) => <code key={variable}>{variable}</code>)}
                    </div>
                  </div>
                )}

                <footer>
                  <span>{item.last_attempted_at ? `Last checked ${formatRelative(item.last_attempted_at)}` : 'Never checked'}</span>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => refresh(item.platform)}
                    loading={refreshing === item.platform}
                    disabled={!item.configured}
                  >
                    {refreshing === item.platform ? 'Refreshing' : 'Refresh now'}
                  </Button>
                </footer>
              </article>
            )
          })}
        </section>
      )}

      <section className="social-sync-explainer">
        <div>
          <span className="summary-kicker">How caching works</span>
          <h2>Fast public pages without wasting API quota.</h2>
        </div>
        <ol>
          <li><span>01</span><div><strong>Serve cached values</strong><p>Every media-kit visit reads your database, not Meta or YouTube.</p></div></li>
          <li><span>02</span><div><strong>Refresh in the background</strong><p>Stale values are refreshed after the page response, with a retry cooldown on errors.</p></div></li>
          <li><span>03</span><div><strong>Keep manual fallbacks</strong><p>If a token expires, your manually entered stats remain visible instead of showing zero.</p></div></li>
        </ol>
      </section>

      <section className="social-growth-section">
        <header>
          <div><span className="eyebrow">Historical snapshots</span><h2>Audience growth over time</h2></div>
          <p>One snapshot is stored per platform per day, giving the manager reliable month-over-month proof without extra API calls.</p>
        </header>
        <div className="social-growth-grid">
          {Object.keys(PLATFORM_META).map((platform) => (
            <GrowthPanel
              key={platform}
              platform={platform}
              snapshots={history.filter((item) => item.platform === platform)}
            />
          ))}
        </div>
      </section>
    </div>
  )
}

function GrowthPanel({ platform, snapshots }) {
  const meta = PLATFORM_META[platform]
  const values = snapshots.map((item) => Number(item.followers || 0))
  const maximum = Math.max(...values, 1)
  const growth = values.length > 1 ? values[values.length - 1] - values[0] : 0
  const recent = snapshots.slice(-12)
  return (
    <article className="social-growth-panel">
      <div className="social-growth-heading">
        <div className={`social-connection-icon platform-${platform}`}>{meta.code}</div>
        <div><span>{meta.label}</span><strong>{growth >= 0 ? '+' : ''}{compactNumber(growth)} followers</strong></div>
        <small>{snapshots.length} daily snapshot{snapshots.length === 1 ? '' : 's'}</small>
      </div>
      {recent.length > 1 ? (
        <div className="social-growth-chart" aria-label={`${meta.label} follower growth chart`}>
          {recent.map((item) => (
            <div key={item.captured_at} title={`${formatDateTime(item.captured_at)}: ${item.followers.toLocaleString('en-IN')}`}>
              <span style={{ height: `${Math.max(8, (Number(item.followers || 0) / maximum) * 100)}%` }} />
            </div>
          ))}
        </div>
      ) : (
        <div className="social-growth-empty">Refresh on another day to begin the growth chart.</div>
      )}
    </article>
  )
}

function LiveMetric({ label, value }) {
  return <div><span>{label}</span><strong>{value || '—'}</strong></div>
}

function statusLabel(item) {
  if (item.status === 'synced') return 'Live'
  if (item.status === 'error') return 'Needs attention'
  return item.configured ? 'Ready to sync' : 'Not connected'
}

function compactNumber(value) {
  const number = Number(value || 0)
  if (number >= 1000000) return `${(number / 1000000).toFixed(number >= 10000000 ? 0 : 1)}M`
  if (number >= 1000) return `${(number / 1000).toFixed(number >= 10000 ? 0 : 1)}K`
  return number.toLocaleString('en-IN')
}

function formatDateTime(value) {
  if (!value) return 'Never'
  return new Date(value).toLocaleString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit',
  })
}

function formatRelative(value) {
  const minutes = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 60000))
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  if (minutes < 1440) return `${Math.round(minutes / 60)}h ago`
  return `${Math.round(minutes / 1440)}d ago`
}
