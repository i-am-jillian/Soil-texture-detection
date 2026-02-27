import time
import threading

import cv2
import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image

CLASSES = ["coarse", "medium", "fine"]

MODEL_PATH = "models/texture_best.pt"   # run uvicorn from texture/ so this resolves
CAM_INDEX = 0
CROP_RATIO = 0.70
FPS = 5

# ---------------- app ----------------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- shared state ----------------
latest = {
    "label": "--",
    "conf": 0.0,
    "timestamp": 0,
    "source": "laptop_webcam",
}

latest_jpeg = None
jpeg_lock = threading.Lock()

# ---------------- model ----------------
device = "cuda" if torch.cuda.is_available() else "cpu"

model = models.mobilenet_v3_small(weights=None)
model.classifier[3] = nn.Linear(model.classifier[3].in_features, len(CLASSES))

state = torch.load(MODEL_PATH, map_location=device)
if isinstance(state, dict) and "model" in state:
    model.load_state_dict(state["model"])
else:
    model.load_state_dict(state)

model.eval().to(device)

transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],
                         [0.229, 0.224, 0.225]),
])

def center_crop_square(frame, crop_ratio=0.7):
    h, w = frame.shape[:2]
    side = int(min(h, w) * crop_ratio)
    y1 = (h - side) // 2
    x1 = (w - side) // 2
    return frame[y1:y1 + side, x1:x1 + side]

@torch.no_grad()
def predict_from_bgr(frame_bgr):
    roi = center_crop_square(frame_bgr, CROP_RATIO)
    rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)

    x = transform(pil).unsqueeze(0).to(device)
    logits = model(x)
    probs = torch.softmax(logits, dim=1)[0].detach().cpu().numpy()

    idx = int(np.argmax(probs))
    return CLASSES[idx], float(probs[idx])

def camera_loop():
    global latest_jpeg  # declare ONCE at the top of the function

    cap = cv2.VideoCapture(CAM_INDEX)
    if not cap.isOpened():
        latest["label"] = "NO_CAMERA"
        latest["conf"] = 0.0
        latest["timestamp"] = int(time.time())
        return

    frame_delay = 1.0 / max(1, FPS)

    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue

        label, conf = predict_from_bgr(frame)
        latest["label"] = label
        latest["conf"] = round(conf, 3)
        latest["timestamp"] = int(time.time())

        # preview frame with overlay
        small = cv2.resize(frame, (640, 480))

        text1 = f"SOIL: {label.upper()}"
        text2 = f"CONF: {conf:.2f}"

        cv2.rectangle(small, (10, 10), (280, 85), (0, 0, 0), -1)
        cv2.putText(small, text1, (20, 42),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(small, text2, (20, 74),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2, cv2.LINE_AA)

        ok, buf = cv2.imencode(".jpg", small, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if ok:
            with jpeg_lock:
                latest_jpeg = buf.tobytes()

        time.sleep(frame_delay)

# start thread once on import
threading.Thread(target=camera_loop, daemon=True).start()

# ---------------- routes ----------------
@app.get("/soil")
def soil():
    return latest

@app.get("/frame.jpg")
def frame_jpg():
    with jpeg_lock:
        data = latest_jpeg
    if data is None:
        return Response(status_code=204)
    return Response(content=data, media_type="image/jpeg")

@app.get("/health")
def health():
    return {"ok": True, "device": device}