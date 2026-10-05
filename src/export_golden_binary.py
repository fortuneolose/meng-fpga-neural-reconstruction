from pathlib import Path
import argparse

import numpy as np


SOURCE = Path(
    "hardware_reference/golden_vectors"
)

DEST = Path(
    "hls/tb/data"
)

IDS = [
    "0805",
    "0809",
    "0824",
]


# (npy name, bin name, dtype, interface-level)
#
# The interface-level files are the accelerator's
# input and output; the rest are intermediates used
# for stage-by-stage bisection.

FILES = [
    ("input_lr_u8.npy", "input_lr_u8.bin", np.uint8, True),
    ("bilinear_ticks_u16.npy", "bilinear_ticks_u16.bin", np.dtype("<u2"), False),
    ("branch_input_u8.npy", "branch_input_u8.bin", np.uint8, False),
    ("conv1_output_u8.npy", "conv1_output_u8.bin", np.uint8, False),
    ("conv2_output_u8.npy", "conv2_output_u8.bin", np.uint8, False),
    ("residual_int8.npy", "residual_int8.bin", np.int8, False),
    ("output_ticks_u16.npy", "output_ticks_u16.bin", np.dtype("<u2"), True),
]


# --------------------------------------------------
# Optional command-line overrides
#
# With no arguments the script behaves exactly as
# before: all seven files for the three golden IDS,
# from hardware_reference/golden_vectors into
# hls/tb/data.
# --------------------------------------------------

parser = argparse.ArgumentParser(
    description=(
        "Export golden vectors as raw "
        "little-endian binaries for the "
        "C testbench."
    )
)

parser.add_argument(
    "--source",
    type=Path,
    default=SOURCE,
)

parser.add_argument(
    "--dest",
    type=Path,
    default=DEST,
)

parser.add_argument(
    "--ids",
    nargs="+",
    default=IDS,
)

parser.add_argument(
    "--interface-only",
    action="store_true",
    help="export only the input and output",
)

args = parser.parse_args()

SOURCE = args.source
DEST = args.dest
IDS = args.ids


def export(
    image_id,
    npy_name,
    bin_name,
    dtype,
):
    array = np.load(
        SOURCE / image_id / npy_name
    )

    array = np.asarray(
        array,
        dtype=dtype
    )

    path = (
        DEST
        / image_id
        / bin_name
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    array.tofile(path)

    print(
        f"{image_id} | "
        f"{bin_name} | "
        f"shape={array.shape} | "
        f"bytes={array.nbytes}"
    )


for image_id in IDS:

    for npy_name, bin_name, dtype, interface in FILES:

        if args.interface_only and not interface:
            continue

        export(
            image_id,
            npy_name,
            bin_name,
            dtype,
        )


print()
print(
    "GOLDEN BINARY EXPORT: PASS"
)
