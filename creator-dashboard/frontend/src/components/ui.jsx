import { Link } from 'react-router-dom'

export function Button({
  children,
  to,
  href,
  variant = 'primary',
  size = 'md',
  icon,
  iconPosition = 'end',
  iconOnly = false,
  loading = false,
  className = '',
  disabled,
  ...props
}) {
  const classes = `ui-button ui-button-${variant} ui-button-${size} ${iconOnly ? 'ui-button-icon-only' : ''} ${className}`.trim()
  const label = props['aria-label'] || (typeof children === 'string' ? children : undefined)
  const content = iconOnly ? (
    <>
      {loading ? <span className="ui-button-spinner" aria-hidden="true" /> : <span className="ui-button-icon">{icon}</span>}
      <span className="sr-only">{children}</span>
    </>
  ) : (
    <>
      {loading && <span className="ui-button-spinner" aria-hidden="true" />}
      {!loading && icon && iconPosition === 'start' && <span className="ui-button-icon">{icon}</span>}
      <span>{children}</span>
      {!loading && icon && iconPosition === 'end' && <span className="ui-button-icon">{icon}</span>}
    </>
  )

  if (iconOnly && label && !props.title) props.title = label

  if (to) return <Link className={classes} to={to} {...props}>{content}</Link>
  if (href) return <a className={classes} href={href} {...props}>{content}</a>
  return (
    <button className={classes} disabled={disabled || loading} {...props}>
      {content}
    </button>
  )
}

export function Icon({ name, size = 18 }) {
  const common = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': true,
  }
  if (name === 'instagram') return (
    <svg {...common}><rect x="3" y="3" width="18" height="18" rx="5" /><circle cx="12" cy="12" r="4" /><circle cx="17.4" cy="6.7" r=".8" fill="currentColor" stroke="none" /></svg>
  )
  if (name === 'youtube') return (
    <svg {...common}><path d="M21 8.1a3 3 0 0 0-2.1-2.1C17 5.5 12 5.5 12 5.5S7 5.5 5.1 6A3 3 0 0 0 3 8.1 31 31 0 0 0 2.6 12 31 31 0 0 0 3 15.9 3 3 0 0 0 5.1 18c1.9.5 6.9.5 6.9.5s5 0 6.9-.5a3 3 0 0 0 2.1-2.1 31 31 0 0 0 .4-3.9 31 31 0 0 0-.4-3.9Z" /><path d="m10 9 5 3-5 3Z" fill="currentColor" stroke="none" /></svg>
  )
  if (name === 'plus') return (
    <svg {...common}><path d="M12 5v14M5 12h14" /></svg>
  )
  return null
}

export function FormField({ label, hint, error, required, className = '', children }) {
  return (
    <div className={`ui-field ${error ? 'has-error' : ''} ${className}`.trim()}>
      <span className="ui-field-label">
        <span>{label}{required && <em aria-hidden="true">*</em>}</span>
      </span>
      {children}
      {(error || hint) && <small className={error ? 'ui-field-error' : ''}>{error || hint}</small>}
    </div>
  )
}

export function Feedback({ tone = 'info', title, children }) {
  return (
    <div className={`ui-feedback ui-feedback-${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <span className="ui-feedback-mark" aria-hidden="true" />
      <div>
        {title && <strong>{title}</strong>}
        {children && <p>{children}</p>}
      </div>
    </div>
  )
}

export function SegmentedControl({ value, onChange, options, label }) {
  return (
    <div className="ui-segmented" aria-label={label}>
      {options.map((option) => (
        <button
          type="button"
          key={option.value}
          className={value === option.value ? 'active' : ''}
          onClick={() => onChange(option.value)}
          aria-pressed={value === option.value}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
