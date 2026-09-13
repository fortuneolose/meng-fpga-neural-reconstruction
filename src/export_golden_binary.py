from pathlib import Path

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

    export(
        image_id,
        "input_lr_u8.npy",
        "input_lr_u8.bin",
        np.uint8,
    )

    export(
        image_id,
        "bilinear_ticks_u16.npy",
        "bilinear_ticks_u16.bin",
        np.dtype("<u2"),
    )

    export(
        image_id,
        "branch_input_u8.npy",
        "branch_input_u8.bin",
        np.uint8,
    )

    export(
        image_id,
        "conv1_output_u8.npy",
        "conv1_output_u8.bin",
        np.uint8,
    )

    export(
        image_id,
        "conv2_output_u8.npy",
        "conv2_output_u8.bin",
        np.uint8,
    )

    export(
        image_id,
        "residual_int8.npy",
        "residual_int8.bin",
        np.int8,
    )

    export(
        image_id,
        "output_ticks_u16.npy",
        "output_ticks_u16.bin",
        np.dtype("<u2"),
    )


print()
print(
    "GOLDEN BINARY EXPORT: PASS"
)