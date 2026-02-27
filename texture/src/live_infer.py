import cv2
import torch
import torch.nn as nn
import numpy as np
from collections import deque
from torchvision import transforms, models
from PIL import Image

# ------------------------------------
# CONFIG
# ------------------------------------
CLASSES = ["coarse", "medium", "fine"]
MODEL_PATH = "models/texture_best.pt"

CAM_INDEX = 0          # try 1 or 2 if wrong camera
CROP_RATIO = 0.70      # 0.55–0.85; higher = more of frame
IMG_SIZE = 224         # matches your training pipeline

SMOOTH_WINDOW = 12     # how many frames to smooth over
CONF_THRESHOLD = 0.45  # below this, show "UNCERTAIN"

# ------------------------------------
# MODEL LOAD
# ------------------------------------
device = "cuda" if torch.cuda.is_available() else "cpu"

model = models.mobilenet_v3_small(weights=None)
model.classifier[3] = nn.Linear(model.classifier[3].in_features, len(CLASSES))

state = torch.load(MODEL_PATH, map_location=device)
model.load_state_dict(state["model"])
model.eval().to(device)

transform = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],
                         [0.229, 0.224, 0.225]),
])

# ------------------------------------
# HELPERS
# ------------------------------------
def center_crop_square(frame, crop_ratio=0.7):
    """Crop a centered square region to reduce background bias."""
    h, w = frame.shape[:2]
    side = int(min(h, w) * crop_ratio)
    y1 = (h - side) // 2
    x1 = (w - side) // 2
    return frame[y1:y1+side, x1:x1+side]

@torch.no_grad()
def predict_probs(frame_bgr):
    """Return per-class probabilities for a BGR frame."""
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb)
    x = transform(pil_img).unsqueeze(0).to(device)
    logits = model(x)
    probs = torch.softmax(logits, dim=1).cpu().numpy()[0]
    return probs  # np array length 3

def format_probs(probs):
    return f"C:{probs[0]:.2f} M:{probs[1]:.2f} F:{probs[2]:.2f}"

def draw_overlay(frame, text_lines, box_xy=(10, 10)):
    x, y = box_xy
    for i, t in enumerate(text_lines):
        pos = (x, y + 30*i)

        # Black shadow
        cv2.putText(frame, t, pos,
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                    (0, 0, 0), 4, cv2.LINE_AA)

        # White text
        cv2.putText(frame, t, pos,
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                    (255, 255, 255), 2, cv2.LINE_AA)

def main():
    cap = cv2.VideoCapture(CAM_INDEX)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera index {CAM_INDEX}. Try CAM_INDEX=1 or 2.")

    # Smoothing buffers
    prob_hist = deque(maxlen=SMOOTH_WINDOW)
    pred_hist = deque(maxlen=SMOOTH_WINDOW)

    print("Controls: q=quit | c=toggle crop box | r=reset smoothing")
    show_crop_box = True

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Crop center ROI
        roi = center_crop_square(frame, CROP_RATIO)

        # Predict probabilities on ROI
        probs = predict_probs(roi)
        prob_hist.append(probs)
        pred_hist.append(int(np.argmax(probs)))

        # Smoothed probs (mean over last N)
        probs_smooth = np.mean(np.array(prob_hist), axis=0)
        pred_idx = int(np.argmax(probs_smooth))
        conf = float(probs_smooth[pred_idx])

        # Majority vote label (optional secondary stabilizer)
        vote_idx = int(np.bincount(np.array(pred_hist), minlength=len(CLASSES)).argmax())

        # Decide label to show
        label = CLASSES[pred_idx]
        if conf < CONF_THRESHOLD:
            label_show = "UNCERTAIN"
        else:
            label_show = label.upper()

        # Draw crop box on the main frame so you know what it's using
        if show_crop_box:
            h, w = frame.shape[:2]
            side = int(min(h, w) * CROP_RATIO)
            y1 = (h - side) // 2
            x1 = (w - side) // 2
            cv2.rectangle(frame, (x1, y1), (x1+side, y1+side), (0, 255, 0), 2)

        lines = [
            f"PRED: {label_show}  (conf={conf:.2f})",
            f"Smooth probs: {format_probs(probs_smooth)}",
            f"Vote label: {CLASSES[vote_idx].upper()}   window={len(prob_hist)}",
            f"Crop ratio: {CROP_RATIO:.2f}  cam={CAM_INDEX}",
        ]
        draw_overlay(frame, lines, (10, 30))

        cv2.imshow("Soil Texture Live Inference", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break
        elif key == ord("c"):
            show_crop_box = not show_crop_box
        elif key == ord("r"):
            prob_hist.clear()
            pred_hist.clear()
            print("Smoothing reset.")

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()