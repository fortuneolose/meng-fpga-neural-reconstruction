from pathlib import Path
import json
import math

import numpy as np
from PIL import Image


PARAMS = Path(
    "hardware_reference/parameters"
)

OUT = Path(
    "hardware_reference/golden_vectors"
)

VAL_LR = Path(
    "data/round3/val/lr"
)

VAL_HR = Path(
    "data/round3/val/hr"
)


# Representative verification cases:
#
# 0805 = ordinary case
# 0809 = most quantisation-sensitive case
# 0824 = difficult / low-PSNR case

GOLDEN_IDS = [
    "0805",
    "0809",
    "0824",
]


# --------------------------------------------------
# Load hardware metadata
# --------------------------------------------------

with open(
    PARAMS / "hardware_metadata.json"
) as file:

    metadata = json.load(file)


REQUANT_SHIFT = int(
    metadata["requant_shift"]
)

FINAL_SHIFT = int(
    metadata[
        "residual_to_output_shift"
    ]
)

OUTPUT_DEN = int(
    metadata["output_denominator"]
)

RESIDUAL_TO_OUTPUT_MULT = int(
    metadata[
        "residual_to_output_multiplier"
    ]
)


# --------------------------------------------------
# Load exported integer parameters
# --------------------------------------------------

def load(name):
    return np.load(
        PARAMS / name
    )


w1 = load(
    "conv1_weights_int8.npy"
).astype(np.int64)

w2 = load(
    "conv2_weights_int8.npy"
).astype(np.int64)

w3 = load(
    "conv3_weights_int8.npy"
).astype(np.int64)


b1 = load(
    "conv1_bias_int32.npy"
).astype(np.int64)

b2 = load(
    "conv2_bias_int32.npy"
).astype(np.int64)

b3 = load(
    "conv3_bias_int32.npy"
).astype(np.int64)


m1 = load(
    "conv1_requant_mult_int32.npy"
).astype(np.int64)

m2 = load(
    "conv2_requant_mult_int32.npy"
).astype(np.int64)

m3 = load(
    "conv3_requant_mult_int32.npy"
).astype(np.int64)


# --------------------------------------------------
# Integer arithmetic helpers
# --------------------------------------------------

def rounded_shift_signed(
    value,
    shift
):
    """
    Signed round-to-nearest followed by
    arithmetic right shift.
    """

    value = value.astype(
        np.int64,
        copy=False
    )

    offset = (
        1 << (shift - 1)
    )

    positive = (
        value + offset
    ) >> shift

    negative = -(
        (
            (-value) + offset
        )
        >> shift
    )

    return np.where(
        value >= 0,
        positive,
        negative
    ).astype(np.int64)


def round_divide_nearest_even_unsigned(
    numerator,
    denominator
):
    """
    Non-negative integer division using
    round-to-nearest-even.
    """

    numerator = numerator.astype(
        np.int64,
        copy=False
    )

    quotient = (
        numerator // denominator
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
                (quotient & 1) == 1
            )
        )
    )

    return (
        quotient
        + increment.astype(np.int64)
    )


# --------------------------------------------------
# Integer 2x bilinear interpolation
# --------------------------------------------------

def axis_coefficients(length):

    output_length = (
        2 * length
    )

    index0 = np.zeros(
        output_length,
        dtype=np.int64
    )

    index1 = np.zeros(
        output_length,
        dtype=np.int64
    )

    weight0 = np.zeros(
        output_length,
        dtype=np.int64
    )

    weight1 = np.zeros(
        output_length,
        dtype=np.int64
    )


    for j in range(
        output_length
    ):

        if j == 0:

            index0[j] = 0
            index1[j] = 0

            weight0[j] = 4
            weight1[j] = 0

        elif j == (
            output_length - 1
        ):

            index0[j] = (
                length - 1
            )

            index1[j] = (
                length - 1
            )

            weight0[j] = 4
            weight1[j] = 0

        elif j % 2 == 0:

            i = j // 2

            index0[j] = (
                i - 1
            )

            index1[j] = i

            weight0[j] = 1
            weight1[j] = 3

        else:

            i = j // 2

            index0[j] = i

            index1[j] = (
                i + 1
            )

            weight0[j] = 3
            weight1[j] = 1


    return (
        index0,
        index1,
        weight0,
        weight1,
    )


