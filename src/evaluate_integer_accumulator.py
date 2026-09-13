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


# --------------------------------------------------
# Fixed Round 4B/C scales
# --------------------------------------------------

INPUT_SCALE = 1.0 / 255.0
CONV1_SCALE = 1.53187513 / 255.0
CONV2_SCALE = 1.00026369 / 255.0
RESIDUAL_SCALE = 0.28041983 / 127.0


VAL_LR = Path("data/round3/val/lr")
VAL_HR = Path("data/round3/val/hr")

ROUND3 = Path("results/round3")

RESULTS = Path(
    "results/round4_int8/integer_accumulator"
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
# Utilities
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

    return 10.0 * math.log10(
        1.0 / error
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
    """
    Bias lives in the convolution accumulator domain:

        bias_q =
            round(
                bias /
                (input_scale * weight_scale)
            )
    """

    accumulator_scales = (
        float(input_scale)
        * weight_scales.double()
    )

    return torch.round(
        bias.double()
        / accumulator_scales
    ).to(torch.int64)


def integer_conv2d(
    x_q,
    weight_q,
    bias_q
):
    """
    Exact integer-valued convolution accumulation.

    torch.unfold does not provide the integer kernel we
    want here, so integer values are represented as
    float64 during matrix multiplication.

    At the magnitudes in this network, integer products
    and sums are exactly representable in float64.

    The result is converted back to int64.
    """

    batch, channels, height, width = (
        x_q.shape
    )

    out_channels = weight_q.shape[0]

    patches = F.unfold(
        x_q.double(),
        kernel_size=3,
        padding=1,
        stride=1
    )

    weights = (
        weight_q
        .double()
        .reshape(
            out_channels,
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
        .view(1, -1, 1)
    )

    accumulator = (
        torch.round(accumulator)
        .to(torch.int64)
    )

    return accumulator.reshape(
        batch,
        out_channels,
        height,
        width
    )


def requantize_relu_uint8(
    accumulator,
    input_scale,
    weight_scales,
    output_scale
):

    accumulator_scales = (
        float(input_scale)
        * weight_scales.double()
    )

    real = (
        accumulator.double()
        * accumulator_scales.view(
            1, -1, 1, 1
        )
    )

    real = torch.clamp(
        real,
        min=0.0
    )

    q = torch.round(
        real / output_scale
    )

    return torch.clamp(
        q,
        0,
        255
    ).to(torch.int64)


def requantize_int8(
    accumulator,
    input_scale,
    weight_scales,
    output_scale
):

    accumulator_scales = (
        float(input_scale)
        * weight_scales.double()
    )

    real = (
        accumulator.double()
        * accumulator_scales.view(
            1, -1, 1, 1
        )
    )

    q = torch.round(
        real / output_scale
    )

    return torch.clamp(
        q,
        -127,
        127
    ).to(torch.int64)


def signed_bits_required(maximum_absolute):

    maximum_absolute = int(
        maximum_absolute
    )

    if maximum_absolute == 0:
        return 1

    return (
        math.ceil(
            math.log2(
                maximum_absolute + 1
            )
        )
        + 1
    )


# --------------------------------------------------
# Load FP32 model
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
# Obtain INT8 weights
# --------------------------------------------------

w8_model, packed = (
    make_weight_quantized_model(
        fp32_model
    )
)

w8_model = w8_model.to(DEVICE)
w8_model.eval()


# --------------------------------------------------
# Quantise biases to accumulator domain
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


for name, bias_q in [
    ("conv1", conv1_bias_q),
    ("conv2", conv2_bias_q),
    ("conv3", conv3_bias_q),
]:

    if int(bias_q.abs().max()) >= 2**31:
        raise RuntimeError(
            f"{name} bias does not fit INT32"
        )


torch.save(
    {
        "conv1_bias_int32":
            conv1_bias_q.to(torch.int32),

        "conv2_bias_int32":
            conv2_bias_q.to(torch.int32),

        "conv3_bias_int32":
            conv3_bias_q.to(torch.int32),

        "input_scale":
            INPUT_SCALE,

        "conv1_activation_scale":
            CONV1_SCALE,

        "conv2_activation_scale":
            CONV2_SCALE,

        "residual_scale":
            RESIDUAL_SCALE,
    },
    RESULTS / "integer_parameters.pt"
)


# --------------------------------------------------
# Existing fake-W8A8 forward for comparison
# --------------------------------------------------

def forward_fake_w8a8(lr):

    baseline = F.interpolate(
        lr,
        scale_factor=2,
        mode="bilinear",
        align_corners=False
    )

    x = fake_quantize_uint8(
        baseline,
        INPUT_SCALE
    )

    x = F.relu(
        w8_model.conv1(x)
    )

    x = fake_quantize_uint8(
        x,
        CONV1_SCALE
    )

    x = F.relu(
        w8_model.conv2(x)
    )

    x = fake_quantize_uint8(
        x,
        CONV2_SCALE
    )

    residual = (
        w8_model.conv3(x)
    )

    residual = fake_quantize_int8(
        residual,
        RESIDUAL_SCALE
    )

    return baseline + residual


# --------------------------------------------------
# Integer-accumulator forward
# --------------------------------------------------

peak_accumulators = {
    "conv1": 0,
    "conv2": 0,
    "conv3": 0,
}


def forward_integer(lr):

    # Preserve the Round 4C FP32 skip path.
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

    # Quantise residual-branch input.
    q0 = torch.round(
        baseline_cpu / INPUT_SCALE
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

    peak_accumulators["conv1"] = max(
        peak_accumulators["conv1"],
        int(acc1.abs().max())
    )

    q1 = requantize_relu_uint8(
        acc1,
        INPUT_SCALE,
        packed["conv1"]["scales"],
        CONV1_SCALE
    )


    # Conv2
    acc2 = integer_conv2d(
        q1,
        packed["conv2"]["qweight"],
        conv2_bias_q
    )

    peak_accumulators["conv2"] = max(
        peak_accumulators["conv2"],
        int(acc2.abs().max())
    )

    q2 = requantize_relu_uint8(
        acc2,
        CONV1_SCALE,
        packed["conv2"]["scales"],
        CONV2_SCALE
    )


    # Conv3
    acc3 = integer_conv2d(
        q2,
        packed["conv3"]["qweight"],
        conv3_bias_q
    )

    peak_accumulators["conv3"] = max(
        peak_accumulators["conv3"],
        int(acc3.abs().max())
    )

    q_residual = requantize_int8(
        acc3,
        CONV2_SCALE,
        packed["conv3"]["scales"],
        RESIDUAL_SCALE
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

fake_mses = []
fake_psnrs = []

integer_mses = []
integer_psnrs = []

bicubic_mses = []
bicubic_psnrs = []

rows = []

wins_vs_bicubic = 0

fake_integer_max_difference = 0.0


print("Device:", DEVICE)
print("Checkpoint epoch:", checkpoint["epoch"])
print()


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

    lr = (
        image_to_tensor(lr_path)
        .to(DEVICE)
    )


    with torch.no_grad():

        fp32_output = fp32_model(
            lr
        )

        fake_output = forward_fake_w8a8(
            lr
        )

        integer_output = forward_integer(
            lr
        )


    fp32_np = (
        fp32_output
        .squeeze()
        .clamp(0, 1)
        .cpu()
        .numpy()
    )

    fake_np = (
        fake_output
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


    values = {}

    for name, prediction in [
        ("fp32", fp32_np),
        ("fake", fake_np),
        ("integer", integer_np),
        ("bicubic", bicubic_np),
    ]:

        error = mse(
            hr_np,
            prediction
        )

        values[name] = (
            error,
            psnr_from_mse(error)
        )


    fp32_mses.append(values["fp32"][0])
    fp32_psnrs.append(values["fp32"][1])

    fake_mses.append(values["fake"][0])
    fake_psnrs.append(values["fake"][1])

    integer_mses.append(values["integer"][0])
    integer_psnrs.append(values["integer"][1])

    bicubic_mses.append(values["bicubic"][0])
    bicubic_psnrs.append(values["bicubic"][1])


    if (
        values["integer"][0]
        < values["bicubic"][0]
    ):
        wins_vs_bicubic += 1


    max_difference = float(
        np.max(
            np.abs(
                fake_np
                - integer_np
            )
        )
    )

    fake_integer_max_difference = max(
        fake_integer_max_difference,
        max_difference
    )


    rows.append([
        stem,
        values["fp32"][0],
        values["fp32"][1],
        values["fake"][0],
        values["fake"][1],
        values["integer"][0],
        values["integer"][1],
        values["bicubic"][0],
        values["bicubic"][1],
        max_difference,
    ])


    print(
        f"{stem} | "
        f"FP32 {values['fp32'][1]:.3f} dB | "
        f"Fake W8A8 {values['fake'][1]:.3f} dB | "
        f"Integer {values['integer'][1]:.3f} dB | "
        f"Bicubic {values['bicubic'][1]:.3f} dB"
    )


fp32_summary = summarize(
    fp32_mses,
    fp32_psnrs
)

fake_summary = summarize(
    fake_mses,
    fake_psnrs
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
print("ROUND 4D — INTEGER ACCUMULATOR")
print("------------------------------")

print(
    f"FP32       PSNR(mean MSE)="
    f"{fp32_summary[1]:.3f} dB"
)

print(
    f"Fake W8A8  PSNR(mean MSE)="
    f"{fake_summary[1]:.3f} dB"
)

print(
    f"Integer    PSNR(mean MSE)="
    f"{integer_summary[1]:.3f} dB"
)

print(
    f"Bicubic    PSNR(mean MSE)="
    f"{bicubic_summary[1]:.3f} dB"
)

print()

print(
    "Integer wins vs bicubic:",
    f"{wins_vs_bicubic}/20"
)

print(
    "Maximum Fake-W8A8 vs integer "
    f"output difference: "
    f"{fake_integer_max_difference:.10f}"
)

print()


for layer in [
    "conv1",
    "conv2",
    "conv3",
]:

    peak = peak_accumulators[layer]

    bits = signed_bits_required(
        peak
    )

    print(
        f"{layer} peak |accumulator|: "
        f"{peak}"
    )

    print(
        f"{layer} minimum signed bits: "
        f"{bits}"
    )

    if peak >= 2**31:
        raise RuntimeError(
            f"{layer} exceeds INT32"
        )


print()
print(
    "All observed accumulators fit INT32."
)


# --------------------------------------------------
# Save evidence
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
        "fake_w8a8_mse",
        "fake_w8a8_psnr",
        "integer_mse",
        "integer_psnr",
        "bicubic_mse",
        "bicubic_psnr",
        "fake_integer_max_abs_difference",
    ])

    writer.writerows(rows)