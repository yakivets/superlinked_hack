// Offline meeting notetaker - capture node.
// Button (P4) toggles a meeting. PDM mic (P3) captures 16kHz mono PCM.
// Audio streams to the backend over a WebSocket while recording.
//
// Backend contract (backend/app/api.py, /ws/device):
//   binary frames  -> raw PCM appended to the meeting
//   {"event":"stop"} -> finalize and run the pipeline
//   server replies {"type":"ack","id":...} then {"type":"status",...}

#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ESP_I2S.h>

#include "ui.h"
#include "secrets.h"

const char* ssid     = WIFI_SSID;
const char* password = WIFI_PASSWORD;

const char* WS_HOST = BACKEND_HOST;
const uint16_t WS_PORT = BACKEND_PORT;
const char* WS_PATH = "/ws/device";

// PDM mic on P3: SEL low = left slot (mono), CLK = IO2, DATA = IO1.
#define MIC_SEL   P3_IO0
#define MIC_DATA  P3_IO1
#define MIC_CLK   P3_IO2

// Push button on P4: LOW when pressed, hardware debounced.
#define BUTTON    P4_IO1

static const uint32_t SAMPLE_RATE = 16000;
static const size_t   FRAME_BYTES = 8192;                  // one websocket frame
static const size_t   RING_BYTES  = SAMPLE_RATE * 2 * 8;   // 8 s of slack
static const uint32_t BTN_MIN_MS  = 200;
static const uint32_t BEAT_MS     = 5000;

I2SClass i2s;
WebSocketsClient ws;

// Single-producer (capture task) / single-consumer (loop) ring buffer in PSRAM.
static uint8_t* ring = nullptr;
static volatile size_t ringHead = 0;
static volatile size_t ringTail = 0;
static uint8_t* frameBuf = nullptr;

static volatile bool recording = false;
static bool wsUp = false;
static bool micReady = false;
static uint32_t framesSent = 0;
static uint32_t droppedBytes = 0;
static int lastButton = HIGH;
static uint32_t lastButtonMs = 0;
static uint32_t lastBeatMs = 0;
static uint32_t recStartMs = 0;
static String localIp = "no ip";

static size_t ringUsed() {
  size_t h = ringHead, t = ringTail;
  return (h >= t) ? (h - t) : (RING_BYTES - t + h);
}

static void ringWrite(const uint8_t* data, size_t len) {
  size_t freeSpace = RING_BYTES - ringUsed() - 1;
  if (len > freeSpace) {
    droppedBytes += len;   // network is not keeping up with capture
    return;
  }
  size_t h = ringHead;
  for (size_t i = 0; i < len; i++) {
    ring[h] = data[i];
    h = (h + 1) % RING_BYTES;
  }
  ringHead = h;
}

static void ringRead(uint8_t* out, size_t len) {
  size_t t = ringTail;
  for (size_t i = 0; i < len; i++) {
    out[i] = ring[t];
    t = (t + 1) % RING_BYTES;
  }
  ringTail = t;
}

// Runs on core 0 so network work never stalls audio capture.
static void captureTask(void*) {
  int16_t buf[512];
  for (;;) {
    if (!recording) {
      vTaskDelay(pdMS_TO_TICKS(20));
      continue;
    }
    size_t n = i2s.readBytes((char*)buf, sizeof(buf));
    if (n > 0) ringWrite((uint8_t*)buf, n);
  }
}

static void onWsEvent(WStype_t type, uint8_t* payload, size_t len) {
  switch (type) {
    case WStype_CONNECTED:
      wsUp = true;
      Serial.println("ws connected");
      break;
    case WStype_DISCONNECTED:
      wsUp = false;
      Serial.println("ws disconnected");
      break;
    case WStype_TEXT:
      Serial.printf("ws server: %.*s\n", (int)len, (const char*)payload);
      break;
    default:
      break;
  }
}

static void startMeeting() {
  ringTail = ringHead;          // drop anything captured while idle
  framesSent = 0;
  droppedBytes = 0;
  recStartMs = millis();
  recording = true;

  ws.begin(WS_HOST, WS_PORT, WS_PATH);
  ws.onEvent(onWsEvent);
  ws.setReconnectInterval(2000);
  Serial.printf("REC start -> ws://%s:%u%s\n", WS_HOST, WS_PORT, WS_PATH);
}

