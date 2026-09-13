from pathlib import Path
import math

import numpy as np
from PIL import Image

import torch
import torch.nn as nn

from model_residual import ResidualReconstructionCNN


SEED = 42

torch.manual_seed(SEED)
torch.cuda.manual_seed_all(SEED)

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

LR_PATH = Path("data/train/lr/0001_p00_lr.png")
HR_PATH = Path("data/train/hr/0001_p00_hr.png")

RESULTS = Path("results/residual")
RESULTS.mkdir(parents=True, exist_ok=True)


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


def save_tensor_image(tensor, path):
    array = (
        tensor
        .detach()
        .cpu()
        .squeeze()
        .clamp(0.0, 1.0)
        .numpy()
    )

    array = (
        array * 255.0
    ).round().astype(np.uint8)

    Image.fromarray(array).save(path)


def psnr_from_mse(mse):
    if mse == 0:
        return float("inf")

    return 10.0 * math.log10(1.0 / mse)


lr = image_to_tensor(LR_PATH).to(DEVICE)
hr = image_to_tensor(HR_PATH).to(DEVICE)

model = ResidualReconstructionCNN().to(DEVICE)

criterion = nn.MSELoss()

optimizer = torch.optim.Adam(
    model.parameters(),
    lr=1e-3
)


# Initial bilinear-equivalent output
model.eval()

with torch.no_grad():
    initial_output = model(lr)
    initial_mse = criterion(
        initial_output,
        hr
    ).item()

initial_psnr = psnr_from_mse(
    initial_mse
)

print("Device:", DEVICE)

print()
print(
    f"Initial MSE:  {initial_mse:.8f}"
)

print(
    f"Initial PSNR: {initial_psnr:.3f} dB"
)


# Train repeatedly on one pair
STEPS = 500

model.train()

for step in range(1, STEPS + 1):

    optimizer.zero_grad()

    output = model(lr)

    loss = criterion(
        output,
        hr
    )

    if not torch.isfinite(loss):
        raise RuntimeError(
            f"Non-finite loss at step {step}"
        )

    loss.backward()
    optimizer.step()

    if step == 1 or step % 50 == 0:

        print(
            f"Step {step:4d}/{STEPS} "
            f"| MSE: {loss.item():.8f}"
        )


# Final result
model.eval()

with torch.no_grad():

    final_output = model(lr)

    final_mse = criterion(
        final_output,
        hr
    ).item()

final_psnr = psnr_from_mse(
    final_mse
)


print()
print("Residual single-pair result")
print("---------------------------")

print(
    f"Initial MSE:  {initial_mse:.8f}"
)

print(
    f"Final MSE:    {final_mse:.8f}"
)

print(
    f"Initial PSNR: {initial_psnr:.3f} dB"
)

print(
    f"Final PSNR:   {final_psnr:.3f} dB"
)

print(
    "Output finite:",
    bool(
        torch.isfinite(
            final_output
        ).all()
    )
)


# Save evidence
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


torch.save(
    {
        "model_state_dict":
            model.state_dict(),

        "optimizer_state_dict":
            optimizer.state_dict(),

        "steps":
            STEPS,

        "seed":
            SEED,

        "initial_mse":
            initial_mse,

        "final_mse":
            final_mse,

        "initial_psnr":
            initial_psnr,

        "final_psnr":
            final_psnr,
    },
    RESULTS / "single_pair_checkpoint.pt"
)


if final_mse < initial_mse:

    print()
    print(
        "RESIDUAL SINGLE-PAIR CHECK: PASS"
    )

else:

    print()
    print(
        "RESIDUAL SINGLE-PAIR CHECK: FAIL"
    )