from pathlib import Path
import math

import numpy as np
from PIL import Image

import torch
import torch.nn as nn

from model import CompactReconstructionCNN


# --------------------------------------------------
# Reproducibility
# --------------------------------------------------

SEED = 42

torch.manual_seed(SEED)
torch.cuda.manual_seed_all(SEED)

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

LR_PATH = Path("data/train/lr/0001_p00_lr.png")
HR_PATH = Path("data/train/hr/0001_p00_hr.png")

RESULTS = Path("results")
RESULTS.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# Image utilities
# --------------------------------------------------

def image_to_tensor(path):
    image = Image.open(path).convert("L")

    array = np.asarray(
        image,
        dtype=np.float32
    ) / 255.0

    tensor = torch.from_numpy(array)

    # H,W -> N,C,H,W
    return tensor.unsqueeze(0).unsqueeze(0)


def save_tensor_image(tensor, path):
    image = (
        tensor
        .detach()
        .cpu()
        .squeeze()
        .clamp(0.0, 1.0)
        .numpy()
    )

    image = (image * 255.0).round().astype(np.uint8)

    Image.fromarray(image, mode="L").save(path)


def psnr_from_mse(mse):
    if mse == 0:
        return float("inf")

    return 10.0 * math.log10(1.0 / mse)


# --------------------------------------------------
# Load one fixed pair
# --------------------------------------------------

lr = image_to_tensor(LR_PATH).to(DEVICE)
hr = image_to_tensor(HR_PATH).to(DEVICE)

print("Device:", DEVICE)
print("LR shape:", tuple(lr.shape))
print("HR shape:", tuple(hr.shape))


# --------------------------------------------------
# Fresh model
# --------------------------------------------------

model = CompactReconstructionCNN().to(DEVICE)

criterion = nn.MSELoss()

optimizer = torch.optim.Adam(
    model.parameters(),
    lr=1e-3
)


# --------------------------------------------------
# Initial measurement
# --------------------------------------------------

model.eval()

with torch.no_grad():
    initial_output = model(lr)
    initial_loss = criterion(initial_output, hr).item()

initial_psnr = psnr_from_mse(initial_loss)

print()
print(f"Initial loss: {initial_loss:.8f}")
print(f"Initial PSNR: {initial_psnr:.3f} dB")


# --------------------------------------------------
# Deliberately overfit one pair
# --------------------------------------------------

STEPS = 500

model.train()

for step in range(1, STEPS + 1):

    optimizer.zero_grad()

    output = model(lr)

    loss = criterion(output, hr)

    if not torch.isfinite(loss):
        raise RuntimeError(
            f"Non-finite loss detected at step {step}"
        )

    loss.backward()

    optimizer.step()

    if step == 1 or step % 50 == 0:
        print(
            f"Step {step:4d}/{STEPS} "
            f"| MSE: {loss.item():.8f}"
        )


# --------------------------------------------------
# Final measurement
# --------------------------------------------------

model.eval()

with torch.no_grad():
    final_output = model(lr)
    final_loss = criterion(final_output, hr).item()

final_psnr = psnr_from_mse(final_loss)

print()
print("Single-pair learning result")
print("---------------------------")
print(f"Initial MSE:  {initial_loss:.8f}")
print(f"Final MSE:    {final_loss:.8f}")
print(f"Initial PSNR: {initial_psnr:.3f} dB")
print(f"Final PSNR:   {final_psnr:.3f} dB")

print(
    "Output finite:",
    bool(torch.isfinite(final_output).all())
)


# --------------------------------------------------
# Save reconstruction evidence
# --------------------------------------------------

save_tensor_image(
    initial_output,
    RESULTS / "single_pair_initial.png"
)

save_tensor_image(
    final_output,
    RESULTS / "single_pair_final.png"
)

Image.open(HR_PATH).save(
    RESULTS / "single_pair_target.png"
)

Image.open(LR_PATH).save(
    RESULTS / "single_pair_input_128.png"
)


# --------------------------------------------------
# Save checkpoint
# --------------------------------------------------

torch.save(
    {
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "steps": STEPS,
        "seed": SEED,
        "initial_loss": initial_loss,
        "final_loss": final_loss,
        "initial_psnr": initial_psnr,
        "final_psnr": final_psnr,
    },
    RESULTS / "single_pair_checkpoint.pt"
)


# --------------------------------------------------
# Pass/fail
# --------------------------------------------------

if final_loss < initial_loss:
    print()
    print("SINGLE-PAIR LEARNING CHECK: PASS")
else:
    print()
    print("SINGLE-PAIR LEARNING CHECK: FAIL")