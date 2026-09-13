from pathlib import Path
import csv
import math

import numpy as np
from PIL import Image

import torch

from model_residual import ResidualReconstructionCNN
from quant_utils import make_weight_quantized_model


DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

VAL_LR = Path("data/round3/val/lr")
VAL_HR = Path("data/round3/val/hr")

ROUND3 = Path("results/round3")

RESULTS = Path(
    "results/round4_int8/weight_only"
)

COMPARE_DIR = RESULTS / "comparison"

RESULTS.mkdir(
    parents=True,
    exist_ok=True
)

COMPARE_DIR.mkdir(
    parents=True,
    exist_ok=True
)


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

    return 10.0 * math.log10(
        1.0 / error
    )


def summarize(
    mse_values,
    psnr_values
):
    mean_mse = float(
        np.mean(mse_values)
    )

    return (
        mean_mse,
        psnr_from_mse(mean_mse),
        float(np.mean(psnr_values))
    )


# --------------------------------------------------
# Load frozen FP32 reference
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
# Create simulated INT8-weight model
# --------------------------------------------------

(
    int8_model,
    packed_weights
) = make_weight_quantized_model(
    fp32_model
)

int8_model = int8_model.to(DEVICE)
int8_model.eval()


# --------------------------------------------------
# Save actual INT8 tensors + scales
# --------------------------------------------------

torch.save(
    packed_weights,
    RESULTS / "quantized_weights_int8.pt"
)


with open(
    RESULTS / "weight_scales.csv",
    "w",
    newline=""
) as file:

    writer = csv.writer(file)

    writer.writerow([
        "layer",
        "output_channel",
        "scale"
    ])

    for layer_name, data in (
        packed_weights.items()
    ):

        for channel, scale in enumerate(
            data["scales"].tolist()
        ):

            writer.writerow([
                layer_name,
                channel,
                scale
            ])


# --------------------------------------------------
# Quantisation summary
# --------------------------------------------------

total_int8_weights = 0

print("Device:", DEVICE)
print(
    "FP32 checkpoint epoch:",
    checkpoint["epoch"]
)
print()


for layer_name, data in (
    packed_weights.items()
):

    qweight = data["qweight"]
    scales = data["scales"]

    total_int8_weights += (
        qweight.numel()
    )

    print(layer_name)

    print(
        "  INT8 weight count:",
        qweight.numel()
    )

    print(
        "  Integer range:",
        int(qweight.min()),
        "to",
        int(qweight.max())
    )

    print(
        "  Scale range:",
        float(scales.min()),
        "to",
        float(scales.max())
    )


print()

print(
    "Total quantised weights:",
    total_int8_weights
)

print(
    "Bias values remaining FP32: 17"
)

print()


# --------------------------------------------------
# Evaluation
# --------------------------------------------------

rows = []

fp32_mses = []
fp32_psnrs = []

int8_mses = []
int8_psnrs = []

bicubic_mses = []
bicubic_psnrs = []

wins_vs_bicubic = 0


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

    lr_tensor = (
        image_to_tensor(lr_path)
        .to(DEVICE)
    )


    with torch.no_grad():

        fp32_output = fp32_model(
            lr_tensor
        )

        int8_output = int8_model(
            lr_tensor
        )


    fp32_np = (
        fp32_output
        .squeeze()
        .clamp(0.0, 1.0)
        .cpu()
        .numpy()
    )

    int8_np = (
        int8_output
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

    int8_mse = mse(
        hr_np,
        int8_np
    )

    bicubic_mse = mse(
        hr_np,
        bicubic_np
    )


    fp32_psnr = psnr_from_mse(
        fp32_mse
    )

    int8_psnr = psnr_from_mse(
        int8_mse
    )

    bicubic_psnr = psnr_from_mse(
        bicubic_mse
    )


    fp32_mses.append(fp32_mse)
    fp32_psnrs.append(fp32_psnr)

    int8_mses.append(int8_mse)
    int8_psnrs.append(int8_psnr)

    bicubic_mses.append(
        bicubic_mse
    )

    bicubic_psnrs.append(
        bicubic_psnr
    )


    if int8_mse < bicubic_mse:
        wins_vs_bicubic += 1


    loss_db = (
        fp32_psnr
        - int8_psnr
    )


    rows.append([
        stem,
        fp32_mse,
        fp32_psnr,
        int8_mse,
        int8_psnr,
        loss_db,
        bicubic_mse,
        bicubic_psnr
    ])


    print(stem)

    print(
        f"  FP32         "
        f"MSE={fp32_mse:.8f} "
        f"PSNR={fp32_psnr:.3f} dB"
    )

    print(
        f"  INT8 weights "
        f"MSE={int8_mse:.8f} "
        f"PSNR={int8_psnr:.3f} dB"
    )

    print(
        f"  Bicubic      "
        f"MSE={bicubic_mse:.8f} "
        f"PSNR={bicubic_psnr:.3f} dB"
    )

    print(
        f"  FP32 -> INT8 loss: "
        f"{loss_db:+.4f} dB"
    )


    Image.fromarray(
        (
            int8_np * 255.0
        )
        .round()
        .astype(np.uint8)
    ).save(
        COMPARE_DIR
        / f"{stem}_int8_weight_only.png"
    )


# --------------------------------------------------
# Aggregate
# --------------------------------------------------

fp32_summary = summarize(
    fp32_mses,
    fp32_psnrs
)

int8_summary = summarize(
    int8_mses,
    int8_psnrs
)

bicubic_summary = summarize(
    bicubic_mses,
    bicubic_psnrs
)


aggregate_loss = (
    fp32_summary[1]
    - int8_summary[1]
)


print()
print(
    "ROUND 4A — WEIGHT-ONLY INT8"
)

print(
    "---------------------------"
)

print(
    f"FP32 residual "
    f"MSE={fp32_summary[0]:.8f} "
    f"| PSNR(mean MSE)="
    f"{fp32_summary[1]:.3f} dB "
    f"| Mean image PSNR="
    f"{fp32_summary[2]:.3f} dB"
)

print(
    f"INT8 weights  "
    f"MSE={int8_summary[0]:.8f} "
    f"| PSNR(mean MSE)="
    f"{int8_summary[1]:.3f} dB "
    f"| Mean image PSNR="
    f"{int8_summary[2]:.3f} dB"
)

print(
    f"Bicubic       "
    f"MSE={bicubic_summary[0]:.8f} "
    f"| PSNR(mean MSE)="
    f"{bicubic_summary[1]:.3f} dB "
    f"| Mean image PSNR="
    f"{bicubic_summary[2]:.3f} dB"
)

print()

print(
    "Aggregate FP32 -> INT8 "
    f"PSNR loss: {aggregate_loss:+.4f} dB"
)

print(
    "INT8 wins vs bicubic: "
    f"{wins_vs_bicubic}/20"
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
        "fp32_mse",
        "fp32_psnr_db",
        "int8_weight_mse",
        "int8_weight_psnr_db",
        "fp32_to_int8_psnr_loss_db",
        "bicubic_mse",
        "bicubic_psnr_db"
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
        "INT8_WEIGHT_ONLY",
        *int8_summary
    ])

    writer.writerow([
        "BICUBIC",
        *bicubic_summary
    ])

    writer.writerow([])

    writer.writerow([
        "FP32_TO_INT8_PSNR_LOSS_DB",
        aggregate_loss
    ])

    writer.writerow([
        "INT8_WINS_VS_BICUBIC",
        wins_vs_bicubic,
        20
    ])