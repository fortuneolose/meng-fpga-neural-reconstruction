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


# --------------------------------------------------
# Configuration
# --------------------------------------------------

SEED = 42

BATCH_SIZE = 8
EPOCHS = 30
LEARNING_RATE = 1e-3

TRAIN_LR = Path("data/round3/train/lr")
TRAIN_HR = Path("data/round3/train/hr")

VAL_LR = Path("data/round3/val/lr")
VAL_HR = Path("data/round3/val/hr")

RESULTS = Path("results/round3")
RESULTS.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# Reproducibility
# --------------------------------------------------

random.seed(SEED)
np.random.seed(SEED)

torch.manual_seed(SEED)
torch.cuda.manual_seed_all(SEED)

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)


# --------------------------------------------------
# Dataset
# --------------------------------------------------

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

        stem = lr_path.stem.replace(
            "_lr",
            ""
        )

        hr_path = (
            self.hr_dir
            / f"{stem}_hr.png"
        )

        if not hr_path.exists():
            raise RuntimeError(
                f"Missing HR pair: {hr_path}"
            )

        lr = (
            np.asarray(
                Image.open(lr_path).convert("L"),
                dtype=np.float32
            )
            / 255.0
        )

        hr = (
            np.asarray(
                Image.open(hr_path).convert("L"),
                dtype=np.float32
            )
            / 255.0
        )

        lr = (
            torch.from_numpy(lr)
            .unsqueeze(0)
        )

        hr = (
            torch.from_numpy(hr)
            .unsqueeze(0)
        )

        return lr, hr


# --------------------------------------------------
# Data loaders
# --------------------------------------------------

train_dataset = ReconstructionDataset(
    TRAIN_LR,
    TRAIN_HR
)

val_dataset = ReconstructionDataset(
    VAL_LR,
    VAL_HR
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
print("Batch size:", BATCH_SIZE)
print("Epochs:", EPOCHS)


# --------------------------------------------------
# Model
# --------------------------------------------------

model = ResidualReconstructionCNN().to(
    DEVICE
)

parameter_count = sum(
    p.numel()
    for p in model.parameters()
    if p.requires_grad
)

print(
    "Trainable parameters:",
    parameter_count
)


criterion = nn.MSELoss()

optimizer = torch.optim.Adam(
    model.parameters(),
    lr=LEARNING_RATE
)


# --------------------------------------------------
# Metrics
# --------------------------------------------------

def psnr_from_mse(error):

    if error == 0:
        return float("inf")

    return (
        10.0
        * math.log10(
            1.0 / error
        )
    )


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

            n = lr.size(0)

            total_loss += (
                loss.item() * n
            )

            total_samples += n

    return (
        total_loss
        / total_samples
    )


# --------------------------------------------------
# Initial bilinear-equivalent result
# --------------------------------------------------

initial_val_mse = evaluate()

initial_val_psnr = psnr_from_mse(
    initial_val_mse
)

print()
print(
    f"Initial validation MSE: "
    f"{initial_val_mse:.8f}"
)

print(
    f"Initial validation PSNR: "
    f"{initial_val_psnr:.3f} dB"
)

print()


# --------------------------------------------------
# Training
# --------------------------------------------------

history = []

best_val_mse = float("inf")

global_step = 0


for epoch in range(
    1,
    EPOCHS + 1
):

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

        global_step += 1

        n = lr.size(0)

        total_train_loss += (
            loss.item() * n
        )

        total_samples += n


    train_mse = (
        total_train_loss
        / total_samples
    )

    val_mse = evaluate()


    train_psnr = psnr_from_mse(
        train_mse
    )

    val_psnr = psnr_from_mse(
        val_mse
    )


    history.append([
        epoch,
        global_step,
        train_mse,
        val_mse,
        train_psnr,
        val_psnr
    ])


    print(
        f"Epoch {epoch:02d}/{EPOCHS} "
        f"| Step {global_step:04d} "
        f"| Train MSE: {train_mse:.8f} "
        f"| Val MSE: {val_mse:.8f} "
        f"| Val PSNR: {val_psnr:.3f} dB"
    )


    if val_mse < best_val_mse:

        best_val_mse = val_mse

        torch.save(
            {
                "epoch":
                    epoch,

                "global_step":
                    global_step,

                "model_state_dict":
                    model.state_dict(),

                "optimizer_state_dict":
                    optimizer.state_dict(),

                "val_mse":
                    val_mse,

                "val_psnr":
                    val_psnr,

                "seed":
                    SEED,

                "batch_size":
                    BATCH_SIZE,

                "learning_rate":
                    LEARNING_RATE,

                "train_samples":
                    len(train_dataset),

                "val_samples":
                    len(val_dataset),

                "parameters":
                    parameter_count,
            },

            RESULTS / "best_model.pt"
        )


# --------------------------------------------------
# Final checkpoint
# --------------------------------------------------

torch.save(
    {
        "epoch":
            EPOCHS,

        "global_step":
            global_step,

        "model_state_dict":
            model.state_dict(),

        "optimizer_state_dict":
            optimizer.state_dict(),

        "seed":
            SEED,

        "batch_size":
            BATCH_SIZE,

        "learning_rate":
            LEARNING_RATE,
    },

    RESULTS
    / "final_model.pt"
)


# --------------------------------------------------
# Save training history
# --------------------------------------------------

with open(
    RESULTS / "training_history.csv",
    "w",
    newline=""
) as file:

    writer = csv.writer(file)

    writer.writerow([
        "epoch",
        "global_step",
        "train_mse",
        "val_mse",
        "train_psnr_db",
        "val_psnr_db"
    ])

    writer.writerows(history)


# --------------------------------------------------
# Summary
# --------------------------------------------------

best_epoch = min(
    history,
    key=lambda row: row[3]
)


print()
print("Round 3 training complete")
print("-------------------------")

print(
    f"Initial validation PSNR: "
    f"{initial_val_psnr:.3f} dB"
)

print(
    f"Best epoch: "
    f"{best_epoch[0]}"
)

print(
    f"Best global step: "
    f"{best_epoch[1]}"
)

print(
    f"Best validation MSE: "
    f"{best_epoch[3]:.8f}"
)

print(
    f"Best validation PSNR: "
    f"{best_epoch[5]:.3f} dB"
)

print(
    f"Total optimiser steps: "
    f"{global_step}"
)

print()
print(
    "ROUND 3 TRAINING: PASS"
)