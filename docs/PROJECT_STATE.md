# Project state

**Last verified engineering/evidence commit: `5bdc65d`** on branch
`kv260-integration`. **Documentation refreshed: 2026-09-18.**

`5bdc65d` is the evidence baseline this document describes, not necessarily the
repository's current HEAD — documentation commits land after it.

Integer-only CNN image reconstruction (128×128 → 256×256), accelerated on a
Kria KV260 (`xck26-sfvc784-2LV-c`) at 200 MHz. Vitis HLS 2025.1.1 / Vivado 2025.1.1.

This document records both the development timeline and the corrections that came
out of a full repository audit. Where the commit history and the repository
disagree, **the repository wins** and the discrepancy is noted.

---

## 1. Status at a glance

| Item | State |
|---|---|
| Integer C model vs. golden vectors | ✅ **Bit-exact** (3 frames) |
| HLS C synthesis @ 200 MHz | ✅ 4.400 ns estimated |
| HLS out-of-context implementation | ✅ **4.793 ns post-route, timing met** |
| Per-image latency | ✅ **28.186 ms** @ 200 MHz |
| RTL co-simulation (Vitis HLS / AXI VIP) | ❌ **Fails** — XSim/AXI VIP kernel exception (tool defect, commit `8c847cd`) |
| **Standalone RTL simulation — `STALL=0` baseline** | ✅ **`RTL_SUITE_PASS`** — 3 frames, 196,608/196,608 pixels, **0 mismatches** |
| **Standalone RTL simulation — `STALL=1` backpressure** | ✅ **`RTL_SUITE_PASS`** — 3 frames, 196,608/196,608 pixels, **0 mismatches**, beat counts unchanged |
| KV260 system synthesis + implementation | ✅ Routed, 0 routing errors |
| KV260 system timing | ⚠️ **Met, WNS = +0.058 ns** (58 ps margin) |
| Bitstream | ✅ Written 2026-09-15 20:19 |
| On-hardware execution | ❌ No record of the bitstream ever being loaded or run |
| KV260 integration committed to git | ✅ **Committed** — `2cbd11e`, `23e1aa5`; see §2 |
| Training checkpoint | ⚠️ **Not present** in the repository or known working tree |
| Round 3 dataset | ⚠️ **Not present** in the repository or known working tree |

---

## 2. Branch and commit state

`kv260-integration` has an upstream at `origin/kv260-integration`, and the KV260
effort is committed. Through the evidence baseline `5bdc65d`:

| Commit | What |
|---|---|
| `2cbd11e` | Integrated Vivado design and packaged HLS IP |
| `23e1aa5` | HLS and routed KV260 evidence |
| `423d06c` | Verified project state and Claude context |
| `0912632` | Standalone RTL golden-vector simulation harness |
| `57b0d55` | Standalone RTL golden-vector pass (`STALL=0`) |
| `5bdc65d` | RTL backpressure stress pass (`STALL=1`) |

`origin/main` remains behind and has not been updated.

> **Historical — resolved 2026-09-17 22:23.** The audit recorded that
> `kv260-integration` had *no integration commit*: the branch pointed at
> `8d075ac`, the same commit as `hls-conv1-line-buffer`, with zero commits of
> its own, no upstream, and no presence on `origin`. Every artefact of the KV260
> effort — the block design, 60 Tcl scripts, the packaged IP, the system reports
> — existed **only in the working tree**, and the branch name described intent
> rather than content. That is no longer the case; the table above is the
> current state.

---

## 3. Development timeline

### Phase 1 — Software reference and quantisation (through 2026-09-13)

Float CNN → residual CNN → int8 quantisation, recorded in `results/`:
`comparison/` (baseline), `residual/`, `round3/` (20 validation frames),
`round4_int8/` (weight-only → w8a8-max → integer accumulator → integer requant →
full integer). Calibration and accumulator-bound analysis are in
`results/round4_int8/calibration/` and `.../integer_accumulator/`.

