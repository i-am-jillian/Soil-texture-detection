#include <WiFiS3.h>
#include <Wire.h>
#include <OneWire.h>
#include <DHT.h>
#include <DallasTemperature.h>
#include <SensirionI2cScd4x.h>
#include <SensirionCore.h>

// ---------------- WIFI ----------------
char ssid[] = "URVISH";
char pass[] = "12345678";
WiFiServer server(80);

// ---------------- ESP32-CAM ----------------
// Must match the ESP32-CAM static IP below
const char* espCamIP = "192.168.137.50";

// ---------------- PIN SETUP ----------------
#define MQ2_AO_PIN   A0
#define MQ2_DO_PIN   7
#define DHT_PIN      2
#define DHT_TYPE     DHT11
#define ONE_WIRE_PIN 3

// ---------------- OBJECTS ----------------
DHT dht(DHT_PIN, DHT_TYPE);
OneWire oneWire(ONE_WIRE_PIN);
DallasTemperature ds18b20(&oneWire);
SensirionI2cScd4x scd4x;

// ---------------- ERROR BUFFER ----------------
char errorMessage[256];
char scdStatusText[64] = "Not started";

// ---------------- SENSOR DATA ----------------
int mq2Analog = 0;
int mq2Digital = 0;

float dhtTemp = NAN;
float dhtHum  = NAN;

float dsTempC = NAN;

uint16_t scdCo2 = 0;
float scdTemp = NAN;
float scdHum = NAN;

// ---------------- TIMING ----------------
unsigned long lastSensorRead = 0;
const unsigned long SENSOR_INTERVAL = 5000;

// ---------------- HELPERS ----------------
bool hasValidIP() {
  IPAddress ip = WiFi.localIP();
  return !(ip[0] == 0 && ip[1] == 0 && ip[2] == 0 && ip[3] == 0);
}

void printNetworkInfo() {
  Serial.println("----- NETWORK INFO -----");
  Serial.print("Status  : "); Serial.println(WiFi.status());
  Serial.print("IP      : "); Serial.println(WiFi.localIP());
  Serial.print("Gateway : "); Serial.println(WiFi.gatewayIP());
  Serial.print("Subnet  : "); Serial.println(WiFi.subnetMask());
  Serial.print("RSSI    : "); Serial.println(WiFi.RSSI());
  Serial.println("------------------------");
}

void connectToWiFi() {
  Serial.print("Connecting to SSID: ");
  Serial.println(ssid);

  WiFi.disconnect();
  delay(1000);

  int attempts = 0;
  while (attempts < 10) {
    WiFi.begin(ssid, pass);

    unsigned long start = millis();
    while (millis() - start < 10000) {
      if (WiFi.status() == WL_CONNECTED && hasValidIP()) {
        Serial.println();
        Serial.println("WiFi connected.");
        printNetworkInfo();
        return;
      }
      delay(500);
      Serial.print(".");
    }

    Serial.println();
    Serial.println("Retrying WiFi...");
    WiFi.disconnect();
    delay(2000);
    attempts++;
  }

  Serial.println("WiFi connection failed.");
  printNetworkInfo();
}

