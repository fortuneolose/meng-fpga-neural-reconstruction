from pathlib import Path
import csv
import math

import numpy as np
from PIL import Image

import torch
import torch.nn.functional as F

from model_residual import ResidualReconstructionCNN


DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

VAL_LR = Path("data/round3/val/lr")
VAL_HR = Path("data/round3/val/hr")

RESULTS = Path("results/round3")
COMPARE_DIR = RESULTS / "comparison"
COMPARE_DIR.mkdir(parents=True, exist_ok=True)


def image_to_numpy(path):
    return (
        np.asarray(
            Image.open(path).convert("L"),
            dtype=np.float32
        )
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
# Load best Round 3 residual model
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
print("Checkpoint epoch:", checkpoint["epoch"])
print("Validation images:", len(list(VAL_LR.glob("*_lr.png"))))
print()


rows = []

methods = {
    "residual": [],
    "torch_bilinear": [],
    "pil_bilinear": [],
    "bicubic": [],
}

psnrs = {
    key: []
    for key in methods
}

wins_vs_bicubic = 0
wins_vs_torch_bilinear = 0


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

    hr_np = image_to_numpy(hr_path)

    lr_pil = (
        Image.open(lr_path)
        .convert("L")
    )

    lr_tensor = (
        image_to_tensor(lr_path)
        .to(DEVICE)
    )


    # ------------------------------------------------
    # Residual CNN
    # ------------------------------------------------

    with torch.no_grad():

        residual_output = model(
            lr_tensor
        )

        torch_bilinear_output = F.interpolate(
            lr_tensor,
            scale_factor=2,
            mode="bilinear",
            align_corners=False
        )


    residual_np = (
        residual_output
        .squeeze()
        .clamp(0.0, 1.0)
        .cpu()
        .numpy()
    )

    torch_bilinear_np = (
        torch_bilinear_output
        .squeeze()
        .cpu()
        .numpy()
    )


    # ------------------------------------------------
    # Pillow conventional interpolation
    # ------------------------------------------------

    pil_bilinear = lr_pil.resize(
        (256, 256),
        Image.Resampling.BILINEAR
    )

    bicubic = lr_pil.resize(
        (256, 256),
        Image.Resampling.BICUBIC
    )


    pil_bilinear_np = (
        np.asarray(
            pil_bilinear,
            dtype=np.float32
        )
        / 255.0
    )

    bicubic_np = (
        np.asarray(
            bicubic,
            dtype=np.float32
        )
        / 255.0
    )


    # ------------------------------------------------
    # Metrics
    # ------------------------------------------------

    values = {
        "residual":
            mse(hr_np, residual_np),

        "torch_bilinear":
            mse(hr_np, torch_bilinear_np),

        "pil_bilinear":
            mse(hr_np, pil_bilinear_np),

        "bicubic":
            mse(hr_np, bicubic_np),
    }


    image_psnr = {
        key: psnr_from_mse(value)
        for key, value in values.items()
    }


    for key in methods:
        methods[key].append(
            values[key]
        )

        psnrs[key].append(
            image_psnr[key]
        )


    if (
        values["residual"]
        < values["bicubic"]
    ):
        wins_vs_bicubic += 1


    if (
        values["residual"]
        < values["torch_bilinear"]
    ):
        wins_vs_torch_bilinear += 1


    rows.append([
        stem,

        values["residual"],
        image_psnr["residual"],

        values["torch_bilinear"],
        image_psnr["torch_bilinear"],

        values["pil_bilinear"],
        image_psnr["pil_bilinear"],

        values["bicubic"],
        image_psnr["bicubic"],
    ])


    print(stem)

    print(
        f"  Residual CNN   "
        f"MSE={values['residual']:.8f} "
        f"PSNR={image_psnr['residual']:.3f} dB"
    )

    print(
        f"  Torch bilinear "
        f"MSE={values['torch_bilinear']:.8f} "
        f"PSNR={image_psnr['torch_bilinear']:.3f} dB"
    )

    print(
        f"  PIL bilinear   "
        f"MSE={values['pil_bilinear']:.8f} "
        f"PSNR={image_psnr['pil_bilinear']:.3f} dB"
    )

    print(
        f"  Bicubic        "
        f"MSE={values['bicubic']:.8f} "
        f"PSNR={image_psnr['bicubic']:.3f} dB"
    )


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

    pil_bilinear.save(
        COMPARE_DIR
        / f"{stem}_bilinear.png"
    )

    bicubic.save(
        COMPARE_DIR
        / f"{stem}_bicubic.png"
    )

    Image.open(hr_path).save(
        COMPARE_DIR
        / f"{stem}_target.png"
    )


# --------------------------------------------------
# Aggregate results
# --------------------------------------------------

print()
print("ROUND 3 AGGREGATE RESULTS")
print("-------------------------")

summary = {}

for key in methods:

    mean_mse = float(
        np.mean(methods[key])
    )

    psnr_mean_mse = (
        psnr_from_mse(mean_mse)
    )

    mean_image_psnr = float(
        np.mean(psnrs[key])
    )

    summary[key] = (
        mean_mse,
        psnr_mean_mse,
        mean_image_psnr
    )


labels = {
    "residual": "Residual CNN",
    "torch_bilinear": "Torch bilinear",
    "pil_bilinear": "PIL bilinear",
    "bicubic": "Bicubic",
}


for key in methods:

    mean_mse, aggregate_psnr, mean_psnr = (
        summary[key]
    )

    print(
        f"{labels[key]:14s} "
        f"MSE={mean_mse:.8f} "
        f"| PSNR(mean MSE)="
        f"{aggregate_psnr:.3f} dB "
        f"| Mean image PSNR="
        f"{mean_psnr:.3f} dB"
    )


print()

print(
    f"Residual wins vs bicubic: "
    f"{wins_vs_bicubic}/20"
)

print(
    f"Residual wins vs exact Torch bilinear: "
    f"{wins_vs_torch_bilinear}/20"
)


# --------------------------------------------------
# Save CSV
# --------------------------------------------------

with open(
    RESULTS / "comparison_metrics.csv",
    "w",
    newline=""
) as file:

    writer = csv.writer(file)

    writer.writerow([
        "image",

        "residual_mse",
        "residual_psnr_db",

        "torch_bilinear_mse",
        "torch_bilinear_psnr_db",

        "pil_bilinear_mse",
        "pil_bilinear_psnr_db",

        "bicubic_mse",
        "bicubic_psnr_db",
    ])

    writer.writerows(rows)


    writer.writerow([])
    writer.writerow([
        "SUMMARY"
    ])


    for key in methods:

        mean_mse, aggregate_psnr, mean_psnr = (
            summary[key]
        )

        writer.writerow([
            labels[key],
            mean_mse,
            aggregate_psnr,
            mean_psnr
        ])


    writer.writerow([])
    writer.writerow([
        "Residual wins vs bicubic",
        wins_vs_bicubic,
        20
    ])

    writer.writerow([
        "Residual wins vs exact Torch bilinear",
        wins_vs_torch_bilinear,
        20
    ])