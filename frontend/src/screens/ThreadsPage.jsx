import { useEffect, useRef, useState } from 'react'
import { forceSimulation, forceLink, forceManyBody, forceCollide, forceX, forceY } from 'd3-force'
import { fetchGraph } from '../api'
import { Meta } from '../components/bits'

const W = 720
const H = 340

export default function ThreadsPage() {
  const [graph, setGraph] = useState(null)
  const [positions, setPositions] = useState(null)
  const [picked, setPicked] = useState(null)
  const simRef = useRef(null)
  const dragRef = useRef(null)
  const svgRef = useRef(null)

  useEffect(() => {
    let alive = true
    fetchGraph().then((g) => alive && setGraph(g)).catch(() => alive && setGraph({ nodes: [], edges: [] }))
    return () => { alive = false }
  }, [])

  useEffect(() => {
    if (!graph || graph.nodes.length === 0) return
    const nodes = graph.nodes.map((n, i) => ({
      ...n,
      x: W / 2 + 70 * Math.cos((2 * Math.PI * i) / graph.nodes.length),
      y: H / 2 + 45 * Math.sin((2 * Math.PI * i) / graph.nodes.length),
    }))
    const links = graph.edges.map((e) => ({ ...e }))
    const spread = Math.min(1, nodes.length / 8)
    const sim = forceSimulation(nodes)
      .force('link', forceLink(links).id((d) => d.id).distance((d) => 150 - d.weight * 60).strength((d) => d.weight))
      .force('charge', forceManyBody().strength(-260 - 140 * spread))
      .force('x', forceX(W / 2).strength(0.09))
      .force('y', forceY(H / 2).strength(0.12))
      .force('collide', forceCollide(64))
      .on('tick', () => {
        for (const n of nodes) {
          n.x = Math.max(70, Math.min(W - 70, n.x))
          n.y = Math.max(48, Math.min(H - 26, n.y))
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
    dragRef.current.fx = p.x
    dragRef.current.fy = p.y
    simRef.current?.alpha(0.5).restart()
  }

  const endDrag = () => {
    if (dragRef.current) {
      dragRef.current.fx = null
      dragRef.current.fy = null
      dragRef.current = null
    }
  }

  if (!graph) return <p className="ink-pulse mt-12 text-soft">Loading…</p>

  if (graph.nodes.length < 2) {
    return (
      <div className="mt-14">
        <p className="text-[1.05rem] font-medium">Not enough meetings yet.</p>
        <p className="mt-2 max-w-[44ch] leading-relaxed text-soft">
          Once two or more meetings are done, related ones connect here.
        </p>
      </div>
    )
  }

  const pos = positions ?? { nodes: graph.nodes.map((n) => ({ ...n, x: W / 2, y: H / 2 })), links: [] }

  return (
    <div className="mt-8">
      <p className="meta max-w-[52ch] leading-relaxed">
        Meetings that talked about similar things sit closer together.
        Click a line to see what two meetings share.
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
              dragRef.current = n
              const p = svgPoint(e)
              n.fx = p.x
              n.fy = p.y
            }}
            onClick={() => { if (!dragRef.current) window.location.hash = `#/meeting/${n.id}` }}
          >
            <circle cx={n.x} cy={n.y} r="11" fill="var(--color-ink)" />
            <text
              x={n.x}
              y={n.y - 22}
              textAnchor="middle"
              fill="var(--color-ink)"
              style={{ fontFamily: 'var(--font-sans)', fontSize: '16.5px', fontWeight: 550 }}
            >
              {n.title}
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
