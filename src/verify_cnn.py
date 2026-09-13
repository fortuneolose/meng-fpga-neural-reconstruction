from pathlib import Path

import numpy as np
from PIL import Image

import torch
import torch.nn as nn

from model import CompactReconstructionCNN


DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

LR_DIR = Path("data/train/lr")
HR_DIR = Path("data/train/hr")


def image_to_tensor(path):
    image = Image.open(path).convert("L")

    array = np.asarray(
        image,
        dtype=np.float32
    ) / 255.0

    tensor = torch.from_numpy(array)

    # H,W -> 1,1,H,W
    tensor = tensor.unsqueeze(0).unsqueeze(0)

    return tensor


# --------------------------------------------------
# Select first training pair
# --------------------------------------------------

lr_path = sorted(LR_DIR.glob("*.png"))[0]

pair_name = lr_path.stem.replace("_lr", "")

hr_path = HR_DIR / f"{pair_name}_hr.png"

print("LR:", lr_path)
print("HR:", hr_path)

# --------------------------------------------------
# Load tensors
# --------------------------------------------------

lr = image_to_tensor(lr_path).to(DEVICE)
hr = image_to_tensor(hr_path).to(DEVICE)

print()
print("Input shape: ", tuple(lr.shape))
print("Target shape:", tuple(hr.shape))
print("Input range: ",
      float(lr.min()),
      "to",
      float(lr.max()))

# --------------------------------------------------
# Build model
# --------------------------------------------------

model = CompactReconstructionCNN().to(DEVICE)

parameter_count = sum(
    p.numel()
    for p in model.parameters()
    if p.requires_grad
)

print()
print("Device:", DEVICE)
print("Trainable parameters:", parameter_count)

# --------------------------------------------------
# Forward pass
# --------------------------------------------------

output = model(lr)

print("Output shape:", tuple(output.shape))

assert output.shape == hr.shape, (
    f"Shape mismatch: {output.shape} vs {hr.shape}"
)

# --------------------------------------------------
# Loss
# --------------------------------------------------

criterion = nn.MSELoss()

loss_before = criterion(output, hr)

print("Initial MSE loss:", loss_before.item())

# --------------------------------------------------
# Verify backpropagation
# --------------------------------------------------

optimizer = torch.optim.Adam(
    model.parameters(),
    lr=1e-3
)

weights_before = (
    model.conv1.weight
    .detach()
    .clone()
)

optimizer.zero_grad()

loss_before.backward()

optimizer.step()

weights_after = (
    model.conv1.weight
    .detach()
    .clone()
)

weights_changed = not torch.equal(
    weights_before,
    weights_after
)

# --------------------------------------------------
# Second forward pass
# --------------------------------------------------

output_after = model(lr)

loss_after = criterion(
    output_after,
    hr
)

print("Loss after one update:", loss_after.item())

print()
print("Weights updated:", weights_changed)

# --------------------------------------------------
# Numerical checks
# --------------------------------------------------

finite_output = torch.isfinite(output_after).all()
finite_loss = torch.isfinite(loss_after)

print("Finite output:", bool(finite_output))
print("Finite loss:", bool(finite_loss))

if (
    output.shape == hr.shape
    and weights_changed
    and finite_output
    and finite_loss
):
    print()
    print("CNN FORWARD/BACKWARD TEST: PASS")
else:
    print()
    print("CNN FORWARD/BACKWARD TEST: FAIL")