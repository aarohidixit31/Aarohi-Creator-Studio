import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { authFetch, clearToken, getToken } from '../api.js'

const NAV_GROUPS = [
  {
    label: 'Workspace',
    items: [
      { to: '/admin', end: true, label: 'Pipeline', icon: 'grid', activePrefixes: ['/admin/collabs/'] },
      { to: '/admin/attention', label: 'Needs attention', icon: 'alert', badge: 'attention' },
      { to: '/admin/calendar', label: 'Calendar', icon: 'calendar' },
    ],
  },
  {
    label: 'Library',
    items: [
      { to: '/admin/brands', label: 'Brands', icon: 'brands' },
    ],
  },
  {
    label: 'Publishing',
    items: [
      { to: '/admin/media-kit', label: 'Media kit', icon: 'spark' },
      { to: '/admin/social-stats', label: 'Live statistics', icon: 'chart' },
    ],
  },
  {
    label: 'Finance',
    items: [
      { to: '/admin/invoices', end: true, label: 'Earnings & invoices', icon: 'invoice' },
      { to: '/admin/invoices/new', label: 'Create invoice', icon: 'plus' },
    ],
  },
]

export default function AdminLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('admin_sidebar_collapsed') === 'true')
  const [attentionCount, setAttentionCount] = useState(0)

  useEffect(() => {
    if (!getToken()) {
      navigate('/admin/login')
      return
    }
    authFetch('/api/collabs/attention')
      .then((response) => response.ok ? response.json() : null)
      .then((data) => setAttentionCount(data?.summary?.total || 0))
      .catch(() => {})
  }, [navigate, location.pathname])

  function toggleSidebar() {
    setCollapsed((current) => {
      localStorage.setItem('admin_sidebar_collapsed', String(!current))
      return !current
    })
  }

  function logout() {
    clearToken()
    navigate('/admin/login')
  }

  return (
    <div className={`admin-shell${collapsed ? ' sidebar-collapsed' : ''}`}>
      <aside className="admin-sidebar">
        <div className="admin-brand-row">
          <NavLink className="admin-brand" to="/admin" title="Aarohi Inframe Creator Studio">
            <span className="admin-brand-mark">AI</span>
            <div className="admin-brand-copy">
              <strong>Aarohi Inframe</strong>
              <span><i /> Creator studio</span>
            </div>
          </NavLink>
          <button className="sidebar-collapse-button" type="button" onClick={toggleSidebar} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
            <NavIcon name="collapse" />
          </button>
        </div>

        <div className="admin-workspace-label">
          <span>Manager workspace</span>
          <em>Private</em>
        </div>

        <nav className="admin-nav" aria-label="Admin navigation">
          {NAV_GROUPS.map((group) => (
            <div className="admin-nav-group" key={group.label}>
              <span className="admin-nav-heading">{group.label}</span>
              <div>
                {group.items.map((item) => {
                  const prefixActive = item.activePrefixes?.some((prefix) => location.pathname.startsWith(prefix))
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end={item.end}
                      title={collapsed ? item.label : undefined}
                      className={({ isActive }) => `admin-nav-link${isActive || prefixActive ? ' active' : ''}`}
                    >
                      <span className="admin-nav-icon"><NavIcon name={item.icon} /></span>
                      <span className="admin-nav-label">{item.label}</span>
                      {item.badge === 'attention' && attentionCount > 0 && <span className="admin-nav-badge">{attentionCount > 99 ? '99+' : attentionCount}</span>}
                    </NavLink>
                  )
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="admin-sidebar-bottom">
          <a className="admin-preview-link" href="/" target="_blank" rel="noreferrer" title="Open public media kit">
            <span className="admin-preview-icon"><NavIcon name="external" /></span>
            <span className="admin-preview-copy"><strong>Public media kit</strong><small>View your live profile</small></span>
            <span className="admin-preview-arrow">&#8599;</span>
          </a>
          <div className="admin-user-row">
            <span className="admin-user-avatar">AD</span>
            <span className="admin-user-copy"><strong>Aarohi</strong><small>Administrator</small></span>
            <button className="admin-logout" onClick={logout} aria-label="Log out" title="Log out"><NavIcon name="logout" /></button>
          </div>
        </div>
      </aside>

      <main className="admin-main">
        <Outlet />
      </main>
    </div>
  )
}

function NavIcon({ name }) {
  const paths = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></>,
    alert: <><path d="M12 3 2.8 19a1.3 1.3 0 0 0 1.1 2h16.2a1.3 1.3 0 0 0 1.1-2L12 3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M8 3v4M16 3v4M3 10h18"/><path d="M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01"/></>,
    brands: <><path d="M4 21V7l8-4 8 4v14"/><path d="M9 21v-5h6v5M8 9h.01M12 9h.01M16 9h.01M8 13h.01M12 13h.01M16 13h.01"/></>,
    play: <><rect x="3" y="4" width="18" height="16" rx="3"/><path d="m10 9 5 3-5 3V9Z"/></>,
    spark: <><path d="m12 3 1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3Z"/><path d="m19 15 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15ZM5 13l.7 1.8 1.8.7-1.8.7L5 18l-.7-1.8-1.8-.7 1.8-.7L5 13Z"/></>,
    chart: <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></>,
    invoice: <><path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z"/><path d="M9 8h6M9 12h6M9 16h3"/></>,
    plus: <><circle cx="12" cy="12" r="9"/><path d="M12 8v8M8 12h8"/></>,
    external: <><path d="M14 4h6v6M20 4l-9 9"/><path d="M18 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h6"/></>,
    logout: <><path d="M10 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h5M14 8l4 4-4 4M18 12H9"/></>,
    collapse: <><path d="M9 5 4 12l5 7M15 5l5 7-5 7"/></>,
  }
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}
