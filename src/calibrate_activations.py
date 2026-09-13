from pathlib import Path
import csv

import numpy as np
from PIL import Image

import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

from model_residual import ResidualReconstructionCNN
from quant_utils import make_weight_quantized_model


SEED = 42
BATCH_SIZE = 8

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

TRAIN_LR = Path("data/round3/train/lr")
ROUND3 = Path("results/round3")

RESULTS = Path(
    "results/round4_int8/calibration"
)

RESULTS.mkdir(
    parents=True,
    exist_ok=True
)


class LRDataset(Dataset):

    def __init__(self, directory):
        self.files = sorted(
            Path(directory).glob("*_lr.png")
        )

        if not self.files:
            raise RuntimeError(
                f"No LR images found in {directory}"
            )

    def __len__(self):
        return len(self.files)

    def __getitem__(self, index):

        image = np.asarray(
            Image.open(
                self.files[index]
            ).convert("L"),
            dtype=np.float32
        ) / 255.0

        return (
            torch.from_numpy(image)
            .unsqueeze(0)
        )


torch.manual_seed(SEED)

dataset = LRDataset(
    TRAIN_LR
)

loader = DataLoader(
    dataset,
    batch_size=BATCH_SIZE,
    shuffle=False
)


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


# Calibrate the network with the same INT8-weight
# representation established in Round 4A.
model, _ = make_weight_quantized_model(
    fp32_model
)

model = model.to(DEVICE)
model.eval()


names = [
    "bilinear_input",
    "conv1_relu",
    "conv2_relu",
    "residual",
    "reconstructed_output",
]


stats = {
    name: {
        "min": float("inf"),
        "max": float("-inf"),
        "absmax": 0.0,
        "samples": [],
    }
    for name in names
}


def collect(name, tensor):

    tensor = tensor.detach()

    stats[name]["min"] = min(
        stats[name]["min"],
        float(tensor.min())
    )

    stats[name]["max"] = max(
        stats[name]["max"],
        float(tensor.max())
    )

    stats[name]["absmax"] = max(
        stats[name]["absmax"],
        float(tensor.abs().max())
    )

    # Sample values for percentile estimation without
    # storing every activation produced by the network.
    flat = (
        tensor
        .flatten()
        .cpu()
    )

    target_samples = 50000

    stride = max(
        1,
        flat.numel() // target_samples
    )

    sampled = flat[::stride]

    if sampled.numel() > target_samples:
        sampled = sampled[:target_samples]

    stats[name]["samples"].append(
        sampled
    )


print("Device:", DEVICE)
print("Calibration images:", len(dataset))
print(
    "Calibration source: Round 3 training set only"
)
print(
    "Validation images used for calibration: 0"
)
print()


with torch.no_grad():

    for batch_index, lr in enumerate(
        loader,
        start=1
    ):

        lr = lr.to(DEVICE)

        baseline = F.interpolate(
            lr,
            scale_factor=2,
            mode="bilinear",
            align_corners=False
        )

        conv1_relu = F.relu(
            model.conv1(
                baseline
            )
        )

        conv2_relu = F.relu(
            model.conv2(
                conv1_relu
            )
        )

        residual = model.conv3(
            conv2_relu
        )

        reconstructed = (
            baseline + residual
        )

        collect(
            "bilinear_input",
            baseline
        )

        collect(
            "conv1_relu",
            conv1_relu
        )

        collect(
            "conv2_relu",
            conv2_relu
        )

        collect(
            "residual",
            residual
        )

        collect(
            "reconstructed_output",
            reconstructed
        )

        if (
            batch_index == 1
            or batch_index % 10 == 0
            or batch_index == len(loader)
        ):
            print(
                f"Processed batch "
                f"{batch_index}/{len(loader)}"
            )


rows = []


print()
print("ACTIVATION CALIBRATION")
print("----------------------")


for name in names:

    samples = torch.cat(
        stats[name]["samples"]
    ).numpy()

    abs_samples = np.abs(
        samples
    )

    minimum = stats[name]["min"]
    maximum = stats[name]["max"]
    absmax = stats[name]["absmax"]

    p99 = float(
        np.percentile(
            abs_samples,
            99.0
        )
    )

    p999 = float(
        np.percentile(
            abs_samples,
            99.9
        )
    )

    # Candidate symmetric INT8 scales.
    scale_absmax_int8 = (
        absmax / 127.0
        if absmax > 0
        else 1.0
    )

    scale_p999_int8 = (
        p999 / 127.0
        if p999 > 0
        else 1.0
    )

    # Candidate UINT8 scale. Useful for ReLU
    # activations, which cannot be negative.
    scale_p999_uint8 = (
        maximum / 255.0
        if maximum > 0
        else 1.0
    )

    rows.append([
        name,
        minimum,
        maximum,
        absmax,
        p99,
        p999,
        scale_absmax_int8,
        scale_p999_int8,
        scale_p999_uint8,
        len(samples),
    ])


    print(name)

    print(
        f"  min:       {minimum:.8f}"
    )

    print(
        f"  max:       {maximum:.8f}"
    )

    print(
        f"  abs max:   {absmax:.8f}"
    )

    print(
        f"  |x| p99:   {p99:.8f}"
    )

    print(
        f"  |x| p99.9: {p999:.8f}"
    )

    print(
        "  symmetric INT8 scale "
        f"(abs max): {scale_absmax_int8:.10f}"
    )

    print(
        "  symmetric INT8 scale "
        f"(p99.9):   {scale_p999_int8:.10f}"
    )

    print()


with open(
    RESULTS / "activation_calibration.csv",
    "w",
    newline=""
) as file:

    writer = csv.writer(file)

    writer.writerow([
        "activation",
        "minimum",
        "maximum",
        "absolute_maximum",
        "absolute_p99",
        "absolute_p99_9",
        "symmetric_int8_scale_absmax",
        "symmetric_int8_scale_p99_9",
        "uint8_scale_max",
        "sample_count",
    ])

    writer.writerows(rows)


print(
    "Saved:",
    RESULTS / "activation_calibration.csv"
)

print()
print(
    "ROUND 4B ACTIVATION CALIBRATION: PASS"
)