from pathlib import Path
import csv
import math

import numpy as np
from PIL import Image

import torch
import torch.nn.functional as F

from model_residual import ResidualReconstructionCNN

from quant_utils import (
    make_weight_quantized_model,
    fake_quantize_uint8,
    fake_quantize_int8,
)


DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)


VAL_LR = Path("data/round3/val/lr")
VAL_HR = Path("data/round3/val/hr")

ROUND3 = Path("results/round3")

RESULTS = Path(
    "results/round4_int8/w8a8_max"
)

COMPARE_DIR = (
    RESULTS / "comparison"
)

RESULTS.mkdir(
    parents=True,
    exist_ok=True
)

COMPARE_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# --------------------------------------------------
# Fixed activation scales from Round 4B
# --------------------------------------------------

INPUT_SCALE = (
    1.0 / 255.0
)

CONV1_RELU_SCALE = (
    1.53187513 / 255.0
)

CONV2_RELU_SCALE = (
    1.00026369 / 255.0
)

RESIDUAL_SCALE = (
    0.28041983 / 127.0
)


print("Activation scales")
print("-----------------")

print(
    f"Input UINT8:      "
    f"{INPUT_SCALE:.10f}"
)

print(
    f"Conv1 ReLU UINT8: "
    f"{CONV1_RELU_SCALE:.10f}"
)

print(
    f"Conv2 ReLU UINT8: "
    f"{CONV2_RELU_SCALE:.10f}"
)

print(
    f"Residual INT8:    "
    f"{RESIDUAL_SCALE:.10f}"
)

print()


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def image_to_numpy(path):

    return (
        np.asarray(
            Image.open(path).convert("L"),
            dtype=np.float32
        )
        / 255.0
    )


