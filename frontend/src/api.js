const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

async function get(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} on ${path}`)
  return res.json()
}

export const listMeetings = () => get('/meetings')
export const getMeeting = (id) => get(`/meetings/${id}`)
export const searchMeetings = (q, k = 5) =>
  get(`/search?q=${encodeURIComponent(q)}&k=${k}`)
export const fetchGraph = () => get('/graph')
export const fetchRouting = () => get('/routing')

export async function askSynthesis(question, k = 5) {
  const res = await fetch(`${BASE}/synthesis`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, k }),
  })
  if (!res.ok) throw new Error(`${res.status} on /synthesis`)
  return res.json()
}

export async function uploadWav(blob, title) {
  const form = new FormData()
  form.append('file', blob, 'recording.wav')
  form.append('title', title)
  const res = await fetch(`${BASE}/meetings/upload`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(`${res.status} on /meetings/upload`)
  return res.json()
}
