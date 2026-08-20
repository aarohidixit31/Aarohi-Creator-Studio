import { useEffect, useState } from 'react'
import { API, authFetch } from '../api.js'
import { Button, Feedback, FormField } from './ui.jsx'


export default function AgreementCenter({ collab, onUpdated }) {
  const [agreement, setAgreement] = useState(null)
  const [baseline, setBaseline] = useState('')
  const [working, setWorking] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    authFetch(`/api/agreements/${collab.id}`)
      .then(async (response) => {
        if (!response.ok) throw new Error('Could not load agreement workspace')
        return response.json()
      })
      .then((data) => {
        const normalized = normalize(data)
        setAgreement(normalized)
        setBaseline(JSON.stringify(normalized))
      })
      .catch((err) => setError(err.message))
  }, [collab.id])

  const dirty = agreement && JSON.stringify(agreement) !== baseline

  function patch(field, value) {
    setAgreement((current) => ({ ...current, [field]: value }))
    setNotice('')
  }

  async function save() {
    setWorking('save')
    setError('')
    try {
      const response = await authFetch(`/api/agreements/${collab.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(toPayload(agreement)),
      })
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(body?.detail || 'Could not save agreement')
      }
      const normalized = normalize(await response.json())
      setAgreement(normalized)
      setBaseline(JSON.stringify(normalized))
      setNotice('Agreement draft saved.')
      onUpdated?.()
      return true
    } catch (err) {
      setError(err.message)
      return false
    } finally {
      setWorking('')
    }
  }

  function discardChanges() {
    if (!baseline) return
    setAgreement(JSON.parse(baseline))
    setError('')
    setNotice('Unsaved agreement changes discarded.')
  }

  async function downloadPdf() {
    if (dirty && !(await save())) return
    setWorking('pdf')
    setError('')
    try {
      const response = await authFetch(`/api/agreements/${collab.id}/pdf`)
      if (!response.ok) throw new Error('Could not generate agreement PDF')
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `${agreement.agreement_number}.pdf`
      anchor.click()
      URL.revokeObjectURL(url)
      setNotice('Agreement PDF generated.')
    } catch (err) {
      setError(err.message)
    } finally {
      setWorking('')
    }
  }

  async function sendAgreement() {
    if (dirty) {
      setError('Save your agreement changes before emailing it.')
      return
    }
    if (agreement.status === 'not_created') {
      setError('Save the agreement draft before emailing it.')
      return
    }
    if (!window.confirm(`Email ${agreement.agreement_number} to ${collab.brand.email || 'the brand'}?`)) return
    setWorking('send')
    setError('')
    try {
      const response = await authFetch(`/api/agreements/${collab.id}/send`, { method: 'POST' })
      const body = await response.json().catch(() => null)
      if (!response.ok) throw new Error(body?.detail || 'Could not email agreement')
      const normalized = normalize(body.agreement)
      setAgreement(normalized)
      setBaseline(JSON.stringify(normalized))
      setNotice(body.message)
      onUpdated?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setWorking('')
    }
  }

  async function uploadSigned(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    setWorking('upload')
    setError('')
    try {
      const response = await authFetch(`/api/agreements/${collab.id}/signed`, { method: 'POST', body: form })
      const body = await response.json().catch(() => null)
      if (!response.ok) throw new Error(body?.detail || 'Could not upload signed agreement')
      const normalized = normalize(body)
      setAgreement(normalized)
      setBaseline(JSON.stringify(normalized))
      setNotice('Signed agreement stored permanently.')
      onUpdated?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setWorking('')
    }
  }

  if (!agreement) return <div className="admin-loading"><span className="loading-dot" />Loading agreement center...</div>

  return (
    <div className="agreement-center">
      <section className="agreement-hero">
        <div>
          <span className="eyebrow">Legal & commercial workspace</span>
          <h2>Agreement Center</h2>
          <p>Generate, send, sign and store this campaign agreement without re-entering brand information.</p>
        </div>
        <div className="agreement-hero-status">
          <span className={`agreement-status status-${agreement.status}`}>{statusLabel(agreement.status)}</span>
          <code>{agreement.agreement_number}</code>
        </div>
      </section>

      {(error || notice) && <Feedback tone={error ? 'error' : 'success'} title={error ? 'Agreement action failed' : 'Agreement updated'}>{error || notice}</Feedback>}

      <div className="agreement-layout">
        <section className="detail-card agreement-editor">
          <header><h2>Campaign terms</h2><p>These fields populate the branded PDF sent to the brand.</p></header>
          <div className="detail-card-body">
            <div className="editor-grid two">
              <Field label="Effective date"><input type="date" value={agreement.effective_date} onChange={(event) => patch('effective_date', event.target.value)} /></Field>
              <Field label="Agreement end date"><input type="date" value={agreement.termination_date} onChange={(event) => patch('termination_date', event.target.value)} /></Field>
              <Field label="Total amount (INR)"><input type="number" min="0" value={agreement.total_amount ?? ''} onChange={(event) => patch('total_amount', event.target.value)} /></Field>
              <Field label="Payment deadline (days)"><input type="number" min="0" value={agreement.payment_due_days} onChange={(event) => patch('payment_due_days', event.target.value)} /></Field>
              <Field label="Included revisions"><input type="number" min="0" value={agreement.revision_limit} onChange={(event) => patch('revision_limit', event.target.value)} /></Field>
              <Field label="Content remains live (months)"><input type="number" min="0" value={agreement.content_live_months} onChange={(event) => patch('content_live_months', event.target.value)} /></Field>
            </div>
            <Field label="Deliverables"><textarea rows="4" value={agreement.deliverables} onChange={(event) => patch('deliverables', event.target.value)} /></Field>
            <Field label="Delivery timeline"><input value={agreement.timeline} onChange={(event) => patch('timeline', event.target.value)} /></Field>
            <Field label="Payment structure"><input value={agreement.payment_structure} onChange={(event) => patch('payment_structure', event.target.value)} /></Field>
            <Field label="Usage rights"><textarea rows="5" value={agreement.usage_rights} onChange={(event) => patch('usage_rights', event.target.value)} /></Field>
            <Field label="Additional terms"><textarea rows="4" value={agreement.additional_terms} onChange={(event) => patch('additional_terms', event.target.value)} placeholder="Optional campaign-specific clauses" /></Field>
            <div className="agreement-editor-actions">
              {dirty && <span className="unsaved-indicator"><i />Unsaved agreement changes</span>}
              {dirty && <Button size="sm" variant="ghost" onClick={discardChanges} disabled={Boolean(working)}>Discard</Button>}
              <Button size="sm" onClick={save} loading={working === 'save'} disabled={!dirty}>Save draft</Button>
            </div>
          </div>
        </section>

        <aside className="agreement-actions-panel">
          <section className="detail-card">
            <header><h2>Agreement workflow</h2><p>Complete these steps in order.</p></header>
            <div className="agreement-workflow">
              <WorkflowStep number="01" title="Review terms" complete={agreement.status !== 'not_created'} note="Confirm deliverables, dates, rights and payment." />
              <WorkflowStep number="02" title="Generate PDF" complete={Boolean(agreement.generated_at)} note="Download the branded agreement for review." />
              <WorkflowStep number="03" title="Send to brand" complete={['sent', 'signed'].includes(agreement.status)} note={agreement.sent_at ? `Sent ${formatDate(agreement.sent_at)}` : 'Email the agreement as a PDF attachment.'} />
              <WorkflowStep number="04" title="Store signed copy" complete={agreement.status === 'signed'} note={agreement.signed_at ? `Signed ${formatDate(agreement.signed_at)}` : 'Upload the returned signed PDF or scan.'} />
            </div>
            <div className="agreement-action-stack">
              <Button variant="secondary" onClick={downloadPdf} loading={working === 'pdf'}>Download PDF</Button>
              <Button onClick={sendAgreement} loading={working === 'send'} disabled={!collab.brand.email || agreement.status === 'not_created'}>Email to brand</Button>
              <label className="ui-button ui-button-secondary ui-button-md agreement-upload-button">
                <span>{working === 'upload' ? 'Uploading signed copy...' : 'Upload signed copy'}</span>
                <input type="file" accept="application/pdf,image/jpeg,image/png" onChange={uploadSigned} disabled={Boolean(working)} />
              </label>
              {agreement.signed_file_url && <a className="agreement-signed-link" href={absoluteUrl(agreement.signed_file_url)} target="_blank" rel="noreferrer">View signed agreement ↗</a>}
            </div>
          </section>
          <div className="agreement-legal-note"><strong>Template note</strong><p>This operational template is based on Aarohi Inframe's supplied agreement. Obtain legal advice before relying on it for unusual, high-value, international, exclusivity, or paid-usage arrangements.</p></div>
        </aside>
      </div>
    </div>
  )
}

function WorkflowStep({ number, title, note, complete }) {
  return <div className={complete ? 'complete' : ''}><span>{complete ? '✓' : number}</span><div><strong>{title}</strong><p>{note}</p></div></div>
}
function Field({ label, children }) { return <FormField label={label}>{children}</FormField> }
function statusLabel(status) { return ({ not_created: 'Not created', draft: 'Draft', sent: 'Sent', signed: 'Signed' })[status] || status }
function dateInput(value) { return value ? new Date(value).toISOString().slice(0, 10) : '' }
function normalize(data) {
  return { ...data, effective_date: dateInput(data.effective_date), termination_date: dateInput(data.termination_date), deliverables: data.deliverables || '', timeline: data.timeline || '', payment_structure: data.payment_structure || '', usage_rights: data.usage_rights || '', additional_terms: data.additional_terms || '' }
}
function toPayload(data) {
  return { effective_date: data.effective_date ? new Date(`${data.effective_date}T12:00:00`).toISOString() : null, termination_date: data.termination_date ? new Date(`${data.termination_date}T12:00:00`).toISOString() : null, deliverables: data.deliverables || null, timeline: data.timeline || null, total_amount: data.total_amount === '' ? null : Number(data.total_amount), payment_structure: data.payment_structure, payment_due_days: Number(data.payment_due_days), revision_limit: Number(data.revision_limit), content_live_months: Number(data.content_live_months), usage_rights: data.usage_rights, additional_terms: data.additional_terms || null }
}
function formatDate(value) { return new Date(value).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) }
function absoluteUrl(value) { return /^https?:\/\//i.test(value) ? value : `${API}${value}` }
