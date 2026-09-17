# meng-fpga-neural-reconstruction

Integer-only CNN image-reconstruction accelerator (128×128 → 256×256), targeting
a **Kria KV260** (`xck26-sfvc784-2LV-c`) at **200 MHz**, via Vitis HLS 2025.1.1
and Vivado 2025.1.1.

## Read this first

**[`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md)** — current verified state,
development timeline, what is proven vs. what is not, and the open issues.
Read it before changing anything; several things in this repo are not what their
filenames suggest.

## Four things to know before you touch the hardware flow

1. **`neural_reconstruction_bd.bd` is authoritative.** No Tcl script creates the
   block design — there is no `create_bd_design` or `write_bd_tcl` anywhere. The
   `.bd` is the only description of the KV260 design. See `vivado/SCRIPTS.md`.
2. **RTL co-simulation does not pass.** CSim is bit-exact; cosim has never
   completed, blocked by an XSim/AXI VIP kernel exception. The file
   `csim_c_model_pass.txt` is CSim output, not RTL evidence. See
   `hls/reports/cosim_xsim_failure/README.md`.
3. **System timing margin is 58 picoseconds** (WNS +0.058 ns at 200 MHz). Never
   assume timing survives a change. See `vivado/reports/system_routed/`.
4. **The original training checkpoint and Round 3 dataset are not present in the
   current repository or known project working tree.** The golden vectors
   therefore cannot currently be regenerated from repository contents, because
   their source dataset is absent. Treat the int8 parameters in
   `hardware_reference/parameters/` and the committed golden vectors as primary
   data until the originals are located.

## Layout

| Path | What |
|---|---|
| `hls/src/` · `hls/tb/` | Accelerator source and C testbench — **authoritative** |
| `hls/reports/` | HLS synthesis/implementation evidence, one directory per milestone |
| `hardware_reference/` | Quantised parameters and golden vectors — **authoritative; not currently reproducible** |
| `src/` | Python training, quantisation and golden-vector generation |
| `vivado/*.tcl` | KV260 build scripts — categorised in `vivado/SCRIPTS.md` |
| `vivado/ip_repo/` | Packaged HLS IP — generated, but required by the `.bd` |
| `vivado/reports/` | Routed system timing and utilization evidence |
| `results/` | Training and evaluation results |

## Conventions

- Evidence lives beside the flow that produced it (`hls/reports/`,
  `vivado/reports/`), one directory per milestone, each with a `PROVENANCE.md`
  recording the source commit, tool version and timestamps.
- Large generated trees (`hls/work/`, `*.runs/`, `*.gen/`, `*.cache/`, `*.xpr`,
  `vitis_workspace/`) are ignored. Copy anything worth keeping out of them
  **before** cleaning — original timestamps preserved.
- `*.log` is ignored, so evidence excerpts are saved as `.txt`.
- Don't re-run synthesis, implementation, HLS or simulation without being asked;
  runs are long and overwrite the ignored trees the evidence was copied from.
