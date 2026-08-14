import { useEffect, useState } from 'react'
import { fetchRouting } from '../api'
import { Meta } from '../components/bits'

const TASK_LABELS = {
  transcribe: 'Transcribe + diarize',
  notes: 'Write notes',
  extract: 'Extract entities',
  embed: 'Embed',
  rerank: 'Rerank',
  synthesis: 'Synthesis',
  chat: 'Meeting chat',
}

const PROVIDER_LABELS = {
  sie: 'SIE · local',
  cloud: 'Alibaba Cloud',
}

function ms(v) {
  return v >= 1000 ? `${(v / 1000).toFixed(1)} s` : `${Math.round(v)} ms`
}

function clock(iso) {
  return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function ProviderChip({ provider }) {
  const cloud = provider === 'cloud'
  return (
    <span
      className={`rounded-md px-2 py-0.5 text-[0.8125rem] font-medium whitespace-nowrap ${
        cloud ? 'bg-action/10 text-action' : 'bg-ink/[0.05] text-ink'
      }`}
    >
      {PROVIDER_LABELS[provider] ?? provider}
    </span>
  )
}

function SummaryBlock({ provider, data }) {
  return (
    <div className="flex-1 rounded-xl border border-line bg-panel p-5 shadow-[0_1px_2px_rgb(31_30_28_/_0.04)]">
      <ProviderChip provider={provider} />
      <p className="mt-3 text-[1.05rem] font-semibold">
        {data ? `${data.calls} ${data.calls === 1 ? 'call' : 'calls'}` : 'No calls yet'}
        {data && <Meta className="ml-2 font-normal">{ms(data.ms)} total</Meta>}
      </p>
      {data && (
        <ul className="mt-2 space-y-1">
          {Object.entries(data.models).map(([model, count]) => (
            <li key={model} className="meta truncate">
              {model.replace('Qwen/', '')} <span className="text-faint">×{count}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function RoutingPage() {
  const [routing, setRouting] = useState(null)

  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const data = await fetchRouting()
        if (alive) setRouting(data)
      } catch {
        /* header banner already reports the backend being down */
      }
    }
    tick()
    const id = setInterval(tick, 2500)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [])

  if (!routing) return <p className="ink-pulse mt-10 text-soft">Loading…</p>

  const calls = routing.calls ?? []

  return (
    <div className="mt-2">
      <p className="meta max-w-[54ch] leading-relaxed">
        Every inference call, live, and the engine that served it. SIE handles
        everything locally; Alibaba Cloud is used only where it earns its keep.
      </p>

      <div className="mt-5 flex flex-col gap-3 sm:flex-row">
        <SummaryBlock provider="sie" data={routing.summary?.sie} />
        <SummaryBlock provider="cloud" data={routing.summary?.cloud} />
      </div>

      {calls.length === 0 ? (
        <p className="mt-10 text-soft">No calls yet. Upload a meeting or run a search and watch them appear.</p>
      ) : (
        <div className="mt-6 divide-y divide-line">
          {calls.map((c, i) => (
            <div key={`${c.at}-${i}`} className="flex items-baseline gap-3 py-3">
              <Meta className="w-16 shrink-0">{clock(c.at)}</Meta>
              <span className="w-40 shrink-0 text-[0.9375rem] font-medium">
                {TASK_LABELS[c.task] ?? c.task}
              </span>
              <Meta className="min-w-0 flex-1 truncate">{c.model.replace('Qwen/', '')}</Meta>
              <ProviderChip provider={c.provider} />
              <Meta className="w-16 shrink-0 text-right">{ms(c.ms)}</Meta>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
