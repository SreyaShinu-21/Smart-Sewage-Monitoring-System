/*
 * Smart Sewage Monitoring System
 * IoT-Enabled Real-Time Detection with GSM Alerts & Blynk Dashboard
 *
 * Hardware:
 *   - ESP32 / Arduino Uno
 *   - HC-SR04 Ultrasonic Sensor (water level)
 *   - MQ-135 Gas Sensor (hazardous gas concentration)
 *   - DHT11 Temperature & Humidity Sensor
 *   - SIM800L GSM Module
 *   - 16x2 LCD Display (I2C)
 *
 * Cloud Platforms: Blynk IoT
 *
 * Authors: T. Vijayakumar, Logesh K, S Dhivya Shree,
 *          Sakthi Dharshini C, Sharan M S, Sreya Shinu
 * Institution: Dr. N.G.P. Institute of Technology, Coimbatore
 */

// ─── Library Includes ────────────────────────────────────────────────────────
#define BLYNK_TEMPLATE_ID   "YOUR_TEMPLATE_ID"
#define BLYNK_TEMPLATE_NAME "SmartSewage"
#define BLYNK_AUTH_TOKEN    "YOUR_AUTH_TOKEN"

#include <WiFi.h>                 // ESP32 Wi-Fi (remove if using Arduino Uno + GSM only)
#include <BlynkSimpleEsp32.h>     // Blynk for ESP32
#include <DHT.h>                  // DHT temperature/humidity sensor
#include <LiquidCrystal_I2C.h>   // I2C LCD
#include <SoftwareSerial.h>       // GSM serial communication

// ─── Pin Definitions ─────────────────────────────────────────────────────────
#define TRIG_PIN        5    // HC-SR04 Trigger
#define ECHO_PIN        18   // HC-SR04 Echo
#define GAS_SENSOR_PIN  34   // MQ-135 Analog output (ADC pin on ESP32)
#define DHT_PIN         4    // DHT11 Data pin
#define DHT_TYPE        DHT11

#define GSM_TX_PIN      16   // SIM800L TX → ESP32 RX
#define GSM_RX_PIN      17   // SIM800L RX → ESP32 TX

// ─── Threshold Constants ─────────────────────────────────────────────────────
const float WATER_LEVEL_THRESHOLD_CM = 50.0;   // Overflow alert if distance ≤ 50 cm
const int   GAS_THRESHOLD_PPM        = 300;    // Gas alert if concentration ≥ 300 ppm
const float TEMP_THRESHOLD_C         = 45.0;   // High-temp alert threshold

// ─── Blynk Virtual Pins ──────────────────────────────────────────────────────
#define VPIN_WATER_LEVEL   V0
#define VPIN_GAS_LEVEL     V1
#define VPIN_TEMPERATURE   V2
#define VPIN_HUMIDITY      V3
#define VPIN_ANOMALY_LED   V4   // LED widget: GREEN = safe, RED = anomaly

// ─── Alert Phone Number ──────────────────────────────────────────────────────
const char* ALERT_PHONE = "+91XXXXXXXXXX";   // Replace with operator's number

// ─── Wi-Fi Credentials ───────────────────────────────────────────────────────
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// ─── Object Instantiation ────────────────────────────────────────────────────
DHT dht(DHT_PIN, DHT_TYPE);
LiquidCrystal_I2C lcd(0x27, 16, 2);
SoftwareSerial gsmSerial(GSM_TX_PIN, GSM_RX_PIN);
BlynkTimer timer;

// ─── Global State ────────────────────────────────────────────────────────────
float waterLevelCm   = 0.0;
int   gasPPM         = 0;
float temperature    = 0.0;
float humidity       = 0.0;
bool  anomalyDetected = false;

// ─── Function Prototypes ─────────────────────────────────────────────────────
float measureWaterLevel();
int   readGasPPM();
void  updateLCD();
void  sendBlynkData();
void  checkThresholdsAndAlert();
void  sendSMSAlert(const String& message);
void  sendGSMCommand(const String& command, unsigned long timeout);

// ═════════════════════════════════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);
  gsmSerial.begin(9600);

  // Sensor & display init
  dht.begin();
  lcd.init();
  lcd.backlight();

  // Ultrasonic sensor pins
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  // Startup message on LCD
  lcd.setCursor(0, 0);
  lcd.print("Smart Sewage");
  lcd.setCursor(0, 1);
  lcd.print("System Init...");
  delay(2000);
  lcd.clear();

  // Connect to Blynk via Wi-Fi
  Blynk.begin(BLYNK_AUTH_TOKEN, WIFI_SSID, WIFI_PASSWORD);

  // Blynk timer: read & upload every 2 seconds
  timer.setInterval(2000L, sendBlynkData);

  Serial.println("System Ready.");
}

// ═════════════════════════════════════════════════════════════════════════════
void loop() {
  Blynk.run();
  timer.run();
}

// ─── Sensor Reading Functions ─────────────────────────────────────────────────

