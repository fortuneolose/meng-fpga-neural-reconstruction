"""
Check that the committed golden vectors regenerate exactly from repository
contents.

Steps, all in a temporary directory (nothing in the repository is written):

1. Rebuild the 20 Round 3 validation pairs from
   results/round3/comparison/*_target.png (src/rebuild_round3_val.py).
   Frames in hls/tb/data/frames.txt that are not validation frames are
   synthetic corner cases; their LR input is taken from the committed
   input_lr_u8.bin, with a blank HR image (HR only feeds the MSE printout).
2. Run src/generate_golden_vectors.py on every frame.
3. Require byte equality with:
     * every .npy in hardware_reference/golden_vectors/<id>/, and
     * every .bin in hls/tb/data/<id>/.
4. For the validation frames, require the output MSE to match
   results/round4_int8/full_integer/comparison_metrics.csv, which was
   produced by a separate evaluation script.

The LR images depend on the Pillow version; Pillow 12.3.0 is known to
reproduce the committed vectors.

Exit status 0 only if everything matches.
"""

from pathlib import Path
import csv
import subprocess
import sys
import tempfile

import numpy as np
import PIL
from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "hardware_reference" / "golden_vectors"
TB_DATA = ROOT / "hls" / "tb" / "data"
TARGETS = ROOT / "results" / "round3" / "comparison"
METRICS = (ROOT / "results" / "round4_int8" / "full_integer"
           / "comparison_metrics.csv")

BIN_DTYPES = {
    "input_lr_u8": np.uint8,
    "bilinear_ticks_u16": np.dtype("<u2"),
    "branch_input_u8": np.uint8,
    "conv1_output_u8": np.uint8,
    "conv2_output_u8": np.uint8,
    "residual_int8": np.int8,
    "output_ticks_u16": np.dtype("<u2"),
}

MSE_RELATIVE_TOLERANCE = 1e-5


def run(args):
    result = subprocess.run(
        [sys.executable] + args, cwd=ROOT, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise SystemExit(f"FAILED: {' '.join(args)}")


def main():
    print(f"Pillow {PIL.__version__}, numpy {np.__version__}")

    frames = (TB_DATA / "frames.txt").read_text().split()
    validation = {p.name[:-len("_target.png")]
                  for p in TARGETS.glob("*_target.png")}
    synthetic = [f for f in frames if f not in validation]

    failures = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        val = tmp / "val"
        out = tmp / "golden"

        run(["src/rebuild_round3_val.py", "--targets", str(TARGETS),
             "--out", str(val)])

        for frame in synthetic:
            lr = np.fromfile(TB_DATA / frame / "input_lr_u8.bin", np.uint8)
            Image.fromarray(lr.reshape(128, 128)).save(
                val / "lr" / f"{frame}_lr.png")
            Image.fromarray(np.zeros((256, 256), np.uint8)).save(
                val / "hr" / f"{frame}_hr.png")

        run(["src/generate_golden_vectors.py", "--val-dir", str(val),
             "--out", str(out), "--ids"] + frames)

        compared = 0

        for frame_dir in sorted(p for p in GOLDEN.iterdir() if p.is_dir()):
            for committed in sorted(frame_dir.glob("*.npy")):
                fresh = out / frame_dir.name / committed.name
                compared += 1
                if committed.read_bytes() != fresh.read_bytes():
                    failures.append(f"{committed.relative_to(ROOT)} differs")

        for frame in frames:
            for committed in sorted((TB_DATA / frame).glob("*.bin")):
                stem = committed.stem
                fresh = np.load(out / frame / f"{stem}.npy")
                fresh = np.asarray(fresh, dtype=BIN_DTYPES[stem]).tobytes()
                compared += 1
                if committed.read_bytes() != fresh:
                    failures.append(f"{committed.relative_to(ROOT)} differs")

        rows = {r["image"]: r for r in csv.DictReader(open(METRICS))}
        worst = 0.0
        for frame in sorted(validation):
            ticks = np.load(out / frame / "output_ticks_u16.npy")
            hr = np.asarray(Image.open(val / "hr" / f"{frame}_hr.png"),
                            dtype=np.float64)
            mse = float(np.mean(
                (ticks.astype(np.float64).reshape(hr.shape) / 4080.0
                 - hr / 255.0) ** 2))
            expected = float(rows[frame]["full_integer_mse"])
            relative = abs(mse - expected) / expected
            worst = max(worst, relative)
            if relative > MSE_RELATIVE_TOLERANCE:
                failures.append(f"{frame}: MSE {mse:.10f} vs committed "
                                f"{expected:.10f}")

    print(f"Compared {compared} committed golden files byte-for-byte "
          f"({len(frames)} frames, {len(synthetic)} synthetic)")
    print(f"Worst relative MSE difference vs {METRICS.name}: {worst:.2e} "
          f"over {len(validation)} validation frames")

    for failure in failures:
        print(f"MISMATCH: {failure}")

    if failures:
        print("GOLDEN VECTOR REGENERATION: FAIL")
        return 1

    print("GOLDEN VECTOR REGENERATION: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
