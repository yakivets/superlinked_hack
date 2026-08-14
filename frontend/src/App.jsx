import { useEffect, useState } from 'react'
import { listMeetings } from './api'
import LandingPage from './screens/LandingPage'
import HomePage from './screens/HomePage'
import MeetingPage from './screens/MeetingPage'
import ThreadsPage from './screens/ThreadsPage'
import RoutingPage from './screens/RoutingPage'

// The Echo mark: the user's generated logo (assets/brand/logo_mark_blue.png)
// redrawn as vectors so it stays crisp at UI sizes.
function Logo() {
  return (
    <svg viewBox="0 0 32 32" width="22" height="22" aria-hidden="true">
      <rect x="1.5" y="1.5" width="29" height="29" rx="6.5" fill="none" stroke="var(--color-ink)" strokeWidth="2.4" />
      <rect x="7" y="7" width="7" height="7" rx="1.4" fill="var(--color-ink)" />
      <rect x="18" y="7" width="7" height="7" rx="1.4" fill="var(--color-ink)" />
      <rect x="7" y="18" width="7" height="7" rx="1.4" fill="var(--color-ink)" />
      <path d="M17.7 19.4 A3 3 0 0 1 17.7 23.6" fill="none" stroke="var(--color-action)" strokeWidth="2" strokeLinecap="round" />
      <path d="M20.4 17.4 A5.9 5.9 0 0 1 20.4 25.6" fill="none" stroke="var(--color-action)" strokeWidth="2" strokeLinecap="round" />
      <path d="M23.1 15.5 A8.7 8.7 0 0 1 23.1 27.5" fill="none" stroke="var(--color-action)" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

function useRoute() {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const onChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  if (hash.startsWith('#/meeting/')) return { name: 'meeting', id: hash.slice('#/meeting/'.length) }
  if (hash === '#/meetings') return { name: 'meetings' }
  if (hash === '#/threads') return { name: 'threads' }
  if (hash === '#/routing') return { name: 'routing' }
  return { name: 'landing' }
}

function useMeetings() {
  const [meetings, setMeetings] = useState(null)
  const [offline, setOffline] = useState(false)
  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const data = await listMeetings()
        if (alive) {
          setMeetings(data.meetings)
          setOffline(false)
        }
      } catch {
        if (alive) setOffline(true)
      }
    }
    tick()
    const id = setInterval(tick, 2500)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [])
  return { meetings, offline }
}

function NavLink({ href, active, children }) {
  return (
    <a
      href={href}
      className={`rounded-md px-2.5 py-1 text-[0.875rem] no-underline transition-colors ${
        active ? 'bg-ink/[0.06] font-medium text-ink' : 'text-soft hover:text-ink'
      }`}
    >
      {children}
    </a>
  )
}

export default function App() {
  const route = useRoute()
  const { meetings, offline } = useMeetings()

  return (
    <div className="mx-auto max-w-[42rem] px-6 pb-24">
      <header className="flex items-center justify-between pt-7 pb-5">
        <a href="#/" className="flex items-center gap-2.5 no-underline">
          <Logo />
          <span className="text-[1rem] font-semibold tracking-tight">Echo</span>
        </a>
        <nav className="flex items-center gap-1">
          <NavLink href="#/meetings" active={route.name === 'meetings' || route.name === 'meeting'}>Meetings</NavLink>
          <NavLink href="#/threads" active={route.name === 'threads'}>Threads</NavLink>
          <NavLink href="#/routing" active={route.name === 'routing'}>Routing</NavLink>
        </nav>
      </header>

      {offline && (
        <p className="meta ink-pulse pb-3 text-danger">Backend unreachable at localhost:8000, retrying</p>
      )}

      <main>
        {route.name === 'landing' && <LandingPage />}
        {route.name === 'meetings' && <HomePage meetings={meetings} />}
        {route.name === 'meeting' && <MeetingPage id={route.id} />}
        {route.name === 'threads' && <ThreadsPage />}
        {route.name === 'routing' && <RoutingPage />}
      </main>
    </div>
  )
}
