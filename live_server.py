"""Live transcription server.

Same /ws/device contract as the real backend, so the firmware needs no change.
Difference: instead of transcribing once at stop, this transcribes every
WINDOW_SECONDS of audio WHILE recording continues, and shows the running
transcript at http://localhost:8000

Run:  python live_server.py
"""

import asyncio
import io
import sys
import wave
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect

sys.path.insert(0, str(Path(__file__).parent / "backend"))
from app.inference import get_router  # noqa: E402

WINDOW_SECONDS = 10
SAMPLE_RATE = 16000
WINDOW_BYTES = SAMPLE_RATE * 2 * WINDOW_SECONDS

app = FastAPI()
router = get_router()

# Newest first, so the page reads top-down.
lines: list[dict] = []
state = {"recording": False, "bytes": 0, "windows": 0}


def pcm_to_wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


async def transcribe_window(pcm: bytes, index: int) -> None:
    """Transcribe one window without blocking the audio stream."""
    stamp = datetime.now().strftime("%H:%M:%S")
    try:
        turns = await router.transcribe(pcm_to_wav(pcm))
        text = " ".join(t.text for t in turns).strip()
    except Exception as exc:  # keep streaming even if one window fails
        text = f"[transcription failed: {exc}]"

    if not text:
        text = "[silence]"

    print(f"[{stamp}] #{index}: {text}", flush=True)
    lines.insert(0, {"time": stamp, "index": index, "text": text})


@app.websocket("/ws/device")
async def device_stream(ws: WebSocket):
    await ws.accept()
    print("device connected", flush=True)
    state.update(recording=True, bytes=0, windows=0)
    lines.clear()

    pending = bytearray()
    window_index = 0
    tasks: list[asyncio.Task] = []
    acked = False

    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break

            if not acked:
                acked = True
                await ws.send_json({"type": "ack", "id": "live"})

            if msg.get("bytes") is not None:
                chunk = msg["bytes"]
                pending.extend(chunk)
                state["bytes"] += len(chunk)

                # Fire each full window off concurrently; capture keeps flowing.
                while len(pending) >= WINDOW_BYTES:
                    window = bytes(pending[:WINDOW_BYTES])
                    del pending[:WINDOW_BYTES]
                    window_index += 1
                    state["windows"] = window_index
                    tasks.append(asyncio.create_task(
                        transcribe_window(window, window_index)))

            elif msg.get("text") is not None and '"stop"' in msg["text"]:
                break
    except WebSocketDisconnect:
        pass

    # Transcribe the leftover tail so the end of the meeting is not lost.
    if len(pending) > SAMPLE_RATE:  # more than 0.5s of audio
        window_index += 1
        tasks.append(asyncio.create_task(transcribe_window(bytes(pending), window_index)))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    state["recording"] = False
    print(f"device disconnected ({state['bytes']} bytes total)", flush=True)


@app.get("/transcript")
def get_transcript():
    return JSONResponse({"state": state, "lines": lines})


@app.get("/", response_class=HTMLResponse)
def page():
    return """<!doctype html>
<title>Live transcript</title>
<style>
 body{font:16px system-ui;background:#111;color:#eee;margin:0;padding:24px}
 h1{font-size:18px;margin:0 0 4px}
 #meta{color:#888;font-size:13px;margin-bottom:16px}
 .dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}
 .on{background:#e33}.off{background:#555}
 .line{padding:10px 0;border-bottom:1px solid #262626}
 .t{color:#666;font-size:12px;margin-right:8px}
 .empty{color:#666;padding:24px 0}
</style>
<h1>Live meeting transcript</h1>
<div id="meta"></div>
<div id="out"><div class="empty">waiting for the device&hellip; press the button on the board</div></div>
<script>
async function tick(){
  try{
    const r = await fetch('/transcript');
    const d = await r.json();
    const s = d.state;
    document.getElementById('meta').innerHTML =
      '<span class="dot '+(s.recording?'on':'off')+'"></span>'+
      (s.recording?'recording':'idle')+
      ' &middot; '+(s.bytes/32000).toFixed(1)+'s audio'+
      ' &middot; '+s.windows+' windows';
    if(d.lines.length){
      document.getElementById('out').innerHTML = d.lines.map(l=>
        '<div class="line"><span class="t">'+l.time+'</span>'+
        l.text.replace(/</g,'&lt;')+'</div>').join('');
    }
  }catch(e){
    document.getElementById('meta').textContent = 'server unreachable';
  }
}
setInterval(tick, 1000); tick();
</script>"""


if __name__ == "__main__":
    import uvicorn
    print(f"transcribing every {WINDOW_SECONDS}s -> http://localhost:8000", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
