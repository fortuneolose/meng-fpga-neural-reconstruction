from pathlib import Path
import csv
import math

import numpy as np
from PIL import Image

import torch
import torch.nn.functional as F

from model_residual import ResidualReconstructionCNN
from quant_utils import make_weight_quantized_model


DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

ROUND3 = Path("results/round3")

VAL_LR = Path("data/round3/val/lr")
VAL_HR = Path("data/round3/val/hr")

RESULTS = Path(
    "results/round4_int8/integer_requant"
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


# --------------------------------------------------
# Quantisation scales from Round 4B/C
# --------------------------------------------------

INPUT_SCALE = 1.0 / 255.0
CONV1_SCALE = 1.53187513 / 255.0
CONV2_SCALE = 1.00026369 / 255.0
RESIDUAL_SCALE = 0.28041983 / 127.0

REQUANT_SHIFT = 20


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


def mse(a, b):

    return float(
        np.mean(
            (a - b) ** 2
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


def summarize(mses, psnrs):

    mean_mse = float(
        np.mean(mses)
    )

    return (
        mean_mse,
        psnr_from_mse(mean_mse),
        float(np.mean(psnrs)),
    )


def quantize_bias(
    bias,
    input_scale,
    weight_scales
):

    accumulator_scale = (
        input_scale
        * weight_scales.double()
    )

    return torch.round(
        bias.double()
        / accumulator_scale
    ).to(torch.int64)


def integer_conv2d(
    x_q,
    weight_q,
    bias_q
):

    batch, _, height, width = (
        x_q.shape
    )

    output_channels = (
        weight_q.shape[0]
    )

    patches = F.unfold(
        x_q.double(),
        kernel_size=3,
        padding=1
    )

    weights = (
        weight_q
        .double()
        .reshape(
            output_channels,
            -1
        )
    )

    acc = torch.einsum(
        "ok,bkl->bol",
        weights,
        patches
    )

    acc += (
        bias_q
        .double()
        .view(1, -1, 1)
    )

    return (
        torch.round(acc)
        .to(torch.int64)
        .reshape(
            batch,
            output_channels,
            height,
            width
        )
    )


# --------------------------------------------------
# Integer requantisation
# --------------------------------------------------

def make_requant_multiplier(
    input_scale,
    weight_scales,
    output_scale,
    shift
):

    real_multiplier = (
        input_scale
        * weight_scales.double()
        / output_scale
    )

    integer_multiplier = torch.round(
        real_multiplier
        * (2 ** shift)
    ).to(torch.int64)

    approximated = (
        integer_multiplier.double()
        / (2 ** shift)
    )

    relative_error = (
        (
            approximated
            - real_multiplier
        )
        .abs()
        / real_multiplier.abs()
    )

    return (
        integer_multiplier,
        real_multiplier,
        relative_error,
    )


def rounded_shift(
    value,
    shift
):
    """
    Signed round-to-nearest before arithmetic
    right shift.
    """

    offset = (
        1 << (shift - 1)
    )

    positive = (
        value + offset
    ) >> shift

    negative = -(
        (
            (-value)
            + offset
        )
        >> shift
    )

    return torch.where(
        value >= 0,
        positive,
        negative
    )


def requantize_uint8_integer(
    accumulator,
    multipliers,
    shift
):

    product = (
        accumulator
        * multipliers.view(
            1, -1, 1, 1
        )
    )

    q = rounded_shift(
        product,
        shift
    )

    q = torch.clamp(
        q,
        0,
        255
    )

    return q.to(torch.int64)


def requantize_int8_integer(
    accumulator,
    multipliers,
    shift
):

    product = (
        accumulator
        * multipliers.view(
            1, -1, 1, 1
        )
    )

    q = rounded_shift(
        product,
        shift
    )

    q = torch.clamp(
        q,
        -127,
        127
    )

    return q.to(torch.int64)


# --------------------------------------------------
# Load model and quantised parameters
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


_, packed = make_weight_quantized_model(
    fp32_model
)


conv1_bias_q = quantize_bias(
    packed["conv1"]["bias"],
    INPUT_SCALE,
    packed["conv1"]["scales"]
)

conv2_bias_q = quantize_bias(
    packed["conv2"]["bias"],
    CONV1_SCALE,
    packed["conv2"]["scales"]
)

conv3_bias_q = quantize_bias(
    packed["conv3"]["bias"],
    CONV2_SCALE,
    packed["conv3"]["scales"]
)


(
    conv1_multiplier,
    conv1_real_multiplier,
    conv1_error,
) = make_requant_multiplier(
    INPUT_SCALE,
    packed["conv1"]["scales"],
    CONV1_SCALE,
    REQUANT_SHIFT
)


(
    conv2_multiplier,
    conv2_real_multiplier,
    conv2_error,
) = make_requant_multiplier(
    CONV1_SCALE,
    packed["conv2"]["scales"],
    CONV2_SCALE,
    REQUANT_SHIFT
)


(
    conv3_multiplier,
    conv3_real_multiplier,
    conv3_error,
) = make_requant_multiplier(
    CONV2_SCALE,
    packed["conv3"]["scales"],
    RESIDUAL_SCALE,
    REQUANT_SHIFT
)


# --------------------------------------------------
# Report requantisation constants
# --------------------------------------------------

print("INTEGER REQUANTISATION PARAMETERS")
print("---------------------------------")
print()

print("Right shift:", REQUANT_SHIFT)
print()


for name, multiplier, error in [
    (
        "conv1",
        conv1_multiplier,
        conv1_error,
    ),
    (
        "conv2",
        conv2_multiplier,
        conv2_error,
    ),
    (
        "conv3",
        conv3_multiplier,
        conv3_error,
    ),
]:

    print(name)

    print(
        "  integer multiplier range:",
        int(multiplier.min()),
        "to",
        int(multiplier.max())
    )

    print(
        "  maximum relative scale error:",
        f"{float(error.max()) * 100:.6f}%"
    )

    print()


# --------------------------------------------------
# Integer forward
# --------------------------------------------------

def forward_integer_requant(lr):

    baseline = F.interpolate(
        lr,
        scale_factor=2,
        mode="bilinear",
        align_corners=False
    )

    baseline_cpu = (
        baseline
        .detach()
        .cpu()
        .double()
    )


    q0 = torch.round(
        baseline_cpu
        / INPUT_SCALE
    )

    q0 = torch.clamp(
        q0,
        0,
        255
    ).to(torch.int64)


    # Conv1
    acc1 = integer_conv2d(
        q0,
        packed["conv1"]["qweight"],
        conv1_bias_q
    )

    q1 = requantize_uint8_integer(
        acc1,
        conv1_multiplier,
        REQUANT_SHIFT
    )


    # Conv2
    acc2 = integer_conv2d(
        q1,
        packed["conv2"]["qweight"],
        conv2_bias_q
    )

    q2 = requantize_uint8_integer(
        acc2,
        conv2_multiplier,
        REQUANT_SHIFT
    )


    # Conv3
    acc3 = integer_conv2d(
        q2,
        packed["conv3"]["qweight"],
        conv3_bias_q
    )

    q_residual = (
        requantize_int8_integer(
            acc3,
            conv3_multiplier,
            REQUANT_SHIFT
        )
    )


    residual = (
        q_residual.double()
        * RESIDUAL_SCALE
    )


    output = (
        baseline_cpu
        + residual
    )

    return output.float()


# --------------------------------------------------
# Evaluation
# --------------------------------------------------

fp32_mses = []
fp32_psnrs = []

integer_mses = []
integer_psnrs = []

bicubic_mses = []
bicubic_psnrs = []

rows = []

wins_vs_bicubic = 0


print("Device:", DEVICE)
print(
    "Validation images:",
    len(
        list(
            VAL_LR.glob("*_lr.png")
        )
    )
)
print()


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

    lr = (
        image_to_tensor(lr_path)
        .to(DEVICE)
    )


    with torch.no_grad():

        fp32_output = (
            fp32_model(lr)
        )

        integer_output = (
            forward_integer_requant(lr)
        )


    fp32_np = (
        fp32_output
        .squeeze()
        .clamp(0, 1)
        .cpu()
        .numpy()
    )

    integer_np = (
        integer_output
        .squeeze()
        .clamp(0, 1)
        .cpu()
        .numpy()
    )


    bicubic = (
        Image.open(lr_path)
        .convert("L")
        .resize(
            (256, 256),
            Image.Resampling.BICUBIC
        )
    )

    bicubic_np = (
        np.asarray(
            bicubic,
            dtype=np.float32
        )
        / 255.0
    )


    fp32_error = mse(
        hr_np,
        fp32_np
    )

    int_error = mse(
        hr_np,
        integer_np
    )

    bicubic_error = mse(
        hr_np,
        bicubic_np
    )


    fp32_psnr = psnr_from_mse(
        fp32_error
    )

    int_psnr = psnr_from_mse(
        int_error
    )

    bicubic_psnr = psnr_from_mse(
        bicubic_error
    )


    fp32_mses.append(
        fp32_error
    )

    fp32_psnrs.append(
        fp32_psnr
    )

    integer_mses.append(
        int_error
    )

    integer_psnrs.append(
        int_psnr
    )

    bicubic_mses.append(
        bicubic_error
    )

    bicubic_psnrs.append(
        bicubic_psnr
    )


    if int_error < bicubic_error:
        wins_vs_bicubic += 1


    rows.append([
        stem,
        fp32_error,
        fp32_psnr,
        int_error,
        int_psnr,
        bicubic_error,
        bicubic_psnr,
    ])


    print(
        f"{stem} | "
        f"FP32 {fp32_psnr:.3f} dB | "
        f"Integer-requant {int_psnr:.3f} dB | "
        f"Bicubic {bicubic_psnr:.3f} dB"
    )


fp32_summary = summarize(
    fp32_mses,
    fp32_psnrs
)

integer_summary = summarize(
    integer_mses,
    integer_psnrs
)

bicubic_summary = summarize(
    bicubic_mses,
    bicubic_psnrs
)


print()
print(
    "ROUND 4E — INTEGER REQUANTISATION"
)
print(
    "---------------------------------"
)

print(
    f"FP32             "
    f"PSNR(mean MSE)="
    f"{fp32_summary[1]:.3f} dB"
)

print(
    f"Integer-requant  "
    f"PSNR(mean MSE)="
    f"{integer_summary[1]:.3f} dB"
)

print(
    f"Bicubic          "
    f"PSNR(mean MSE)="
    f"{bicubic_summary[1]:.3f} dB"
)

print()

print(
    "FP32 -> integer-requant loss:",
    f"{fp32_summary[1] - integer_summary[1]:+.4f} dB"
)

print(
    "Integer-requant wins vs bicubic:",
    f"{wins_vs_bicubic}/20"
)


# --------------------------------------------------
# Save constants and metrics
# --------------------------------------------------

torch.save(
    {
        "shift": REQUANT_SHIFT,

        "conv1_multiplier":
            conv1_multiplier,

        "conv2_multiplier":
            conv2_multiplier,

        "conv3_multiplier":
            conv3_multiplier,

        "conv1_bias_int32":
            conv1_bias_q.to(
                torch.int32
            ),

        "conv2_bias_int32":
            conv2_bias_q.to(
                torch.int32
            ),

        "conv3_bias_int32":
            conv3_bias_q.to(
                torch.int32
            ),
    },
    RESULTS
    / "integer_requant_parameters.pt"
)


with open(
    RESULTS / "comparison_metrics.csv",
    "w",
    newline=""
) as file:

    writer = csv.writer(file)

    writer.writerow([
        "image",
        "fp32_mse",
        "fp32_psnr",
        "integer_requant_mse",
        "integer_requant_psnr",
        "bicubic_mse",
        "bicubic_psnr",
    ])

    writer.writerows(rows)