from pathlib import Path
import json

import numpy as np
import torch

from model_residual import ResidualReconstructionCNN
from quant_utils import make_weight_quantized_model


DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

ROUND3 = Path("results/round3")

OUT = Path(
    "hardware_reference/parameters"
)

OUT.mkdir(
    parents=True,
    exist_ok=True
)


# --------------------------------------------------
# Fixed quantisation configuration
# --------------------------------------------------

INPUT_SCALE = 1.0 / 255.0
CONV1_SCALE = 1.53187513 / 255.0
CONV2_SCALE = 1.00026369 / 255.0
RESIDUAL_SCALE = 0.28041983 / 127.0

REQUANT_SHIFT = 20

OUTPUT_DEN = 4080
OUTPUT_SCALE = 1.0 / OUTPUT_DEN

FINAL_SHIFT = 20

RESIDUAL_TO_OUTPUT_MULTIPLIER = 9446373


# Guaranteed widths from bound analysis
ACCUMULATOR_BITS = {
    "conv1": 19,
    "conv2": 22,
    "conv3": 21,
}

FINAL_ADD_BITS = 14


# --------------------------------------------------
# Helpers
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
    ).to(torch.int32)


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

    return torch.round(
        real_multiplier
        * (2 ** shift)
    ).to(torch.int32)


def save_array(
    filename,
    array
):

    np.save(
        OUT / filename,
        array
    )


def c_array(
    name,
    values,
    c_type
):

    flat = values.reshape(-1)

    lines = []

    lines.append(
        f"static const {c_type} "
        f"{name}[{flat.size}] = {{"
    )

    row = []

    for index, value in enumerate(flat):

        row.append(
            str(int(value))
        )

        if (
            len(row) == 12
            or index == len(flat) - 1
        ):

            lines.append(
                "    "
                + ", ".join(row)
                + (
                    ","
                    if index != len(flat) - 1
                    else ""
                )
            )

            row = []

    lines.append("};")

    return "\n".join(lines)


# --------------------------------------------------
# Load the frozen FP32 checkpoint
# --------------------------------------------------

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
    checkpoint[
        "model_state_dict"
    ]
)

model.eval()


# --------------------------------------------------
# Reproduce the frozen INT8 weights
# --------------------------------------------------

_, packed = make_weight_quantized_model(
    model
)


weights = {}

weight_scales = {}

biases = {}

multipliers = {}


layer_configuration = [
    (
        "conv1",
        INPUT_SCALE,
        CONV1_SCALE,
    ),
    (
        "conv2",
        CONV1_SCALE,
        CONV2_SCALE,
    ),
    (
        "conv3",
        CONV2_SCALE,
        RESIDUAL_SCALE,
    ),
]


for (
    layer,
    input_scale,
    output_scale,
) in layer_configuration:

    weights[layer] = (
        packed[layer]["qweight"]
        .numpy()
        .astype(np.int8)
    )

    weight_scales[layer] = (
        packed[layer]["scales"]
        .numpy()
        .astype(np.float64)
    )

    biases[layer] = (
        quantize_bias(
            packed[layer]["bias"],
            input_scale,
            packed[layer]["scales"],
        )
        .numpy()
        .astype(np.int32)
    )

    multipliers[layer] = (
        make_multiplier(
            input_scale,
            packed[layer]["scales"],
            output_scale,
            REQUANT_SHIFT,
        )
        .numpy()
        .astype(np.int32)
    )


# --------------------------------------------------
# Save machine-readable arrays
# --------------------------------------------------

for layer in [
    "conv1",
    "conv2",
    "conv3",
]:

    save_array(
        f"{layer}_weights_int8.npy",
        weights[layer]
    )

    save_array(
        f"{layer}_bias_int32.npy",
        biases[layer]
    )

    save_array(
        f"{layer}_requant_mult_int32.npy",
        multipliers[layer]
    )

    # Documentation / traceability only.
    save_array(
        f"{layer}_weight_scales_float64.npy",
        weight_scales[layer]
    )


# --------------------------------------------------
# Metadata
# --------------------------------------------------

