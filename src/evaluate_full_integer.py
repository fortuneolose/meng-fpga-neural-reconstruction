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


# --------------------------------------------------
# Quantisation constants
# --------------------------------------------------

INPUT_SCALE = 1.0 / 255.0

CONV1_SCALE = (
    1.53187513 / 255.0
)

CONV2_SCALE = (
    1.00026369 / 255.0
)

RESIDUAL_SCALE = (
    0.28041983 / 127.0
)


REQUANT_SHIFT = 20

# Exact 2x bilinear denominator:
BILINEAR_DEN = 16

PIXEL_DEN = 255

# 1.0 in the final integer image domain:
OUTPUT_DEN = (
    PIXEL_DEN
    * BILINEAR_DEN
)

OUTPUT_SCALE = (
    1.0 / OUTPUT_DEN
)

FINAL_SHIFT = 20


VAL_LR = Path(
    "data/round3/val/lr"
)

VAL_HR = Path(
    "data/round3/val/hr"
)

ROUND3 = Path(
    "results/round3"
)

RESULTS = Path(
    "results/round4_int8/full_integer"
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
# General utilities
# --------------------------------------------------

def image_to_numpy(path):

    return (
        np.asarray(
            Image.open(path).convert("L"),
            dtype=np.float32
        )
        / 255.0
    )


def image_to_float_tensor(path):

    return (
        torch.from_numpy(
            image_to_numpy(path)
        )
        .unsqueeze(0)
        .unsqueeze(0)
    )


def image_to_u8_tensor(path):

    array = np.array(
        Image.open(path).convert("L"),
        dtype=np.uint8,
        copy=True
    )

    return (
        torch.from_numpy(array)
        .unsqueeze(0)
        .unsqueeze(0)
        .to(torch.int64)
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


def signed_bits_required(max_abs):

    max_abs = int(max_abs)

    bits = 1

    while max_abs > (
        (2 ** (bits - 1)) - 1
    ):
        bits += 1

    return bits


# --------------------------------------------------
# Exact 2x integer bilinear interpolation
# --------------------------------------------------

def axis_coefficients(length):

    index0 = []
    index1 = []

    weight0 = []
    weight1 = []

    output_length = (
        2 * length
    )

    for j in range(
        output_length
    ):

        # Border replication matches
        # PyTorch interpolate behaviour.

        if j == 0:

            index0.append(0)
            index1.append(0)

            weight0.append(4)
            weight1.append(0)

        elif j == (
            output_length - 1
        ):

            index0.append(
                length - 1
            )

            index1.append(
                length - 1
            )

            weight0.append(4)
            weight1.append(0)

        elif (
            j % 2 == 0
        ):

            i = j // 2

            index0.append(
                i - 1
            )

            index1.append(i)

            weight0.append(1)
            weight1.append(3)

        else:

            i = j // 2

            index0.append(i)

            index1.append(
                i + 1
            )

            weight0.append(3)
            weight1.append(1)


    return (
        torch.tensor(
            index0,
            dtype=torch.long
        ),
        torch.tensor(
            index1,
            dtype=torch.long
        ),
        torch.tensor(
            weight0,
            dtype=torch.int64
        ),
        torch.tensor(
            weight1,
            dtype=torch.int64
        ),
    )


def integer_bilinear_2x_scaled16(
    x_q
):
    """
    Exact integer implementation of the
    2x bilinear interpolation currently used
    by the model.

    Input:
        uint8-equivalent values [0,255]

    Output:
        integer values where 4080 represents 1.0

        scale = 1 / (255 * 16)
    """

    (
        batch,
        channels,
        height,
        width,
    ) = x_q.shape


    (
        left,
        right,
        wl,
        wr,
    ) = axis_coefficients(
        width
    )


    horizontal = (
        x_q.index_select(
            3,
            left
        )
        * wl.view(
            1, 1, 1, -1
        )
        +
        x_q.index_select(
            3,
            right
        )
        * wr.view(
            1, 1, 1, -1
        )
    )


    (
        top,
        bottom,
        wt,
        wb,
    ) = axis_coefficients(
        height
    )


    output = (
        horizontal.index_select(
            2,
            top
        )
        * wt.view(
            1, 1, -1, 1
        )
        +
        horizontal.index_select(
            2,
            bottom
        )
        * wb.view(
            1, 1, -1, 1
        )
    )


    return output


# --------------------------------------------------
# Exact integer rounding helpers
# --------------------------------------------------

def round_divide_nearest_even_unsigned(
    numerator,
    denominator
):
    """
    Round non-negative integer numerator /
    denominator to nearest integer.

    Exact ties are rounded to even,
    matching torch.round behaviour.
    """

    quotient = torch.div(
        numerator,
        denominator,
        rounding_mode="floor"
    )

    remainder = (
        numerator
        - quotient * denominator
    )

    half = (
        denominator // 2
    )

    increment = (
        (remainder > half)
        |
        (
            (remainder == half)
            &
            (
                (quotient & 1)
                == 1
            )
        )
    )

    return (
        quotient
        + increment.to(
            quotient.dtype
        )
    )


def rounded_shift(
    value,
    shift
):

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


# --------------------------------------------------
# Integer CNN helpers
# --------------------------------------------------

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

    (
        batch,
        _,
        height,
        width,
    ) = x_q.shape

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


    accumulator = torch.einsum(
        "ok,bkl->bol",
        weights,
        patches
    )


    accumulator += (
        bias_q
        .double()
        .view(
            1,
            -1,
            1
        )
    )


    return (
        torch.round(
            accumulator
        )
        .to(torch.int64)
        .reshape(
            batch,
            output_channels,
            height,
            width
        )
    )


def make_multiplier(
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

    integer_multiplier = (
        torch.round(
            real_multiplier
            * (2 ** shift)
        )
        .to(torch.int64)
    )

    return integer_multiplier


def requantize_uint8(
    accumulator,
    multiplier,
    shift
):

    product = (
        accumulator
        * multiplier.view(
            1, -1, 1, 1
        )
    )

    q = rounded_shift(
        product,
        shift
    )

    return (
        torch.clamp(
            q,
            0,
            255
        )
        .to(torch.int64)
    )


def requantize_int8(
    accumulator,
    multiplier,
    shift
):

    product = (
        accumulator
        * multiplier.view(
            1, -1, 1, 1
        )
    )

    q = rounded_shift(
        product,
        shift
    )

    return (
        torch.clamp(
            q,
            -127,
            127
        )
        .to(torch.int64)
    )


# --------------------------------------------------
# Load frozen model
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
    checkpoint[
        "model_state_dict"
    ]
)

fp32_model.eval()


_, packed = (
    make_weight_quantized_model(
        fp32_model
    )
)


# --------------------------------------------------
# Integer biases
# --------------------------------------------------

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


# --------------------------------------------------
# Integer layer requantisation constants
# --------------------------------------------------

conv1_multiplier = make_multiplier(
    INPUT_SCALE,
    packed["conv1"]["scales"],
    CONV1_SCALE,
    REQUANT_SHIFT
)

conv2_multiplier = make_multiplier(
    CONV1_SCALE,
    packed["conv2"]["scales"],
    CONV2_SCALE,
    REQUANT_SHIFT
)

conv3_multiplier = make_multiplier(
    CONV2_SCALE,
    packed["conv3"]["scales"],
    RESIDUAL_SCALE,
    REQUANT_SHIFT
)


# --------------------------------------------------
# Convert residual domain to final output domain
# --------------------------------------------------

residual_to_output_real = (
    RESIDUAL_SCALE
    / OUTPUT_SCALE
)

residual_to_output_multiplier = int(
    round(
        residual_to_output_real
        * (2 ** FINAL_SHIFT)
    )
)

residual_to_output_approx = (
    residual_to_output_multiplier
    / (2 ** FINAL_SHIFT)
)

residual_to_output_error = (
    abs(
        residual_to_output_approx
        - residual_to_output_real
    )
    / residual_to_output_real
)


print(
    "FULL INTEGER OUTPUT PARAMETERS"
)

print(
    "------------------------------"
)

print(
    "Output denominator:",
    OUTPUT_DEN
)

print(
    "Output scale:",
    OUTPUT_SCALE
)

print(
    "Residual -> output real multiplier:",
    residual_to_output_real
)

print(
    "Residual -> output integer multiplier:",
    residual_to_output_multiplier
)

print(
    "Residual -> output shift:",
    FINAL_SHIFT
)

print(
    "Residual -> output relative error:",
    f"{residual_to_output_error * 100:.8f}%"
)

print()


# --------------------------------------------------
# Full integer forward path
# --------------------------------------------------

def forward_full_integer(
    lr_u8
):

    # ----------------------------------------------
    # Integer bilinear skip path
    #
    # baseline_ticks uses scale 1/4080.
    # ----------------------------------------------

    baseline_ticks = (
        integer_bilinear_2x_scaled16(
            lr_u8
        )
    )


    # ----------------------------------------------
    # Quantise the bilinear output to UINT8 for
    # the learned residual branch.
    #
    # This matches the Round 4E residual branch.
    # ----------------------------------------------

    q0 = (
        round_divide_nearest_even_unsigned(
            baseline_ticks,
            BILINEAR_DEN
        )
    )

    q0 = torch.clamp(
        q0,
        0,
        255
    )


    # Conv1

    acc1 = integer_conv2d(
        q0,
        packed["conv1"]["qweight"],
        conv1_bias_q
    )

    q1 = requantize_uint8(
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

    q2 = requantize_uint8(
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

    q_residual = requantize_int8(
        acc3,
        conv3_multiplier,
        REQUANT_SHIFT
    )


    # ----------------------------------------------
    # Convert the signed INT8 residual into the
    # common 1/4080 output domain.
    # ----------------------------------------------

    residual_product = (
        q_residual
        * residual_to_output_multiplier
    )

    residual_ticks = rounded_shift(
        residual_product,
        FINAL_SHIFT
    )


    # ----------------------------------------------
    # Integer skip connection and residual add.
    # ----------------------------------------------

    output_ticks = (
        baseline_ticks
        + residual_ticks
    )


    # Existing evaluation clips to [0,1].
    # In this fixed-point domain that is [0,4080].

    output_ticks = torch.clamp(
        output_ticks,
        0,
        OUTPUT_DEN
    )


    return (
        output_ticks,
        baseline_ticks,
        q_residual
    )


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

maximum_bilinear_difference = 0.0


print(
    "Device:",
    DEVICE
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


for lr_path in sorted(
    VAL_LR.glob("*_lr.png")
):

    stem = (
        lr_path.stem
        .replace(
            "_lr",
            ""
        )
    )

    hr_path = (
        VAL_HR
        / f"{stem}_hr.png"
    )


    hr_np = image_to_numpy(
        hr_path
    )


    lr_float = (
        image_to_float_tensor(
            lr_path
        )
        .to(DEVICE)
    )

    lr_u8 = image_to_u8_tensor(
        lr_path
    )


    with torch.no_grad():

        fp32_output = (
            fp32_model(
                lr_float
            )
        )

        torch_bilinear = (
            F.interpolate(
                lr_float,
                scale_factor=2,
                mode="bilinear",
                align_corners=False
            )
        )


    (
        integer_ticks,
        baseline_ticks,
        q_residual,
    ) = forward_full_integer(
        lr_u8
    )


    integer_baseline = (
        baseline_ticks.double()
        / OUTPUT_DEN
    )


    baseline_difference = float(
        torch.max(
            torch.abs(
                torch_bilinear
                .cpu()
                .double()
                - integer_baseline
            )
        )
    )


    maximum_bilinear_difference = max(
        maximum_bilinear_difference,
        baseline_difference
    )


    fp32_np = (
        fp32_output
        .squeeze()
        .clamp(0, 1)
        .cpu()
        .numpy()
    )


    integer_np = (
        integer_ticks
        .squeeze()
        .double()
        .numpy()
        / OUTPUT_DEN
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

    integer_error = mse(
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

    integer_psnr = psnr_from_mse(
        integer_error
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
        integer_error
    )

    integer_psnrs.append(
        integer_psnr
    )

    bicubic_mses.append(
        bicubic_error
    )

    bicubic_psnrs.append(
        bicubic_psnr
    )


    if (
        integer_error
        < bicubic_error
    ):
        wins_vs_bicubic += 1


    rows.append([
        stem,
        fp32_error,
        fp32_psnr,
        integer_error,
        integer_psnr,
        bicubic_error,
        bicubic_psnr,
        baseline_difference,
    ])


    print(
        f"{stem} | "
        f"FP32 {fp32_psnr:.3f} dB | "
        f"Full integer {integer_psnr:.3f} dB | "
        f"Bicubic {bicubic_psnr:.3f} dB"
    )


    Image.fromarray(
        np.round(
            integer_np * 255.0
        )
        .clip(
            0,
            255
        )
        .astype(np.uint8)
    ).save(
        COMPARE_DIR
        / f"{stem}_full_integer.png"
    )


# --------------------------------------------------
# Aggregate results
# --------------------------------------------------

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
    "ROUND 4F — FULL INTEGER PATH"
)

print(
    "----------------------------"
)

print(
    f"FP32         "
    f"MSE={fp32_summary[0]:.8f} "
    f"| PSNR(mean MSE)="
    f"{fp32_summary[1]:.3f} dB"
)

print(
    f"Full integer "
    f"MSE={integer_summary[0]:.8f} "
    f"| PSNR(mean MSE)="
    f"{integer_summary[1]:.3f} dB"
)

print(
    f"Bicubic      "
    f"MSE={bicubic_summary[0]:.8f} "
    f"| PSNR(mean MSE)="
    f"{bicubic_summary[1]:.3f} dB"
)

print()

print(
    "FP32 -> full integer loss:",
    f"{fp32_summary[1] - integer_summary[1]:+.4f} dB"
)

print(
    "Full integer wins vs bicubic:",
    f"{wins_vs_bicubic}/20"
)

print(
    "Maximum integer-bilinear vs "
    "PyTorch bilinear difference:",
    f"{maximum_bilinear_difference:.12f}"
)


# --------------------------------------------------
# Final-add width analysis
# --------------------------------------------------

qtest = torch.tensor(
    [-127, 127],
    dtype=torch.int64
)

residual_bound = (
    rounded_shift(
        qtest
        * residual_to_output_multiplier,
        FINAL_SHIFT
    )
)

maximum_residual_ticks = int(
    residual_bound.abs().max()
)

maximum_preclip = (
    OUTPUT_DEN
    + maximum_residual_ticks
)

minimum_preclip = (
    -maximum_residual_ticks
)

add_bits = signed_bits_required(
    max(
        abs(minimum_preclip),
        abs(maximum_preclip)
    )
)


print()

print(
    "Maximum |residual| in output ticks:",
    maximum_residual_ticks
)

print(
    "Final-add theoretical range:",
    minimum_preclip,
    "to",
    maximum_preclip
)

print(
    "Minimum signed final-add width:",
    add_bits,
    "bits"
)


# --------------------------------------------------
# Save metrics and hardware constants
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
        "fp32_psnr",
        "full_integer_mse",
        "full_integer_psnr",
        "bicubic_mse",
        "bicubic_psnr",
        "integer_bilinear_max_abs_difference",
    ])

    writer.writerows(
        rows
    )


with open(
    RESULTS / "hardware_constants.txt",
    "w"
) as file:

    file.write(
        f"OUTPUT_DEN={OUTPUT_DEN}\n"
    )

    file.write(
        f"OUTPUT_SCALE={OUTPUT_SCALE}\n"
    )

    file.write(
        f"REQUANT_SHIFT={REQUANT_SHIFT}\n"
    )

    file.write(
        f"FINAL_SHIFT={FINAL_SHIFT}\n"
    )

    file.write(
        "RESIDUAL_TO_OUTPUT_MULTIPLIER="
        f"{residual_to_output_multiplier}\n"
    )

    file.write(
        "MAX_RESIDUAL_OUTPUT_TICKS="
        f"{maximum_residual_ticks}\n"
    )

    file.write(
        "FINAL_ADD_MIN="
        f"{minimum_preclip}\n"
    )

    file.write(
        "FINAL_ADD_MAX="
        f"{maximum_preclip}\n"
    )

    file.write(
        "FINAL_ADD_MIN_SIGNED_BITS="
        f"{add_bits}\n"
    )


print()

print(
    "ROUND 4F FULL INTEGER: PASS"
)