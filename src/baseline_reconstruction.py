from pathlib import Path
import math

import numpy as np
from PIL import Image


SOURCE = Path("data/source/test_image.jpeg")
RESULTS = Path("results")
RESULTS.mkdir(parents=True, exist_ok=True)


def mse(reference, reconstruction):
    return np.mean((reference - reconstruction) ** 2)


def psnr(reference, reconstruction):
    error = mse(reference, reconstruction)

    if error == 0:
        return float("inf")

    return 10 * math.log10(1.0 / error)


# Load the source image as grayscale
image = Image.open(SOURCE).convert("L")

# Create the 256x256 reference image
target = image.resize((256, 256), Image.Resampling.LANCZOS)

# Downsample to the common 128x128 low-resolution input
low_res = target.resize((128, 128), Image.Resampling.LANCZOS)

# Reconstruct to 256x256
bilinear = low_res.resize((256, 256), Image.Resampling.BILINEAR)
bicubic = low_res.resize((256, 256), Image.Resampling.BICUBIC)

# Convert pixels to floating point [0, 1]
target_np = np.asarray(target, dtype=np.float32) / 255.0
bilinear_np = np.asarray(bilinear, dtype=np.float32) / 255.0
bicubic_np = np.asarray(bicubic, dtype=np.float32) / 255.0

# Calculate metrics
bilinear_mse = mse(target_np, bilinear_np)
bicubic_mse = mse(target_np, bicubic_np)

bilinear_psnr = psnr(target_np, bilinear_np)
bicubic_psnr = psnr(target_np, bicubic_np)

print(f"Target shape: {target_np.shape}")
print(f"Pixel range: {target_np.min():.4f} to {target_np.max():.4f}")

print("\nBilinear")
print(f"MSE:  {bilinear_mse:.8f}")
print(f"PSNR: {bilinear_psnr:.3f} dB")

print("\nBicubic")
print(f"MSE:  {bicubic_mse:.8f}")
print(f"PSNR: {bicubic_psnr:.3f} dB")

# Preserve evidence
target.save(RESULTS / "target.png")
low_res.save(RESULTS / "low_res_128.png")
bilinear.save(RESULTS / "bilinear_256.png")
bicubic.save(RESULTS / "bicubic_256.png")