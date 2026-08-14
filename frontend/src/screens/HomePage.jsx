import { useEffect, useRef, useState } from 'react'
import { searchMeetings, askSynthesis } from '../api'
import {
  Meta, AnswerText,
  formatDate, formatTime, formatDuration, shortError, STATUS_WORDS,
} from '../components/bits'

export default function HomePage({ meetings }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const [answer, setAnswer] = useState(null)
  const [asking, setAsking] = useState(false)
  const debounce = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    clearTimeout(debounce.current)
    const q = query.trim()
    if (!q) {
      setResults(null)
      return
    }
    debounce.current = setTimeout(async () => {
      try {
        const data = await searchMeetings(q)
        setResults(data.results)
      } catch {
        setResults([])
      }
    }, 280)
    return () => clearTimeout(debounce.current)
  }, [query])

  const ask = async () => {
    const q = query.trim()
    if (!q || asking) return
    setAsking(true)
    setAnswer(null)
    try {
      setAnswer(await askSynthesis(q))
    } catch {
      setAnswer({ answer: 'Could not reach the backend.', sources: [] })
    } finally {
      setAsking(false)
    }
  }

  const clear = () => {
    setQuery('')
    setResults(null)
    setAnswer(null)
    inputRef.current?.focus()
  }

  return (
    <div>
      <div className="relative mt-2">
        <svg
          viewBox="0 0 20 20"
          width="16"
          height="16"
          aria-hidden="true"
          className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-faint"
        >
          <circle cx="9" cy="9" r="6" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <path d="M13.5 13.5 L17.5 17.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
        <input
          ref={inputRef}
          type="text"
          value={query}
          autoFocus
          spellCheck={false}
          placeholder="Search or ask anything"
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') ask()
            if (e.key === 'Escape') clear()
          }}
          className="w-full rounded-xl border border-line bg-panel py-3 pl-11 pr-24 text-[0.9375rem] shadow-[0_1px_2px_rgb(31_30_28_/_0.04)] transition-[border-color,box-shadow] placeholder:text-faint focus:border-action/60 focus:shadow-[0_0_0_3px_rgb(37_99_235_/_0.12)]"
          aria-label="Search or ask anything"
        />
        {query.trim() && (
          <button
            onClick={ask}
            disabled={asking}
            className="absolute top-1/2 right-2.5 -translate-y-1/2 cursor-pointer rounded-lg bg-action px-3 py-1.5 text-[0.8125rem] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            Ask
          </button>
        )}
      </div>

      {asking && <p className="ink-pulse mt-6 text-soft">Thinking across meetings…</p>}

      {answer && !asking && (
        <section className="mt-6 rounded-xl border border-line bg-panel p-5 shadow-[0_1px_2px_rgb(31_30_28_/_0.04)]">
          <AnswerText text={answer.answer} className="leading-[1.65]" />
          {answer.sources.length > 0 && (
            <p className="meta mt-4 border-t border-line pt-3">
              Sources:{' '}
              {answer.sources.map((s, i) => (
                <span key={s.id}>
                  {i > 0 && ', '}
                  <a href={`#/meeting/${s.id}`} className="text-action no-underline hover:underline">
                    {s.title}
                  </a>
                </span>
              ))}
            </p>
          )}
        </section>
      )}

      {results !== null ? (
        <ResultsList results={results} query={query} />
      ) : (
        <MeetingList meetings={meetings} />
      )}
    </div>
  )
}

function Row({ href, title, summary, metaLine, note }) {
  return (
    <a
      href={href}
      className="-mx-3 block rounded-lg px-3 py-4 no-underline transition-colors hover:bg-ink/[0.03]"
    >
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="truncate text-[0.9375rem] font-semibold">{title}</h2>
        {metaLine && <Meta className="shrink-0">{metaLine}</Meta>}
      </div>
      {summary && (
        <p
          className="mt-1 text-[0.875rem] leading-relaxed text-soft"
          style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
        >
          {summary}
        </p>
      )}
      {note}
    </a>
  )
}

function Divided({ children }) {
  return <div className="mt-4 divide-y divide-line">{children}</div>
}

function ResultsList({ results, query }) {
  if (results.length === 0) {
    return <p className="mt-8 text-soft">No matches for “{query.trim()}”.</p>
  }
  return (
    <Divided>
      {results.map((r) => (
        <Row
          key={r.id}
          href={`#/meeting/${r.id}`}
          title={r.title}
          summary={r.summary}
          metaLine={`${formatDate(r.created_at)} · ${Math.round(r.score * 100)}% match`}
        />
      ))}
    </Divided>
  )
}

function MeetingList({ meetings }) {
  if (meetings === null) {
    return <p className="ink-pulse mt-8 text-soft">Loading…</p>
  }
  if (meetings.length === 0) {
    return (
      <div className="mt-12 text-center">
        <p className="text-[1.05rem] font-medium">No meetings yet</p>
        <p className="mx-auto mt-1.5 max-w-[38ch] leading-relaxed text-soft">
          Press record on the device and the meeting will appear here as it happens.
        </p>
      </div>
    )
  }
  return (
    <Divided>
      {meetings.map((m) => {
        const inFlight = m.status === 'processing' || m.status === 'transcribed'
        const failed = m.status === 'error'
        const when = `${formatDate(m.created_at)}, ${formatTime(m.created_at)}`
        const dur = formatDuration(m.duration_s)
        return (
          <Row
            key={m.id}
            href={`#/meeting/${m.id}`}
            title={m.title}
            summary={m.notes?.summary}
            metaLine={dur ? `${when} · ${dur}` : when}
            note={
              inFlight ? (
                <p className="meta ink-pulse mt-1.5 text-action">{STATUS_WORDS[m.status]}</p>
              ) : failed ? (
                <p className="meta mt-1.5 text-danger">Failed: {shortError(m.error)}</p>
              ) : null
            }
          />
        )
      })}
    </Divided>
  )
}