Outputs, all still present and verified:

- `hardware_reference/parameters/` — int8 weights, int32 biases, int32 requant
  multipliers, `reconstruction_params.h` (SHA256 verified against
  `reconstruction_params_sha256.txt`).
- `hardware_reference/golden_vectors/{0805,0809,0824}/` — `.npy` intermediates
  and outputs, exported to `.bin` in `hls/tb/data/`.

Fixed-point contract (`hardware_metadata.json`, matching the header):
`REQUANT_SHIFT 20`, `OUTPUT_DEN 4080`, `BILINEAR_DEN 16`,
`RESIDUAL_TO_OUTPUT_MULT 9446373`. Layer shapes 8×1×3×3, 8×8×3×3, 1×8×3×3.

### Phase 2 — HLS optimisation ladder (2026-09-13 → 09-15)

All at 5.00 ns target, 12 % uncertainty, estimated 4.400 ns throughout. Latency
per image:

| Commit | Milestone | Cycles | Latency | Evidence |
|---|---|---|---|---|
| `448edad` | Baseline Vitis HLS synthesis | 43,317,309 | 0.217 s | `results/hls_baseline_v1/` |
| `ba4be8d` | Naive URAM feature maps | 43,317,309 | 0.217 s | `hls/reports/uram_naive/` |
| `a6de56c` | Packed 64-bit URAM words | 45,091,885 | 0.225 s ⚠️ regression | `hls/reports/packed_feature_maps/` |
| `e7a2c07` | Conv2 input channels parallel | 12,061,741 | 60.309 ms | `hls/reports/conv2_parallel/` |
| `8c847cd` | Conv3 input channels parallel | 7,932,974 | **39.665 ms** | `hls/reports/conv3_parallel/` |
| `07b87ea` | Conv1 pipeline-off diagnostic | 10,945,070 | 54.725 ms ⚠️ deliberate regression | `hls/reports/conv1_pipeline_off_impl/` |
| `c70365c` | Conv3 weights block-partitioned | — | — | (no report) |
| `4b5450b` | Conv1 pixel loop II=1 | — | — | (no report) |
| `8d075ac` | **Conv1 requant multiply bound to DSP** | 5,637,182 | **28.186 ms** | `hls/reports/conv1_requant_dsp_impl/` |

**39.665 ms → 28.186 ms** is the headline improvement from the final three
commits. The `07b87ea` diagnostic deliberately disabled the Conv1 pipeline to
isolate a timing failure; it produced the project's first successful
out-of-context implementation (4.861 ns, 27 DSP) at the cost of latency. The
pragma was reverted — `reconstruction_accel.cpp:364` is `II=1` at HEAD, no
diagnostic residue remains.

Binding the Conv1 requant multiply (`bind_op … impl=dsp latency=2`) raised DSP
usage 27 → 69 and brought post-implementation timing to **4.793 ns**.

Current bottleneck: **Conv2 is 23.593 ms of the 28.186 ms (84 %)**.

### Phase 3 — KV260 integration (2026-09-15 → 09-16)

Built interactively through 60 Tcl scripts (see `vivado/SCRIPTS.md`).

Block design `neural_reconstruction_bd`, 8 cells:

```
zynq_ultra_ps_e_0  ──M_AXI_HPM0_FPD──▶ sc_control ──▶ s_axi_control  @ 0xA000_0000 / 64K
reconstruction_accel_0 ──m_axi_gmem0──▶ sc_gmem0 ──▶ S_AXI_HP0_FPD  (SAXIGP2, 0x0, 2G)
                       ──m_axi_gmem1──▶ sc_gmem1 ──▶ S_AXI_HP1_FPD  (SAXIGP3, 0x0, 2G)
pl_clk0 @ 200 MHz ──▶ ap_clk, all aclk
pl_resetn0 ──▶ resetn_inverter (NOT) ──▶ rst_200m.ext_reset_in ──▶ ap_rst_n
reset_locked_const (1) ──▶ rst_200m.dcm_locked
```

