#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <DIYables_LCD_I2C.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <Keypad.h>

// ==================================================
// HARDWARE
// ==================================================

#define ONE_WIRE_BUS 4

DIYables_LCD_I2C lcd(0x27, 16, 2);

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);


// ==================================================
// WIFI / SERVER
// ==================================================

const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

const char* SERVER_BASE = "http://192.168.1.20:5000";


// ==================================================
// KEYPAD
// ==================================================

const byte ROWS = 4;
const byte COLS = 3;

char keys[ROWS][COLS] = {
    {'1', '2', '3'},
    {'4', '5', '6'},
    {'7', '8', '9'},
    {'*', '0', '#'}
};

byte rowPins[ROWS] = { 13, 14, 16, 17 };
byte colPins[COLS] = { 18, 19, 23 };

Keypad keypad = Keypad(
    makeKeymap(keys),
    rowPins,
    colPins,
    ROWS,
    COLS
);


// ==================================================
// VARIABLES
// ==================================================

float currentTemperatureF = DEVICE_DISCONNECTED_F;


// ==================================================
// LCD
// ==================================================

void showMessage(String line1, String line2 = "") {
    lcd.clear();

    lcd.setCursor(0, 0);
    lcd.print(line1);

    lcd.setCursor(0, 1);
    lcd.print(line2);
}


void showHome() {
    sensors.requestTemperatures();
    currentTemperatureF = sensors.getTempFByIndex(0);

    lcd.clear();

    lcd.setCursor(0, 0);
    lcd.print("Tay's Cyberdeck");

    lcd.setCursor(0, 1);

    if (currentTemperatureF == DEVICE_DISCONNECTED_F) {
        lcd.print("Temp error");
    }
    else {
        lcd.print(currentTemperatureF, 1);
        lcd.write((uint8_t)223);
        lcd.print("F");
    }
}


void showHelp() {
    showMessage(
        "1Temp 2Status",
        "3Report *Home"
    );

    delay(2500);
    showHome();
}


// ==================================================
// WIFI
// ==================================================

bool connectWiFi() {
    if (WiFi.status() == WL_CONNECTED) {
        return true;
    }

    showMessage("Connecting WiFi");
    Serial.print("Connecting to WiFi");

    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    unsigned long startTime = millis();

    while (WiFi.status() != WL_CONNECTED &&
        millis() - startTime < 10000) {

        delay(500);
        Serial.print(".");
    }

    Serial.println();

    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi connection failed");

        showMessage(
            "WiFi failed",
            "Check network"
        );

        delay(1500);
        return false;
    }

    Serial.print("ESP32 IP: ");
    Serial.println(WiFi.localIP());

    showMessage(
        "WiFi connected",
        WiFi.localIP().toString()
    );

    delay(1200);
    return true;
}


// ==================================================
// TEMPERATURE
// ==================================================

void sendTemperature() {
    sensors.requestTemperatures();
    currentTemperatureF = sensors.getTempFByIndex(0);

    if (currentTemperatureF == DEVICE_DISCONNECTED_F) {
        showMessage(
            "Temp error",
            "Not sent"
        );

        delay(1200);
        showHome();
        return;
    }

    if (!connectWiFi()) {
        showHome();
        return;
    }

    HTTPClient http;

    String url = String(SERVER_BASE) + "/temperature";
    String json =
        "{\"temperature_f\":" +
        String(currentTemperatureF, 1) +
        "}";

    http.begin(url);
    http.addHeader("Content-Type", "application/json");

    int code = http.POST(json);

    http.end();

    Serial.print("Temperature POST: ");
    Serial.println(code);

    if (code >= 200 && code < 300) {
        showMessage(
            "Temp sent!",
            String(currentTemperatureF, 1) + " F"
        );
    }
    else {
        showMessage(
            "Send failed",
            "HTTP " + String(code)
        );
    }

    delay(1500);
    showHome();
}


// ==================================================
// SERVER STATUS
// ==================================================

void checkServer() {
    if (!connectWiFi()) {
        showHome();
        return;
    }

    HTTPClient http;

    String url = String(SERVER_BASE) + "/health";

    http.begin(url);

    int code = http.GET();

    http.end();

    Serial.print("Server health: ");
    Serial.println(code);

    if (code >= 200 && code < 300) {
        showMessage(
            "Server",
            "ONLINE"
        );
    }
    else {
        showMessage(
            "Server",
            "OFFLINE"
        );
    }

    delay(1500);
    showHome();
}


// ==================================================
// REPORT
// ==================================================

void sendReport() {
    if (!connectWiFi()) {
        showHome();
        return;
    }

    showMessage(
        "Report",
        "Sending..."
    );

    HTTPClient http;

    String url = String(SERVER_BASE) + "/email-report";

    http.begin(url);
    http.addHeader("Content-Type", "application/json");

    int code = http.POST("{}");

    http.end();

    Serial.print("Report request: ");
    Serial.println(code);

    if (code >= 200 && code < 300) {
        showMessage(
            "Report",
            "SENT!"
        );
    }
    else {
        showMessage(
            "Report failed",
            "HTTP " + String(code)
        );
    }

    delay(1800);
    showHome();
}


// ==================================================
// KEYPAD
// ==================================================

void handleKey(char key) {
    Serial.print("Key pressed: ");
    Serial.println(key);

    switch (key) {

    case '1':
        sendTemperature();
        break;

    case '2':
        checkServer();
        break;

    case '3':
        sendReport();
        break;

    case '0':
        showHelp();
        break;

    case '*':
        showHome();
        break;

    default:
        showMessage(
            "Unused key",
            String(key)
        );

        delay(800);
        showHome();
        break;
    }
}


// ==================================================
// SETUP
// ==================================================

void setup() {
    Serial.begin(115200);

    // LCD
    Wire.begin(21, 22);
    lcd.init();
    lcd.backlight();

    // Temperature sensor
    sensors.begin();

    // WiFi
    connectWiFi();

    showHome();
}


// ==================================================
// LOOP
// ==================================================

void loop() {
    char key = keypad.getKey();

    if (key) {
        handleKey(key);
    }

    delay(10);
}