def integer_bilinear_2x_scaled16(
    x
):
    """
    Input:
        uint8-equivalent pixels [0,255]

    Output:
        integer fixed-point representation
        where 4080 represents 1.0.

    Bilinear denominator = 16.
    """

    height, width = x.shape


    (
        left,
        right,
        wl,
        wr,
    ) = axis_coefficients(
        width
    )


    horizontal = (
        x[:, left]
        * wl[np.newaxis, :]
        +
        x[:, right]
        * wr[np.newaxis, :]
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
        horizontal[top, :]
        * wt[:, np.newaxis]
        +
        horizontal[bottom, :]
        * wb[:, np.newaxis]
    )


    return output.astype(
        np.int64
    )


# --------------------------------------------------
# Pure integer convolution
# --------------------------------------------------

def conv2d_integer(
    x,
    weight,
    bias
):
    """
    Pure NumPy integer 3x3 convolution.

    x:
        [C,H,W]

    weight:
        [O,C,3,3]

    output:
        [O,H,W] int64
    """

    x = x.astype(
        np.int64,
        copy=False
    )

    weight = weight.astype(
        np.int64,
        copy=False
    )


    padded = np.pad(
        x,
        (
            (0, 0),
            (1, 1),
            (1, 1),
        ),
        mode="constant",
        constant_values=0
    )


    windows = (
        np.lib.stride_tricks
        .sliding_window_view(
            padded,
            (3, 3),
            axis=(1, 2)
        )
    )


    accumulator = np.einsum(
        "chwkl,ockl->ohw",
        windows,
        weight,
        dtype=np.int64,
        optimize=True
    )


    accumulator += (
        bias[:, None, None]
    )


    return accumulator.astype(
        np.int64
    )


# --------------------------------------------------
# Integer requantisation
# --------------------------------------------------

def requant_uint8(
    accumulator,
    multiplier
):

    product = (
        accumulator
        * multiplier[:, None, None]
    )

    q = rounded_shift_signed(
        product,
        REQUANT_SHIFT
    )

    return np.clip(
        q,
        0,
        255
    ).astype(np.uint8)


def requant_int8(
    accumulator,
    multiplier
):

    product = (
        accumulator
        * multiplier[:, None, None]
    )

    q = rounded_shift_signed(
        product,
        REQUANT_SHIFT
    )

    return np.clip(
        q,
        -127,
        127
    ).astype(np.int8)


# --------------------------------------------------
# Metrics
# --------------------------------------------------

def mse(a, b):

    return float(
        np.mean(
            (
                a.astype(np.float64)
                - b.astype(np.float64)
            ) ** 2
        )
    )


def psnr(error):

    return (
        10.0
        * math.log10(
            1.0 / error
        )
    )


# --------------------------------------------------
# Generate golden vectors
# --------------------------------------------------

print(
    "PURE INTEGER GOLDEN VECTOR GENERATION"
)

print(
    "-------------------------------------"
)

print()