Synthesised, implemented, routed (14,998/14,998 nets, 0 errors, no black boxes),
bitstream written 09-15 20:19, embedded XSA exported 09-15 22:40.

A second session on 09-16 re-derived several scripts under a hyphenated naming
convention, producing near-duplicates — one of which (`export-xsa.tcl`) is wrong.

---

## 4. Verified results

### 4.1 HLS, current HEAD — `hls/reports/conv1_requant_dsp_impl/`

| Metric | Value |
|---|---|
| Estimated clock (csynth) | 4.400 ns |
| CP achieved post-synthesis | 4.942 ns |
| **CP achieved post-implementation** | **4.793 ns — timing met** |
| Latency | 5,637,182 cycles = **28.186 ms / image** @ 200 MHz |
| Conv2 / Conv3 / Bilinear / Conv1 | 23.593 / 2.949 / 1.311 / 0.333 ms |
| Post-impl resources | LUT 5,848 · FF 4,467 · DSP 69 · BRAM 91 · URAM 32 |

Out-of-context implementation of the accelerator alone.

### 4.2 KV260 integrated system — `vivado/reports/system_routed/`

| Metric | Value |
|---|---|
| **WNS** | **+0.058 ns** at 200 MHz, 0 failing endpoints of 30,800 |
| WHS | +0.010 ns, 0 failing |
| Routing | 14,998 / 14,998 routable nets, 0 errors |
| CLB LUTs | 7,393 (6.31 %) |
| CLB Registers | 6,362 (2.72 %) |
| DSP48E2 | 69 (5.53 %) |
| BRAM tiles | 45.5 (31.60 %) |
| **URAM** | **32 (50.00 %)** |

**58 picoseconds of setup margin.** Integration consumed ~0.15 ns of the
accelerator's standalone 0.207 ns. Any IP bump, tool update, or placement-seed
change can flip this — re-run timing after every PL change. URAM at 50 % is the
tightest resource.

### 4.3 Verification

| Level | Result |
|---|---|
| CSim vs. golden vectors | ✅ **Bit-exact**, frames 0805 / 0809 / 0824, max difference 0 ticks |
| C/RTL co-simulation (Vitis HLS / AXI VIP) | ❌ **FAIL** — tool defect, see below |
| **Standalone RTL simulation — `STALL=0`** | ✅ **`RTL_SUITE_PASS`** — 3 frames, 196,608/196,608 pixels, 0 mismatches, see `hls/reports/standalone_rtl_sim/` |
| **Standalone RTL simulation — `STALL=1`** | ✅ **`RTL_SUITE_PASS`** — 3 frames, 196,608/196,608 pixels, 0 mismatches, cumulative `stalled_cycles=2,202,721`, see `hls/reports/standalone_rtl_stress/` |

**The co-simulation failure is a tool defect, not a demonstrated arithmetic
mismatch.** XSim raised a kernel `FATAL_ERROR` inside the Xilinx-supplied AXI VIP
slave sequence (`axi_slave_seq_lib.sv`, `axi_slave_sequence(ADDR_WIDTH=64,
STRB_WIDTH=4, LEN_WIDTH=8)`), with 0 of 1 transactions completed — the simulation
died before any output was compared. Evidence and full reading in
`hls/reports/cosim_xsim_failure/README.md`.

Cosim was last run 09-13 20:55 against commit `8c847cd`. **It has not been re-run
since**, so it predates HEAD by three source commits.

**Superseded 2026-09-18 — see `hls/reports/standalone_rtl_sim/`.** The AXI VIP
was bypassed by a standalone testbench that drives the packaged RTL through its
real AXI4 memory and AXI4-Lite control interfaces, loading nothing from the
crashing VIP stack. Against commit `423d06c`, XSim 2025.1.1 returned
**`RTL_SUITE_PASS`**: golden frames 0805 / 0809 / 0824, **65,536 pixels each,
196,608 / 196,608 compared, 0 mismatches**, 6,164,920 cycles and 262,144 /
32,768 read/write beats per frame, normal `$finish`, exit code 0.

