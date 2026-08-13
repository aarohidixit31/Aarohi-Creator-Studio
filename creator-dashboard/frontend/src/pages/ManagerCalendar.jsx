import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { authFetch } from '../api.js'
import { Button, Feedback } from '../components/ui.jsx'


const EVENT_TYPES = [
  ['deadline', 'Deadlines'],
  ['follow_up', 'Follow-ups'],
  ['invoice', 'Payments'],
  ['content', 'Content'],
]


export default function ManagerCalendar() {
  const [month, setMonth] = useState(() => startOfMonth(new Date()))
  const [events, setEvents] = useState([])
  const [enabledTypes, setEnabledTypes] = useState(() => new Set(EVENT_TYPES.map(([value]) => value)))
  const [selectedDate, setSelectedDate] = useState(() => dateKey(new Date()))
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const gridStart = useMemo(() => startOfCalendarGrid(month), [month])
  const gridEnd = useMemo(() => addDays(gridStart, 42), [gridStart])

  useEffect(() => {
    setLoading(true)
    setError('')
    const params = new URLSearchParams({
      start: gridStart.toISOString(),
      end: gridEnd.toISOString(),
    })
    authFetch(`/api/calendar/?${params}`)
      .then(async (response) => {
        if (!response.ok) {
          const body = await response.json().catch(() => null)
          throw new Error(body?.detail || 'Could not load calendar')
        }
        return response.json()
      })
      .then((data) => setEvents(data.events || []))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [gridStart, gridEnd])

  const visibleEvents = useMemo(() => events.filter((event) => enabledTypes.has(event.type)), [events, enabledTypes])
  const eventsByDay = useMemo(() => {
    const grouped = new Map()
    visibleEvents.forEach((event) => {
      const key = dateKey(new Date(event.starts_at))
      grouped.set(key, [...(grouped.get(key) || []), event])
    })
    return grouped
  }, [visibleEvents])
  const days = useMemo(() => Array.from({ length: 42 }, (_, index) => addDays(gridStart, index)), [gridStart])
  const selectedEvents = eventsByDay.get(selectedDate) || []
  const upcoming = visibleEvents
    .filter((event) => new Date(event.starts_at) >= startOfDay(new Date()))
    .slice(0, 8)

  function moveMonth(offset) {
    const next = new Date(month.getFullYear(), month.getMonth() + offset, 1)
    setMonth(next)
    setSelectedDate(dateKey(next))
  }

  function goToday() {
    const today = new Date()
    setMonth(startOfMonth(today))
    setSelectedDate(dateKey(today))
  }

  function toggleType(type) {
    setEnabledTypes((current) => {
      const next = new Set(current)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

  return (
    <div className="admin-page calendar-page">
      <header className="admin-page-header">
        <div>
          <span className="eyebrow">Manager schedule</span>
          <h1>Campaign calendar</h1>
          <p>Every follow-up, deadline, payment and content date in one operational view.</p>
        </div>
        <div className="header-actions">
          <Button variant="secondary" onClick={goToday}>Today</Button>
          <Button to="/admin" icon="→">Open pipeline</Button>
        </div>
      </header>

      {error && <Feedback tone="error" title="Calendar unavailable">{error}</Feedback>}

      <section className="calendar-toolbar manager-card">
        <div className="calendar-month-control">
          <button type="button" onClick={() => moveMonth(-1)} aria-label="Previous month">‹</button>
          <h2>{month.toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })}</h2>
          <button type="button" onClick={() => moveMonth(1)} aria-label="Next month">›</button>
        </div>
        <div className="calendar-filters" aria-label="Calendar event filters">
          {EVENT_TYPES.map(([value, label]) => (
            <button type="button" className={`${enabledTypes.has(value) ? 'active' : ''} event-${value}`} key={value} onClick={() => toggleType(value)}>
              <i />{label}<span>{events.filter((event) => event.type === value).length}</span>
            </button>
          ))}
        </div>
      </section>

      <div className="calendar-layout">
        <section className="manager-card calendar-board">
          <div className="calendar-weekdays">
            {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day) => <span key={day}>{day}</span>)}
          </div>
          <div className={`calendar-grid${loading ? ' loading' : ''}`}>
            {days.map((day) => {
              const key = dateKey(day)
              const dayEvents = eventsByDay.get(key) || []
              const outside = day.getMonth() !== month.getMonth()
              return (
                <button
                  type="button"
                  className={`calendar-day${outside ? ' outside' : ''}${key === selectedDate ? ' selected' : ''}${key === dateKey(new Date()) ? ' today' : ''}`}
                  key={key}
                  onClick={() => setSelectedDate(key)}
                >
                  <span className="calendar-day-number">{day.getDate()}</span>
                  <div className="calendar-day-events">
                    {dayEvents.slice(0, 3).map((event) => (
                      <span className={`calendar-event-chip event-${event.type}`} key={event.key} title={`${event.brand_name || ''} ${event.title}`}>
                        <i />{event.brand_name || event.title}
                      </span>
                    ))}
                    {dayEvents.length > 3 && <em>+{dayEvents.length - 3} more</em>}
                  </div>
                </button>
              )
            })}
          </div>
        </section>

        <aside className="calendar-sidebar">
          <section className="manager-card calendar-agenda-card">
            <header>
              <span>Selected day</span>
              <h2>{humanDate(selectedDate)}</h2>
            </header>
            <div className="calendar-agenda-list">
              {selectedEvents.map((event) => <CalendarAgendaItem event={event} key={event.key} />)}
              {!selectedEvents.length && <div className="calendar-empty-day"><span>✓</span><strong>No scheduled work</strong><p>This day is clear.</p></div>}
            </div>
          </section>

          <section className="manager-card calendar-upcoming-card">
            <header><span>Coming up</span><strong>Next 8 events</strong></header>
            <div>
              {upcoming.map((event) => (
                <Link to={event.href} key={`upcoming-${event.key}`}>
                  <time><b>{new Date(event.starts_at).getDate()}</b>{new Date(event.starts_at).toLocaleDateString('en-IN', { month: 'short' })}</time>
                  <span><strong>{event.brand_name || event.title}</strong><small>{event.title}</small></span>
                  <i className={`event-${event.type}`} />
                </Link>
              ))}
              {!upcoming.length && <p className="calendar-upcoming-empty">No upcoming events in this calendar window.</p>}
            </div>
          </section>
        </aside>
      </div>
    </div>
  )
}


