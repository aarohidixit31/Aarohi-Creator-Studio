import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { API, setToken } from '../api.js'
import { Button, Feedback, FormField } from '../components/ui.jsx'

export default function AdminLogin() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  async function submit(event) {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const body = new URLSearchParams({ username: email, password })
      const response = await fetch(`${API}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
      })
      if (!response.ok) throw new Error('Incorrect email or password.')
      const data = await response.json()
      setToken(data.access_token)
      navigate('/admin')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <section className="login-brand-panel">
        <Link to="/" className="media-logo"><span>AI</span>Aarohi Inframe</Link>
        <div>
          <span className="hero-kicker">Creator operations</span>
          <h1>One place to run every partnership.</h1>
          <p>Manage brand inquiries, your public media kit and invoices without losing context.</p>
        </div>
        <small>Built for Aarohi and her management team.</small>
      </section>
      <section className="login-form-panel">
        <form onSubmit={submit}>
          <div className="eyebrow">Private workspace</div>
          <h2>Welcome back.</h2>
          <p>Sign in to manage your creator studio.</p>
          <FormField label="Email address" required>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
          </FormField>
          <FormField label="Password" required>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
          </FormField>
          {error && <Feedback tone="error" title="Could not sign in">{error}</Feedback>}
          <Button type="submit" loading={loading} icon="->">
            {loading ? 'Signing in...' : 'Open dashboard'}
          </Button>
          <Link className="login-back" to="/">← Back to public media kit</Link>
        </form>
      </section>
    </div>
  )
}
