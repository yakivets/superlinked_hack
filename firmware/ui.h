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

void uiBegin();
void uiTick();                      // poll the encoder; call every loop()
void uiRender(const UiState& st);   // throttled internally to ~30fps
