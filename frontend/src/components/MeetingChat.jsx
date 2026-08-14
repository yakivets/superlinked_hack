import { useEffect, useRef, useState } from 'react'
import { askMeeting, relatedMeetings } from '../api'
import { AnswerText, Meta } from './bits'

const SUGGESTIONS = [
  'What was decided?',
  'What is still unresolved?',
  'Who owns what?',
]

function SendArrow() {
  return (
    <svg viewBox="0 0 14 12" width="12" height="10" aria-hidden="true">
      <path
        d="M8 1 L12.5 6 L8 11 M12.5 6 H1"
        fill="none" stroke="currentColor" strokeWidth="1.6"
        strokeLinecap="round" strokeLinejoin="round"
      />
    </svg>
  )
}

export default function MeetingChat({ meetingId, ready }) {
  const [turns, setTurns] = useState([])
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
  const [related, setRelated] = useState([])
  const [failed, setFailed] = useState(null)
  const endRef = useRef(null)

  useEffect(() => {
    let alive = true
    relatedMeetings(meetingId)
      .then((r) => alive && setRelated(r.related ?? []))
      .catch(() => {})
    return () => { alive = false }
  }, [meetingId])

  useEffect(() => {
    if (turns.length) endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [turns, pending])

  async function ask(question) {
    const q = question.trim()
    if (!q || pending) return

    // Send the prior exchange as history so follow-ups resolve pronouns.
    const history = turns.map((t) => ({ role: t.role, content: t.content }))
    setTurns((t) => [...t, { role: 'user', content: q }])
    setDraft('')
    setPending(true)
    setFailed(null)

    try {
      const r = await askMeeting(meetingId, q, history)
      setTurns((t) => [...t, { role: 'assistant', content: r.answer, sources: r.sources ?? [] }])
    } catch (e) {
      setFailed(e.message)
    } finally {
      setPending(false)
    }
  }

  if (!ready) {
    return (
      <section className="mt-8 border-t border-line pt-5">
        <h2 className="text-[0.875rem] font-semibold">Ask about this meeting</h2>
        <p className="meta mt-2">Available once the notes are written.</p>
      </section>
    )
  }

  return (
    <section className="mt-8 border-t border-line pt-5 pb-4">
      <h2 className="text-[0.875rem] font-semibold">
        Ask about this meeting
        {related.length > 0 && (
          <Meta className="ml-2 font-normal">
            + {related.length} related {related.length === 1 ? 'meeting' : 'meetings'}
          </Meta>
        )}
      </h2>

      {related.length > 0 && (
        <p className="meta mt-1.5">
          Also drawing on {related.map((r) => r.title).join(', ')}
        </p>
      )}

      {turns.length > 0 && (
        <div className="mt-5 space-y-5">
          {turns.map((t, i) =>
            t.role === 'user' ? (
              <p key={i} className="set-line flex gap-2.5 leading-relaxed font-medium">
                <span className="select-none text-faint">›</span>
                <span>{t.content}</span>
              </p>
            ) : (
              <div key={i} className="set-line">
                <AnswerText text={t.content} className="leading-[1.7]" />
                {t.sources?.length > 0 && (
                  <p className="meta mt-2">
                    From {t.sources.map((s) => s.title).join(' · ')}
                  </p>
                )}
              </div>
            ),
          )}
          {pending && <p className="ink-pulse text-soft">Reading the transcript…</p>}
          <div ref={endRef} />
        </div>
      )}

      {failed && <p className="meta mt-3 text-danger">Could not answer: {failed}</p>}

      {turns.length === 0 && !pending && (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => ask(s)}
              className="cursor-pointer rounded-full bg-ink/[0.05] px-2.5 py-1 text-[0.8125rem] text-soft transition-colors hover:bg-ink/[0.09] hover:text-ink"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={(e) => { e.preventDefault(); ask(draft) }}
        className="mt-4 flex items-center gap-2 rounded-lg border border-line bg-panel px-3 py-2 focus-within:border-action/40"
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask a question…"
          disabled={pending}
          className="min-w-0 flex-1 bg-transparent text-[0.9375rem] placeholder:text-faint disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={pending || !draft.trim()}
          aria-label="Ask"
          className="shrink-0 cursor-pointer rounded-md p-1.5 text-action transition-opacity disabled:cursor-default disabled:opacity-25"
        >
          <SendArrow />
        </button>
      </form>
    </section>
  )
}
