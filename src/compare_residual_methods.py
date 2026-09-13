from pathlib import Path
import csv
import math

import numpy as np
from PIL import Image

import torch

from model_residual import ResidualReconstructionCNN


DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

VAL_LR = Path("data/val/lr")
VAL_HR = Path("data/val/hr")

RESULTS = Path("results/residual")
COMPARE_DIR = RESULTS / "comparison"
COMPARE_DIR.mkdir(parents=True, exist_ok=True)


def image_to_numpy(path):
    image = Image.open(path).convert("L")

    return (
        np.asarray(image, dtype=np.float32)
        / 255.0
    )


def image_to_tensor(path):
    array = image_to_numpy(path)

    return (
        torch.from_numpy(array)
        .unsqueeze(0)
        .unsqueeze(0)
    )


def mse(reference, reconstruction):
    return float(
        np.mean(
            (reference - reconstruction) ** 2
        )
    )


def psnr_from_mse(error):
    if error == 0:
        return float("inf")

    return 10.0 * math.log10(
        1.0 / error
    )


# --------------------------------------------------
# Load best residual model
# --------------------------------------------------

checkpoint = torch.load(
    RESULTS / "best_model.pt",
    map_location=DEVICE,
    weights_only=False
)

model = ResidualReconstructionCNN().to(DEVICE)

model.load_state_dict(
    checkpoint["model_state_dict"]
)

model.eval()


print("Device:", DEVICE)
print(
    "Residual checkpoint epoch:",
    checkpoint["epoch"]
)
print()


rows = []

residual_mse_values = []
bilinear_mse_values = []
bicubic_mse_values = []

