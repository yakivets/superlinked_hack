import { useEffect, useRef, useState } from 'react'
import { forceSimulation, forceLink, forceManyBody, forceCollide, forceX, forceY } from 'd3-force'
import { fetchGraph } from '../api'
import { Meta } from '../components/bits'
import threadsArt from '../assets/brand/icon_threads.webp'

const W = 1080
const H = 560

// Labels are the densest thing on the canvas, so they are kept small and short.
// A full title in large type covers the very connections the page exists to show.
const LABEL_MAX_CHARS = 17
const LABEL_MAX_LINES = 2

/** Wrap a title onto at most two short lines, eliding the rest. */
function labelLines(title) {
  const words = String(title ?? '').split(/\s+/).filter(Boolean)
  const lines = []
  let line = ''

  for (const word of words) {
    const candidate = line ? `${line} ${word}` : word
    if (candidate.length <= LABEL_MAX_CHARS) {
      line = candidate
      continue
    }
    if (line) lines.push(line)
    if (lines.length === LABEL_MAX_LINES) break
    line = word.length > LABEL_MAX_CHARS ? `${word.slice(0, LABEL_MAX_CHARS - 1)}…` : word
  }
  if (line && lines.length < LABEL_MAX_LINES) lines.push(line)

  // Anything that did not fit is signalled on the last line rather than dropped
  // silently, so a truncated title never reads as the whole title.
  const used = lines.join(' ')
  if (used.length < String(title ?? '').length && !used.endsWith('…')) {
    lines[lines.length - 1] = `${lines[lines.length - 1]}…`
  }
  return lines
}

// Pinned node positions survive navigation: dragging the graph into a readable
// shape is work, and losing it on every visit makes the page feel broken.
const PINS_KEY = 'threads.pins.v1'

function loadPins() {
  try {
    return JSON.parse(localStorage.getItem(PINS_KEY)) ?? {}
  } catch {
    return {}
  }
}

function savePins(nodes) {
  try {
    const pins = {}
    for (const n of nodes) {
      if (n.fx != null && n.fy != null) pins[n.id] = { fx: n.fx, fy: n.fy }
    }
    localStorage.setItem(PINS_KEY, JSON.stringify(pins))
  } catch {
    // A full or blocked localStorage must not break the graph.
  }
}

