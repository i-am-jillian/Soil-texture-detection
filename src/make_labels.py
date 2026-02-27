import cv2
import numpy as np
import time
from pathlib import Path

CLASS_NAME = "coarse"   # change to "medium" or "fine"
NUM_FRAMES = 50
IMG_SIZE = 300

CAPTURE_INTERVAL_SEC = 0.20  # 0.20 = 5 fps, 0.50 = 2 fps, 1.0 = 1 fps
CAM_INDEX = 0                # try 1 or 2 if using Continuity Camera / iPhone

SAVE_DIR = Path("data/images")
NPY_DIR = Path("data")

# If True, running again with same CLASS_NAME overwrites coarse_frames.npy and coarse_custom_*.jpg
OVERWRITE = True


def capture_frames():
    cap = cv2.VideoCapture(CAM_INDEX)

    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera index {CAM_INDEX}. Try CAM_INDEX=1 or 2.")

    print("Press 's' to start capturing")
    print("Press 'q' to quit")

    frames = []
    capturing = False
    count = 0

    last_capture_time = 0.0

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            print("Failed to read frame from camera.")
            break

        display = frame.copy()

        # Overlay info
        cv2.putText(display, f"Class: {CLASS_NAME}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(display, f"Captured: {count}/{NUM_FRAMES}", (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        if capturing:
            # green border while capturing
            cv2.rectangle(display, (0, 0), (display.shape[1], display.shape[0]),
                          (0, 255, 0), 10)

            now = time.time()
            if now - last_capture_time >= CAPTURE_INTERVAL_SEC:
                resized = cv2.resize(frame, (IMG_SIZE, IMG_SIZE))
                frames.append(resized)
                count += 1
                last_capture_time = now
                print(f"Captured {count}/{NUM_FRAMES}")

                if count >= NUM_FRAMES:
                    break

        cv2.imshow("Soil Capture", display)
        key = cv2.waitKey(1) & 0xFF

        #click the OpenCV window before pressing keys
        if key == ord("s"):
            capturing = True
            last_capture_time = 0.0
            print("Capturing started...")

        if key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

    return np.array(frames, dtype=np.uint8)


def save_data(frames: np.ndarray):
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    NPY_DIR.mkdir(parents=True, exist_ok=True)

    if frames.shape[0] == 0:
        print("No frames captured; nothing to save.")
        return

    # Save numpy array
    if OVERWRITE:
        npy_path = NPY_DIR / f"{CLASS_NAME}_frames.npy"
    else:
        ts = int(time.time())
        npy_path = NPY_DIR / f"{CLASS_NAME}_frames_{ts}.npy"

    np.save(npy_path, frames)
    print(f"Saved numpy array to {npy_path}")
    print("Array shape:", frames.shape)  # (50, 300, 300, 3)

    # Save images for your existing training pipeline
    for i, img in enumerate(frames):
        if OVERWRITE:
            filename = SAVE_DIR / f"{CLASS_NAME}_custom_{i}.jpg"
        else:
            ts = int(time.time())
            filename = SAVE_DIR / f"{CLASS_NAME}_{ts}_{i}.jpg"

        cv2.imwrite(str(filename), img)

    print(f"Saved {len(frames)} images to {SAVE_DIR}")


if __name__ == "__main__":
    frames = capture_frames()
    save_data(frames)