/**
 * Measure distance from ultrasonic sensor to water surface (cm).
 * A shorter distance means a higher water level (sensor mounted at top).
 */
float measureWaterLevel() {
  // Send 10 µs pulse
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000); // 30 ms timeout
  if (duration == 0) return -1.0; // Sensor error

  float distance = (duration * 0.0343) / 2.0; // Speed of sound: 343 m/s
  return distance;
}

/**
 * Read MQ-135 analog value and convert to approximate PPM.
 * Calibration constant (RS_R0_RATIO) should be tuned in clean air.
 */
int readGasPPM() {
  int rawADC = analogRead(GAS_SENSOR_PIN); // 0–4095 on ESP32

  // Simple linear approximation (replace with datasheet curve for accuracy)
  // Typical: 0 → 0 ppm, 4095 → 1000 ppm
  int ppm = map(rawADC, 0, 4095, 0, 1000);
  return ppm;
}

// ─── Data Upload to Blynk ────────────────────────────────────────────────────
void sendBlynkData() {
  // Read all sensors
  waterLevelCm = measureWaterLevel();
  gasPPM       = readGasPPM();
  temperature  = dht.readTemperature();
  humidity     = dht.readHumidity();

  // Guard against sensor errors
  if (isnan(temperature)) temperature = 0.0;
  if (isnan(humidity))    humidity    = 0.0;

  // Check thresholds
  checkThresholdsAndAlert();

  // Push to Blynk
  Blynk.virtualWrite(VPIN_WATER_LEVEL,  waterLevelCm);
  Blynk.virtualWrite(VPIN_GAS_LEVEL,    gasPPM);
  Blynk.virtualWrite(VPIN_TEMPERATURE,  temperature);
  Blynk.virtualWrite(VPIN_HUMIDITY,     humidity);
  Blynk.virtualWrite(VPIN_ANOMALY_LED,  anomalyDetected ? 255 : 0);

  // Update LCD
  updateLCD();

  // Serial monitor log
  Serial.printf("[DATA] Level: %.1f cm | Gas: %d ppm | Temp: %.1f°C | Hum: %.1f%%\n",
                waterLevelCm, gasPPM, temperature, humidity);
}

// ─── Threshold-Based Anomaly Detection ───────────────────────────────────────
void checkThresholdsAndAlert() {
  bool waterAlert = (waterLevelCm > 0 && waterLevelCm <= WATER_LEVEL_THRESHOLD_CM);
  bool gasAlert   = (gasPPM >= GAS_THRESHOLD_PPM);
  bool tempAlert  = (temperature >= TEMP_THRESHOLD_C);

  anomalyDetected = waterAlert || gasAlert || tempAlert;

  if (waterAlert) {
    String msg = "ALERT: Sewage overflow risk! Water level: " +
                 String(waterLevelCm, 1) + " cm (threshold: " +
                 String(WATER_LEVEL_THRESHOLD_CM, 0) + " cm)";
    Serial.println(msg);
    sendSMSAlert(msg);
    Blynk.logEvent("water_overflow", msg);
  }

  if (gasAlert) {
    String msg = "ALERT: Hazardous gas detected! Concentration: " +
                 String(gasPPM) + " ppm (threshold: " +
                 String(GAS_THRESHOLD_PPM) + " ppm)";
    Serial.println(msg);
    sendSMSAlert(msg);
    Blynk.logEvent("gas_leak", msg);
  }

  if (tempAlert) {
    String msg = "ALERT: High temperature! Temp: " +
                 String(temperature, 1) + "°C";
    Serial.println(msg);
    Blynk.logEvent("high_temp", msg);
  }
}

// ─── LCD Display Update ───────────────────────────────────────────────────────
void updateLCD() {
  lcd.clear();
  // Row 0: Water level & gas
  lcd.setCursor(0, 0);
  lcd.printf("W:%.0fcm G:%dppm", waterLevelCm, gasPPM);
  // Row 1: Temperature & status
  lcd.setCursor(0, 1);
  if (anomalyDetected) {
    lcd.print("!! ANOMALY !!   ");
  } else {
    lcd.printf("T:%.0fC H:%.0f%% OK", temperature, humidity);
  }
}

// ─── GSM SMS Alert ────────────────────────────────────────────────────────────
void sendSMSAlert(const String& message) {
  Serial.println("Sending SMS alert...");
  sendGSMCommand("AT", 1000);
  sendGSMCommand("AT+CMGF=1", 1000);                          // Text mode
  sendGSMCommand("AT+CMGS=\"" + String(ALERT_PHONE) + "\"", 1000);
  gsmSerial.print(message);
  gsmSerial.write(26); // Ctrl+Z to send
  delay(3000);
  Serial.println("SMS sent.");
}

void sendGSMCommand(const String& command, unsigned long timeout) {
  gsmSerial.println(command);
  unsigned long start = millis();
  while (millis() - start < timeout) {
    if (gsmSerial.available()) {
      Serial.write(gsmSerial.read());
    }
  }
}
