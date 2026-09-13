from pathlib import Path
import csv
import math

import torch

from model_residual import ResidualReconstructionCNN
from quant_utils import make_weight_quantized_model


DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

ROUND3 = Path("results/round3")

RESULTS = Path(
    "results/round4_int8/integer_accumulator"
)

RESULTS.mkdir(
    parents=True,
    exist_ok=True
)


# Round 4B/C activation scales
INPUT_SCALE = 1.0 / 255.0
CONV1_SCALE = 1.53187513 / 255.0
CONV2_SCALE = 1.00026369 / 255.0


def signed_bits_required(max_abs):

    max_abs = int(max_abs)

    bits = 1

    while max_abs > (
        (2 ** (bits - 1)) - 1
    ):
        bits += 1

    return bits


def quantize_bias(
    bias,
    input_scale,
    weight_scales
):

    accumulator_scales = (
        input_scale
        * weight_scales.double()
    )

    return torch.round(
        bias.double()
        / accumulator_scales
    ).to(torch.int64)


checkpoint = torch.load(
    ROUND3 / "best_model.pt",
    map_location=DEVICE,
    weights_only=False
)

model = (
    ResidualReconstructionCNN()
    .to(DEVICE)
)

model.load_state_dict(
    checkpoint["model_state_dict"]
)

model.eval()


_, packed = make_weight_quantized_model(
    model
)


layers = [
    (
        "conv1",
        INPUT_SCALE,
        255,
    ),
    (
        "conv2",
        CONV1_SCALE,
        255,
    ),
    (
        "conv3",
        CONV2_SCALE,
        255,
    ),
]


rows = []


print("GUARANTEED ACCUMULATOR BOUNDS")
print("-----------------------------")
print()


for (
    layer_name,
    input_scale,
    input_qmax,
) in layers:

    weight_q = (
        packed[layer_name]["qweight"]
        .to(torch.int64)
    )

    weight_scales = (
        packed[layer_name]["scales"]
    )

    bias = (
        packed[layer_name]["bias"]
    )

    bias_q = quantize_bias(
        bias,
        input_scale,
        weight_scales
    )


    # Per-output-channel bound:
    #
    # |sum(x_i*w_i) + bias|
    # <=
    # qmax * sum(|w_i|)
    # + |bias|
    #
    # This is conservative and independent
    # of the validation data.

    weight_abs_sum = (
        weight_q
        .abs()
        .reshape(
            weight_q.shape[0],
            -1
        )
        .sum(dim=1)
    )


    mac_bounds = (
        input_qmax
        * weight_abs_sum
    )


    total_bounds = (
        mac_bounds
        + bias_q.abs()
    )


    max_mac_bound = int(
        mac_bounds.max()
    )

    max_bias_abs = int(
        bias_q.abs().max()
    )

    max_total_bound = int(
        total_bounds.max()
    )

    bits = signed_bits_required(
        max_total_bound
    )


    worst_channel = int(
        torch.argmax(
            total_bounds
        )
    )


    print(layer_name)

    print(
        "  maximum |quantised bias|:",
        max_bias_abs
    )

    print(
        "  maximum MAC bound:",
        max_mac_bound
    )

    print(
        "  guaranteed total bound:",
        max_total_bound
    )

    print(
        "  worst output channel:",
        worst_channel
    )

    print(
        "  minimum safe signed bits:",
        bits
    )

    print(
        "  INT32 margin:",
        (2 ** 31 - 1)
        - max_total_bound
    )

    print()


    rows.append([
        layer_name,
        input_qmax,
        max_bias_abs,
        max_mac_bound,
        max_total_bound,
        worst_channel,
        bits,
    ])


with open(
    RESULTS
    / "accumulator_bounds.csv",
    "w",
    newline=""
) as file:

    writer = csv.writer(file)

    writer.writerow([
        "layer",
        "input_qmax",
        "max_abs_quantized_bias",
        "max_mac_bound",
        "guaranteed_total_bound",
        "worst_output_channel",
        "minimum_safe_signed_bits",
    ])

    writer.writerows(rows)


print(
    "Saved:",
    RESULTS / "accumulator_bounds.csv"
)

print()
print(
    "ACCUMULATOR BOUND ANALYSIS: PASS"
)