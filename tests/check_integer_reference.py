"""
Independent check of the integer golden vectors.

This is a second implementation of the accelerator's fixed-point contract,
written from hardware_reference/parameters/hardware_metadata.json and the
parameter arrays. It deliberately does not import or copy
src/generate_golden_vectors.py, so agreement between the two is evidence
rather than tautology.

It checks, for every frame in hls/tb/data/frames.txt:
  * the final output against output_ticks_u16.bin, and
  * every intermediate stage against hardware_reference/golden_vectors/<id>/
    where those files exist (the three primary frames).

It also checks that hls/src/reconstruction_params.h carries the same numbers
as the .npy parameters and the metadata.

The fixed-point contract (metadata does not state the rounding modes; they are
recorded here and in hls/src/reconstruction_accel.cpp):

  bilinear    2x, half-pixel centres (PyTorch align_corners=False), edge
              replication; per-axis weights (1,3)/4, so 2-D weights sum to 16.
              Result in "ticks" of 1/4080 = 1/(255*16).
  branch      ticks / 16, round half to EVEN, clip [0, 255].
  conv1-3     3x3, zero padding, OIHW int8 weights, int32 bias, exact integer
              accumulation.
  requant     acc * mult / 2^20, round half AWAY FROM ZERO;
              conv1, conv2 clip [0, 255]; conv3 clip [-127, 127].
  output      ticks + round_half_away(residual * 9446373 / 2^20),
              clip [0, 4080].

Exit status 0 only if everything matches exactly.
"""

from pathlib import Path
import json
import re
import sys

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
PARAMS = ROOT / "hardware_reference" / "parameters"
GOLDEN = ROOT / "hardware_reference" / "golden_vectors"
TB_DATA = ROOT / "hls" / "tb" / "data"
HEADER = ROOT / "hls" / "src" / "reconstruction_params.h"

STAGES = [
    ("bilinear_ticks_u16", np.uint16),
    ("branch_input_u8", np.uint8),
    ("conv1_output_u8", np.uint8),
    ("conv2_output_u8", np.uint8),
    ("residual_int8", np.int8),
    ("output_ticks_u16", np.uint16),
]


# ---------------------------------------------------------------------------
# Rounding primitives
# ---------------------------------------------------------------------------

def shift_round_half_away(x, shift):
    """Round x / 2^shift to nearest, ties away from zero."""
    half = 1 << (shift - 1)
    magnitude = (np.abs(x) + half) >> shift
    return np.where(x < 0, -magnitude, magnitude)


def divide_round_half_even(x, d):
    """Round non-negative x / d to nearest, ties to even."""
    q, r = np.divmod(x, d)
    up = (2 * r > d) | ((2 * r == d) & (q % 2 == 1))
    return q + up


