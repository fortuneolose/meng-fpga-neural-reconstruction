# Improvement plan

**Created 2026-10-05** from a full repository review, at `kv260-integration`
`7f8f97b`. This is the working plan for bringing the repository, the evidence
and the final report into agreement, and then improving the accelerator and
taking it onto the board.

The work is split between two Claude sessions:

| Session | Where | Owns | Branch |
|---|---|---|---|
| **Cloud** | Linux container, no AMD tools | §3: tests, CI, hash tooling, golden-vector extension, documentation reconciliation | `kv260-integration` |
| **Local** | Windows PC with Vivado / Vitis (and possibly the KV260) | §4: toolchain, evidence import, HLS changes, rebuild, host software, bring-up | its own branches (see §4) |

**Local session: `git pull` before starting, and again before merging
anything into `kv260-integration`.** The cloud session's work (§3) is complete
and pushed, so the documentation is free to edit.

`CLAUDE.md` says not to re-run synthesis, implementation, HLS or simulation
without being asked. The user has asked for the full set of changes, but
confirm at the start of the local session that long tool runs are cleared.

---

## 1. Verified facts from the review

Each of these was checked by running something, not by reading the docs.

| Fact | How it was verified |
|---|---|
| The HLS C model is bit-exact on golden frames 0805 / 0809 / 0824 | Built natively with g++ 13 and Xilinx's open-source `ap_int` headers (`github.com/Xilinx/HLS_arbitrary_Precision_Types`); testbench printed `HLS C MODEL VERIFICATION: PASS` |
| The golden vectors are internally consistent at every stage | Independent numpy implementation written from `hardware_metadata.json` and the header only: all 6 stages × 3 frames bit-exact |
| **The Round 3 checkpoint is in the repository** | `results/round3.zip` → `round3/best_model.pt`, SHA256 `af6c79ce…5ac5`, equal to `results/round4_int8/reference/round3_best_model_sha256.txt`. `CLAUDE.md` and `PROJECT_STATE.md` §5.3 still say it is absent |
| The committed int8 parameters re-derive exactly from that checkpoint | Re-running the exporter's quantisation reproduces every int8 weight, int32 bias, multiplier, scale and `RESIDUAL_TO_OUTPUT_MULT = 9446373` bit-exactly. Calibration maxima need the absent training set |
| **All 20 validation frames can be regenerated** | `results/round3/comparison/*_target.png` are the lossless HR crops; Pillow 12.3.0 bicubic downsampling reproduces `input_lr_u8` bit-identically for the 3 golden frames, and the committed FP32 / integer / bicubic MSEs to within 6e-7 relative for all 20 |
| Quality: full-integer model vs bicubic | +0.80 dB mean per-image PSNR, 20 / 20 wins, bootstrap 95 % CI [0.71, 0.89] dB. Quantisation costs 0.064 dB vs FP32 |
| Recorded SHA256 files do not match a Linux (LF) checkout | `reconstruction_params_sha256.txt` and `standalone_rtl_sim/manifest.json` (0 / 101) were hashed on CRLF Windows copies; they match after LF→CRLF conversion |
| System critical path is inside the accelerator | `vivado/reports/system_routed/…timing_summary_routed.rpt`: Conv2 weight ROM `p_ZL13CONV2_WEIGHTS_1_U/q0_reg` → unregistered `mul_8s_8ns_16_1_1_U104` → `mac_muladd_8s_8ns_16s_17_4_1_U106`. Not SmartConnect |
| Bilinear stage makes 4 single-byte external reads per output pixel | 262,144 read beats per frame in the standalone RTL logs = 65,536 pixels × 4 (`hls/src/reconstruction_accel.cpp:291-308`); HLS adapter allows 2 outstanding reads per channel |
| Measured RTL latency is above the headline | csynth 5,637,182 cycles (28.186 ms); standalone RTL `STALL=0` 6,164,920 cycles (30.825 ms, +9.4 %) |
| No host software exists | No bare-metal app, Linux app, device-tree overlay, `shell.json` or `.bit.bin` anywhere in the repository |
| The accelerator `interrupt` pin is unconnected | Block design, although PS IRQ0 is enabled |