void readSensors() {
  // -------- MQ2 --------
  mq2Analog = analogRead(MQ2_AO_PIN);
  mq2Digital = digitalRead(MQ2_DO_PIN);

  // -------- DHT11 --------
  dhtTemp = dht.readTemperature();
  dhtHum  = dht.readHumidity();

  // -------- DS18B20 --------
  ds18b20.requestTemperatures();
  dsTempC = ds18b20.getTempCByIndex(0);

  // -------- SCD41 --------
  uint16_t co2 = 0;
  float t = 0.0f;
  float h = 0.0f;

  uint16_t error = scd4x.readMeasurement(co2, t, h);

  if (error) {
    errorToString(error, errorMessage, sizeof(errorMessage));
    strncpy(scdStatusText, errorMessage, sizeof(scdStatusText) - 1);
    scdStatusText[sizeof(scdStatusText) - 1] = '\0';

    Serial.print("SCD41 readMeasurement() error: ");
    Serial.println(errorMessage);
  } else if (co2 == 0) {
    strncpy(scdStatusText, "No new data yet", sizeof(scdStatusText) - 1);
    scdStatusText[sizeof(scdStatusText) - 1] = '\0';

    Serial.println("SCD41: no new data yet");
  } else {
    scdCo2 = co2;
    scdTemp = t;
    scdHum = h;

    strncpy(scdStatusText, "OK", sizeof(scdStatusText) - 1);
    scdStatusText[sizeof(scdStatusText) - 1] = '\0';
  }

  // -------- SERIAL DEBUG --------
  Serial.println("----------- SENSOR DATA -----------");

  Serial.print("MQ2 Analog   : "); Serial.println(mq2Analog);
  Serial.print("MQ2 Digital  : "); Serial.println(mq2Digital);

  Serial.print("DHT Temp     : ");
  if (isnan(dhtTemp)) Serial.println("FAILED"); else Serial.println(dhtTemp);

  Serial.print("DHT Hum      : ");
  if (isnan(dhtHum)) Serial.println("FAILED"); else Serial.println(dhtHum);

  Serial.print("DS18B20 Temp : ");
  if (dsTempC == DEVICE_DISCONNECTED_C) Serial.println("NOT DETECTED"); else Serial.println(dsTempC);

  Serial.print("SCD41 Status : "); Serial.println(scdStatusText);
  Serial.print("SCD41 CO2    : "); Serial.println(scdCo2);

  Serial.print("SCD41 Temp   : ");
  if (isnan(scdTemp)) Serial.println("NAN"); else Serial.println(scdTemp);

  Serial.print("SCD41 Hum    : ");
  if (isnan(scdHum)) Serial.println("NAN"); else Serial.println(scdHum);
}

void sendJson(WiFiClient &client) {
  IPAddress ip = WiFi.localIP();

  client.println("HTTP/1.1 200 OK");
  client.println("Content-Type: application/json");
  client.println("Access-Control-Allow-Origin: *");
  client.println("Connection: close");
  client.println();

  client.print("{");

  client.print("\"mq2Analog\":"); client.print(mq2Analog); client.print(",");
  client.print("\"mq2Digital\":"); client.print(mq2Digital); client.print(",");
  client.print("\"mq2DigitalText\":\""); client.print(mq2Digital ? "HIGH" : "LOW"); client.print("\",");

  client.print("\"dhtTemp\":");
  if (isnan(dhtTemp)) client.print("null"); else client.print(dhtTemp, 1);
  client.print(",");

  client.print("\"dhtHum\":");
  if (isnan(dhtHum)) client.print("null"); else client.print(dhtHum, 1);
  client.print(",");

  client.print("\"dsTemp\":");
  if (dsTempC == DEVICE_DISCONNECTED_C) client.print("null"); else client.print(dsTempC, 1);
  client.print(",");

  client.print("\"co2\":"); client.print(scdCo2); client.print(",");

  client.print("\"scdTemp\":");
  if (isnan(scdTemp)) client.print("null"); else client.print(scdTemp, 1);
  client.print(",");

  client.print("\"scdHum\":");
  if (isnan(scdHum)) client.print("null"); else client.print(scdHum, 1);
  client.print(",");

  client.print("\"scdStatus\":\"");
  client.print(scdStatusText);
  client.print("\",");

  client.print("\"camIp\":\"");
  client.print(espCamIP);
  client.print("\",");

  client.print("\"camSnapshotUrl\":\"http://");
  client.print(espCamIP);
  client.print("/capture\",");

  client.print("\"ip\":\"");
  client.print(ip[0]); client.print(".");
  client.print(ip[1]); client.print(".");
  client.print(ip[2]); client.print(".");
  client.print(ip[3]); client.print("\"");

  client.print("}");
}

