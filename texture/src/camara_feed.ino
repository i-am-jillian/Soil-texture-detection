#define CAMERA_MODEL_AI_THINKER
#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>

// ---------------- WIFI ----------------
const char* ssid = "URVISH";
const char* password = "12345678";

// ---------------- STATIC IP ----------------
IPAddress local_IP(192, 168, 137, 50);
IPAddress gateway(192, 168, 137, 1);
IPAddress subnet(255, 255, 255, 0);

// ---------------- CAMERA MODEL: AI THINKER ----------------
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

WebServer server(80);

// ---------------- WEB PAGE ----------------
void handleRoot() {
  String html = "";
  html += "<!DOCTYPE html><html><head><meta charset='UTF-8'>";
  html += "<meta name='viewport' content='width=device-width,initial-scale=1.0'>";
  html += "<title>ESP32-CAM Live Stream</title>";
  html += "<style>";
  html += "body{font-family:Arial;background:#111;color:#fff;text-align:center;padding:20px;}";
  html += "img{max-width:100%;border-radius:12px;border:2px solid #333;}";
  html += "a{color:#7ec8ff;}";
  html += "</style>";
  html += "</head><body>";
  html += "<h2>ESP32-CAM Low-Latency Stream</h2>";
  html += "<p><a href='/capture' target='_blank'>Open Single Snapshot</a></p>";
  html += "<img src='/stream'>";
  html += "</body></html>";

  server.send(200, "text/html", html);
}

// ---------------- SINGLE SNAPSHOT ----------------
void handleCapture() {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    server.send(500, "text/plain", "Camera capture failed");
    return;
  }

  WiFiClient client = server.client();
  client.setNoDelay(true);

  client.println("HTTP/1.1 200 OK");
  client.println("Content-Type: image/jpeg");
  client.print("Content-Length: ");
  client.println(fb->len);
  client.println("Access-Control-Allow-Origin: *");
  client.println("Cache-Control: no-store, no-cache, must-revalidate, max-age=0");
  client.println("Pragma: no-cache");
  client.println("Expires: 0");
  client.println("Connection: close");
  client.println();

  client.write(fb->buf, fb->len);
  esp_camera_fb_return(fb);
}

// ---------------- LIVE MJPEG STREAM ----------------
void handleStream() {
  WiFiClient client = server.client();
  client.setNoDelay(true);

  client.println("HTTP/1.1 200 OK");
  client.println("Content-Type: multipart/x-mixed-replace; boundary=frame");
  client.println("Access-Control-Allow-Origin: *");
  client.println("Cache-Control: no-cache, no-store, must-revalidate");
  client.println("Pragma: no-cache");
  client.println("Expires: 0");
  client.println("Connection: close");
  client.println();

  while (client.connected()) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Stream capture failed");
      break;
    }

    client.println("--frame");
    client.println("Content-Type: image/jpeg");
    client.print("Content-Length: ");
    client.println(fb->len);
    client.println();

    client.write(fb->buf, fb->len);
    client.println();

    esp_camera_fb_return(fb);

    delay(20);   // lower = faster updates, but more load
    yield();
  }
}

// ---------------- CAMERA SETUP ----------------
void startCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  // Lower latency settings
  config.frame_size = FRAMESIZE_QVGA;   // 320x240
  config.jpeg_quality = 18;             // higher number = more compression = smaller frames

  if (psramFound()) {
    config.fb_count = 2;
    config.grab_mode = CAMERA_GRAB_LATEST;
    config.fb_location = CAMERA_FB_IN_PSRAM;
  } else {
    config.fb_count = 1;
    config.grab_mode = CAMERA_GRAB_LATEST;
    config.fb_location = CAMERA_FB_IN_DRAM;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.print("Camera init failed. Error: ");
    Serial.println((int)err);
    while (true) {
      delay(1000);
    }
  }

  sensor_t *s = esp_camera_sensor_get();
  if (s) {
    // Invert the image 180 degrees
    s->set_vflip(s, 1);
    s->set_hmirror(s, 1);

    // Optional tuning
    s->set_brightness(s, 0);
    s->set_contrast(s, 0);
    s->set_saturation(s, 0);
  }
}

// ---------------- WIFI SETUP ----------------
void connectToWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);   // reduces WiFi latency

  if (!WiFi.config(local_IP, gateway, subnet)) {
    Serial.println("Static IP config failed, continuing...");
  }

  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("WiFi connected");
  Serial.print("ESP32-CAM IP: ");
  Serial.println(WiFi.localIP());

  Serial.print("Live stream: http://");
  Serial.print(WiFi.localIP());
  Serial.println("/");

  Serial.print("Snapshot: http://");
  Serial.print(WiFi.localIP());
  Serial.println("/capture");
}

// ---------------- MAIN ----------------
void setup() {
  Serial.begin(115200);
  delay(1500);

  startCamera();
  connectToWiFi();

  server.on("/", HTTP_GET, handleRoot);
  server.on("/capture", HTTP_GET, handleCapture);
  server.on("/stream", HTTP_GET, handleStream);

  server.begin();
  Serial.println("Camera server started.");
}

void loop() {
  server.handleClient();
}