The testbench rejects unwritten output bytes rather than accepting incomplete
output, guards memory outside the output window, and requires non-zero AXI
traffic. All **101 / 101** packaged RTL and ROM files were verified byte-identical
to the HLS output, and every comparison traces by SHA256 to the committed golden
vectors.

The testbench's `STALL=1` backpressure variant was subsequently run against
commit `57b0d55` and also returned **`RTL_SUITE_PASS`** — see
`hls/reports/standalone_rtl_stress/`:

| | `STALL=0` | `STALL=1` |
|---|---|---|
| Result | `RTL_SUITE_PASS` | `RTL_SUITE_PASS` |
| Frames | 3 | 3 |
| Pixels | 196,608 / 196,608 | 196,608 / 196,608 |
| Mismatches | **0** | **0** |
| Read beats / frame | 262,144 | 262,144 |
| Write beats / frame | 32,768 | 32,768 |
| Cycles / frame | 6,164,920 (all three) | 6,362,231 / 6,358,129 / 6,358,129 |
| Cumulative `stalled_cycles` | 1,579,005 | **2,202,721** |

Injected backpressure — `AWREADY` withheld 1 cycle in 7, `ARREADY` 1 in 5,
`WREADY` 1 in 4, `RVALID` bubbled 1 in 3, a 3-cycle `B` delay, plus AXI4-Lite
host delays — increased per-frame RTL execution by roughly **3.1–3.2 %** while
leaving results and transaction counts exactly unchanged. Every `_actual.hex` is
byte-identical to both its expected file and the `STALL=0` output for the same
frame. No timeout, fatal, X/Z, payload-stability assertion, protocol assertion,
guard-region corruption or deadlock occurred. An independent one-frame scout run
in a separate directory reproduced the stressed 0805 cycle count exactly
(6,362,231).

Note that `stalled_cycles` is **not** a direct measure of injected backpressure:
it also counts ordinary handshake waits from the single-outstanding-burst
testbench memory model, which is why the `STALL=0` baseline is already non-zero.
The evidence that injection was genuinely active is recorded in
`hls/reports/standalone_rtl_stress/PROVENANCE.md`.

**Consequence: the standalone XSim results close the previously missing
RTL-level functional-verification gap for the packaged reconstruction accelerator
RTL used by the integrated KV260 design, both with an always-ready memory and
under injected AXI backpressure. They do not constitute post-route functional
simulation or hardware validation of the generated bitstream.** Routing and
timing closure still prove only that the design *fits and runs at speed*.
Remaining gaps: 3 of 20 evaluation frames, final output only (see §6.2), a single
fixed stall pattern rather than an exhaustive exploration of AXI timing, no
SmartConnect 32→128-bit width conversion or real DDR in the testbench, and no
board execution.

---

## 5. What is authoritative

| Class | Files |
|---|---|
| **Authoritative, not currently reproducible** | `hardware_reference/parameters/**`, `hardware_reference/golden_vectors/**`, `hls/tb/data/**` |
| **Authoritative, hand-written** | `hls/src/**`, `hls/tb/**`, `hls/hls_config.cfg`, `src/*.py`, **`neural_reconstruction_bd.bd`** |
| **Generated, preserved deliberately** | `vivado/ip_repo/reconstruction_accel_1_0/**` |
| **Evidence** | `hls/reports/**`, `vivado/reports/**`, `results/**` |
| **Historical / diagnostic** | `vivado/inspect*.tcl`, `probe_*.tcl`, superseded scripts |
| **Regenerable, ignored** | `hls/work/`, `*.gen/`, `*.runs/`, `*.cache/`, `*.xpr`, `vitis_workspace/` (≈310 MB) |

### 5.1 The `.bd` is authoritative because Tcl cannot recreate it

