import { useEffect, useState } from 'react'
import { getMeeting } from '../api'
import {
  Meta, formatDate, formatTime, formatDuration, shortError, STATUS_WORDS,
} from '../components/bits'

function BackArrow() {
  return (
    <svg viewBox="0 0 14 12" width="12" height="10" aria-hidden="true" className="mr-1 inline-block -translate-y-px">
      <path d="M6 1 L1.5 6 L6 11 M1.5 6 H13" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function Section({ title, children }) {
  return (
    <section className="mt-8">
      <h2 className="text-[0.875rem] font-semibold">{title}</h2>
      <div className="mt-2.5">{children}</div>
    </section>
  )
}

function Tab({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={`cursor-pointer rounded-md px-2.5 py-1 text-[0.875rem] transition-colors ${
        active ? 'bg-ink/[0.06] font-medium text-ink' : 'text-soft hover:text-ink'
      }`}
    >
      {children}
    </button>
  )
}

export default function MeetingPage({ id }) {
  const [meeting, setMeeting] = useState(null)
  const [missing, setMissing] = useState(false)
  const [tab, setTab] = useState('notes')

  useEffect(() => {
    let alive = true
    let timer
    const tick = async () => {
      try {
        const m = await getMeeting(id)
        if (!alive) return
        setMeeting(m)
        if (m.status !== 'done' && m.status !== 'error') timer = setTimeout(tick, 2000)
      } catch {
        if (alive) setMissing(true)
      }
    }
    tick()
    return () => {
      alive = false
      clearTimeout(timer)
    }
  }, [id])

  if (missing) {
    return (
      <div className="mt-10">
        <p className="text-[1.05rem] font-medium">Meeting not found.</p>
        <a href="#/" className="meta mt-2 inline-block text-action no-underline hover:underline"><BackArrow />Back to meetings</a>
      </div>
    )
  }
  if (!meeting) {
    return <p className="ink-pulse mt-10 text-soft">Loading…</p>
  }

  const m = meeting
  const inFlight = m.status === 'processing' || m.status === 'transcribed'
  const failed = m.status === 'error'
  const hasTranscript = m.transcript?.length > 0

  const metaParts = [
    `${formatDate(m.created_at)}, ${formatTime(m.created_at)}`,
    formatDuration(m.duration_s),
  ].filter(Boolean)

  return (
    <div className="mt-2">
      <a href="#/" className="meta no-underline hover:text-ink"><BackArrow />Meetings</a>

      <h1 className="mt-4 text-[1.5rem] font-semibold leading-tight tracking-tight" style={{ textWrap: 'balance' }}>
        {m.title}
      </h1>
      <p className="meta mt-1.5">
        {metaParts.join(' · ')}
        {inFlight && <span className="ink-pulse ml-3 text-action">{STATUS_WORDS[m.status]}</span>}
      </p>
      {failed && <p className="meta mt-2 text-danger">Failed: {shortError(m.error)}</p>}

      {hasTranscript && (
        <div className="mt-6 flex gap-1 border-b border-line pb-3">
          <Tab active={tab === 'notes'} onClick={() => setTab('notes')}>Notes</Tab>
          <Tab active={tab === 'transcript'} onClick={() => setTab('transcript')}>
            Transcript
          </Tab>
        </div>
      )}

      {tab === 'notes' || !hasTranscript ? <Notes m={m} inFlight={inFlight} /> : <Transcript m={m} />}
    </div>
  )
}

function Notes({ m, inFlight }) {
  const actions = m.entities?.action_items ?? []
  const topics = m.entities?.topics ?? []
  return (
    <div>
      {m.notes?.summary ? (
        <p className="mt-6 leading-[1.7]">{m.notes.summary}</p>
      ) : inFlight ? (
        <p className="ink-pulse mt-6 text-soft">Notes are being written…</p>
      ) : null}

      {m.notes?.decisions?.length > 0 && (
        <Section title="Decisions">
          <ul className="space-y-2">
            {m.notes.decisions.map((d, i) => (
              <li key={i} className="flex gap-2.5 leading-relaxed">
                <span className="select-none text-faint">·</span>
                <span>{d}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {actions.length > 0 && (
        <Section title="Action items">
          <ul className="space-y-2">
            {actions.map((a, i) => (
              <li key={i} className="flex items-baseline gap-2.5 leading-relaxed">
                <svg viewBox="0 0 14 14" width="13" height="13" aria-hidden="true" className="shrink-0 translate-y-[1.5px] text-faint">
                  <rect x="1" y="1" width="12" height="12" rx="3.5" fill="none" stroke="currentColor" strokeWidth="1.4" />
                </svg>
                <span>
                  {a.text}
                  {a.owner && <Meta className="ml-2">{a.owner}</Meta>}
                </span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {m.notes?.open_questions?.length > 0 && (
        <Section title="Open questions">
          <ul className="space-y-2">
            {m.notes.open_questions.map((q, i) => (
              <li key={i} className="flex gap-2.5 leading-relaxed text-soft">
                <span className="select-none text-faint">·</span>
                <span>{q}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {topics.length > 0 && (
        <Section title="Topics">
          <div className="flex flex-wrap gap-1.5">
            {topics.map((t) => (
              <span key={t} className="rounded-full bg-ink/[0.05] px-2.5 py-1 text-[0.8125rem] text-soft">
                {t}
              </span>
            ))}
          </div>
        </Section>
      )}
    </div>
  )
}

function Transcript({ m }) {
  const turns = m.transcript
  const speakers = [...new Set(turns.map((t) => t.speaker))]
  return (
    <div>
      {m.notes?.summary && (
        <div className="mt-6 rounded-xl border border-line bg-panel p-5 shadow-[0_1px_2px_rgb(31_30_28_/_0.04)]">
          <p className="leading-[1.65]">{m.notes.summary}</p>
          <p className="meta mt-3 border-t border-line pt-3">
            AI summary · written from the raw transcript below
          </p>
        </div>
      )}
      <p className="meta mt-6">
        {turns.length} {turns.length === 1 ? 'turn' : 'turns'} · {speakers.length}{' '}
        {speakers.length === 1 ? 'speaker' : 'speakers'}
      </p>
      <ol className="mt-4 space-y-4">
        {turns.map((t, i) => (
          <li key={i} className="grid grid-cols-[auto_1fr] items-baseline gap-x-3">
            <span className="rounded-md bg-ink/[0.05] px-2 py-0.5 text-[0.8125rem] font-medium whitespace-nowrap">
              {t.speaker}
            </span>
            <p className="text-[0.9375rem] leading-relaxed">{t.text}</p>
          </li>
        ))}
      </ol>
    </div>
  )
}
