# Hardware Wiring Diagram

## ESP32 Pin Connections

```
ESP32 Pin   →   Component
─────────────────────────────────────────────────────
GPIO 5      →   HC-SR04 TRIG
GPIO 18     →   HC-SR04 ECHO
GPIO 34     →   MQ-135 AOUT  (analog read)
GPIO 4      →   DHT11 DATA
GPIO 16     →   SIM800L TX   (ESP32 RX2)
GPIO 17     →   SIM800L RX   (ESP32 TX2)
GPIO 21     →   LCD SDA      (I2C)
GPIO 22     →   LCD SCL      (I2C)

3.3V        →   HC-SR04 VCC, DHT11 VCC, LCD VCC
5V          →   MQ-135 VCC, SIM800L VCC (use separate regulator)
GND         →   All component GNDs
```

## Arduino Uno Pin Connections (alternative)

```
Arduino Pin →   Component
─────────────────────────────────────────────────────
D5          →   HC-SR04 TRIG
D6          →   HC-SR04 ECHO
A0          →   MQ-135 AOUT
D4          →   DHT11 DATA
D2 (RX)     →   SIM800L TX   (via SoftwareSerial)
D3 (TX)     →   SIM800L RX   (via SoftwareSerial)
A4          →   LCD SDA
A5          →   LCD SCL

5V          →   HC-SR04, DHT11, LCD
VIN / ext.  →   MQ-135, SIM800L  (requires 4.0-4.2V @ 2A peak)
GND         →   All GNDs
```

## Power Notes

- SIM800L requires **4.0–4.2V at up to 2A peak** during GSM transmission.
  Use a dedicated LM2596 buck converter; do NOT power from Arduino 5V directly.
- MQ-135 needs a **preheat time of ~24–48 hours** for stable readings.
  Shorter warmup (~3 min) is acceptable for demo purposes.

## Sensor Calibration

### HC-SR04 (Ultrasonic)
- Mount sensor at the **top of the sewage chamber**.
- Distance to water surface = measured value.
- Safe level: distance > 50 cm (water level low).
- Overflow risk: distance ≤ 50 cm (water level high).

### MQ-135 (Gas)
- Allow 3-minute warmup before readings.
- Clean air baseline: ~200–300 raw ADC (0 ppm equivalent).
- Default alert threshold: 300 ppm.
- Adjust `GAS_THRESHOLD_PPM` in firmware per local regulations.

### DHT11 (Temperature & Humidity)
- Operating range: 0–50°C, 20–90% RH.
- Accuracy: ±2°C, ±5% RH.
- Sampling rate: max 1 Hz (1-second delay between reads required).