function CalendarAgendaItem({ event }) {
  return (
    <Link className={`calendar-agenda-item event-${event.type}`} to={event.href}>
      <i />
      <div>
        <span>{eventTypeLabel(event.type)} · {formatTime(event.starts_at)}</span>
        <strong>{event.brand_name || event.title}</strong>
        <p>{event.brand_name ? event.title : event.detail}</p>
        {event.amount != null && <em>{money(event.amount)}</em>}
      </div>
      <b>→</b>
    </Link>
  )
}

function eventTypeLabel(type) {
  return EVENT_TYPES.find(([value]) => value === type)?.[1]?.replace(/s$/, '') || type
}

function startOfMonth(date) { return new Date(date.getFullYear(), date.getMonth(), 1) }
function startOfDay(date) { return new Date(date.getFullYear(), date.getMonth(), date.getDate()) }
function addDays(date, count) { const next = new Date(date); next.setDate(next.getDate() + count); return next }
function startOfCalendarGrid(month) {
  const first = startOfMonth(month)
  const mondayOffset = (first.getDay() + 6) % 7
  return addDays(first, -mondayOffset)
}
function dateKey(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}
function humanDate(key) {
  return new Date(`${key}T12:00:00`).toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })
}
function formatTime(value) {
  return new Date(value).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })
}
function money(value) {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value || 0)
}
