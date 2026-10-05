# FPGA neural image reconstruction (Kria KV260)

An integer-only convolutional network that reconstructs a 256×256 grayscale
image from a 128×128 input, implemented with Vitis HLS and integrated into a
Kria KV260 (`xck26-sfvc784-2LV-c`) block design at 200 MHz.

The network is a 2× bilinear upsample plus a learned residual: three 3×3
convolutions (1→8→8→1 channels, 737 parameters), quantised to int8 weights with
int32 biases and a fixed 20-bit requantisation shift. Every stage is defined in
exact integer arithmetic, so software, C model and RTL can be compared
bit-for-bit.

[![verify](https://github.com/fortuneolose/meng-fpga-neural-reconstruction/actions/workflows/verify.yml/badge.svg?branch=kv260-integration)](https://github.com/fortuneolose/meng-fpga-neural-reconstruction/actions/workflows/verify.yml)

## Status

| | Result | Evidence |
|---|---|---|
| Reconstruction quality | Integer model beats bicubic on 20 / 20 validation frames, +0.80 dB mean PSNR; quantisation costs 0.07 dB vs FP32 | `results/round4_int8/full_integer/` |
| C model vs golden vectors | Bit-exact, all 20 frames | CI: `hls/tb/run_csim_native.sh --all` |
| Golden vectors | Regenerate byte-for-byte from repository contents; independently re-implemented and matched at every stage | CI: `tests/` |
| HLS synthesis | 5,637,182 cycles = 28.186 ms / frame (estimate); out-of-context timing 4.793 ns | `hls/reports/conv1_requant_dsp_impl/` |
| Packaged RTL (2025.1.1 IP) | Standalone XSim, 3 frames, 0 mismatches, with and without AXI backpressure; 6,164,920 cycles = 30.8 ms / frame | `hls/reports/standalone_rtl_sim/`, `standalone_rtl_stress/` |
| Vitis C/RTL cosim | 2025.1.1: failed with a simulator kernel exception before any comparison. 2026.1.1: pass **reported, evidence not yet in repository** | `hls/reports/cosim_xsim_failure/` |
| KV260 system | Routed, setup WNS +0.058 ns at 200 MHz (2025.1.1). A 2026.1.1 rebuild at +0.132 ns is **reported, evidence not yet in repository** | `vivado/reports/system_routed/` |
| On hardware | **Not yet run.** No host software exists yet | — |

[`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md) has the full verified state
and history; [`docs/IMPROVEMENT_PLAN.md`](docs/IMPROVEMENT_PLAN.md) the
current work plan.

## Verify without AMD tools

Needs Python 3, g++ and git:

```
pip install -r requirements-verify.txt
python tools/verify_recorded_hashes.py      # recorded SHA256s, any platform
python tests/check_golden_regeneration.py   # golden vectors rebuild exactly
python tests/check_integer_reference.py     # independent integer model
hls/tb/run_csim_native.sh --all             # HLS C model, all 20 frames
```

These are what CI runs. They check the C model and the golden data, not the
synthesised RTL, the bitstream or the board.

## Layout

| Path | What |
|---|---|
| `hls/src/`, `hls/tb/` | Accelerator source and C testbench |
| `hls/tb/data/` | Golden vectors as raw binaries, with provenance |
| `hls/reports/` | HLS and RTL-simulation evidence, one directory per milestone |
| `hardware_reference/` | Quantised parameters and golden vectors (primary data) |
| `src/` | Training, quantisation, evaluation and golden-vector generation |
| `tests/`, `tools/` | Verification scripts run by CI |
| `vivado/` | Block design, Tcl scripts (see `vivado/SCRIPTS.md`), packaged IP, routed-system evidence |
| `results/` | Training and evaluation results; `round3.zip` holds the Round 3 checkpoint |
| `docs/` | Project state, plan and reports |

## Rebuilding

- **Software:** `requirements.txt` (PyTorch 2.14.0 with CUDA 13.0 was used
  originally). The Round 3 checkpoint is `round3/best_model.pt` inside
  `results/round3.zip`. The training images are not in the repository; the 20
  validation pairs are rebuilt by `src/rebuild_round3_val.py`.
- **HLS:** `hls/hls_config.cfg` (Vitis HLS). Note it carries
  `vivado.flow=impl`, so synthesis also runs implementation.
- **Block design:** `vivado/replay_bd.tcl` rebuilds it from
  `vivado/neural_reconstruction_bd.tcl`. Synthesis to bitstream and XSA follow
  the sequence in `vivado/SCRIPTS.md`; a single portable entry point is
  planned.

## Licence

Not yet chosen.
