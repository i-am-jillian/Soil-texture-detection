import os, glob, csv, re, shutil
import numpy as np
from pathlib import Path

RAW_DIR = Path("raw/14725633")          # <-- your folder
OUT_IMG_DIR = Path("data/images")
OUT_CSV = Path("data/labels.csv")

# thresholds in mm (practical URC bins)
def texture_from_d50(d50_mm: float) -> str:
    if d50_mm < 0.06:
        return "fine"
    elif d50_mm < 0.6:
        return "medium"
    else:
        return "coarse"

def detect_columns(fieldnames):
    lower = [c.lower().strip() for c in fieldnames]
    # diameter column candidates
    diam_candidates = ["diam", "diameter", "d", "size", "particle_size", "particle size", "x"]
    finer_candidates = ["finer", "percent_finer", "percent finer", "finer(%)", "cumulative", "cum", "y"]

    def find_any(cands):
        for cand in cands:
            for i, name in enumerate(lower):
                if cand == name:
                    return fieldnames[i]
        # fallback: substring match
        for cand in cands:
            for i, name in enumerate(lower):
                if cand in name:
                    return fieldnames[i]
        return None

    diam_col = find_any(diam_candidates)
    finer_col = find_any(finer_candidates)

    return diam_col, finer_col

def load_psd(csv_path: Path):
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"No header in {csv_path}")
        diam_col, finer_col = detect_columns(reader.fieldnames)
        if diam_col is None or finer_col is None:
            raise ValueError(f"Could not detect diam/finer columns in {csv_path.name}. Columns: {reader.fieldnames}")

        diam = []
        finer = []
        for r in reader:
            try:
                diam.append(float(str(r[diam_col]).strip()))
                finer.append(float(str(r[finer_col]).strip()))
            except:
                continue

    if len(diam) < 3:
        raise ValueError(f"Not enough numeric rows in {csv_path.name}")

    diam = np.array(diam, dtype=float)
    finer = np.array(finer, dtype=float)

    order = np.argsort(diam)
    diam = diam[order]
    finer = finer[order]
    return diam, finer

def d_at_percent(diam, finer, p=50.0):
    # interpolate diameter where cumulative percent finer crosses p
    # make monotonic safer:
    # if finer isn't increasing, sort by finer too (rare)
    if np.any(np.diff(finer) < 0):
        order = np.argsort(finer)
        finer = finer[order]
        diam = diam[order]

    p = float(p)
    if p <= float(finer.min()):
        return float(diam[np.argmin(finer)])
    if p >= float(finer.max()):
        return float(diam[np.argmax(finer)])
    return float(np.interp(p, finer, diam))

def extract_sample_ids_from_csvs(psd_csvs):
    sample_to_label = {}
    for p in psd_csvs:
        sample_id = Path(p).stem  # e.g. F827
        try:
            diam, finer = load_psd(Path(p))
            d50 = d_at_percent(diam, finer, 50.0)
            sample_to_label[sample_id] = texture_from_d50(d50)
        except Exception as e:
            # skip bad csvs (but print so you know)
            print(f"[skip csv] {p} -> {e}")
    return sample_to_label

def find_sample_in_filename(filename, sample_ids):
    # match whole token like F827, not random substring
    # common pattern: F### or S### etc — we also try direct membership
    base = Path(filename).stem
    for sid in sample_ids:
        if re.search(rf"\b{re.escape(sid)}\b", base):
            return sid
    # fallback: substring match
    for sid in sample_ids:
        if sid in base:
            return sid
    return None

def main():
    OUT_IMG_DIR.mkdir(parents=True, exist_ok=True)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    psd_csvs = glob.glob(str(RAW_DIR / "**" / "*.csv"), recursive=True)
    if not psd_csvs:
        raise SystemExit(f"No CSV files found under {RAW_DIR}")

    # images are inside All_photos (your case), but we search recursively anyway
    imgs = []
    for ext in ("*.jpg", "*.JPG", "*.jpeg", "*.JPEG", "*.png", "*.PNG"):
        imgs += glob.glob(str(RAW_DIR / "**" / ext), recursive=True)
    if not imgs:
        raise SystemExit(f"No images found under {RAW_DIR}")

    sample_to_label = extract_sample_ids_from_csvs(psd_csvs)
    if not sample_to_label:
        raise SystemExit("No valid PSD CSVs parsed. Check CSV headers/format.")

    sample_ids = list(sample_to_label.keys())

    rows = []
    copied = 0
    for img in imgs:
        sid = find_sample_in_filename(img, sample_ids)
        if not sid:
            continue
        label = sample_to_label[sid]
        dst = OUT_IMG_DIR / Path(img).name
        shutil.copy2(img, dst)
        rows.append((str(dst).replace("\\", "/"), label))
        copied += 1

    if copied == 0:
        raise SystemExit("Matched 0 images to CSV sample IDs. Filenames may not include sample IDs; we can fix matching.")

    with open(OUT_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["filepath", "label"])
        w.writerows(rows)

    print(f"✅ Wrote {len(rows)} labeled images to {OUT_CSV}")
    print(f"✅ Copied images into {OUT_IMG_DIR}")

if __name__ == "__main__":
    main()