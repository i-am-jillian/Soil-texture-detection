import csv, random
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, models
from PIL import Image
from tqdm import tqdm

CLASSES = ["coarse", "medium", "fine"]
C2I = {c:i for i,c in enumerate(CLASSES)}

class CSVDataset(Dataset):
    def __init__(self, csv_path, transform=None):
        self.items = []
        with open(csv_path, "r", newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                self.items.append((row["filepath"], C2I[row["label"]]))
        self.transform = transform

    def __len__(self): return len(self.items)

    def __getitem__(self, idx):
        fp, y = self.items[idx]
        x = Image.open(fp).convert("RGB")
        if self.transform: x = self.transform(x)
        return x, torch.tensor(y)

def split_csv(in_csv="data/labels.csv", out_train="data/train.csv", out_val="data/val.csv", val_ratio=0.2, seed=42):
    with open(in_csv, "r", newline="") as f:
        rows = list(csv.DictReader(f))
    random.Random(seed).shuffle(rows)
    n_val = max(1, int(len(rows)*val_ratio))
    val = rows[:n_val]
    train = rows[n_val:]

    for out, data in [(out_train, train), (out_val, val)]:
        with open(out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["filepath","label"])
            for r in data:
                w.writerow([r["filepath"], r["label"]])

    print(f"Split: train={len(train)} val={len(val)}")

@torch.no_grad()
def eval_acc(model, loader, device):
    model.eval()
    ok = 0; total = 0
    for x,y in loader:
        x,y = x.to(device), y.to(device)
        pred = model(x).argmax(1)
        ok += (pred==y).sum().item()
        total += y.numel()
    return ok/total

def main():
    split_csv()

    device = "cuda" if torch.cuda.is_available() else "cpu"

    train_tfm = transforms.Compose([
        transforms.Resize((224,224)),
        transforms.RandomHorizontalFlip(0.5),
        transforms.ColorJitter(0.15,0.15,0.1),
        transforms.ToTensor(),
        transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225]),
    ])
    val_tfm = transforms.Compose([
        transforms.Resize((224,224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225]),
    ])

    train_ds = CSVDataset("data/train.csv", train_tfm)
    val_ds   = CSVDataset("data/val.csv", val_tfm)
    train_ld = DataLoader(train_ds, batch_size=32, shuffle=True, num_workers=2)
    val_ld   = DataLoader(val_ds, batch_size=32, shuffle=False, num_workers=2)

    model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
    model.classifier[3] = nn.Linear(model.classifier[3].in_features, len(CLASSES))
    model = model.to(device)

    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()

    Path("models").mkdir(exist_ok=True)
    best = 0.0
    for epoch in range(1, 16):
        model.train()
        pbar = tqdm(train_ld, desc=f"epoch {epoch}")
        for x,y in pbar:
            x,y = x.to(device), y.to(device)
            logits = model(x)
            loss = loss_fn(logits, y)
            opt.zero_grad()
            loss.backward()
            opt.step()
            pbar.set_postfix(loss=float(loss.item()))

        acc = eval_acc(model, val_ld, device)
        print("val acc:", round(acc, 3))
        if acc > best:
            best = acc
            torch.save({"model": model.state_dict()}, "models/texture_best.pt")
            print("saved models/texture_best.pt")

if __name__ == "__main__":
    main()