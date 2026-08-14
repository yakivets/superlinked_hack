#include "ui.h"

#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <RotaryEncoder.h>

// Display on P2: CS=IO0, RST=IO1, DC=IO2.
#define TFT_CS   P2_IO0
#define TFT_RST  P2_IO1
#define TFT_DC   P2_IO2

// Encoder on P1: BTN=IO0, CLK=IO1, DT=IO2.
#define ENC_BTN  P1_IO0
#define ENC_CLK  P1_IO1
#define ENC_DT   P1_IO2

static const int16_t W = 160;
static const int16_t H = 80;
static const uint32_t FRAME_MS = 33;   // ~30fps; SPI draws are expensive

enum View { VIEW_STATUS = 0, VIEW_STATS, VIEW_NET, VIEW_COUNT };

// Must match backend/app/agents.py AGENT_ORDER.
const char* const AGENT_IDS[] = {
  "general", "fintech", "engineering", "standup", "sales", "interview", "legal"
};
const char* const AGENT_NAMES[] = {
  "General", "Fintech", "Engineering", "Standup", "Sales", "Interview", "Legal"
};
const int AGENT_COUNT = 7;

SPIClass mySPI(FSPI);
Adafruit_ST7735 tft = Adafruit_ST7735(&mySPI, TFT_CS, TFT_DC, TFT_RST);
GFXcanvas16 canvas(W, H);
RotaryEncoder encoder(ENC_CLK, ENC_DT, RotaryEncoder::LatchMode::TWO03);

static int currentView = VIEW_STATUS;
static int selectedAgent = 0;   // committed choice
static int pendingAgent = 0;    // what the dial is browsing, while picking
static bool picking = false;
static long lastEncPos = 0;
static uint32_t lastDraw = 0;

// Encoder button is ACTIVE HIGH with a built-in pull-down.
static bool lastBtnState = LOW;
static unsigned long lastBtnTime = 0;

// This panel is BGR: color565 takes (B, G, R), not (R, G, B).
static uint16_t cBlack, cWhite, cGray, cRed, cGreen, cAmber;

static void initColors() {
  cBlack = tft.color565(0, 0, 0);
  cWhite = tft.color565(255, 255, 255);
  cGray  = tft.color565(140, 140, 140);
  cRed   = tft.color565(0, 0, 255);       // R via the B slot
  cGreen = tft.color565(0, 220, 0);
  cAmber = tft.color565(0, 190, 255);
}

void uiBegin() {
  mySPI.begin(SCK, MISO, MOSI);
  tft.initR(INITR_MINI160x80);
  tft.setRotation(3);
  initColors();

  pinMode(ENC_BTN, INPUT);   // built-in pull-down; encoder button is active HIGH
  lastEncPos = encoder.getPosition();

  canvas.fillScreen(cBlack);
  canvas.setTextColor(cWhite);
  canvas.setTextSize(1);
  canvas.setCursor(4, 34);
  canvas.print("booting...");
  tft.drawRGBBitmap(0, 0, canvas.getBuffer(), W, H);
}

// Press the dial to start picking an agent, turn to browse, press again to
// commit. Turning outside picking mode just changes the view, so a stray nudge
// can never change which agent handles a meeting.
void uiTick(bool recording) {
  encoder.tick();

  bool btn = digitalRead(ENC_BTN);
  if (btn == HIGH && lastBtnState == LOW && (millis() - lastBtnTime > 150)) {
    lastBtnTime = millis();
    if (recording) {
      // Agent is locked for the duration of a meeting.
    } else if (picking) {
      selectedAgent = pendingAgent;   // commit
      picking = false;
    } else {
      pendingAgent = selectedAgent;   // start browsing from the current choice
      picking = true;
    }
  }
  lastBtnState = btn;

  long pos = encoder.getPosition();
  if (pos == lastEncPos) return;
  int delta = (pos > lastEncPos) ? 1 : -1;
  lastEncPos = pos;

  if (picking) {
    pendingAgent = (pendingAgent + delta + AGENT_COUNT) % AGENT_COUNT;
  } else {
    currentView = (currentView + delta + VIEW_COUNT) % VIEW_COUNT;
  }
}

const char* uiSelectedAgentId() {
  return AGENT_IDS[selectedAgent];
}