export default function ThreadsPage() {
  const [graph, setGraph] = useState(null)
  const [positions, setPositions] = useState(null)
  const [picked, setPicked] = useState(null)
  const simRef = useRef(null)
  const dragRef = useRef(null)
  const lastMoved = useRef(false)
  const svgRef = useRef(null)

  useEffect(() => {
    let alive = true
    fetchGraph().then((g) => alive && setGraph(g)).catch(() => alive && setGraph({ nodes: [], edges: [] }))
    return () => { alive = false }
  }, [])

  useEffect(() => {
    if (!graph || graph.nodes.length === 0) return
    const pins = loadPins()
    const nodes = graph.nodes.map((n, i) => {
      const pin = pins[n.id]
      return {
        ...n,
        x: pin?.fx ?? W / 2 + 70 * Math.cos((2 * Math.PI * i) / graph.nodes.length),
        y: pin?.fy ?? H / 2 + 45 * Math.sin((2 * Math.PI * i) / graph.nodes.length),
        // Restoring fx/fy holds the node where it was left; unpinned nodes are
        // free to settle around them.
        fx: pin?.fx ?? null,
        fy: pin?.fy ?? null,
      }
    })
    const links = graph.edges.map((e) => ({ ...e }))
    const spread = Math.min(1, nodes.length / 8)
    const sim = forceSimulation(nodes)
      .force('link', forceLink(links).id((d) => d.id).distance((d) => 240 - d.weight * 110).strength((d) => d.weight))
      .force('charge', forceManyBody().strength(-420 - 220 * spread))
      .force('x', forceX(W / 2).strength(0.08))
      .force('y', forceY(H / 2).strength(0.11))
      // Small labels need less clearance than the old full-size ones, so nodes
      // can sit closer and more of them fit before the graph becomes a tangle.
      .force('collide', forceCollide(54))
      .on('tick', () => {
        for (const n of nodes) {
          n.x = Math.max(60, Math.min(W - 60, n.x))
          // Labels hang below the node, so leave room for two lines.
          n.y = Math.max(24, Math.min(H - 42, n.y))
        }
        setPositions({ nodes: [...nodes], links: [...links] })
      })
    simRef.current = sim
    return () => sim.stop()
  }, [graph])

  const svgPoint = (e) => {
    const rect = svgRef.current.getBoundingClientRect()
    return {
      x: ((e.clientX - rect.left) / rect.width) * W,
      y: ((e.clientY - rect.top) / rect.height) * H,
    }
  }

  const onPointerMove = (e) => {
    if (!dragRef.current) return
    const p = svgPoint(e)
    const d = dragRef.current
    if (Math.hypot(p.x - d.startX, p.y - d.startY) > 5) d.moved = true
    d.node.fx = p.x
    d.node.fy = p.y
    simRef.current?.alpha(0.5).restart()
  }

  // A real drag pins the node where it was dropped; a still pointer is a click.
  const endDrag = () => {
    const d = dragRef.current
    if (!d) return
    if (!d.moved) {
      d.node.fx = null
      d.node.fy = null
    }
    savePins(positions?.nodes ?? [])
    lastMoved.current = d.moved
    dragRef.current = null
  }

  if (!graph) return <p className="ink-pulse mt-12 text-soft">Loading…</p>

  if (graph.nodes.length < 2) {
    return (
      <div className="mt-14 text-center">
        <img src={threadsArt} alt="" width="110" height="110" className="mx-auto rounded-full" />
        <p className="mt-4 text-[1.05rem] font-medium">Not enough meetings yet.</p>
        <p className="mx-auto mt-1.5 max-w-[44ch] leading-relaxed text-soft">
          Once two or more meetings are done, related ones connect here.
        </p>
      </div>
    )
  }

  const pos = positions ?? { nodes: graph.nodes.map((n) => ({ ...n, x: W / 2, y: H / 2 })), links: [] }

  return (
    <div className="relative left-1/2 mt-8 w-[min(94vw,72rem)] -translate-x-1/2">
      <p className="meta max-w-[52ch] leading-relaxed">
        Meetings that talked about similar things sit closer together.
        Click a line to see what two meetings share. Drag a meeting and it stays where you leave it.
      </p>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="mt-2 w-full touch-none select-none"
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerLeave={endDrag}
        role="img"
        aria-label="Similarity graph of meetings"
      >
        {pos.links.map((l, i) => (
          <g key={i} onClick={() => setPicked(picked?.index === i ? null : { ...l, index: i })} className="cursor-pointer">
            <line x1={l.source.x} y1={l.source.y} x2={l.target.x} y2={l.target.y} stroke="transparent" strokeWidth="16" />
            <line
              x1={l.source.x} y1={l.source.y} x2={l.target.x} y2={l.target.y}
              stroke={picked?.index === i ? 'var(--color-action)' : 'var(--color-ink)'}
              strokeWidth={1.75 + (l.weight - 0.4) * 5}
              opacity={picked && picked.index !== i ? 0.18 : picked?.index === i ? 0.95 : 0.55}
            />
          </g>
        ))}
        {pos.nodes.map((n) => (
          <g
            key={n.id}
            className="cursor-pointer"
            onPointerDown={(e) => {
              e.preventDefault()
              const p = svgPoint(e)
              dragRef.current = { node: n, startX: p.x, startY: p.y, moved: false }
              n.fx = p.x
              n.fy = p.y
            }}
            onClick={() => { if (!lastMoved.current) window.location.hash = `#/meeting/${n.id}` }}
          >
            <circle cx={n.x} cy={n.y} r="8" fill="var(--color-ink)" />
            <text
              x={n.x}
              y={n.y + 20}
              textAnchor="middle"
              fill="var(--color-ink)"
              // The paper-coloured stroke sits behind the glyphs, so a
              // connection passing under a label cannot cut through the words.
              stroke="var(--color-paper)"
              strokeWidth="3.5"
              paintOrder="stroke"
              opacity={picked && picked.source.id !== n.id && picked.target.id !== n.id ? 0.35 : 1}
              style={{ fontFamily: 'var(--font-sans)', fontSize: '11.5px', fontWeight: 500 }}
            >
              <title>{n.title}</title>
              {labelLines(n.title).map((line, i) => (
                <tspan key={i} x={n.x} dy={i === 0 ? 0 : '1.15em'}>{line}</tspan>
              ))}
            </text>
          </g>
        ))}
      </svg>
      <div className="rule" />
      <p className="mt-3 min-h-[1.25rem]">
        {picked ? (
          <Meta>
            <span className="font-semibold text-ink">{picked.source.title}</span> and{' '}
            <span className="font-semibold text-ink">{picked.target.title}</span>
            {picked.shared.length > 0 ? ` share ${picked.shared.join(', ')}` : ' are similar'} ·{' '}
            {Math.round(picked.weight * 100)}%
          </Meta>
        ) : (
          <Meta>Drag to rearrange. Click a meeting to open it.</Meta>
        )}
      </p>
    </div>
  )
}