void sendDashboard(WiFiClient &client) {
  client.println("HTTP/1.1 200 OK");
  client.println("Content-Type: text/html");
  client.println("Connection: close");
  client.println();

  client.println("<!DOCTYPE html>");
  client.println("<html>");
  client.println("<head>");
  client.println("<meta charset='UTF-8'>");
  client.println("<meta name='viewport' content='width=device-width, initial-scale=1.0'>");
  client.println("<title>UNO R4 Sensor Dashboard</title>");
  client.println("<style>");
  client.println("body{font-family:Arial,sans-serif;background:#111;color:#fff;margin:0;padding:20px;}");
  client.println(".wrap{max-width:1100px;margin:auto;}");
  client.println("h1{margin-bottom:8px;}");
  client.println(".sub{color:#bbb;margin-bottom:20px;}");
  client.println(".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;}");
  client.println(".card{background:#1d1d1d;border-radius:14px;padding:16px;box-shadow:0 0 12px rgba(0,0,0,0.25);}");
  client.println(".label{font-size:13px;color:#aaa;margin-bottom:6px;}");
  client.println(".value{font-size:28px;font-weight:bold;}");
  client.println(".small{font-size:14px;color:#ccc;margin-top:6px;}");
  client.println(".camBox{margin-top:20px;background:#1d1d1d;border-radius:14px;padding:16px;}");
  client.println("img{width:100%;max-width:640px;border-radius:12px;background:#000;display:block;}");
  client.println("a{color:#7ec8ff;}");
  client.println("</style>");
  client.println("</head>");
  client.println("<body>");
  client.println("<div class='wrap'>");
  client.println("<h1>UNO R4 Sensor Dashboard</h1>");
  client.println("<div class='sub'>Hosted on Arduino UNO R4 WiFi</div>");

  client.println("<div class='grid'>");
  client.println("<div class='card'><div class='label'>MQ2 Analog</div><div class='value' id='mq2a'>--</div></div>");
  client.println("<div class='card'><div class='label'>MQ2 Digital</div><div class='value' id='mq2d'>--</div><div class='small' id='mq2dt'>--</div></div>");
  client.println("<div class='card'><div class='label'>DHT Temperature</div><div class='value' id='dhtt'>--</div></div>");
  client.println("<div class='card'><div class='label'>DHT Humidity</div><div class='value' id='dhth'>--</div></div>");
  client.println("<div class='card'><div class='label'>DS18B20 Temperature</div><div class='value' id='dst'>--</div></div>");
  client.println("<div class='card'><div class='label'>CO2</div><div class='value' id='co2'>--</div></div>");
  client.println("<div class='card'><div class='label'>SCD41 Temperature</div><div class='value' id='scdt'>--</div></div>");
  client.println("<div class='card'><div class='label'>SCD41 Humidity</div><div class='value' id='scdh'>--</div></div>");
  client.println("<div class='card'><div class='label'>SCD41 Status</div><div class='value' style='font-size:20px' id='scds'>--</div></div>");
  client.println("<div class='card'><div class='label'>UNO R4 IP</div><div class='value' style='font-size:20px' id='unoip'>--</div></div>");
  client.println("</div>");

  client.println("<div class='camBox'>");
  client.println("<h2>ESP32-CAM View</h2>");
  client.println("<img id='camImg' alt='ESP32-CAM feed'>");
  client.println("<div class='small'>Source: <a id='camLink' href='#' target='_blank'>Open camera snapshot</a></div>");
  client.println("</div>");

  client.println("</div>");

  client.println("<script>");
  client.println("let camUrl='';");
  client.println("function fmt(v,u){ if(v===null||v===undefined){return '--';} return v + (u?(' '+u):''); }");
  client.println("function refreshCam(){ if(camUrl){ document.getElementById('camImg').src = camUrl + '?t=' + Date.now(); } }");
  client.println("async function updateData(){");
  client.println("  try {");
  client.println("    const res = await fetch('/data');");
  client.println("    const d = await res.json();");
  client.println("    document.getElementById('mq2a').innerText = d.mq2Analog;");
  client.println("    document.getElementById('mq2d').innerText = d.mq2Digital;");
  client.println("    document.getElementById('mq2dt').innerText = d.mq2DigitalText;");
  client.println("    document.getElementById('dhtt').innerText = fmt(d.dhtTemp, 'C');");
  client.println("    document.getElementById('dhth').innerText = fmt(d.dhtHum, '%');");
  client.println("    document.getElementById('dst').innerText = fmt(d.dsTemp, 'C');");
  client.println("    document.getElementById('co2').innerText = fmt(d.co2, 'ppm');");
  client.println("    document.getElementById('scdt').innerText = fmt(d.scdTemp, 'C');");
  client.println("    document.getElementById('scdh').innerText = fmt(d.scdHum, '%');");
  client.println("    document.getElementById('scds').innerText = d.scdStatus;");
  client.println("    document.getElementById('unoip').innerText = d.ip;");
  client.println("    camUrl = d.camSnapshotUrl;");
  client.println("    document.getElementById('camLink').href = camUrl;");
  client.println("    refreshCam();");
  client.println("  } catch(e) {");
  client.println("    document.getElementById('scds').innerText = 'Dashboard fetch error';");
  client.println("  }");
  client.println("}");
  client.println("updateData();");
  client.println("setInterval(updateData, 3000);");
  client.println("setInterval(refreshCam, 1200);");
  client.println("</script>");

  client.println("</body>");
  client.println("</html>");
}