static void stopMeeting() {
  recording = false;

  // Drain whatever is still buffered so the tail of the meeting survives.
  uint32_t t0 = millis();
  while (ringUsed() > 0 && wsUp && millis() - t0 < 3000) {
    size_t len = ringUsed() < FRAME_BYTES ? ringUsed() : FRAME_BYTES;
    ringRead(frameBuf, len);
    ws.sendBIN(frameBuf, len);
    framesSent++;
    ws.loop();
  }

  ws.sendTXT("{\"event\":\"stop\"}");
  ws.loop();
  Serial.printf("REC stop (%lu frames sent)\n", (unsigned long)framesSent);
  ws.disconnect();
  wsUp = false;
}

static void handleButton() {
  int now = digitalRead(BUTTON);
  if (now == LOW && lastButton == HIGH && millis() - lastButtonMs > BTN_MIN_MS) {
    lastButtonMs = millis();
    if (recording) stopMeeting();
    else startMeeting();
  }
  lastButton = now;
}

// Never let serial go quiet - a silent board is indistinguishable from a dead one.
static void heartbeat() {
  if (millis() - lastBeatMs < BEAT_MS) return;
  lastBeatMs = millis();
  Serial.printf("[beat] wifi=%d ws=%d rec=%d mic=%d buffered=%u frames=%lu\n",
                WiFi.status() == WL_CONNECTED, wsUp, recording, micReady,
                (unsigned)ringUsed(), (unsigned long)framesSent);
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== Meeting notetaker booting ===");

  ring = (uint8_t*)ps_malloc(RING_BYTES);
  frameBuf = (uint8_t*)ps_malloc(FRAME_BYTES);
  if (!ring || !frameBuf) {
    Serial.println("PSRAM alloc FAILED - cannot run");
    return;
  }
  Serial.printf("PSRAM ok (ring=%u frame=%u)\n", (unsigned)RING_BYTES, (unsigned)FRAME_BYTES);

  pinMode(BUTTON, INPUT);
  uiBegin();

  pinMode(MIC_SEL, OUTPUT);
  digitalWrite(MIC_SEL, LOW);          // left slot for mono capture
  i2s.setPinsPdmRx(MIC_CLK, MIC_DATA);
  micReady = i2s.begin(I2S_MODE_PDM_RX, SAMPLE_RATE,
                       I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO);
  Serial.println(micReady ? "mic ready" : "PDM mic init FAILED");

  WiFi.begin(ssid, password);
  Serial.printf("connecting to '%s'", ssid);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 15000) {
    delay(500);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    localIp = WiFi.localIP().toString();
    Serial.printf("\nconnected, IP %s\n", localIp.c_str());
  } else {
    Serial.printf("\nWiFi FAILED for '%s'\n", ssid);
  }

  xTaskCreatePinnedToCore(captureTask, "capture", 4096, nullptr, 5, nullptr, 0);
  Serial.println("ready - press the button to start a meeting");
}

void loop() {
  uiTick();
  handleButton();
  heartbeat();
  if (recording || wsUp) ws.loop();

  UiState st;
  st.recording  = recording;
  st.wifiUp     = WiFi.status() == WL_CONNECTED;
  st.wsUp       = wsUp;
  st.micReady   = micReady;
  st.elapsedMs  = recording ? millis() - recStartMs : 0;
  st.framesSent = framesSent;
  st.buffered   = ringUsed();
  st.ip         = localIp.c_str();
  uiRender(st);

  if (recording && wsUp && ringUsed() >= FRAME_BYTES) {
    ringRead(frameBuf, FRAME_BYTES);
    if (ws.sendBIN(frameBuf, FRAME_BYTES)) framesSent++;

    if (droppedBytes > 0) {
      Serial.printf("WARNING dropped %u bytes - network behind capture\n",
                    (unsigned)droppedBytes);
      droppedBytes = 0;
    }
  }
}
