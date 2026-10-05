"""
Rebuild the Round 3 validation pairs from the committed target crops.

The original Round 3 dataset is not in the repository, but its 20 validation
high-resolution crops are: results/round3/comparison/<id>_target.png are the
lossless 256x256 grayscale HR images. The low-resolution inputs are recreated
exactly as prepare_dataset_round3.py made them (save_pair): a Pillow bicubic
resize to 128x128.

The LR images therefore depend on the Pillow version. Pillow 12.3.0 reproduces
the committed input_lr_u8 golden vectors bit-for-bit; check with
tests/check_golden_regeneration.py before trusting another version.

Writes <out>/hr/<id>_hr.png and <out>/lr/<id>_lr.png, the layout
generate_golden_vectors.py reads. The default, data/round3/val, is gitignored.
"""

from pathlib import Path
import argparse

from PIL import Image


TARGETS = Path(
    "results/round3/comparison"
)

PATCH_SIZE = 256
LR_SIZE = 128


parser = argparse.ArgumentParser(
    description=__doc__.strip().splitlines()[0]
)

parser.add_argument(
    "--targets",
    type=Path,
    default=TARGETS,
)

parser.add_argument(
    "--out",
    type=Path,
    default=Path("data/round3/val"),
)

args = parser.parse_args()

hr_dir = args.out / "hr"
lr_dir = args.out / "lr"

hr_dir.mkdir(parents=True, exist_ok=True)
lr_dir.mkdir(parents=True, exist_ok=True)

paths = sorted(
    args.targets.glob("*_target.png")
)

if not paths:
    raise SystemExit(
        f"No *_target.png files in {args.targets}"
    )

for path in paths:

    image_id = path.name[:-len("_target.png")]

    hr = Image.open(path).convert("L")

    if hr.size != (PATCH_SIZE, PATCH_SIZE):
        raise SystemExit(
            f"{path}: expected {PATCH_SIZE}x{PATCH_SIZE}, got {hr.size}"
        )

    hr.save(hr_dir / f"{image_id}_hr.png")

    hr.resize(
        (LR_SIZE, LR_SIZE),
        Image.Resampling.BICUBIC
    ).save(lr_dir / f"{image_id}_lr.png")

print(
    f"Rebuilt {len(paths)} validation pairs in {args.out}"
)