def image_to_tensor(path):

    return (
        torch.from_numpy(
            image_to_numpy(path)
        )
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

    return (
        10.0
        * math.log10(
            1.0 / error
        )
    )


def summarize(
    mse_values,
    psnr_values
):

    mean_mse = float(
        np.mean(mse_values)
    )

    aggregate_psnr = (
        psnr_from_mse(
            mean_mse
        )
    )

    mean_image_psnr = float(
        np.mean(psnr_values)
    )

    return (
        mean_mse,
        aggregate_psnr,
        mean_image_psnr
    )


# --------------------------------------------------
# Load FP32 reference
# --------------------------------------------------

checkpoint = torch.load(
    ROUND3 / "best_model.pt",
    map_location=DEVICE,
    weights_only=False
)

fp32_model = (
    ResidualReconstructionCNN()
    .to(DEVICE)
)

fp32_model.load_state_dict(
    checkpoint["model_state_dict"]
)

fp32_model.eval()


# --------------------------------------------------
# Weight-quantised model
# --------------------------------------------------

w8_model, _ = (
    make_weight_quantized_model(
        fp32_model
    )
)

w8_model = w8_model.to(DEVICE)
w8_model.eval()


# --------------------------------------------------
# Explicit W8A8 forward path
# --------------------------------------------------

def forward_w8a8(lr):

    # Full-precision baseline used by the skip path.
    baseline_fp32 = F.interpolate(
        lr,
        scale_factor=2,
        mode="bilinear",
        align_corners=False
    )

    # Quantised copy feeds the learned residual branch.
    x = fake_quantize_uint8(
        baseline_fp32,
        INPUT_SCALE
    )

    x = w8_model.conv1(x)
    x = F.relu(x)

    x = fake_quantize_uint8(
        x,
        CONV1_RELU_SCALE
    )

    x = w8_model.conv2(x)
    x = F.relu(x)

    x = fake_quantize_uint8(
        x,
        CONV2_RELU_SCALE
    )

    residual = w8_model.conv3(x)

    residual = fake_quantize_int8(
        residual,
        RESIDUAL_SCALE
    )

    # Skip/add deliberately stays FP32 in Round 4C.
    output = (
        baseline_fp32
        + residual
    )

    return output


# --------------------------------------------------
# Evaluation storage
# --------------------------------------------------

fp32_mses = []
fp32_psnrs = []

w8a8_mses = []
w8a8_psnrs = []

bicubic_mses = []
bicubic_psnrs = []

rows = []

wins_vs_bicubic = 0
wins_vs_fp32 = 0


print("Device:", DEVICE)
print(
    "Checkpoint epoch:",
    checkpoint["epoch"]
)
print(
    "Validation images:",
    len(
        list(
            VAL_LR.glob("*_lr.png")
        )
    )
)
print()


# --------------------------------------------------
# Evaluate same 20 held-out images
# --------------------------------------------------

for lr_path in sorted(
    VAL_LR.glob("*_lr.png")
):

    stem = (
        lr_path.stem
        .replace("_lr", "")
    )

    hr_path = (
        VAL_HR
        / f"{stem}_hr.png"
    )

    hr_np = image_to_numpy(
        hr_path
    )

    lr_tensor = (
        image_to_tensor(lr_path)
        .to(DEVICE)
    )


    with torch.no_grad():

        fp32_output = fp32_model(
            lr_tensor
        )

        w8a8_output = forward_w8a8(
            lr_tensor
        )


    fp32_np = (
        fp32_output
        .squeeze()
        .clamp(0.0, 1.0)
        .cpu()
        .numpy()
    )

    w8a8_np = (
        w8a8_output
        .squeeze()
        .clamp(0.0, 1.0)
        .cpu()
        .numpy()
    )


    lr_pil = (
        Image.open(lr_path)
        .convert("L")
    )

    bicubic = lr_pil.resize(
        (256, 256),
        Image.Resampling.BICUBIC
    )

    bicubic_np = (
        np.asarray(
            bicubic,
            dtype=np.float32
        )
        / 255.0
    )


    fp32_mse = mse(
        hr_np,
        fp32_np
    )

    w8a8_mse = mse(
        hr_np,
        w8a8_np
    )

    bicubic_mse = mse(
        hr_np,
        bicubic_np
    )


    fp32_psnr = psnr_from_mse(
        fp32_mse
    )

    w8a8_psnr = psnr_from_mse(
        w8a8_mse
    )

    bicubic_psnr = psnr_from_mse(
        bicubic_mse
    )


    fp32_mses.append(
        fp32_mse
    )

    fp32_psnrs.append(
        fp32_psnr
    )

    w8a8_mses.append(
        w8a8_mse
    )

    w8a8_psnrs.append(
        w8a8_psnr
    )

    bicubic_mses.append(
        bicubic_mse
    )

    bicubic_psnrs.append(
        bicubic_psnr
    )


    if w8a8_mse < bicubic_mse:
        wins_vs_bicubic += 1

    if w8a8_mse < fp32_mse:
        wins_vs_fp32 += 1


    loss_db = (
        fp32_psnr
        - w8a8_psnr
    )


    rows.append([
        stem,
        fp32_mse,
        fp32_psnr,
        w8a8_mse,
        w8a8_psnr,
        loss_db,
        bicubic_mse,
        bicubic_psnr,
    ])


    print(stem)

    print(
        f"  FP32   "
        f"MSE={fp32_mse:.8f} "
        f"PSNR={fp32_psnr:.3f} dB"
    )

    print(
        f"  W8A8   "
        f"MSE={w8a8_mse:.8f} "
        f"PSNR={w8a8_psnr:.3f} dB"
    )

    print(
        f"  Bicubic "
        f"MSE={bicubic_mse:.8f} "
        f"PSNR={bicubic_psnr:.3f} dB"
    )

    print(
        f"  FP32 -> W8A8 loss: "
        f"{loss_db:+.4f} dB"
    )


    Image.fromarray(
        (
            w8a8_np * 255.0
        )
        .round()
        .astype(np.uint8)
    ).save(
        COMPARE_DIR
        / f"{stem}_w8a8_max.png"
    )


# --------------------------------------------------
# Aggregate
# --------------------------------------------------

fp32_summary = summarize(
    fp32_mses,
    fp32_psnrs
)

w8a8_summary = summarize(
    w8a8_mses,
    w8a8_psnrs
)

bicubic_summary = summarize(
    bicubic_mses,
    bicubic_psnrs
)


aggregate_loss = (
    fp32_summary[1]
    - w8a8_summary[1]
)


print()
print(
    "ROUND 4C — W8A8 MAX-RANGE PTQ"
)

print(
    "-----------------------------"
)

print(
    f"FP32     "
    f"MSE={fp32_summary[0]:.8f} "
    f"| PSNR(mean MSE)="
    f"{fp32_summary[1]:.3f} dB "
    f"| Mean image PSNR="
    f"{fp32_summary[2]:.3f} dB"
)

print(
    f"W8A8     "
    f"MSE={w8a8_summary[0]:.8f} "
    f"| PSNR(mean MSE)="
    f"{w8a8_summary[1]:.3f} dB "
    f"| Mean image PSNR="
    f"{w8a8_summary[2]:.3f} dB"
)

print(
    f"Bicubic  "
    f"MSE={bicubic_summary[0]:.8f} "
    f"| PSNR(mean MSE)="
    f"{bicubic_summary[1]:.3f} dB "
    f"| Mean image PSNR="
    f"{bicubic_summary[2]:.3f} dB"
)

print()

print(
    "Aggregate FP32 -> W8A8 "
    f"PSNR loss: {aggregate_loss:+.4f} dB"
)

print(
    "W8A8 wins vs bicubic: "
    f"{wins_vs_bicubic}/20"
)

print(
    "W8A8 wins vs FP32: "
    f"{wins_vs_fp32}/20"
)


# --------------------------------------------------
# Save metrics
# --------------------------------------------------

with open(
    RESULTS / "comparison_metrics.csv",
    "w",
    newline=""
) as file:

    writer = csv.writer(file)

    writer.writerow([
        "image",
        "fp32_mse",
        "fp32_psnr_db",
        "w8a8_mse",
        "w8a8_psnr_db",
        "fp32_to_w8a8_psnr_loss_db",
        "bicubic_mse",
        "bicubic_psnr_db",
    ])

    writer.writerows(rows)

    writer.writerow([])

    writer.writerow([
        "AGGREGATE"
    ])

    writer.writerow([
        "FP32",
        *fp32_summary
    ])

    writer.writerow([
        "W8A8_MAX",
        *w8a8_summary
    ])

    writer.writerow([
        "BICUBIC",
        *bicubic_summary
    ])

    writer.writerow([])

    writer.writerow([
        "FP32_TO_W8A8_PSNR_LOSS_DB",
        aggregate_loss
    ])

    writer.writerow([
        "W8A8_WINS_VS_BICUBIC",
        wins_vs_bicubic,
        20
    ])