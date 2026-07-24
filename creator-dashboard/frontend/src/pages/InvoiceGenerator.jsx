import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { authFetch, getToken } from '../api.js'
import { Button, Feedback, FormField } from '../components/ui.jsx'

const EMPTY_ITEM = { description: '', quantity: 1, rate: '' }
const money = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 2,
})

export default function InvoiceGenerator() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [brands, setBrands] = useState([])
  const [brandId, setBrandId] = useState(searchParams.get('brand_id') || '')
  const [collabId] = useState(searchParams.get('collab_id') || '')
  const [newBrand, setNewBrand] = useState({ name: '', contact_person: '', email: '' })
  const [showNewBrand, setShowNewBrand] = useState(false)
  const [items, setItems] = useState([{ ...EMPTY_ITEM }])
  const [taxPercent, setTaxPercent] = useState(0)
  const [paymentTerms, setPaymentTerms] = useState('Due within 15 days')
  const [dueDate, setDueDate] = useState('')
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')
  const [pdfUrl, setPdfUrl] = useState('')
  const [invoiceNumber, setInvoiceNumber] = useState('')

  useEffect(() => {
    if (!getToken()) {
      navigate('/admin/login')
      return
    }
    authFetch('/api/brands/')
      .then((response) => {
        if (!response.ok) throw new Error('Could not load brands')
        return response.json()
      })
      .then(setBrands)
      .catch((err) => setError(err.message))

    if (collabId) {
      authFetch(`/api/collabs/${collabId}`)
        .then((response) => response.json())
        .then((collab) => {
          setBrandId(String(collab.brand_id))
          if (collab.deliverables || collab.campaign_type) {
            setItems([{
              description: collab.deliverables || collab.campaign_type,
              quantity: 1,
              rate: collab.budget || '',
            }])
          }
        })
    }
  }, [collabId, navigate])

  function updateItem(index, field, value) {
    setItems((current) => current.map((item, itemIndex) => (
      itemIndex === index ? { ...item, [field]: value } : item
    )))
  }

  function removeItem(index) {
    setItems((current) => current.filter((_, itemIndex) => itemIndex !== index))
  }

  const subtotal = items.reduce(
    (sum, item) => sum + (Number(item.quantity) || 0) * (Number(item.rate) || 0),
    0,
  )
  const tax = subtotal * (Number(taxPercent) || 0) / 100
  const total = subtotal + tax

  async function submit(event) {
    event.preventDefault()
    setError('')
    setStatus('sending')
    try {
      let finalBrandId = brandId
      if (showNewBrand) {
        const brandResponse = await authFetch('/api/brands/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newBrand),
        })
        if (!brandResponse.ok) throw new Error('Could not create the brand')
        finalBrandId = (await brandResponse.json()).id
      }

      if (!finalBrandId) throw new Error('Select a brand before generating the invoice')

      const response = await authFetch('/api/invoices/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          brand_id: Number(finalBrandId),
          collab_id: collabId ? Number(collabId) : null,
          line_items: items.map((item) => ({
            description: item.description,
            quantity: Number(item.quantity),
            rate: Number(item.rate),
          })),
          tax_percent: Number(taxPercent),
          payment_terms: paymentTerms,
          due_date: dueDate ? new Date(`${dueDate}T12:00:00`).toISOString() : null,
        }),
      })
      if (!response.ok) throw new Error('Could not create the invoice')
      const invoice = await response.json()

      const pdfResponse = await authFetch(`/api/invoices/${invoice.id}/pdf`)
      if (!pdfResponse.ok) throw new Error('Invoice created, but the PDF could not be generated')
      const url = URL.createObjectURL(await pdfResponse.blob())
      setPdfUrl(url)
      setInvoiceNumber(invoice.invoice_number)
      setStatus('done')
    } catch (err) {
      setError(err.message || 'Something went wrong')
      setStatus('error')
    }
  }

  if (status === 'done') {
    return (
      <div className="admin-page invoice-complete-page">
        <div className="invoice-complete-card">
          <div className="invoice-complete-mark">PDF</div>
          <span className="eyebrow">Invoice ready</span>
          <h1>{invoiceNumber}</h1>
          <p>The invoice is saved in your ledger and ready to share with the brand.</p>
          <div className="invoice-complete-actions">
            <Button href={pdfUrl} download={`${invoiceNumber}.pdf`} icon="↓">Download PDF</Button>
            <Button variant="secondary" onClick={() => navigate('/admin/invoices')}>Open invoice ledger</Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="admin-page invoice-builder-page">
      <header className="admin-page-header">
        <div>
          <span className="eyebrow">{collabId ? `From collaboration #${collabId}` : 'Finance desk'}</span>
          <h1>Create invoice</h1>
          <p>Build a clear, branded invoice and save it directly to your ledger.</p>
        </div>
        <Button variant="secondary" onClick={() => navigate('/admin/invoices')}>Back to ledger</Button>
      </header>

      <form className="invoice-builder-layout" onSubmit={submit}>
        <div className="invoice-builder-main">
          <BuilderCard number="01" title="Bill to" description="Choose an existing CRM brand or create one.">
            {!showNewBrand ? (
              <>
                <FormField label="Brand" required>
                  <select value={brandId} onChange={(event) => setBrandId(event.target.value)} required>
                    <option value="">Select a brand...</option>
                    {brands.map((brand) => <option key={brand.id} value={brand.id}>{brand.name}</option>)}
                  </select>
                </FormField>
                <Button type="button" size="sm" variant="ghost" icon="+" onClick={() => setShowNewBrand(true)}>
                  Add a new brand
                </Button>
              </>
            ) : (
              <div className="invoice-new-brand">
                <div className="invoice-field-grid">
                  <FormField label="Brand name" required>
                    <input value={newBrand.name} onChange={(event) => setNewBrand({ ...newBrand, name: event.target.value })} required />
                  </FormField>
                  <FormField label="Contact person">
                    <input value={newBrand.contact_person} onChange={(event) => setNewBrand({ ...newBrand, contact_person: event.target.value })} />
                  </FormField>
                </div>
                <FormField label="Email">
                  <input type="email" value={newBrand.email} onChange={(event) => setNewBrand({ ...newBrand, email: event.target.value })} />
                </FormField>
                <Button type="button" size="sm" variant="ghost" onClick={() => setShowNewBrand(false)}>
                  Use an existing brand
                </Button>
              </div>
            )}
          </BuilderCard>

          <BuilderCard number="02" title="Line items" description="Describe exactly what the brand is paying for.">
            <div className="invoice-line-items">
              <div className="invoice-line-labels"><span>Description</span><span>Qty</span><span>Rate</span><span /></div>
              {items.map((item, index) => (
                <div className="invoice-line-row" key={index}>
                  <input
                    value={item.description}
                    onChange={(event) => updateItem(index, 'description', event.target.value)}
                    placeholder="e.g. Instagram Reel integration"
                    required
                  />
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={item.quantity}
                    onChange={(event) => updateItem(index, 'quantity', event.target.value)}
                    aria-label="Quantity"
                    required
                  />
                  <div className="invoice-rate-input">
                    <span>₹</span>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={item.rate}
                      onChange={(event) => updateItem(index, 'rate', event.target.value)}
                      aria-label="Rate"
                      required
                    />
                  </div>
                  <button
                    type="button"
                    className="invoice-remove-line"
                    onClick={() => removeItem(index)}
                    disabled={items.length === 1}
                    aria-label="Remove line item"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
            <Button type="button" size="sm" variant="secondary" icon="+" onClick={() => setItems((current) => [...current, { ...EMPTY_ITEM }])}>
              Add line item
            </Button>
          </BuilderCard>

          <BuilderCard number="03" title="Payment details" description="Set the tax, due date, and terms shown on the PDF.">
            <div className="invoice-field-grid">
              <FormField label="Tax percentage">
                <input type="number" min="0" step="0.01" value={taxPercent} onChange={(event) => setTaxPercent(event.target.value)} />
              </FormField>
              <FormField label="Due date">
                <input type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
              </FormField>
            </div>
            <FormField label="Payment terms">
              <input value={paymentTerms} onChange={(event) => setPaymentTerms(event.target.value)} />
            </FormField>
          </BuilderCard>
        </div>

        <aside className="invoice-preview-card">
          <div className="invoice-preview-heading">
            <span className="eyebrow">Live total</span>
            <strong>{money.format(total)}</strong>
            <small>Invoice preview</small>
          </div>
          <div className="invoice-preview-lines">
            {items.filter((item) => item.description).map((item, index) => (
              <div key={index}>
                <span>{item.description}</span>
                <strong>{money.format((Number(item.quantity) || 0) * (Number(item.rate) || 0))}</strong>
              </div>
            ))}
            {!items.some((item) => item.description) && <p>Add a line item to preview the invoice.</p>}
          </div>
          <div className="invoice-preview-totals">
            <div><span>Subtotal</span><strong>{money.format(subtotal)}</strong></div>
            <div><span>Tax ({Number(taxPercent) || 0}%)</span><strong>{money.format(tax)}</strong></div>
            <div className="grand-total"><span>Total</span><strong>{money.format(total)}</strong></div>
          </div>
          {error && <Feedback tone="error" title="Could not generate invoice">{error}</Feedback>}
          <Button type="submit" loading={status === 'sending'} icon="->" className="invoice-generate-button">
            {status === 'sending' ? 'Generating invoice' : 'Generate invoice PDF'}
          </Button>
          <small className="invoice-save-note">The invoice will also be saved to your ledger as a draft.</small>
        </aside>
      </form>
    </div>
  )
}

function BuilderCard({ number, title, description, children }) {
  return (
    <section className="invoice-builder-card">
      <header>
        <span>{number}</span>
        <div><h2>{title}</h2><p>{description}</p></div>
      </header>
      <div className="invoice-builder-body">{children}</div>
    </section>
  )
}
