import { useEffect, useMemo, useState } from 'react'
import { authFetch } from '../api.js'
import { Button } from '../components/ui.jsx'

const STATUSES = ['all', 'draft', 'sent', 'paid', 'overdue']
const money = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

function formatDate(value) {
  if (!value) return 'No due date'
  return new Intl.DateTimeFormat('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric',
  }).format(new Date(value))
}

function effectiveStatus(invoice) {
  if (invoice.status === 'sent' && invoice.due_date && new Date(invoice.due_date) < new Date()) {
    return 'overdue'
  }
  return invoice.status
}

export default function InvoiceList() {
  const [invoices, setInvoices] = useState([])
  const [ledger, setLedger] = useState(null)
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [updatingId, setUpdatingId] = useState(null)
  const [error, setError] = useState('')

  async function load() {
    setError('')
    try {
      const [invoiceRes, ledgerRes] = await Promise.all([
        authFetch('/api/invoices/'),
        authFetch('/api/invoices/ledger'),
      ])
      if (!invoiceRes.ok || !ledgerRes.ok) throw new Error('Could not load your invoices')
      const [invoiceData, ledgerData] = await Promise.all([invoiceRes.json(), ledgerRes.json()])
      setInvoices(invoiceData)
      setLedger(ledgerData)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const visibleInvoices = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    return invoices.filter((invoice) => {
      const matchesStatus = filter === 'all' || effectiveStatus(invoice) === filter
      const matchesQuery = !normalized
        || invoice.invoice_number.toLowerCase().includes(normalized)
        || invoice.brand?.name?.toLowerCase().includes(normalized)
        || invoice.brand?.contact_person?.toLowerCase().includes(normalized)
      return matchesStatus && matchesQuery
    })
  }, [invoices, filter, query])

  async function updateStatus(invoice, status) {
    setUpdatingId(invoice.id)
    setError('')
    try {
      const response = await authFetch(`/api/invoices/${invoice.id}/status?status=${status}`, {
        method: 'PATCH',
      })
      if (!response.ok) throw new Error('Could not update invoice status')
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setUpdatingId(null)
    }
  }

  async function downloadPdf(invoice) {
    setError('')
    try {
      const response = await authFetch(`/api/invoices/${invoice.id}/pdf`)
      if (!response.ok) throw new Error('Could not generate the invoice PDF')
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `${invoice.invoice_number}.pdf`
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="admin-page invoice-page">
      <header className="admin-page-header">
        <div>
          <span className="eyebrow">Finance desk</span>
          <h1>Invoices & ledger</h1>
          <p>Track what has been billed, received, and still needs a follow-up.</p>
        </div>
        <Button to="/admin/invoices/new" icon="+">New invoice</Button>
      </header>

      <section className="ledger-grid" aria-label="Invoice summary">
        <article className="ledger-card primary">
          <span>Total invoiced</span>
          <strong>{money.format(ledger?.total_invoiced || 0)}</strong>
          <small>{ledger?.invoice_count || 0} invoices created</small>
        </article>
        <article className="ledger-card success">
          <span>Received</span>
          <strong>{money.format(ledger?.total_received || 0)}</strong>
          <small>{ledger?.paid_count || 0} paid invoices</small>
        </article>
        <article className="ledger-card warning">
          <span>Outstanding</span>
          <strong>{money.format(ledger?.total_outstanding || 0)}</strong>
          <small>{ledger?.outstanding_count || 0} need attention</small>
        </article>
        <article className="ledger-card">
          <span>Still in draft</span>
          <strong>{money.format(ledger?.total_draft || 0)}</strong>
          <small>Not sent to brands yet</small>
        </article>
      </section>

      <section className="invoice-panel">
        <div className="invoice-toolbar">
          <div className="invoice-filters" role="tablist" aria-label="Filter invoices by status">
            {STATUSES.map((status) => (
              <button
                key={status}
                className={filter === status ? 'active' : ''}
                onClick={() => setFilter(status)}
                type="button"
              >
                {status}
                <span>
                  {status === 'all'
                    ? invoices.length
                    : invoices.filter((invoice) => effectiveStatus(invoice) === status).length}
                </span>
              </button>
            ))}
          </div>
          <label className="invoice-search">
            <span>Search</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Brand or invoice number"
            />
          </label>
        </div>

        {error && <p className="manager-alert error">{error}</p>}

        {loading ? (
          <div className="invoice-empty">Loading your financial desk...</div>
        ) : visibleInvoices.length === 0 ? (
          <div className="invoice-empty">
            <span>INR</span>
            <h2>No invoices found</h2>
            <p>{invoices.length ? 'Try a different filter or search.' : 'Create your first invoice to start the ledger.'}</p>
            {!invoices.length && <Button variant="secondary" to="/admin/invoices/new">Create invoice</Button>}
          </div>
        ) : (
          <div className="invoice-table-wrap">
            <table className="invoice-table">
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Brand</th>
                  <th>Issued</th>
                  <th>Due</th>
                  <th>Amount</th>
                  <th>Status</th>
                  <th><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {visibleInvoices.map((invoice) => {
                  const status = effectiveStatus(invoice)
                  return (
                    <tr key={invoice.id}>
                      <td>
                        <strong className="invoice-number-cell">{invoice.invoice_number}</strong>
                        <span>{invoice.line_items.length} line item{invoice.line_items.length === 1 ? '' : 's'}</span>
                      </td>
                      <td>
                        <strong>{invoice.brand?.name || 'Unknown brand'}</strong>
                        <span>{invoice.brand?.contact_person || invoice.brand?.email || 'No contact'}</span>
                      </td>
                      <td>{formatDate(invoice.created_at)}</td>
                      <td className={status === 'overdue' ? 'due-overdue' : ''}>{formatDate(invoice.due_date)}</td>
                      <td><strong>{money.format(invoice.total)}</strong></td>
                      <td>
                        <select
                          className={`invoice-status status-${status}`}
                          value={status}
                          disabled={updatingId === invoice.id}
                          onChange={(event) => updateStatus(invoice, event.target.value)}
                        >
                          <option value="draft">Draft</option>
                          <option value="sent">Sent</option>
                          <option value="paid">Paid</option>
                          <option value="overdue">Overdue</option>
                        </select>
                      </td>
                      <td>
                        <button className="invoice-download" type="button" onClick={() => downloadPdf(invoice)}>
                          PDF
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