residual_psnr_values = []
bilinear_psnr_values = []
bicubic_psnr_values = []


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

    hr_np = image_to_numpy(
        hr_path
    )

    lr_pil = (
        Image.open(lr_path)
        .convert("L")
    )


    # ------------------------------------------------
    # Conventional bilinear
    # ------------------------------------------------

    bilinear_pil = lr_pil.resize(
        (256, 256),
        Image.Resampling.BILINEAR
    )

    bilinear_np = (
        np.asarray(
            bilinear_pil,
            dtype=np.float32
        )
        / 255.0
    )


    # ------------------------------------------------
    # Conventional bicubic
    # ------------------------------------------------

    bicubic_pil = lr_pil.resize(
        (256, 256),
        Image.Resampling.BICUBIC
    )

    bicubic_np = (
        np.asarray(
            bicubic_pil,
            dtype=np.float32
        )
        / 255.0
    )


    # ------------------------------------------------
    # Residual CNN
    # ------------------------------------------------

    lr_tensor = (
        image_to_tensor(lr_path)
        .to(DEVICE)
    )

    with torch.no_grad():

        residual_output = model(
            lr_tensor
        )

    residual_np = (
        residual_output
        .squeeze()
        .clamp(0.0, 1.0)
        .cpu()
        .numpy()
    )


    # ------------------------------------------------
    # Metrics
    # ------------------------------------------------

    residual_mse = mse(
        hr_np,
        residual_np
    )

    bilinear_mse = mse(
        hr_np,
        bilinear_np
    )

    bicubic_mse = mse(
        hr_np,
        bicubic_np
    )


    residual_psnr = psnr_from_mse(
        residual_mse
    )

    bilinear_psnr = psnr_from_mse(
        bilinear_mse
    )

    bicubic_psnr = psnr_from_mse(
        bicubic_mse
    )


    residual_mse_values.append(
        residual_mse
    )

    bilinear_mse_values.append(
        bilinear_mse
    )

    bicubic_mse_values.append(
        bicubic_mse
    )


    residual_psnr_values.append(
        residual_psnr
    )

    bilinear_psnr_values.append(
        bilinear_psnr
    )

    bicubic_psnr_values.append(
        bicubic_psnr
    )


    rows.append([
        stem,
        residual_mse,
        residual_psnr,
        bilinear_mse,
        bilinear_psnr,
        bicubic_mse,
        bicubic_psnr,
    ])


    print(stem)

    print(
        f"  Residual CNN "
        f"MSE={residual_mse:.8f} "
        f"PSNR={residual_psnr:.3f} dB"
    )

    print(
        f"  Bilinear     "
        f"MSE={bilinear_mse:.8f} "
        f"PSNR={bilinear_psnr:.3f} dB"
    )

    print(
        f"  Bicubic      "
        f"MSE={bicubic_mse:.8f} "
        f"PSNR={bicubic_psnr:.3f} dB"
    )


    # Save outputs

    Image.fromarray(
        (
            residual_np * 255.0
        )
        .round()
        .astype(np.uint8)
    ).save(
        COMPARE_DIR
        / f"{stem}_residual_cnn.png"
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
# Aggregate MSE
# --------------------------------------------------

residual_avg_mse = float(
    np.mean(residual_mse_values)
)

bilinear_avg_mse = float(
    np.mean(bilinear_mse_values)
)

bicubic_avg_mse = float(
    np.mean(bicubic_mse_values)
)


# PSNR computed from aggregate mean MSE

residual_psnr_from_avg_mse = (
    psnr_from_mse(
        residual_avg_mse
    )
)

bilinear_psnr_from_avg_mse = (
    psnr_from_mse(
        bilinear_avg_mse
    )
)

bicubic_psnr_from_avg_mse = (
    psnr_from_mse(
        bicubic_avg_mse
    )
)


# Arithmetic mean of per-image PSNRs

residual_mean_image_psnr = float(
    np.mean(residual_psnr_values)
)

bilinear_mean_image_psnr = float(
    np.mean(bilinear_psnr_values)
)

bicubic_mean_image_psnr = float(
    np.mean(bicubic_psnr_values)
)


print()
print("AGGREGATE RESULTS")
print("-----------------")

print(
    f"Residual CNN "
    f"MSE={residual_avg_mse:.8f} "
    f"PSNR(from mean MSE)="
    f"{residual_psnr_from_avg_mse:.3f} dB "
    f"| Mean image PSNR="
    f"{residual_mean_image_psnr:.3f} dB"
)

print(
    f"Bilinear     "
    f"MSE={bilinear_avg_mse:.8f} "
    f"PSNR(from mean MSE)="
    f"{bilinear_psnr_from_avg_mse:.3f} dB "
    f"| Mean image PSNR="
    f"{bilinear_mean_image_psnr:.3f} dB"
)

print(
    f"Bicubic      "
    f"MSE={bicubic_avg_mse:.8f} "
    f"PSNR(from mean MSE)="
    f"{bicubic_psnr_from_avg_mse:.3f} dB "
    f"| Mean image PSNR="
    f"{bicubic_mean_image_psnr:.3f} dB"
)


# --------------------------------------------------
# Save results
# --------------------------------------------------

with open(
    RESULTS / "comparison_metrics.csv",
    "w",
    newline=""
) as file:

    writer = csv.writer(file)

    writer.writerow([
        "image",
        "residual_cnn_mse",
        "residual_cnn_psnr_db",
        "bilinear_mse",
        "bilinear_psnr_db",
        "bicubic_mse",
        "bicubic_psnr_db"
    ])

    writer.writerows(rows)

    writer.writerow([])

    writer.writerow([
        "MEAN_MSE",
        residual_avg_mse,
        "",
        bilinear_avg_mse,
        "",
        bicubic_avg_mse,
        ""
    ])

    writer.writerow([
        "PSNR_FROM_MEAN_MSE",
        "",
        residual_psnr_from_avg_mse,
        "",
        bilinear_psnr_from_avg_mse,
        "",
        bicubic_psnr_from_avg_mse
    ])

    writer.writerow([
        "MEAN_PER_IMAGE_PSNR",
        "",
        residual_mean_image_psnr,
        "",
        bilinear_mean_image_psnr,
        "",
        bicubic_mean_image_psnr
    ])