There is **no `create_bd_design` and no `write_bd_tcl`** in any of the 60 scripts.
All of them call `open_bd_design [get_files */neural_reconstruction_bd.bd]` on a
BD that must already exist. `create_base_bd.tcl` opens an existing BD despite its
name; `create_kv260_project.tcl` creates an empty project and never adds the
`.bd`. The block design therefore survives only as the `.bd` file itself.

### 5.2 The packaged HLS IP is generated but must be preserved

`vivado/ip_repo/reconstruction_accel_1_0/component.xml` is byte-identical to
`hls/work/hls/impl/ip/component.xml` (SHA256
`37b32cd43ddaeebd23ff2dda4acfc8b938ced2178f5b58e563792fa245e7eb1e`) — a verbatim
HLS export. It is committed anyway because the `.bd` resolves the accelerator by VLNV
and will not open without it, because regenerating needs Vitis HLS 2025.1.1 plus
a full csynth + implementation cycle, and because its `.dat` ROM images bake in
the quantised weights. Full rationale: `vivado/ip_repo/README.md`.

### 5.3 The model and dataset are not present in the repository

**The original training checkpoint and Round 3 dataset are not present in the
current repository or known project working tree.**

- No `*.pt` / `*.pth` / `*.ckpt` was found anywhere under the working tree.
  `results/round3/best_model.pt` — named as `source_checkpoint` in
  `hardware_metadata.json` — is absent. Its SHA256
  `af6c79ce172c70a97a565edd76ea183af25c8fcc4cb2002de2a575a15c335ac5` is recorded
  in `results/round4_int8/reference/round3_best_model_sha256.txt`, so a copy
  found elsewhere can be positively identified.
- `data/` does not exist here and is gitignored, so
  `src/generate_golden_vectors.py` (which reads `data/round3/val/{lr,hr}`)
  **cannot currently regenerate the golden vectors from repository contents,
  because their source dataset is absent.**

