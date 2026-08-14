// TEST-ONLY laptop-mic recorder. The real capture path is the hardware device
// over /ws/device; delete this file and its one usage in App.jsx to remove.
import { useRef, useState } from 'react'
import { uploadWav } from '../api'

function encodeWav(float32, sampleRate) {
  // Downsample to 16k mono 16-bit PCM, matching the device stream format.
  const target = 16000
  const ratio = sampleRate / target
  const length = Math.floor(float32.length / ratio)
  const pcm = new Int16Array(length)
  for (let i = 0; i < length; i++) {
    const s = Math.max(-1, Math.min(1, float32[Math.floor(i * ratio)]))
    pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff
  }
  const buf = new ArrayBuffer(44 + pcm.length * 2)
  const v = new DataView(buf)
  const str = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)) }
  str(0, 'RIFF'); v.setUint32(4, 36 + pcm.length * 2, true); str(8, 'WAVE')
  str(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true)
  v.setUint32(24, target, true); v.setUint32(28, target * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true)
  str(36, 'data'); v.setUint32(40, pcm.length * 2, true)
  new Int16Array(buf, 44).set(pcm)
  return new Blob([buf], { type: 'audio/wav' })
}

export default function MicTest() {
  const [recording, setRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [busy, setBusy] = useState(false)
  const session = useRef(null)
  const fileRef = useRef(null)

  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const ctx = new AudioContext()
      const source = ctx.createMediaStreamSource(stream)
      const proc = ctx.createScriptProcessor(4096, 1, 1)
      const chunks = []
      proc.onaudioprocess = (e) => chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)))
      source.connect(proc)
      proc.connect(ctx.destination)
      const timer = setInterval(() => setSeconds((s) => s + 1), 1000)
      session.current = { stream, ctx, proc, chunks, timer }
      setSeconds(0)
      setRecording(true)
    } catch {
      /* mic denied: stay quiet, this is a test control */
    }
  }

  const stop = async () => {
    const s = session.current
    if (!s) return
    clearInterval(s.timer)
    s.proc.disconnect()
    s.stream.getTracks().forEach((t) => t.stop())
    const total = s.chunks.reduce((n, c) => n + c.length, 0)
    const all = new Float32Array(total)
    let off = 0
    for (const c of s.chunks) { all.set(c, off); off += c.length }
    const wav = encodeWav(all, s.ctx.sampleRate)
    await s.ctx.close()
    session.current = null
    setRecording(false)
    setBusy(true)
    const at = new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
    try { await uploadWav(wav, `Mic test ${at}`) } catch { /* backend down; list poll will show nothing */ }
    setBusy(false)
  }

  const onFile = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setBusy(true)
    try { await uploadWav(file, file.name.replace(/\.wav$/i, '')) } catch { /* ignore in test control */ }
    setBusy(false)
  }

  return (
    <span className="mr-3 hidden items-baseline gap-3 sm:flex">
      <button
        onClick={recording ? stop : start}
        className="meta cursor-pointer text-soft hover:text-ink"
        aria-pressed={recording}
      >
        {recording ? (
          <span className="text-danger">
            <span className="rec-pulse mr-1.5 inline-block h-[7px] w-[7px] rounded-full bg-danger align-baseline" />
            stop · 0:{String(seconds).padStart(2, '0')}
          </span>
        ) : busy ? 'sending…' : 'test: record'}
      </button>
      <button onClick={() => fileRef.current?.click()} className="meta cursor-pointer text-soft hover:text-ink">
        upload wav
      </button>
      <input ref={fileRef} type="file" accept=".wav,audio/wav" onChange={onFile} className="hidden" />
    </span>
  )
}
