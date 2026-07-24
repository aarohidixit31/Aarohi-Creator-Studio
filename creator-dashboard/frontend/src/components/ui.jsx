import { Link } from 'react-router-dom'

export function Button({
  children,
  to,
  href,
  variant = 'primary',
  size = 'md',
  icon,
  iconPosition = 'end',
  loading = false,
  className = '',
  disabled,
  ...props
}) {
  const classes = `ui-button ui-button-${variant} ui-button-${size} ${className}`.trim()
  const content = (
    <>
      {loading && <span className="ui-button-spinner" aria-hidden="true" />}
      {!loading && icon && iconPosition === 'start' && <span className="ui-button-icon">{icon}</span>}
      <span>{children}</span>
      {!loading && icon && iconPosition === 'end' && <span className="ui-button-icon">{icon}</span>}
    </>
  )

  if (to) return <Link className={classes} to={to} {...props}>{content}</Link>
  if (href) return <a className={classes} href={href} {...props}>{content}</a>
  return (
    <button className={classes} disabled={disabled || loading} {...props}>
      {content}
    </button>
  )
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