### Not verified: claims that exist only outside the repository

The final report and `hls/reports/cosim_xsim_failure/README.md` (commit
`449606f`) describe results whose evidence is held at
`C:\kv260_cosim_recovery\evidence\`, not in the repository:

- C/RTL co-simulation **passing** under Vitis / XSim 2026.1.1 (current source
  and historical `8c847cd`);
- a Vivado 2026.1.1 rebuild where the **default strategy failed timing**
  (WNS −0.104 ns) and `Performance_Explore` reached +0.132 ns;
- a new bitstream and XSA from that rebuild.

Two caveats a reviewer will raise:

1. Cosim re-synthesises the RTL, so a 2026.1.1 cosim pass verifies
   2026.1.1-generated RTL, **not** the packaged 2025.1.1 IP in `vivado/ip_repo/`.
   The standalone RTL simulation is what verifies the packaged IP.
2. The historical failing cosim reports `0 / 1` transactions
   (`hls_run_cosim_axi_vip_exception.txt:63`), but the committed C testbench —
   unchanged since `599da3e` — calls the kernel 3 times. Either a different
   testbench was used in that run, or the count means something else. Until
   that is explained, the "exact historical control" may not have replicated
   the failing run.

---

## 2. Ground rules

These are the standards the review applied; the fixes are held to them too.

1. **Every claim has in-repository evidence** beside the flow that produced it,
   with a `PROVENANCE.md` recording source commit, tool version, host and
   timestamps. A claim without in-repository evidence is labelled
   *reported, not verified in repository*.
2. **Corrections are appended, not rewritten.** Add an errata or "superseded"
   note beside the old text, as the repository already does. Never edit the
   byte-exact evidence files listed in `.gitattributes`.
3. **One toolchain.** Decide before rebuilding anything (see §5). Record the
   version in every new `PROVENANCE.md`.
4. **Copy before you rebuild.** Copy anything worth keeping out of `hls/work/`,
   `*.runs/`, `*.gen/` before each rebuild, preserving timestamps. Archive the
   current XSA and bitstream (SHA256 in `PROJECT_STATE.md` §7) first.
5. **Re-run system timing after every PL change** and report it against the
   current baseline: WNS +0.058 ns, WHS +0.010 ns.
6. **Keep source and artefacts in step.** `hls/src/` must not change on
   `kv260-integration` unless the regenerated IP, bitstream and evidence land
   with it. Do HLS work on its own branch.
7. **Label estimates.** Performance figures in this plan marked *(estimate)*
   are back-of-envelope arithmetic, not synthesis results.
8. **Record SHA256s in a platform-independent way** (see §3, hash tooling).

---

## 3. Cloud session (in progress on `kv260-integration`)

**Complete (2026-10-05).**

| Item | Result |
|---|---|
| Native C-model runner (`hls/tb/run_csim_native.sh`) | g++ against pinned open-source `ap_int` headers; `--all` runs every frame |
| Independent integer reference (`tests/check_integer_reference.py`) | Matches every stage of the 3 primary frames and the output of all 20; checks `reconstruction_params.h` against the `.npy` parameters |
| Golden vectors for all 20 validation frames | 17 new frames in `hls/tb/data/`; the C model is bit-exact on all 20; `tests/check_golden_regeneration.py` regenerates all 76 committed golden files byte-for-byte |
| Cross-platform hash verification (`tools/verify_recorded_hashes.py`) | 317 records, 0 mismatches; 216 match only the Windows (CRLF) form |
| `requirements*.txt`, root `README.md`, CI | `.github/workflows/verify.yml` runs all of the above |
| Documentation reconciled | `CLAUDE.md` rewritten; dated notes in `PROJECT_STATE.md` (§0) and the evidence READMEs / PROVENANCE files |

One finding from this work: requantisation rounding (half away from zero vs.
half up) is **not observable** with these parameters — every negative tie clips
— so no golden vector can distinguish the two, and none needs to. The test
proves this from the parameters and will flag it if new parameters change it.
The bilinear-to-branch half-to-even rounding *is* observable and is exercised
86,674 times by the 20 frames.

---

## 4. Local session work items, in order

### L0 — Set-up

- Record tool versions: `vivado -version`, `vitis_hls -version` (or
  `vitis-run --version`), host RAM. Cosim peaked at about 8.4–8.9 GB.
- Ask the user the §5 decisions before running anything long.
- Locate the trees the build expects: the repo's `vivado/kv260_project/`, the
  `V:` / `M:` `subst` conventions in `vivado/SCRIPTS.md`, and the archived
  artefacts in `FPGA_Archives\meng-fpga-neural-reconstruction\`.

### L1 — Import the 2026.1.1 evidence

Copy `C:\kv260_cosim_recovery\evidence\` into the repository with
`PROVENANCE.md` files, for example:

- `hls/reports/cosim_2026_1_1/` — current-source and `8c847cd` cosim runs
  (consoles, `*_cosim.rpt`, csynth reports, the SHA256 manifest);
- `vivado/reports/system_routed_2026_1_1/` — the default-strategy failure and
  the `Performance_Explore` result (timing summary, route status,
  utilization), plus the bitstream / XSA SHA256s.

Save `.log` excerpts as `.txt` (`*.log` is ignored). If the evidence is not
available, tell the user; the documentation will keep those claims labelled
as unverified. Also try to explain the `0 / 1` transaction count above.

### L2 — Make the build reproducible

- Point `hls/run_csim_2026_1.cmd` / `run_csim_direct.cmd` at the chosen
  toolchain and a path relative to the script (they still `cd` into an old
  OneDrive location).
- Add one entry point that goes from a clean clone to bitstream and XSA:
  `replay_bd.tcl` → wrapper → synth → impl (named strategy) → bitstream →
  `write_hw_platform -fixed -include_bit` with
  `platform.design_intent.embedded true`. Derive every path from
  `[info script]`; no `V:` / `M:` drives. `replay_bd.tcl` already covers the
  block design.
- Mark the superseded duplicates in `vivado/SCRIPTS.md` (`export-xsa.tcl`,
  `generate_bd_targets.tcl`, `generate_bd_targets_short.tcl`) rather than
  deleting them.

### L3 — HLS changes, on branch `hls-perf`

One commit per change, each with its evidence directory. Verification gate
for every change, in order:

1. CSim bit-exact on **all 20** frames: `hls/tb/run_csim_native.sh --all`, or
   Vitis with `csim.argv=--all`;
2. csynth report (latency, II, resources);
3. C/RTL cosim, 3 frames;
4. HLS out-of-context implementation timing;
5. standalone RTL simulation `STALL=0` and `STALL=1`
   (`hls/reports/standalone_rtl_sim/prepare.py` regenerates the harness from
   new RTL; expected beat counts will change);
6. package the IP.

Changes, in priority order:

| # | Change | Why | Expected effect |
|---|---|---|---|
| a | Register the Conv2 weight-ROM → DSP multiply (e.g. `bind_op … latency`, or hold the 576 weights in registers) | It is the system critical path | More setup margin than 58 ps |
| b | Burst-read the 16 KB input into on-chip memory once; run bilinear from it | 262,144 single-byte DDR reads per frame; latency on real DDR is unknown | Read beats 262,144 → 4,096; bilinear no longer DDR-latency-bound |
| c | Unroll `CONV2_OC` so all 8 output channels share one window read | Conv2 is 84 % of latency at 8 MACs / cycle | Conv2 23.6 → ~2.95 ms; frame ~7.5 ms *(estimate)* |
| d | Remove the contradictory `PIPELINE` + `UNROLL` pragmas inside the already-pipelined Conv1 loop (`reconstruction_accel.cpp:435-437`) | Cleanliness | None functional |
| e | *Stretch:* line-buffered dataflow, one pixel per clock per layer | Removes the 1 MB of URAM frame buffers | ~0.33 ms / frame *(estimate)* |

Merge `hls-perf` into `kv260-integration` only together with L4's rebuilt
artefacts and evidence.

### L4 — Re-integrate and rebuild

Update `vivado/ip_repo/`, upgrade the IP in the block design, re-export
`vivado/neural_reconstruction_bd.tcl` with `write_bd_tcl`, check
`vivado/assert_reset_topology.tcl`, then synth → impl → bitstream → XSA.
Report timing and utilization against the baseline, archive artefacts by
SHA256, and write `PROVENANCE.md`. Optionally connect the accelerator
`interrupt` pin to PS IRQ0 (a block-design change, so it needs the same
re-timing).

### L5 — Host software and board bring-up

Ask the user whether the board runs bare-metal (Vitis platform from the XSA)
or Linux (Ubuntu on KV260: `xmutil`, `.dtbo`, `shell.json`, `.bit.bin`).
Put the code in a new top-level `host/` directory. Constraints the host must
respect:

- Control registers at `0xA000_0000`: `0x00` control (`ap_start` bit 0,
  `ap_done` bit 1 clear-on-read, `ap_idle` bit 2), `0x10`/`0x14` input
  address, `0x1c`/`0x20` output address — see
  `vivado/ip_repo/…/xreconstruction_accel_hw.h`.
- Buffers must be **physically contiguous and below 2 GB**: `gmem0`/`gmem1`
  map only `HP{0,1}_DDR_LOW` (`0x0`–`0x7FFF_FFFF`). A bad address returns
  DECERR, which HLS ignores — the output is silently wrong and `ap_done`
  still asserts.
- HP ports are **not cache-coherent** (AxCACHE `0011`): flush the input
  buffer before `ap_start` and invalidate the output buffer after `ap_done`,
  or use non-cached CMA memory.
- Don't touch `0xA000_0000` until the bitstream is loaded and `pl_clk0`
  (200 MHz) and `pl_resetn0` are up, or the APU can hang.

Run all 20 golden frames from `hls/tb/data/` and require exact equality.
Measure accelerator-only latency, end-to-end latency and repeatability.
Save results as evidence under a new `hardware_runs/<date>/` with
`PROVENANCE.md`.

### L6 — Harden the standalone RTL testbench (needs XSim)

Assert the beat and burst counts instead of printing them; detect X on
`ARLEN`/`AWLEN` and the VALID signals; allow more than one outstanding read;
check the write-response drain properly; add random stall patterns. Move the
runnable harness to `hls/tb/rtl/`, leaving the evidence copy in
`hls/reports/`. Re-run `STALL=0` and `STALL=1`.

### L7 — The final report (author's own)

The report is assessed work, so edits are the author's. A session can supply
the list of statements that disagree with in-repository evidence, and the
factual record of AI assistance in the git history (7 of 22 commits at
`7f8f97b` carry a Claude co-author trailer). Appendix B (Generative AI Usage
Declaration) is still "to be completed", and the latency, throughput and
power sections are empty.

---

## 5. Decisions needed from the user

1. **Toolchain:** stay on 2025.1.1 (matches the committed IP, bitstream and
   timing evidence) or move everything to 2026.1.1 (what the report's cosim
   pass and rebuild used). Recommendation: 2026.1.1, regenerating IP,
   bitstream and evidence under it.
2. **Board:** connected? JTAG / UART, or Ubuntu on the board?
3. **Checkpoint:** extract `best_model.pt` from `results/round3.zip` into a
   tracked file (16 KB, needs a `.gitignore` exception), or leave it zipped.
4. **Licence** for the repository.
5. **Merging `hls-perf`:** only after L4 is complete and timing closes.
