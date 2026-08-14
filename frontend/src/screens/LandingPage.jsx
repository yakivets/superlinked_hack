import sloth from '../assets/brand/mascot_sloth.webp'
import iconMeetings from '../assets/brand/icon_meetings.webp'
import iconThreads from '../assets/brand/icon_threads.webp'
import iconRouting from '../assets/brand/icon_record.webp'

const MODES = [
  {
    href: '#/meetings',
    icon: iconMeetings,
    title: 'Meetings',
    line: 'Live transcripts with speakers, notes, and action items.',
  },
  {
    href: '#/threads',
    icon: iconThreads,
    title: 'Threads',
    line: 'How your meetings connect to each other.',
  },
  {
    href: '#/routing',
    icon: iconRouting,
    title: 'Routing',
    line: 'Every AI call, and the engine that served it.',
  },
]

export default function LandingPage() {
  return (
    <div className="mt-10 text-center sm:mt-14">
      <img src={sloth} alt="Echo mascot" width="170" height="170" className="mx-auto rounded-full" />
      <h1 className="mt-5 text-[1.5rem] font-semibold leading-tight tracking-tight">
        Meetings, remembered.
      </h1>
      <p className="mx-auto mt-2 max-w-[44ch] leading-relaxed text-soft">
        A small recorder sits in the room. Echo turns what was said into
        notes, answers, and connections.
      </p>

      <div className="mt-9 grid grid-cols-1 gap-3 text-left sm:grid-cols-3">
        {MODES.map((m) => (
          <a
            key={m.title}
            href={m.href}
            className="group rounded-xl border border-line bg-panel p-5 no-underline shadow-[0_1px_2px_rgb(31_30_28_/_0.04)] transition-colors hover:border-ink/25"
          >
            <img src={m.icon} alt="" width="56" height="56" className="rounded-full" />
            <p className="mt-3 text-[0.9375rem] font-semibold group-hover:text-action">{m.title}</p>
            <p className="mt-1 text-[0.875rem] leading-relaxed text-soft">{m.line}</p>
          </a>
        ))}
      </div>
    </div>
  )
}