metadata = {

    "source_checkpoint":
        "results/round3/best_model.pt",

    "checkpoint_epoch":
        int(checkpoint["epoch"]),

    "tensor_layout":
        "OIHW",

    "input_shape":
        [1, 128, 128],

    "output_shape":
        [1, 256, 256],

    "layers": {

        "conv1": {
            "shape": list(
                weights["conv1"].shape
            ),
            "weight_dtype": "int8",
            "bias_dtype": "int32",
            "activation_output": "uint8",
            "accumulator_min_bits": 19,
        },

        "conv2": {
            "shape": list(
                weights["conv2"].shape
            ),
            "weight_dtype": "int8",
            "bias_dtype": "int32",
            "activation_output": "uint8",
            "accumulator_min_bits": 22,
        },

        "conv3": {
            "shape": list(
                weights["conv3"].shape
            ),
            "weight_dtype": "int8",
            "bias_dtype": "int32",
            "activation_output": "int8",
            "accumulator_min_bits": 21,
        },
    },

    "activation_scales": {
        "input": INPUT_SCALE,
        "conv1": CONV1_SCALE,
        "conv2": CONV2_SCALE,
        "residual": RESIDUAL_SCALE,
    },

    "requant_shift":
        REQUANT_SHIFT,

    "bilinear_denominator":
        16,

    "output_denominator":
        OUTPUT_DEN,

    "output_scale":
        OUTPUT_SCALE,

    "residual_to_output_multiplier":
        RESIDUAL_TO_OUTPUT_MULTIPLIER,

    "residual_to_output_shift":
        FINAL_SHIFT,

    "final_add_min_bits":
        FINAL_ADD_BITS,

    "final_add_preclip_range":
        [-1144, 5224],
}


with open(
    OUT / "hardware_metadata.json",
    "w"
) as file:

    json.dump(
        metadata,
        file,
        indent=4
    )


# --------------------------------------------------
# Generate C/C++ header for HLS
# --------------------------------------------------

header = []

header.append(
    "#ifndef RECONSTRUCTION_PARAMS_H"
)

header.append(
    "#define RECONSTRUCTION_PARAMS_H"
)

header.append("")

header.append(
    "#include <stdint.h>"
)

header.append("")

header.append(
    "// Automatically exported from the frozen"
)

header.append(
    "// Round 3 / Round 4 quantised model."
)

header.append(
    "// Weight layout: [OUT][IN][KY][KX]"
)

header.append("")

header.append(
    "#define REQUANT_SHIFT 20"
)

header.append(
    "#define FINAL_SHIFT 20"
)

header.append(
    "#define OUTPUT_DEN 4080"
)

header.append(
    "#define BILINEAR_DEN 16"
)

header.append(
    "#define RESIDUAL_TO_OUTPUT_MULT 9446373"
)

header.append("")

header.append(
    c_array(
        "CONV1_WEIGHTS",
        weights["conv1"],
        "int8_t"
    )
)

header.append("")

header.append(
    c_array(
        "CONV1_BIAS",
        biases["conv1"],
        "int32_t"
    )
)

header.append("")

header.append(
    c_array(
        "CONV1_MULT",
        multipliers["conv1"],
        "int32_t"
    )
)

header.append("")


header.append(
    c_array(
        "CONV2_WEIGHTS",
        weights["conv2"],
        "int8_t"
    )
)

header.append("")

header.append(
    c_array(
        "CONV2_BIAS",
        biases["conv2"],
        "int32_t"
    )
)

header.append("")

header.append(
    c_array(
        "CONV2_MULT",
        multipliers["conv2"],
        "int32_t"
    )
)

header.append("")


header.append(
    c_array(
        "CONV3_WEIGHTS",
        weights["conv3"],
        "int8_t"
    )
)

header.append("")

header.append(
    c_array(
        "CONV3_BIAS",
        biases["conv3"],
        "int32_t"
    )
)

header.append("")

header.append(
    c_array(
        "CONV3_MULT",
        multipliers["conv3"],
        "int32_t"
    )
)

header.append("")

header.append(
    "#endif"
)


with open(
    OUT / "reconstruction_params.h",
    "w"
) as file:

    file.write(
        "\n".join(header)
    )


# --------------------------------------------------
# Verification summary
# --------------------------------------------------

print(
    "HARDWARE PARAMETER EXPORT"
)

print(
    "-------------------------"
)

print()


total_weights = 0
total_biases = 0


for layer in [
    "conv1",
    "conv2",
    "conv3",
]:

    total_weights += (
        weights[layer].size
    )

    total_biases += (
        biases[layer].size
    )

    print(layer)

    print(
        "  weight shape:",
        weights[layer].shape
    )

    print(
        "  weight count:",
        weights[layer].size
    )

    print(
        "  weight range:",
        int(weights[layer].min()),
        "to",
        int(weights[layer].max())
    )

    print(
        "  bias count:",
        biases[layer].size
    )

    print(
        "  bias range:",
        int(biases[layer].min()),
        "to",
        int(biases[layer].max())
    )

    print(
        "  multiplier range:",
        int(multipliers[layer].min()),
        "to",
        int(multipliers[layer].max())
    )

    print()


print(
    "Total INT8 weights:",
    total_weights
)

print(
    "Total INT32 biases:",
    total_biases
)

print()

print(
    "Saved hardware parameter package:"
)

print(
    OUT
)

print()

print(
    "HARDWARE PARAMETER EXPORT: PASS"
)