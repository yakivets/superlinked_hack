import { useEffect, useState } from 'react'
import { listMeetings } from './api'
import HomePage from './screens/HomePage'
import MeetingPage from './screens/MeetingPage'
import ThreadsPage from './screens/ThreadsPage'
import MicTest from './components/MicTest'

function Logo() {
  return (
    <svg viewBox="0 0 32 32" width="22" height="22" aria-hidden="true">
      <rect width="32" height="32" rx="7" fill="var(--color-ink)" />
      <circle cx="13" cy="16" r="3.2" fill="var(--color-paper)" />
      <path d="M19 10.5 A7.5 7.5 0 0 1 19 21.5" fill="none" stroke="var(--color-paper)" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M23 7.5 A12 12 0 0 1 23 24.5" fill="none" stroke="var(--color-paper)" strokeWidth="2.2" strokeLinecap="round" opacity="0.55" />
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
  if (hash === '#/threads') return { name: 'threads' }
  return { name: 'home' }
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
          <MicTest />
          <NavLink href="#/" active={route.name !== 'threads'}>Meetings</NavLink>
          <NavLink href="#/threads" active={route.name === 'threads'}>Threads</NavLink>
        </nav>
      </header>

      {offline && (
        <p className="meta ink-pulse pb-3 text-danger">Backend unreachable at localhost:8000, retrying</p>
      )}

      <main>
        {route.name === 'home' && <HomePage meetings={meetings} />}
        {route.name === 'meeting' && <MeetingPage id={route.id} />}
        {route.name === 'threads' && <ThreadsPage />}
      </main>
    </div>
  )
}
