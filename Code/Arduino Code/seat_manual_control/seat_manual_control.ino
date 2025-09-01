/* =======================================================================
  Arduino Nano ESP32-S3 — Minimal TWAI (CAN) periodic TX with Recovery
  - Bitrate: 100 kbit/s
  - Pins:    D9 → GPIO18 (RX),  D10 → GPIO21 (TX)
  - Frames:
      ID 0x165  DLC=1  data: 02                   period: 60.0 s  offset: 0 ms
      ID 0x325  DLC=8  data: 00 00 00 00 00 00 00 00  period: 100 ms  offset: 100 ms
  ======================================================================= */
#include <Arduino.h>
#include "driver/twai.h"
#include "esp_wifi.h"
#include "esp_bt.h"
#include "WiFi.h"
/* ---- Pins (Nano ESP32-S3 board mapping) ----------------------------- */
#define RX_GPIO_NUM GPIO_NUM_18   // D9
#define TX_GPIO_NUM GPIO_NUM_21   // D10
/* ---- Optional: shut down Wi-Fi/Bluetooth to reduce interference ----- */
static void disableWiFiAndBT() {
  WiFi.disconnect(true); WiFi.mode(WIFI_OFF);
  esp_wifi_stop();       esp_wifi_deinit();
  if (esp_bt_controller_get_status() == ESP_BT_CONTROLLER_STATUS_ENABLED)
    esp_bt_controller_disable();
  if (esp_bt_controller_get_status() != ESP_BT_CONTROLLER_STATUS_IDLE)
    esp_bt_controller_deinit();
  btStop();
}
/* ---- Frame schedule -------------------------------------------------- */
struct TxItem {
  twai_message_t msg;
  uint32_t       period_ms;
  uint32_t       next_due_ms;   // absolute (millis) time of next send
};
/* Two frames mirroring your RasPi setup */
TxItem txItems[2];
static void prepareFrames() {
  // ID 0x165, "02", every 60.0s, offset 0 ms
  memset(&txItems[0].msg, 0, sizeof(twai_message_t));
  txItems[0].msg.identifier        = 0x165;
  txItems[0].msg.data_length_code  = 1;
  txItems[0].msg.data[0]           = 0x02;
  txItems[0].period_ms             = 60000UL;
  // ID 0x325, 8x00, every 100ms, offset 100 ms
  memset(&txItems[1].msg, 0, sizeof(twai_message_t));
  txItems[1].msg.identifier        = 0x325;
  txItems[1].msg.data_length_code  = 8;
  for (int i = 0; i < 8; ++i) txItems[1].msg.data[i] = 0x00;
  txItems[1].period_ms             = 100UL;
}
/* ---- TWAI helpers ---------------------------------------------------- */
static bool startTWAI() {
  twai_general_config_t g =
      TWAI_GENERAL_CONFIG_DEFAULT(TX_GPIO_NUM, RX_GPIO_NUM, TWAI_MODE_NORMAL);
  twai_timing_config_t  t = TWAI_TIMING_CONFIG_100KBITS();
  twai_filter_config_t  f = TWAI_FILTER_CONFIG_ACCEPT_ALL();
  if (twai_driver_install(&g, &t, &f) != ESP_OK) {
    Serial.println("[TWAI] driver install failed");
    return false;
  }
  if (twai_start() != ESP_OK) {
    Serial.println("[TWAI] start failed");
    twai_driver_uninstall();
    return false;
  }
  return true;
}
static void stopTWAI() {
  twai_stop();
  twai_driver_uninstall();
}
static void recoverIfBusOff() {
  twai_status_info_t s; twai_get_status_info(&s);
  if (s.state == TWAI_STATE_BUS_OFF) {
    Serial.println("[TWAI] BUS-OFF → restarting driver");
    stopTWAI();
    delay(50);
    startTWAI();  // try a clean restart
  }
}
/* ============================ setup ================================== */
void setup() {
  Serial.begin(115200);
  delay(50);
  Serial.println("\n=== Nano ESP32-S3 | Minimal TWAI periodic TX @100k ===");
  disableWiFiAndBT();
  if (!startTWAI()) {
    Serial.println("[FATAL] TWAI init failed. Halting.");
    while (true) delay(1000);
  }
  prepareFrames();
  const uint32_t now = millis();
  // Apply initial offsets: item0 = 0 ms, item1 = 100 ms
  txItems[0].next_due_ms = now + 0UL;
  txItems[1].next_due_ms = now + 100UL;
  Serial.println("[INFO] Streaming started. ID 0x165 @60s, ID 0x325 @100ms (offset 100ms).");
}
/* ============================ loop =================================== */
void loop() {
  const uint32_t now = millis();
  // Attempt sends when due
  for (int i = 0; i < 2; ++i) {
    // handle signed wrap-safe comparison
    if ((int32_t)(now - txItems[i].next_due_ms) >= 0) {
      if (twai_transmit(&txItems[i].msg, pdMS_TO_TICKS(10)) == ESP_OK) {
        // Keep exact cadence: advance by integer multiples of period if we're behind
        do {
          txItems[i].next_due_ms += txItems[i].period_ms;
        } while ((int32_t)(now - txItems[i].next_due_ms) >= 0);
      } else {
        // On TX error, check/recover bus; try again on next loop tick
        Serial.println("[TWAI] TX error; checking bus …");
        recoverIfBusOff();
        // Nudge schedule forward minimally so we don't hot-loop on errors
        txItems[i].next_due_ms = now + 5;
      }
    }
  }
  // Lightweight health check occasionally
  static uint32_t lastHealth = 0;
  if (now - lastHealth >= 1000UL) {
    lastHealth = now;
    twai_status_info_t s; twai_get_status_info(&s);
    if (s.state != TWAI_STATE_RUNNING) {
      Serial.printf("[TWAI] State=%d — attempting recovery\n", (int)s.state);
      recoverIfBusOff();
    }
  }
  // Keep loop responsive without busy-wait
  delay(1);
}