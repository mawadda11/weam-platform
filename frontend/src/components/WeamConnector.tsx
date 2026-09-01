interface Props {
  className?: string
  variant?: 'background' | 'mark'
}

/**
 * The "harmony" motif: soft paths from three directions (guardian, specialist,
 * center) converging on the child. Decorative only — always aria-hidden.
 */
export default function WeamConnector({ className = '', variant = 'background' }: Props) {
  if (variant === 'mark') {
    return (
      <svg
        className={`weam-connector-mark ${className}`.trim()}
        viewBox="0 0 96 96"
        fill="none"
        aria-hidden="true"
      >
        <path d="M48 50 C 30 38, 20 24, 14 10" stroke="var(--primary-bright)" strokeWidth="2.5" strokeLinecap="round" opacity="0.55" />
        <path d="M48 50 C 66 38, 76 24, 82 10" stroke="var(--teal)" strokeWidth="2.5" strokeLinecap="round" opacity="0.55" />
        <path d="M48 50 C 48 68, 48 78, 48 90" stroke="var(--accent)" strokeWidth="2.5" strokeLinecap="round" opacity="0.55" />
        <circle cx="14" cy="10" r="5" fill="var(--primary-bright)" opacity="0.85" />
        <circle cx="82" cy="10" r="5" fill="var(--teal)" opacity="0.85" />
        <circle cx="48" cy="90" r="5" fill="var(--accent)" opacity="0.85" />
        <circle cx="48" cy="50" r="9" fill="var(--primary)" />
      </svg>
    )
  }

  return (
    <svg
      className={`weam-connector-bg ${className}`.trim()}
      viewBox="0 0 800 800"
      fill="none"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
    >
      <path d="M400 420 C 260 340, 160 260, 70 150" stroke="#4338CA" strokeWidth="2" strokeLinecap="round" opacity="0.12" />
      <path d="M400 420 C 540 340, 660 260, 760 160" stroke="#0F8A82" strokeWidth="2" strokeLinecap="round" opacity="0.12" />
      <path d="M400 420 C 380 560, 360 660, 320 760" stroke="#E8A33D" strokeWidth="2" strokeLinecap="round" opacity="0.14" />
      <circle cx="70" cy="150" r="10" fill="#4338CA" opacity="0.16" />
      <circle cx="760" cy="160" r="10" fill="#0F8A82" opacity="0.16" />
      <circle cx="320" cy="760" r="10" fill="#E8A33D" opacity="0.18" />
      <circle cx="400" cy="420" r="16" fill="#4338CA" opacity="0.10" />
    </svg>
  )
}
