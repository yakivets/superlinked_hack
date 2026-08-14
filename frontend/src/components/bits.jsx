export function Meta({ className = '', children, ...rest }) {
  return (
    <span className={`meta ${className}`} {...rest}>
      {children}
    </span>
  )
}

export function formatDate(iso) {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

export function formatTime(iso) {
  return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}

export function formatDuration(s) {
  if (s == null) return null
  const m = Math.floor(s / 60)
  const sec = Math.round(s % 60)
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`
}

export const STATUS_WORDS = {
  processing: 'Transcribing…',
  transcribed: 'Writing notes…',
}

/** Minimal renderer for the synthesis answer: paragraphs plus **bold**. */
export function AnswerText({ text, className = '' }) {
  const paragraphs = text.split(/\n{2,}/).filter(Boolean)
  return (
    <div className={className}>
      {paragraphs.map((p, i) => (
        <p key={i} className="set-line mt-4 first:mt-0" style={{ animationDelay: `${i * 120}ms` }}>
          {p.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g).map((part, j) =>
            part.startsWith('**') ? (
              <strong key={j} className="font-semibold">{part.slice(2, -2)}</strong>
            ) : part.startsWith('*') && part.endsWith('*') && part.length > 2 ? (
              <em key={j}>{part.slice(1, -1)}</em>
            ) : (
              <span key={j}>{part}</span>
            ),
          )}
        </p>
      ))}
    </div>
  )
}