static void drawHeader(const UiState& st) {
  canvas.setTextSize(2);
  if (st.recording) {
    uint32_t s = st.elapsedMs / 1000;
    canvas.setTextColor(cRed);
    canvas.setCursor(4, 4);
    canvas.printf("REC %02u:%02u", (unsigned)(s / 60), (unsigned)(s % 60));
  } else {
    canvas.setTextColor(cGray);
    canvas.setCursor(4, 4);
    canvas.print("IDLE");
  }

  // Thin rule under the header.
  canvas.drawFastHLine(0, 24, W, cGray);
}

static void drawStatus(const UiState& st) {
  // The agent is the headline when idle: it is what the dial is choosing.
  canvas.setTextSize(2);
  canvas.setTextColor(cAmber);
  canvas.setCursor(4, 30);
  canvas.print(AGENT_NAMES[selectedAgent]);

  canvas.setTextSize(1);
  canvas.setCursor(4, 50);
  canvas.setTextColor(st.micReady ? cGreen : cRed);
  canvas.print(st.micReady ? "mic ok" : "mic FAIL");

  canvas.setCursor(64, 50);
  canvas.setTextColor(st.wsUp ? cGreen : cGray);
  canvas.print(st.wsUp ? "streaming" : "idle");

  canvas.setCursor(4, 64);
  canvas.setTextColor(cGray);
  canvas.print(st.recording ? "dial: change view" : "press dial: agent");
}

static void drawStats(const UiState& st) {
  canvas.setTextSize(1);
  canvas.setTextColor(cGray);
  canvas.setCursor(4, 30);
  canvas.print("frames sent");
  canvas.setTextColor(cWhite);
  canvas.setTextSize(2);
  canvas.setCursor(4, 40);
  canvas.printf("%lu", (unsigned long)st.framesSent);

  canvas.setTextSize(1);
  canvas.setTextColor(cGray);
  canvas.setCursor(4, 62);
  canvas.printf("buffered %lu B", (unsigned long)st.buffered);
}

static void drawNet(const UiState& st) {
  canvas.setTextSize(1);

  canvas.setCursor(4, 32);
  canvas.setTextColor(st.wifiUp ? cGreen : cRed);
  canvas.print(st.wifiUp ? "wifi connected" : "wifi down");

  canvas.setCursor(4, 46);
  canvas.setTextColor(cWhite);
  canvas.print(st.ip);

  canvas.setCursor(4, 60);
  canvas.setTextColor(st.wsUp ? cGreen : cAmber);
  canvas.print(st.wsUp ? "socket streaming" : "socket idle");
}

// Full-screen picker: previous / current / next, so turning the dial reads as
// scrolling a list rather than a value flickering in place.
static void drawPicker() {
  canvas.setTextSize(1);
  canvas.setTextColor(cGray);
  canvas.setCursor(4, 4);
  canvas.print("SELECT AGENT");
  canvas.drawFastHLine(0, 15, W, cGray);

  int prev = (pendingAgent - 1 + AGENT_COUNT) % AGENT_COUNT;
  int next = (pendingAgent + 1) % AGENT_COUNT;

  canvas.setTextColor(cGray);
  canvas.setCursor(10, 22);
  canvas.print(AGENT_NAMES[prev]);

  canvas.setTextSize(2);
  canvas.setTextColor(cAmber);
  canvas.setCursor(4, 34);
  canvas.printf(">%s", AGENT_NAMES[pendingAgent]);

  canvas.setTextSize(1);
  canvas.setTextColor(cGray);
  canvas.setCursor(10, 54);
  canvas.print(AGENT_NAMES[next]);

  canvas.setCursor(4, 68);
  canvas.setTextColor(cWhite);
  canvas.printf("press to confirm  %d/%d", pendingAgent + 1, AGENT_COUNT);
}

void uiRender(const UiState& st) {
  if (millis() - lastDraw < FRAME_MS) return;
  lastDraw = millis();

  canvas.fillScreen(cBlack);

  if (picking) {
    drawPicker();
    tft.drawRGBBitmap(0, 0, canvas.getBuffer(), W, H);
    return;
  }

  drawHeader(st);

  switch (currentView) {
    case VIEW_STATS: drawStats(st); break;
    case VIEW_NET:   drawNet(st);   break;
    default:         drawStatus(st); break;
  }

  tft.drawRGBBitmap(0, 0, canvas.getBuffer(), W, H);
}
