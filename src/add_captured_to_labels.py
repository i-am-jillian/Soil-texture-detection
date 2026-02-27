import glob, csv, os

# Change these patterns if your filenames differ
PATTERNS = [
    ("data/images/coarse_custom_*.jpg", "coarse"),
    ("data/images/medium_custom_*.jpg", "medium"),
    ("data/images/fine_custom_*.jpg", "fine"),
]

LABELS_CSV = "data/labels.csv"

def main():
    existing = set()
    if os.path.exists(LABELS_CSV):
        with open(LABELS_CSV, "r", newline="") as f:
            r = csv.reader(f)
            for row in r:
                if len(row) >= 2:
                    existing.add((row[0], row[1]))

    added = 0
    with open(LABELS_CSV, "a", newline="") as f:
        w = csv.writer(f)
        for pattern, label in PATTERNS:
            files = sorted(glob.glob(pattern))
            for fp in files:
                row = (fp, label)
                if row not in existing:
                    w.writerow([fp, label])
                    added += 1


if __name__ == "__main__":
    main()