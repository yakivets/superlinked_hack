import { useEffect, useState } from 'react'
import { getMeeting } from '../api'
import MeetingChat from '../components/MeetingChat'
import {
  Meta, formatDate, formatTime, formatDuration, STATUS_WORDS,
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

export default function MeetingPage({ id }) {
  const [meeting, setMeeting] = useState(null)
  const [missing, setMissing] = useState(false)

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
  const actions = m.entities?.action_items ?? []
  const topics = m.entities?.topics ?? []

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
      {failed && <p className="meta mt-2 text-danger">Failed: {m.error}</p>}

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

      {m.transcript?.length > 0 && <Transcript turns={m.transcript} />}

      <MeetingChat meetingId={id} ready={m.status === 'done'} />
    </div>
  )
}

function Transcript({ turns }) {
  const [open, setOpen] = useState(false)
  return (
    <section className="mt-8 border-t border-line pt-5 pb-4">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full cursor-pointer items-baseline justify-between text-left"
        aria-expanded={open}
      >
        <span className="text-[0.875rem] font-semibold">
          Transcript
          <Meta className="ml-2 font-normal">{turns.length} {turns.length === 1 ? 'turn' : 'turns'}</Meta>
        </span>
        <span className="meta text-action">{open ? 'Hide' : 'Show'}</span>
      </button>
      {open && (
        <ol className="mt-4 space-y-3.5">
          {turns.map((t, i) => (
            <li key={i} className="text-[0.9375rem] leading-relaxed">
              <span className="mr-2 font-medium text-soft">{t.speaker}</span>
              {t.text}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
