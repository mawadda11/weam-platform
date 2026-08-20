import { Link } from 'react-router-dom'

interface Props {
  to?: string
  compact?: boolean
  light?: boolean
  className?: string
}

export default function WeamLogo({ to, compact = false, light = false, className = '' }: Props) {
  const content = (
    <span className={`weam-logo ${compact ? 'compact' : ''} ${light ? 'light' : ''} ${className}`.trim()}>
      <span className="weam-word" aria-label="Weam">
        Weam
        <span className="weam-people" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
      </span>
      {!compact && <span className="weam-tagline">كل رحلة تستحق أن تُرى</span>}
    </span>
  )

  return to ? <Link to={to} className="weam-logo-link">{content}</Link> : content
}