Both may still exist outside this tree. The recorded SHA paths point at
`C:\Users\avent\OneDrive\Documents\meng-fpga-neural-reconstruction\`, a previous
location of this project — but **that folder no longer exists in the local
OneDrive tree** (verified 2026-09-17; `OneDrive\Documents` is present and
contains no such directory). Remaining avenues are OneDrive's server-side
version history and recycle bin via the web interface, and any external backup.
Verify any candidate against `round3_best_model_sha256.txt`
(`af6c79ce172c70a97a565edd76ea183af25c8fcc4cb2002de2a575a15c335ac5`) before
trusting it.

Until they are recovered, the int8 parameters in
`hardware_reference/parameters/` and the committed golden vectors are the only
derivatives of the trained network available here. Treat them as primary data
and do not overwrite them.

---

## 6. Open issues

### 6.1 Reset polarity: scripts contradict the shipped design

`add_reset_200m.tcl` sets `CONFIG.C_EXT_RESET_HIGH 0` and wires `pl_resetn0`
directly to `rst_200m/ext_reset_in`. `fix_reset_polarity.tcl` later inserts a
`util_vector_logic` NOT gate into that path but **never restores the property**.

The shipped design has `C_EXT_RESET_HIGH = 1` (generated XCI,
`value_src="propagated"`; the `.bd` records no override), so inverter +
active-high is correct and the built hardware is sound. **Replaying both scripts
in order gives active-low `ext_reset_in` fed by an inverted `pl_resetn0` — reset
asserted permanently.** Not yet fixed.

### 6.2 Golden-vector coverage is incomplete

`test_reconstruction.cpp` compares **only** the final `output_ticks_u16`. The
five intermediates — `conv1_output_u8`, `conv2_output_u8`, `branch_input_u8`,
`residual_int8`, `bilinear_ticks_u16` — are generated, exported to `.bin`,
committed twice (`.npy` + `.bin`), and checked by nothing. They are useful for
manual bisection but provide zero automated coverage.

Coverage is also 3 frames of the 20-frame Round 3 / Round 4 evaluation set.

Combined with §4.3, a per-stage arithmetic fault could reach hardware undetected.

### 6.3 CSim runner scripts are stale and will not run

`run_csim_2026_1.cmd` and `run_csim_direct.cmd` invoke **Vitis 2026.1** from
`C:\AMDDesignTools\2026.1` and `cd` to
`C:\Users\avent\OneDrive\Documents\meng-fpga-neural-reconstruction`. The repo has
moved out of OneDrive, and every artefact in it was built with **2025.1.1** from
`C:/Xilinx/2025.1.1`. Neither script works as committed.

### 6.4 Tcl scripts are unportable

Thirteen scripts hardcode `subst` drives (`V:` = `vivado/kv260_project/`,
`M:` = repo root); the rest assume CWD is a repo *subdirectory* (`../vivado/…`).
Neither convention was documented before `vivado/SCRIPTS.md`.

### 6.5 Duplicated parameter header

`hls/src/reconstruction_params.h` is a manual byte-identical copy of
`hardware_reference/parameters/reconstruction_params.h`. Currently consistent
(SHA256 verified), with no automated check to keep it that way.

### 6.6 32-bit gmem against 128-bit HP ports

`m_axi_gmem0`/`gmem1` are 32-bit data / 64-bit address, feeding 128-bit
`S_AXI_HP0`/`HP1` through SmartConnect — a 4× bandwidth de-rate. Not currently
limiting (Conv2 makes the design compute-bound at 84 % of latency), but it caps
future dataflow work.

### 6.7 `hls_config.cfg` carries `vivado.flow=impl`

Added for the `07b87ea` diagnostic. Every C synthesis now triggers a full Vivado
implementation run. Correct for gathering timing evidence, expensive otherwise.

---

## 7. Release / build artefacts — ignored by Git, **archival still outstanding**

Binaries deliberately kept out of ordinary source control: each is a 1.6–7.8 MB
blob that is re-exported on every build, so committing one would add a permanent
new blob to history each time. They are recorded here by SHA256 so that any
archived copy can be positively identified as this build.

| Artefact | Size | Built | SHA256 |
|---|---|---|---|
| `vivado/kv260_project/…/impl_1/neural_reconstruction_bd_wrapper.bit` | 7.80 MB | 09-15 20:19 | `0ae427314550b4e4bb8884ce09e8776b325d0ecf517bba134e4e81d7dad853f9` |
| ✅ `vivado/kv260_project/neural_reconstruction_kv260_embedded.xsa` | 1.62 MB | 09-15 22:40 | `4b2b2bfb9b722441fa478ad354c85d87bb7f115c914943b151012dd0f7d00d74` |
| ⚠️ `vivado/neural_reconstruction_kv260.xsa` | 1.62 MB | 09-16 22:15 | `e2a4415eb8d6bf534d29884552fb0455f3b6984eeb42810e553f8cb280a9954f` |
| `neural_reconstruction_bd.bd` (tracked, for cross-reference) | 57 KB | 09-15 18:52 | `12ef4b3982ca04e00602ccb15c29bd7932f0d32e494862c3ba10a2d9395d7eca` |

✅ **`neural_reconstruction_kv260_embedded.xsa` is the good one** — the platform
the Vitis workspace actually consumed, exported by `export_xsa_embedded.tcl` with
`platform.design_intent.embedded true` and `open_run impl_1`.

⚠️ `vivado/neural_reconstruction_kv260.xsa` was produced by the superseded
`export-xsa.tcl`, which omits **both** `open_run impl_1` and
`platform.design_intent.embedded`. Do not treat it as a release artefact.

### Archival — done on-machine and to OneDrive, 2026-09-18

The XSA and bitstream were archived out of the single working tree on
2026-09-18. Both were verified against the SHA256s above before packaging:

| Copy | Location |
|---|---|
| Local archive | `FPGA_Archives\meng-fpga-neural-reconstruction\kv260_2026-09-17_423d06c\` — XSA + BIT with original build timestamps, plus `PROVENANCE.txt` and `SHA256SUMS.txt` |
| Local package | `…\kv260_2026-09-17_423d06c.zip` (1.95 MB, 4 entries) |
| Off-machine copy | `OneDrive\FPGA_Archives\meng-fpga-neural-reconstruction\kv260_2026-09-17_423d06c.zip` — same SHA256 as the local zip |

The zip round-trips to the original inner hashes, so the package is verified end
to end rather than merely written. **Caveat on the zip hash:**
`Compress-Archive` output is not deterministic — it embeds entry timestamps —
so re-creating the zip from the same inputs yields a different SHA256. The zip
hash identifies *this package*; the durable fingerprints are the two inner
hashes, carried inside the archive as `SHA256SUMS.txt`.

**Still outstanding:** OneDrive upload completion was never positively
confirmed — local file attributes look identical before and after upload, so
this needs checking via the OneDrive client or web interface. A tagged release
asset or an additional independent backup would also be worth having.

This matters more than usual here: regenerating the XSA currently requires the
reset-polarity fix (§6.1) plus a full rebuild, and system timing closes with only
**58 ps** of margin, so a rebuild is not guaranteed to reproduce an equivalent
result.

The `STALL=0` baseline simulation outputs — the three `_actual.hex` files and
`baseline_complete.log`, which existed only in a scratch run directory — were
archived alongside, to
`FPGA_Archives\meng-fpga-neural-reconstruction\stall0_2026-09-18\`, all four
verified against the hashes in
`hls/reports/standalone_rtl_sim/PROVENANCE.md`.

---

## 8. Immediate next steps

### Complete

- ✅ **KV260 integration committed** (`2cbd11e`, `23e1aa5`) — §2.
- ✅ **Standalone RTL baseline verification** (2026-09-18) — `RTL_SUITE_PASS`,
  3 frames, 196,608/196,608 pixels, 0 mismatches
  (`hls/reports/standalone_rtl_sim/`).
- ✅ **Standalone RTL backpressure verification** (2026-09-18) —
  `RTL_SUITE_PASS` under `STALL=1`, 3 frames, 196,608/196,608 pixels,
  0 mismatches, transaction counts unchanged
  (`hls/reports/standalone_rtl_stress/`).
- ✅ **Build artefacts archived** off the single working tree, with an
  off-machine copy — §7, subject to the OneDrive sync confirmation noted there.

### The next major boundary: KV260 hardware bring-up

RTL-level functional verification is now as complete as this harness can make
it. Every remaining question about whether the design *works* — as opposed to
whether it *fits and runs at speed* — requires the board.

1. **KV260 hardware bring-up.** Load the bitstream, run a golden frame on the
   PS, and compare against `hls/tb/data/`. Nothing in this repository has ever
   been executed on hardware.
2. **Fix the reset-polarity contradiction** (§6.1) and add a `write_bd_tcl`
   export so the block design has a reviewable text form alongside the `.bd`.
   Required before any rebuild, and therefore a prerequisite for regenerating
   the XSA.
3. **Re-run system timing after any PL change** — 58 ps is not margin.

### Optional, in parallel or after bring-up

4. **Widen RTL coverage** beyond the 3 golden frames toward the 20-frame
   Round 3 / Round 4 evaluation set.
5. **Extend the testbench to check the five intermediates** (§6.2), which remain
   covered by no automated test.
6. **Search for the checkpoint and Round 3 dataset** (§5.3) — start with the
   OneDrive location the recorded SHA paths point at, including its version
   history and recycle bin. Verify any candidate against
   `round3_best_model_sha256.txt` before trusting it.
7. **Update the CSim runners** to 2025.1.1 and the current path (§6.3).
8. **Confirm the OneDrive archive upload completed** (§7), and consider a tagged
   release asset or a second independent backup.
