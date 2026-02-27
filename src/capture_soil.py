import cv2
import numpy as np
import os
from pathlib import Path

# CONFIG
CLASS_NAME = "coarse"   # change to "medium" or "fine"
NUM_FRAMES = 50
IMG_SIZE = 300

SAVE_DIR = Path("data/images")
NPY_DIR = Path("data")
SAVE_DIR.mkdir(parents=True, exist_ok=True)
NPY_DIR.mkdir(parents=True, exist_ok=True)

def capture_frames():
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        raise RuntimeError("Could not open webcam")

    print("Press 's' to start capturing 50 frames")
    print("Press 'q' to quit")

    frames = []
    capturing = False
    count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        display = frame.copy()
        cv2.putText(display, f"Class: {CLASS_NAME}", (10,30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)

        if capturing:
            resized = cv2.resize(frame, (IMG_SIZE, IMG_SIZE))
            frames.append(resized)
            count += 1
            print(f"Captured {count}/{NUM_FRAMES}")

            if count >= NUM_FRAMES:
                break

        cv2.imshow("Soil Capture", display)
        key = cv2.waitKey(1) & 0xFF

        if key == ord("s"):
            capturing = True
            print("Capturing started...")

        if key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

    return np.array(frames)

def save_data(frames):
    npy_path = NPY_DIR / f"{CLASS_NAME}_frames.npy"
    np.save(npy_path, frames)
    print(f"Saved numpy array to {npy_path}")

    # Also save individual images for training
    for i, img in enumerate(frames):
        filename = SAVE_DIR / f"{CLASS_NAME}_custom_{i}.jpg"
        cv2.imwrite(str(filename), img)

    print(f"Saved {len(frames)} images to {SAVE_DIR}")

if __name__ == "__main__":
    frames = capture_frames()
    print("Array shape:", frames.shape)  # (50, 300, 300, 3)
    save_data(frames)