def self_test_rounding():
    s = 20
    one = 1 << s
    cases = [
        (shift_round_half_away(np.int64(3 * one // 2), s), 2),     # +1.5 -> 2
        (shift_round_half_away(np.int64(-3 * one // 2), s), -2),   # -1.5 -> -2
        (shift_round_half_away(np.int64(-one // 2), s), -1),       # -0.5 -> -1
        (shift_round_half_away(np.int64(one // 2 - 1), s), 0),     # <0.5 -> 0
        (divide_round_half_even(np.int64(8), 16), 0),              # 0.5 -> 0
        (divide_round_half_even(np.int64(24), 16), 2),             # 1.5 -> 2
        (divide_round_half_even(np.int64(40), 16), 2),             # 2.5 -> 2
        (divide_round_half_even(np.int64(9), 16), 1),              # >0.5 -> 1
    ]
    bad = [(int(got), want) for got, want in cases if int(got) != want]
    if bad:
        raise AssertionError(f"rounding self-test failed: {bad}")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def bilinear_ticks(lr):
    """2x bilinear upsample; result is the weighted sum over 16."""
    x = np.pad(lr.astype(np.int64), 1, mode="edge")
    h, w = lr.shape

    rows = np.empty((2 * h, w + 2), np.int64)
    rows[0::2] = x[0:h] + 3 * x[1:h + 1]          # output row 2i:   (i-1, i)
    rows[1::2] = 3 * x[1:h + 1] + x[2:h + 2]      # output row 2i+1: (i, i+1)

    out = np.empty((2 * h, 2 * w), np.int64)
    out[:, 0::2] = rows[:, 0:w] + 3 * rows[:, 1:w + 1]
    out[:, 1::2] = 3 * rows[:, 1:w + 1] + rows[:, 2:w + 2]
    return out


def conv3x3(x, weights, bias):
    """x: (C, H, W); weights: (O, C, 3, 3). Zero padding, exact integers."""
    _, h, w = x.shape
    padded = np.pad(x, ((0, 0), (1, 1), (1, 1)))
    acc = np.zeros((weights.shape[0], h, w), np.int64)
    for ky in range(3):
        for kx in range(3):
            window = padded[:, ky:ky + h, kx:kx + w]
            acc += np.einsum("oc,chw->ohw", weights[:, :, ky, kx], window)
    return acc + bias[:, None, None]


class Model:

    def __init__(self):
        meta = json.loads((PARAMS / "hardware_metadata.json").read_text())

        self.shift = int(meta["requant_shift"])
        self.bilinear_den = int(meta["bilinear_denominator"])
        self.output_den = int(meta["output_denominator"])
        self.residual_mult = int(meta["residual_to_output_multiplier"])
        self.residual_shift = int(meta["residual_to_output_shift"])

        load = lambda name: np.load(PARAMS / name).astype(np.int64)
        self.weights = [load(f"conv{i}_weights_int8.npy") for i in (1, 2, 3)]
        self.bias = [load(f"conv{i}_bias_int32.npy") for i in (1, 2, 3)]
        self.mult = [load(f"conv{i}_requant_mult_int32.npy") for i in (1, 2, 3)]

        for i, layer in enumerate(("conv1", "conv2", "conv3")):
            expected = tuple(meta["layers"][layer]["shape"])
            if self.weights[i].shape != expected:
                raise AssertionError(
                    f"{layer} weights {self.weights[i].shape} != {expected}"
                )

    def requant(self, acc, layer):
        return shift_round_half_away(acc * self.mult[layer][:, None, None],
                                     self.shift)

    def run(self, lr):
        ties = {}

        ticks = bilinear_ticks(lr)
        ties["branch"] = int(np.sum(ticks % self.bilinear_den
                                    == self.bilinear_den // 2))
        branch = np.clip(divide_round_half_even(ticks, self.bilinear_den),
                         0, 255)

        a1 = conv3x3(branch[None], self.weights[0], self.bias[0])
        c1 = np.clip(self.requant(a1, 0), 0, 255)

        a2 = conv3x3(c1, self.weights[1], self.bias[1])
        c2 = np.clip(self.requant(a2, 1), 0, 255)

        a3 = conv3x3(c2, self.weights[2], self.bias[2])
        residual = np.clip(self.requant(a3, 2), -127, 127)

        residual_ticks = shift_round_half_away(
            residual[0] * self.residual_mult, self.residual_shift
        )
        output = np.clip(ticks + residual_ticks, 0, self.output_den)

        stages = {
            "bilinear_ticks_u16": ticks,
            "branch_input_u8": branch,
            "conv1_output_u8": c1,
            "conv2_output_u8": c2,
            "residual_int8": residual,
            "output_ticks_u16": output,
        }
        return stages, ties


# ---------------------------------------------------------------------------
# Rounding-mode observability
# ---------------------------------------------------------------------------

def requant_tie_observability(model):
    """Can "half away from zero" and "half up" give different outputs?

    They differ only on exact negative ties, value = -(n + 0.5). Returns a
    list of stages where such a tie can change the clipped result, given
    these parameters. An empty list means the golden vectors cannot
    distinguish the two conventions - and no hardware can get it wrong.
    """
    s = model.shift
    half = 1 << (s - 1)
    observable = []

    # conv1, conv2 clip at 0: -(n+0.5) rounds to -n or -(n+1), both <= 0.

    # conv3 clips at -127. A negative tie needs acc * mult = -(2k+1) * 2^19
    # for an integer acc; find the smallest such magnitude.
    for mult in model.mult[2]:
        mult = int(mult)
        odd = 1
        while (odd * half) % mult:
            odd += 2
            if odd > 2 * mult + 1:          # no integer solution at all
                odd = None
                break
        if odd is not None:
            n = (odd * half) >> s           # tie value is -(n + 0.5)
            if n < 127:
                observable.append(f"conv3 (tie at -{n}.5)")

    # residual -> output: residual in [-127, 127], multiplier fixed.
    for r in range(-127, 0):
        if (-r * model.residual_mult) % (1 << model.residual_shift) == \
                1 << (model.residual_shift - 1):
            observable.append(f"residual-to-output (residual {r})")
            break

    return observable


# ---------------------------------------------------------------------------
# Header consistency
# ---------------------------------------------------------------------------

def check_header(model):
    text = HEADER.read_text()

    defines = dict(re.findall(r"#define\s+(\w+)\s+(-?\d+)", text))
    expected_defines = {
        "REQUANT_SHIFT": model.shift,
        "FINAL_SHIFT": model.residual_shift,
        "OUTPUT_DEN": model.output_den,
        "BILINEAR_DEN": model.bilinear_den,
        "RESIDUAL_TO_OUTPUT_MULT": model.residual_mult,
    }

    arrays = {
        name: np.array([int(v) for v in re.findall(r"-?\d+", body)])
        for name, body in re.findall(
            r"static const \w+ (\w+)\[\d+\]\s*=\s*\{([^}]*)\}", text
        )
    }
    expected_arrays = {}
    for i in range(3):
        expected_arrays[f"CONV{i + 1}_WEIGHTS"] = model.weights[i].ravel()
        expected_arrays[f"CONV{i + 1}_BIAS"] = model.bias[i].ravel()
        expected_arrays[f"CONV{i + 1}_MULT"] = model.mult[i].ravel()

    problems = []
    for name, value in expected_defines.items():
        if name not in defines or int(defines[name]) != value:
            problems.append(f"#define {name} = {defines.get(name)} != {value}")
    for name, value in expected_arrays.items():
        if name not in arrays or not np.array_equal(arrays[name], value):
            problems.append(f"{name} differs from the .npy parameters")
    return problems


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    self_test_rounding()
    model = Model()
    failures = 0

    problems = check_header(model)
    for problem in problems:
        print(f"HEADER MISMATCH: {problem}")
    failures += len(problems)
    if not problems:
        print("reconstruction_params.h matches the .npy parameters "
              "and metadata")

    observable = requant_tie_observability(model)
    if observable:
        print("NOTE: requant rounding mode is observable at: "
              + ", ".join(observable)
              + " - add a vector that hits it")
    else:
        print("Requant ties: half-away-from-zero and half-up give identical "
              "outputs for these parameters (every negative tie clips)")

    frames = (TB_DATA / "frames.txt").read_text().split()
    total_ties = {"branch": 0}

    for frame in frames:
        lr = np.fromfile(TB_DATA / frame / "input_lr_u8.bin", np.uint8)
        stages, ties = model.run(lr.reshape(128, 128))
        for key in total_ties:
            total_ties[key] += ties[key]

        expected = {
            "output_ticks_u16": np.fromfile(
                TB_DATA / frame / "output_ticks_u16.bin", "<u2"
            )
        }
        golden_dir = GOLDEN / frame
        if golden_dir.is_dir():
            for name, _ in STAGES:
                expected[name] = np.load(golden_dir / f"{name}.npy")

        checked = 0
        frame_failed = False
        for name, _ in STAGES:
            if name not in expected:
                continue
            want = expected[name].astype(np.int64).ravel()
            got = stages[name].ravel()
            mismatches = int(np.sum(got != want))
            if mismatches:
                frame_failed = True
                print(f"{frame} {name}: FAIL, {mismatches} / {want.size} "
                      f"mismatches, max |diff| "
                      f"{int(np.max(np.abs(got - want)))}")
            checked += 1

        if frame_failed:
            failures += 1
        else:
            print(f"{frame}: {checked} stage(s) bit-exact")

    print()
    print(f"Branch ties exercised (half-to-even observable): "
          f"{total_ties['branch']}")

    if failures:
        print(f"INDEPENDENT INTEGER REFERENCE: FAIL ({failures})")
        return 1

    print(f"INDEPENDENT INTEGER REFERENCE: PASS ({len(frames)} frames)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
