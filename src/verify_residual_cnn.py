from pathlib import Path

import numpy as np
from PIL import Image

import torch
import torch.nn as nn
import torch.nn.functional as F

from model_residual import ResidualReconstructionCNN


DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

LR_PATH = Path("data/train/lr/0001_p00_lr.png")
HR_PATH = Path("data/train/hr/0001_p00_hr.png")


def image_to_tensor(path):
    image = Image.open(path).convert("L")

    array = np.asarray(
        image,
        dtype=np.float32
    ) / 255.0

    return (
        torch.from_numpy(array)
        .unsqueeze(0)
        .unsqueeze(0)
    )


lr = image_to_tensor(LR_PATH).to(DEVICE)
hr = image_to_tensor(HR_PATH).to(DEVICE)

model = ResidualReconstructionCNN().to(DEVICE)

parameter_count = sum(
    p.numel()
    for p in model.parameters()
    if p.requires_grad
)

print("Device:", DEVICE)
print("Parameters:", parameter_count)

print("LR shape:", tuple(lr.shape))
print("HR shape:", tuple(hr.shape))


# --------------------------------------------------
# Check initial output
# --------------------------------------------------

with torch.no_grad():

    output = model(lr)

    bilinear = F.interpolate(
        lr,
        scale_factor=2,
        mode="bilinear",
        align_corners=False
    )


print("Output shape:", tuple(output.shape))

difference = torch.max(
    torch.abs(output - bilinear)
).item()

print(
    "Maximum initial difference "
    "from bilinear:",
    difference
)


# --------------------------------------------------
# Backpropagation test
# --------------------------------------------------

criterion = nn.MSELoss()

optimizer = torch.optim.Adam(
    model.parameters(),
    lr=1e-3
)

initial_loss = criterion(
    output,
    hr
)

weights_before = (
    model.conv3.weight
    .detach()
    .clone()
)

optimizer.zero_grad()

output = model(lr)

loss = criterion(
    output,
    hr
)

loss.backward()
optimizer.step()

weights_after = (
    model.conv3.weight
    .detach()
    .clone()
)

weights_changed = not torch.equal(
    weights_before,
    weights_after
)

with torch.no_grad():

    output_after = model(lr)

    loss_after = criterion(
        output_after,
        hr
    )


print()
print(
    "Initial MSE:",
    initial_loss.item()
)

print(
    "MSE after one update:",
    loss_after.item()
)

print(
    "Weights updated:",
    weights_changed
)

print(
    "Finite output:",
    bool(
        torch.isfinite(
            output_after
        ).all()
    )
)


if (
    parameter_count == 737
    and output.shape == hr.shape
    and difference < 1e-7
    and weights_changed
    and torch.isfinite(output_after).all()
):

    print()
    print(
        "RESIDUAL CNN VERIFICATION: PASS"
    )

else:

    print()
    print(
        "RESIDUAL CNN VERIFICATION: FAIL"
    )