void sendNotFound(WiFiClient &client) {
  client.println("HTTP/1.1 404 Not Found");
  client.println("Content-Type: text/plain");
  client.println("Access-Control-Allow-Origin: *");
  client.println("Connection: close");
  client.println();
  client.println("Use / for dashboard or /data for JSON");
}

void setup() {
  Serial.begin(115200);
  delay(1500);

  pinMode(MQ2_DO_PIN, INPUT);

  dht.begin();
  ds18b20.begin();
  Wire.begin();

  // -------- SCD41 init --------
  scd4x.begin(Wire, 0x62);

  uint16_t error;

  error = scd4x.stopPeriodicMeasurement();
  if (error) {
    Serial.print("SCD41 stopPeriodicMeasurement() error: ");
    errorToString(error, errorMessage, sizeof(errorMessage));
    Serial.println(errorMessage);
  }

  error = scd4x.startPeriodicMeasurement();
  if (error) {
    Serial.print("SCD41 startPeriodicMeasurement() error: ");
    errorToString(error, errorMessage, sizeof(errorMessage));
    Serial.println(errorMessage);
    strncpy(scdStatusText, "Start failed", sizeof(scdStatusText) - 1);
  } else {
    Serial.println("SCD41 started.");
    strncpy(scdStatusText, "Started", sizeof(scdStatusText) - 1);
  }
  scdStatusText[sizeof(scdStatusText) - 1] = '\0';

  Serial.println("Warming up sensors...");
  delay(10000);

  connectToWiFi();

  server.begin();
  Serial.println("Server started.");
  Serial.println("Open dashboard in browser:");
  Serial.print("http://");
  Serial.print(WiFi.localIP());
  Serial.println("/");

  Serial.println("Raw JSON:");
  Serial.print("http://");
  Serial.print(WiFi.localIP());
  Serial.println("/data");

  Serial.println("ESP32-CAM snapshot URL:");
  Serial.print("http://");
  Serial.print(espCamIP);
  Serial.println("/capture");

  readSensors();
}

void loop() {
  if (millis() - lastSensorRead >= SENSOR_INTERVAL) {
    lastSensorRead = millis();
    readSensors();
  }

  WiFiClient client = server.available();
  if (!client) return;

  String request = "";
  unsigned long timeout = millis();

  while (client.connected() && millis() - timeout < 1200) {
    while (client.available()) {
      char c = client.read();
      request += c;
      if (request.endsWith("\r\n\r\n")) break;
    }
    if (request.endsWith("\r\n\r\n")) break;
  }

  if (request.indexOf("GET /data ") >= 0) {
    sendJson(client);
  } else if (request.indexOf("GET / HTTP") >= 0) {
    sendDashboard(client);
  } else {
    sendNotFound(client);
  }

  delay(1);
  client.stop();
}