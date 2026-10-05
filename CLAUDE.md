# meng-fpga-neural-reconstruction

Integer-only CNN image-reconstruction accelerator (128×128 → 256×256), targeting
a **Kria KV260** (`xck26-sfvc784-2LV-c`) at **200 MHz**. The committed IP,
bitstream evidence and timing reports were built with Vitis HLS / Vivado
2025.1.1; later 2026.1.1 runs are reported but their evidence is not yet in the
repository.

## Read this first

**[`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md)** — current verified state,
development timeline, what is proven vs. what is not, and the open issues. Start
at its §0 (2026-10-05 corrections). Several things in this repo are not what
their filenames suggest.

**[`docs/IMPROVEMENT_PLAN.md`](docs/IMPROVEMENT_PLAN.md)** — the active work
plan: verified review findings, the split between the cloud session (no AMD
tools) and the local session (Vivado / Vitis / board), and the ordered work
items with their verification gates.

## Five things to know before you touch the hardware flow

1. **`neural_reconstruction_bd.bd` is authoritative.** The step-by-step Tcl
   scripts never create it, but `vivado/neural_reconstruction_bd.tcl` (a
   `write_bd_tcl` export) does, and `vivado/replay_bd.tcl` replays it (verified
   end to end 2026-09-18); `vivado/assert_reset_topology.tcl` checks the result. Synthesis
   to bitstream still follows `vivado/SCRIPTS.md` — there is no single portable
   entry point yet.
2. **Three RTL verification results — don't conflate them.**
   - **Standalone XSim RTL simulation passes** for the **packaged 2025.1.1 IP**
     (the RTL in the bitstream): `STALL=0` and `STALL=1`, 3 golden frames,
     196,608/196,608 pixels, 0 mismatches. See `hls/reports/standalone_rtl_sim/`
     and `hls/reports/standalone_rtl_stress/`. Behavioural RTL only — not
     post-route, bitstream or hardware validation.
   - **Vitis HLS C/RTL cosim failed under 2025.1.1** with an XSim/AXI VIP kernel
     exception before any comparison — a tool failure, not an arithmetic
     mismatch. Evidence: `hls/reports/cosim_xsim_failure/`.
   - **A cosim pass under 2026.1.1 is reported but not in the repository.**
     Cosim re-synthesises the RTL, so even once its evidence is committed it
     verifies 2026.1.1 RTL, not the packaged IP.

   `csim_c_model_pass.txt` is CSim output, not RTL evidence.
3. **System timing margin is 58 picoseconds** (WNS +0.058 ns at 200 MHz). Never
   assume timing survives a change. The critical path is inside the accelerator
   (Conv2 weight ROM → unregistered DSP multiply), not in the interconnect. A
   2026.1.1 rebuild reportedly failed timing with the default strategy. See
   `vivado/reports/system_routed/`.
4. **Golden vectors are primary data — and now reproducible.** The Round 3
   checkpoint is `round3/best_model.pt` inside `results/round3.zip`
   (hash-verified), and the 20 validation pairs rebuild exactly from
   `results/round3/comparison/*_target.png`. `tests/check_golden_regeneration.py`
   proves the committed vectors regenerate byte-for-byte (Pillow 12.3.0). The
   training images are still absent. Never overwrite
   `hardware_reference/` or `hls/tb/data/`: regenerate into a scratch directory
   with `--out` and compare.
5. **Recorded SHA256s were mostly taken on Windows (CRLF).** On a Linux checkout
   they won't match byte-for-byte; use `tools/verify_recorded_hashes.py`, which
   checks every record as-is and in CRLF/LF form.

## Checks that need no AMD tools

Run before pushing; CI (`.github/workflows/verify.yml`) runs the same:

```
pip install -r requirements-verify.txt
python tools/verify_recorded_hashes.py
python tests/check_golden_regeneration.py
python tests/check_integer_reference.py
hls/tb/run_csim_native.sh --all
```

They cover the C model and the golden data only.

## Layout

| Path | What |
|---|---|
| `hls/src/` · `hls/tb/` | Accelerator source and C testbench — **authoritative** |
| `hls/tb/data/` | Golden vectors as raw binaries; `frames.txt`, `SHA256SUMS`, provenance in `README.md` |
| `hls/reports/` | HLS synthesis/implementation and RTL-simulation evidence, one directory per milestone |
| `hardware_reference/` | Quantised parameters and golden vectors — **authoritative primary data; regenerates exactly** |
| `src/` | Python training, quantisation and golden-vector generation |
| `tests/` · `tools/` | Verification scripts run by CI |
| `vivado/*.tcl` | KV260 build scripts — categorised in `vivado/SCRIPTS.md` |
| `vivado/ip_repo/` | Packaged HLS IP — generated, but required by the `.bd` |
| `vivado/reports/` | Routed system timing and utilization evidence |
| `results/` | Training and evaluation results; `round3.zip` holds the checkpoint |

## Conventions

- Evidence lives beside the flow that produced it (`hls/reports/`,
  `vivado/reports/`), one directory per milestone, each with a `PROVENANCE.md`
  recording the source commit, tool version and timestamps. A claim without
  in-repository evidence is labelled *reported, not verified in repository*.
- Corrections are added as dated notes beside the old text, not by rewriting
  it. Never edit the byte-exact evidence files listed in `.gitattributes`.
- Keep `hls/src/` in step with the packaged IP and bitstream: HLS changes go on
  their own branch until the rebuilt artefacts and evidence land with them.
- Large generated trees (`hls/work/`, `*.runs/`, `*.gen/`, `*.cache/`, `*.xpr`,
  `vitis_workspace/`) are ignored. Copy anything worth keeping out of them
  **before** cleaning — original timestamps preserved.
- `*.log` is ignored, so evidence excerpts are saved as `.txt`.
- Don't re-run synthesis, implementation, HLS or simulation without being asked;
  runs are long and overwrite the ignored trees the evidence was copied from.
  (The native g++ C-model check above is seconds long and writes only to the
  ignored `hls/tb/.native/`.)
