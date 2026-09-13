from pathlib import Path
import csv
import math

import numpy as np
from PIL import Image

import torch
import torch.nn as nn
import torch.nn.functional as F

from model import CompactReconstructionCNN


DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

VAL_LR = Path("data/val/lr")
VAL_HR = Path("data/val/hr")

RESULTS = Path("results")
COMPARE_DIR = RESULTS / "comparison"

COMPARE_DIR.mkdir(
    parents=True,
    exist_ok=True
)


def image_to_numpy(path):
    image = Image.open(path).convert("L")

    return (
        np.asarray(
            image,
            dtype=np.float32
        ) / 255.0
    )


def image_to_tensor(path):
    array = image_to_numpy(path)

    return (
        torch
        .from_numpy(array)
        .unsqueeze(0)
        .unsqueeze(0)
    )


def mse(reference, reconstruction):
    return float(
        np.mean(
            (reference - reconstruction) ** 2
        )
    )


def psnr(reference, reconstruction):
    error = mse(
        reference,
        reconstruction
    )

    if error == 0:
        return float("inf")

    return (
        10.0
        * math.log10(1.0 / error)
    )


# --------------------------------------------------
# Load best trained model
# --------------------------------------------------

checkpoint = torch.load(
    RESULTS / "best_model.pt",
    map_location=DEVICE,
    weights_only=False
)

model = CompactReconstructionCNN().to(DEVICE)

model.load_state_dict(
    checkpoint["model_state_dict"]
)

model.eval()

print("Device:", DEVICE)
print(
    "Checkpoint epoch:",
    checkpoint["epoch"]
)

print(
    "Checkpoint validation PSNR:",
    f"{checkpoint['val_psnr']:.3f} dB"
)

print()


# --------------------------------------------------
# Evaluation
# --------------------------------------------------

rows = []

cnn_mse_all = []
bilinear_mse_all = []
bicubic_mse_all = []

for lr_path in sorted(
    VAL_LR.glob("*_lr.png")
):

    stem = lr_path.stem.replace(
        "_lr",
        ""
    )

    hr_path = (
        VAL_HR
        / f"{stem}_hr.png"
    )

    lr_pil = (
        Image
        .open(lr_path)
        .convert("L")
    )

    hr_np = image_to_numpy(
        hr_path
    )

    # ----------------------------------------------
    # Bilinear
    # ----------------------------------------------

    bilinear_pil = lr_pil.resize(
        (256, 256),
        Image.Resampling.BILINEAR
    )

    bilinear_np = (
        np.asarray(
            bilinear_pil,
            dtype=np.float32
        ) / 255.0
    )

    # ----------------------------------------------
    # Bicubic
    # ----------------------------------------------

    bicubic_pil = lr_pil.resize(
        (256, 256),
        Image.Resampling.BICUBIC
    )

    bicubic_np = (
        np.asarray(
            bicubic_pil,
            dtype=np.float32
        ) / 255.0
    )

    # ----------------------------------------------
    # CNN
    # ----------------------------------------------

    lr_tensor = (
        image_to_tensor(lr_path)
        .to(DEVICE)
    )

    with torch.no_grad():

        cnn_output = model(
            lr_tensor
        )

    cnn_np = (
        cnn_output
        .squeeze()
        .clamp(0.0, 1.0)
        .cpu()
        .numpy()
    )

    # ----------------------------------------------
    # Metrics
    # ----------------------------------------------

    cnn_mse = mse(
        hr_np,
        cnn_np
    )

    bilinear_mse = mse(
        hr_np,
        bilinear_np
    )

    bicubic_mse = mse(
        hr_np,
        bicubic_np
    )

    cnn_psnr = psnr(
        hr_np,
        cnn_np
    )

    bilinear_psnr = psnr(
        hr_np,
        bilinear_np
    )

    bicubic_psnr = psnr(
        hr_np,
        bicubic_np
    )

    cnn_mse_all.append(cnn_mse)
    bilinear_mse_all.append(
        bilinear_mse
    )
    bicubic_mse_all.append(
        bicubic_mse
    )

    rows.append([
        stem,
        cnn_mse,
        cnn_psnr,
        bilinear_mse,
        bilinear_psnr,
        bicubic_mse,
        bicubic_psnr
    ])

    print(stem)

    print(
        f"  CNN      "
        f"MSE={cnn_mse:.8f} "
        f"PSNR={cnn_psnr:.3f} dB"
    )

    print(
        f"  Bilinear "
        f"MSE={bilinear_mse:.8f} "
        f"PSNR={bilinear_psnr:.3f} dB"
    )

    print(
        f"  Bicubic  "
        f"MSE={bicubic_mse:.8f} "
        f"PSNR={bicubic_psnr:.3f} dB"
    )

    # ----------------------------------------------
    # Save example reconstructions
    # ----------------------------------------------

    Image.fromarray(
        (
            cnn_np * 255.0
        ).round().astype(np.uint8)
    ).save(
        COMPARE_DIR
        / f"{stem}_cnn.png"
    )

    bilinear_pil.save(
        COMPARE_DIR
        / f"{stem}_bilinear.png"
    )

    bicubic_pil.save(
        COMPARE_DIR
        / f"{stem}_bicubic.png"
    )

    Image.open(hr_path).save(
        COMPARE_DIR
        / f"{stem}_target.png"
    )


# --------------------------------------------------
# Aggregate metrics
# --------------------------------------------------

cnn_avg_mse = np.mean(
    cnn_mse_all
)

bilinear_avg_mse = np.mean(
    bilinear_mse_all
)

bicubic_avg_mse = np.mean(
    bicubic_mse_all
)


cnn_avg_psnr = (
    10.0
    * math.log10(
        1.0 / cnn_avg_mse
    )
)

bilinear_avg_psnr = (
    10.0
    * math.log10(
        1.0 / bilinear_avg_mse
    )
)

bicubic_avg_psnr = (
    10.0
    * math.log10(
        1.0 / bicubic_avg_mse
    )
)


print()
print("AVERAGE RESULTS")
print("---------------")

print(
    f"CNN      "
    f"MSE={cnn_avg_mse:.8f} "
    f"PSNR={cnn_avg_psnr:.3f} dB"
)

print(
    f"Bilinear "
    f"MSE={bilinear_avg_mse:.8f} "
    f"PSNR={bilinear_avg_psnr:.3f} dB"
)

print(
    f"Bicubic  "
    f"MSE={bicubic_avg_mse:.8f} "
    f"PSNR={bicubic_avg_psnr:.3f} dB"
)


# --------------------------------------------------
# Save table
# --------------------------------------------------

with open(
    RESULTS / "comparison_metrics.csv",
    "w",
    newline=""
) as file:

    writer = csv.writer(file)

    writer.writerow([
        "image",
        "cnn_mse",
        "cnn_psnr_db",
        "bilinear_mse",
        "bilinear_psnr_db",
        "bicubic_mse",
        "bicubic_psnr_db"
    ])

    writer.writerows(rows)

    writer.writerow([])

    writer.writerow([
        "AVERAGE",
        cnn_avg_mse,
        cnn_avg_psnr,
        bilinear_avg_mse,
        bilinear_avg_psnr,
        bicubic_avg_mse,
        bicubic_avg_psnr
    ])