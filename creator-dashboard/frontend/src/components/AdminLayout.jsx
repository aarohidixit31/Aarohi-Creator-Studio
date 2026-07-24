import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { clearToken, getToken } from '../api.js'
import { useEffect } from 'react'

const NAV = [
  { to: '/admin', end: true, label: 'Overview', icon: '01' },
  { to: '/admin/attention', label: 'Needs attention', icon: '!' },
  { to: '/admin/brands', label: 'Brands', icon: '02' },
  { to: '/admin/media-kit', label: 'Media kit', icon: '03' },
  { to: '/admin/invoices', end: true, label: 'Invoices', icon: '04' },
  { to: '/admin/invoices/new', label: 'New invoice', icon: '+' },
]

export default function AdminLayout() {
  const navigate = useNavigate()

  useEffect(() => {
    if (!getToken()) navigate('/admin/login')
  }, [navigate])

  function logout() {
    clearToken()
    navigate('/admin/login')
  }

  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <div className="admin-brand">
          <span className="admin-brand-mark">AI</span>
          <div>
            <strong>Aarohi Inframe</strong>
            <span>Creator studio</span>
          </div>
        </div>

        <nav className="admin-nav">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `admin-nav-link${isActive ? ' active' : ''}`}
            >
              <span className="admin-nav-icon">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="admin-sidebar-bottom">
          <a className="admin-preview-link" href="/" target="_blank" rel="noreferrer">
            View public media kit <span>↗</span>
          </a>
          <button className="admin-logout" onClick={logout}>Log out</button>
        </div>
      </aside>

      <main className="admin-main">
        <Outlet />
      </main>
    </div>
  )
}
