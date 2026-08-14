#pragma once
#include <Arduino.h>

// Everything the screen needs to know, passed in each frame so the UI owns no
// application state of its own.
struct UiState {
  bool recording;
  bool wifiUp;
  bool wsUp;
  bool micReady;
  uint32_t elapsedMs;
  uint32_t framesSent;
  uint32_t buffered;
  const char* ip;
};

// Agent ids must match backend/app/agents.py AGENT_ORDER.
extern const char* const AGENT_IDS[];
extern const char* const AGENT_NAMES[];
extern const int AGENT_COUNT;

void uiBegin();
void uiTick(bool recording);        // poll the encoder; call every loop()
void uiRender(const UiState& st);   // throttled internally to ~30fps

// Which agent the dial is currently on - sent to the backend on connect.
const char* uiSelectedAgentId();
