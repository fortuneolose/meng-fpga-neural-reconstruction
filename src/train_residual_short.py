from pathlib import Path
import csv
import math
import random

import numpy as np
from PIL import Image

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

from model_residual import ResidualReconstructionCNN


SEED = 42

random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.cuda.manual_seed_all(SEED)

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

BATCH_SIZE = 8
EPOCHS = 30
LEARNING_RATE = 1e-3

RESULTS = Path("results/residual")
RESULTS.mkdir(parents=True, exist_ok=True)


class ReconstructionDataset(Dataset):

    def __init__(self, lr_dir, hr_dir):
        self.lr_dir = Path(lr_dir)
        self.hr_dir = Path(hr_dir)

        self.lr_files = sorted(
            self.lr_dir.glob("*_lr.png")
        )

        if not self.lr_files:
            raise RuntimeError(
                f"No LR images found in {self.lr_dir}"
            )

    def __len__(self):
        return len(self.lr_files)

    def __getitem__(self, index):

        lr_path = self.lr_files[index]

        name = lr_path.stem.replace("_lr", "")

        hr_path = self.hr_dir / f"{name}_hr.png"

        lr = Image.open(lr_path).convert("L")
        hr = Image.open(hr_path).convert("L")

        lr = (
            np.asarray(lr, dtype=np.float32)
            / 255.0
        )

        hr = (
            np.asarray(hr, dtype=np.float32)
            / 255.0
        )

        lr = torch.from_numpy(lr).unsqueeze(0)
        hr = torch.from_numpy(hr).unsqueeze(0)

        return lr, hr


train_dataset = ReconstructionDataset(
    "data/train/lr",
    "data/train/hr"
)

val_dataset = ReconstructionDataset(
    "data/val/lr",
    "data/val/hr"
)

generator = torch.Generator()
generator.manual_seed(SEED)

train_loader = DataLoader(
    train_dataset,
    batch_size=BATCH_SIZE,
    shuffle=True,
    generator=generator
)

val_loader = DataLoader(
    val_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False
)

print("Device:", DEVICE)
print("Training samples:", len(train_dataset))
print("Validation samples:", len(val_dataset))


model = ResidualReconstructionCNN().to(DEVICE)

criterion = nn.MSELoss()

optimizer = torch.optim.Adam(
    model.parameters(),
    lr=LEARNING_RATE
)


def psnr_from_mse(mse):
    if mse == 0:
        return float("inf")

    return 10.0 * math.log10(1.0 / mse)


def evaluate():

    model.eval()

    total_loss = 0.0
    total_samples = 0

    with torch.no_grad():

        for lr, hr in val_loader:

            lr = lr.to(DEVICE)
            hr = hr.to(DEVICE)

            output = model(lr)

            loss = criterion(
                output,
                hr
            )

            batch_size = lr.size(0)

            total_loss += (
                loss.item()
                * batch_size
            )

            total_samples += batch_size

    return total_loss / total_samples


# Initial validation performance before training
initial_val_loss = evaluate()
initial_val_psnr = psnr_from_mse(
    initial_val_loss
)

print()
print(
    f"Initial validation MSE: "
    f"{initial_val_loss:.8f}"
)

print(
    f"Initial validation PSNR: "
    f"{initial_val_psnr:.3f} dB"
)

print()


history = []

best_val_loss = float("inf")

for epoch in range(1, EPOCHS + 1):

    model.train()

    total_train_loss = 0.0
    total_samples = 0

    for lr, hr in train_loader:

        lr = lr.to(DEVICE)
        hr = hr.to(DEVICE)

        optimizer.zero_grad()

        output = model(lr)

        loss = criterion(
            output,
            hr
        )

        if not torch.isfinite(loss):
            raise RuntimeError(
                f"Non-finite loss "
                f"at epoch {epoch}"
            )

        loss.backward()
        optimizer.step()

        batch_size = lr.size(0)

        total_train_loss += (
            loss.item()
            * batch_size
        )

        total_samples += batch_size

    train_loss = (
        total_train_loss
        / total_samples
    )

    val_loss = evaluate()

    train_psnr = psnr_from_mse(
        train_loss
    )

    val_psnr = psnr_from_mse(
        val_loss
    )

    history.append([
        epoch,
        train_loss,
        val_loss,
        train_psnr,
        val_psnr
    ])

    print(
        f"Epoch {epoch:02d}/{EPOCHS} "
        f"| Train MSE: {train_loss:.8f} "
        f"| Val MSE: {val_loss:.8f} "
        f"| Val PSNR: {val_psnr:.3f} dB"
    )

    if val_loss < best_val_loss:

        best_val_loss = val_loss

        torch.save(
            {
                "epoch":
                    epoch,

                "model_state_dict":
                    model.state_dict(),

                "optimizer_state_dict":
                    optimizer.state_dict(),

                "val_loss":
                    val_loss,

                "val_psnr":
                    val_psnr,

                "seed":
                    SEED,

                "batch_size":
                    BATCH_SIZE,

                "learning_rate":
                    LEARNING_RATE,

                "initial_val_loss":
                    initial_val_loss,

                "initial_val_psnr":
                    initial_val_psnr,
            },
            RESULTS / "best_model.pt"
        )


torch.save(
    {
        "model_state_dict":
            model.state_dict(),

        "optimizer_state_dict":
            optimizer.state_dict(),

        "epochs":
            EPOCHS,

        "seed":
            SEED,

        "batch_size":
            BATCH_SIZE,

        "learning_rate":
            LEARNING_RATE,
    },
    RESULTS / "short_training_final.pt"
)


with open(
    RESULTS / "training_history.csv",
    "w",
    newline=""
) as file:

    writer = csv.writer(file)

    writer.writerow([
        "epoch",
        "train_mse",
        "val_mse",
        "train_psnr_db",
        "val_psnr_db"
    ])

    writer.writerows(history)


best_epoch = min(
    history,
    key=lambda row: row[2]
)


print()
print("Residual training complete")
print("--------------------------")

print(
    f"Initial validation PSNR: "
    f"{initial_val_psnr:.3f} dB"
)

print(
    f"Best epoch: "
    f"{best_epoch[0]}"
)

print(
    f"Best validation MSE: "
    f"{best_epoch[2]:.8f}"
)

print(
    f"Best validation PSNR: "
    f"{best_epoch[4]:.3f} dB"
)

print()
print(
    "RESIDUAL SHORT TRAINING: PASS"
)