for image_id in GOLDEN_IDS:

    lr_path = (
        VAL_LR
        / f"{image_id}_lr.png"
    )

    hr_path = (
        VAL_HR
        / f"{image_id}_hr.png"
    )


    image_dir = (
        OUT / image_id
    )

    image_dir.mkdir(
        parents=True,
        exist_ok=True
    )


    # ----------------------------------------------
    # Original 128x128 input
    # ----------------------------------------------

    lr_u8 = np.asarray(
        Image.open(
            lr_path
        ).convert("L"),
        dtype=np.uint8
    )


    # ----------------------------------------------
    # Integer bilinear 2x
    # ----------------------------------------------

    baseline_ticks = (
        integer_bilinear_2x_scaled16(
            lr_u8.astype(
                np.int64
            )
        )
    )


    # Convert 1/4080 fixed-point bilinear
    # representation back to UINT8 for CNN input.

    q0 = (
        round_divide_nearest_even_unsigned(
            baseline_ticks,
            16
        )
    )

    q0 = np.clip(
        q0,
        0,
        255
    ).astype(np.uint8)


    # ----------------------------------------------
    # Conv1
    # ----------------------------------------------

    acc1 = conv2d_integer(
        q0[np.newaxis, :, :],
        w1,
        b1
    )

    q1 = requant_uint8(
        acc1,
        m1
    )


    # ----------------------------------------------
    # Conv2
    # ----------------------------------------------

    acc2 = conv2d_integer(
        q1,
        w2,
        b2
    )

    q2 = requant_uint8(
        acc2,
        m2
    )


    # ----------------------------------------------
    # Conv3
    # ----------------------------------------------

    acc3 = conv2d_integer(
        q2,
        w3,
        b3
    )

    q_residual = requant_int8(
        acc3,
        m3
    )


    # ----------------------------------------------
    # Convert residual to 1/4080 output domain
    # ----------------------------------------------

    residual_product = (
        q_residual.astype(np.int64)
        * RESIDUAL_TO_OUTPUT_MULT
    )


    residual_ticks = (
        rounded_shift_signed(
            residual_product,
            FINAL_SHIFT
        )
    )


    # ----------------------------------------------
    # Integer skip connection
    # ----------------------------------------------

    output_ticks = (
        baseline_ticks
        + residual_ticks[0]
    )


    output_ticks = np.clip(
        output_ticks,
        0,
        OUTPUT_DEN
    ).astype(np.uint16)


    # ----------------------------------------------
    # Save interface-level golden vectors
    # ----------------------------------------------

    np.save(
        image_dir
        / "input_lr_u8.npy",
        lr_u8
    )

    np.save(
        image_dir
        / "bilinear_ticks_u16.npy",
        baseline_ticks.astype(
            np.uint16
        )
    )

    np.save(
        image_dir
        / "branch_input_u8.npy",
        q0
    )

    np.save(
        image_dir
        / "conv1_output_u8.npy",
        q1
    )

    np.save(
        image_dir
        / "conv2_output_u8.npy",
        q2
    )

    np.save(
        image_dir
        / "residual_int8.npy",
        q_residual
    )

    np.save(
        image_dir
        / "output_ticks_u16.npy",
        output_ticks
    )


    # ----------------------------------------------
    # Sanity metric
    # ----------------------------------------------

    output_float = (
        output_ticks.astype(
            np.float64
        )
        / OUTPUT_DEN
    )


    hr = (
        np.asarray(
            Image.open(
                hr_path
            ).convert("L"),
            dtype=np.float64
        )
        / 255.0
    )


    error = mse(
        hr,
        output_float
    )

    quality = psnr(
        error
    )


    output_u8 = np.clip(
        np.round(
            output_float * 255.0
        ),
        0,
        255
    ).astype(np.uint8)


    Image.fromarray(
        output_u8
    ).save(
        image_dir
        / "output_preview.png"
    )


    print(image_id)

    print(
        "  Input shape:",
        lr_u8.shape
    )

    print(
        "  Bilinear shape:",
        baseline_ticks.shape
    )

    print(
        "  Conv1 shape:",
        q1.shape
    )

    print(
        "  Conv2 shape:",
        q2.shape
    )

    print(
        "  Residual shape:",
        q_residual.shape
    )

    print(
        "  Output shape:",
        output_ticks.shape
    )

    print(
        "  Output tick range:",
        int(output_ticks.min()),
        "to",
        int(output_ticks.max())
    )

    print(
        f"  MSE:  {error:.8f}"
    )

    print(
        f"  PSNR: {quality:.3f} dB"
    )

    print()


print(
    "PURE INTEGER GOLDEN VECTORS: PASS"
)