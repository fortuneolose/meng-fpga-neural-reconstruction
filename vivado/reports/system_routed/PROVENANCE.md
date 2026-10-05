# KV260 integrated system — routed implementation evidence

Evidence that the **full KV260 block design** (PS + accelerator + SmartConnects
+ reset logic) synthesised, placed, routed and produced a bitstream.

Copied verbatim from the ignored Vivado project tree so the result survives a
project regeneration. **Original file timestamps are preserved.** Nothing was
re-run to produce this directory.

---

## ⚠️ This build came from an UNCOMMITTED working-tree state

**The routed result recorded here was produced from an integration state that had
never been committed to Git.** At the time of the build — and at the time this
evidence was captured — branch `kv260-integration` contained **no integration
commit at all**: it pointed at `8d075ac`, an HLS-only commit identical to
`hls-conv1-line-buffer`, with zero commits of its own.

Everything the build consumed (`neural_reconstruction_bd.bd`, the 60 Tcl scripts,
`vivado/ip_repo/`) existed **only as untracked files in one working tree on one
machine**. There is therefore no commit SHA that identifies this build. It is
pinned by the content hashes below instead.

The preservation commit that this evidence is part of is the first commit to
capture that state. Anything predating it is reconstructable only from these
hashes.

Note also that the Tcl scripts as written **do not reproduce this build** — see
`vivado/SCRIPTS.md`, "Known defects in the build sequence" (no `create_bd_design`
anywhere; the reset-polarity scripts contradict the shipped design).

---

## Build identification

| Field | Value |
|---|---|
| Design | `neural_reconstruction_bd_wrapper` |
| Git commit for the integration state | **none — uncommitted working tree** |
| HLS source commit behind the packaged IP | `8d075ac` |
| **Tool version** | **Vivado v.2025.1.1 (win64), Build 6233196, Thu Sep 11 21:27:30 MDT 2025** |
| Vitis HLS (packaged IP) | 2025.1.1, Build 6214317 |
| Part | `xck26-sfvc784-2LV-c` |
| Speed file | `-2LV` PRODUCTION 1.30, 05-15-2022 |
| Board part | `xilinx.com:kv260_som:part0:1.4` |
| Target clock | `pl_clk0` @ **200 MHz** (5.000 ns) |
| Host | `Fortune` (Windows) |
| **Synthesis run** | `synth_1`, 2026-09-15 19:30 |
| **Implementation routed** | **2026-09-15 19:52:12** |
| **Bitstream written** | **2026-09-15 20:19:06** |
| Utilization reports | 2026-09-15 20:01:46 / 20:14:51 |
| Embedded XSA exported | 2026-09-15 22:40:58 |

## Content hashes (SHA256)

These identify the build in the absence of a commit SHA.

| Artefact | SHA256 |
|---|---|
| **Block design** `neural_reconstruction_bd.bd` (tracked) | `12ef4b3982ca04e00602ccb15c29bd7932f0d32e494862c3ba10a2d9395d7eca` |
| **Packaged IP** `vivado/ip_repo/reconstruction_accel_1_0/component.xml` (tracked) | `37b32cd43ddaeebd23ff2dda4acfc8b938ced2178f5b58e563792fa245e7eb1e` |
| **Bitstream** `…/impl_1/neural_reconstruction_bd_wrapper.bit` (7.80 MB, ignored) | `0ae427314550b4e4bb8884ce09e8776b325d0ecf517bba134e4e81d7dad853f9` |
| **Embedded XSA** `vivado/kv260_project/neural_reconstruction_kv260_embedded.xsa` (1.62 MB, ignored) | `4b2b2bfb9b722441fa478ad354c85d87bb7f115c914943b151012dd0f7d00d74` |

The packaged IP `component.xml` hash is byte-identical to
`hls/work/hls/impl/ip/component.xml`, confirming `vivado/ip_repo/` is the
unmodified HLS export for source commit `8d075ac`.

⚠️ A second XSA exists, `vivado/neural_reconstruction_kv260.xsa`
(`e2a4415eb8d6bf534d29884552fb0455f3b6984eeb42810e553f8cb280a9954f`, 2026-09-16
22:15). It was produced by the superseded `export-xsa.tcl`, which omits both
`open_run impl_1` and `platform.design_intent.embedded`. **It is not the platform
the Vitis workspace consumed and is not a release artefact.**

### Artefact retention

The bitstream and the embedded XSA are **deliberately ignored by Git** — each is a
multi-megabyte binary re-exported on every build. They are **not deleted**, and
they still require **durable archival outside ordinary Git history** (tagged
release asset, artefact store, or backed-up archive), verified against the hashes
above. See `docs/PROJECT_STATE.md` §7.

---

## Routed timing result — the headline number

```
WNS(ns)   TNS(ns)   TNS Failing Endpoints   TNS Total Endpoints
  0.058     0.000                       0                 30800

WHS(ns)   THS(ns)   THS Failing Endpoints   THS Total Endpoints
  0.010     0.000                       0                 30800

WPWS(ns)  TPWS(ns)  TPWS Failing Endpoints  TPWS Total Endpoints
  1.000     0.000                       0                  7528

All user specified timing constraints are met.
```

**WNS = +0.058 ns at the 200 MHz target.** Timing is met — with **58 picoseconds**
of setup margin. Hold margin is +0.010 ns. This is closure, but with essentially
no headroom: an IP version bump, a tool update, or a different placement seed can
plausibly flip it. Treat any change touching the PL as requiring a fresh timing
run, not an assumption.

For contrast, the accelerator **alone** (out-of-context HLS implementation,
`hls/reports/conv1_requant_dsp_impl/`) closes at 4.793 ns — 0.207 ns of margin.
Integration consumed roughly 0.15 ns of that.

## Routing result

```
# of logical nets .............. 76035
# of routable nets ............. 14998
# of fully routed nets ......... 14998
# of nets with routing errors ...... 0
```

No black boxes, no unrouted nets.

## Routed utilization result

| Resource | Used | Available | % |
|---|---|---|---|
| CLB LUTs | 7,393 | 117,120 | 6.31 |
| — LUT as Logic | 6,824 | 117,120 | 5.83 |
| — LUT as Memory | 569 | 57,600 | 0.99 |
| CLB Registers | 6,362 | 234,240 | 2.72 |
| CARRY8 | 307 | 14,640 | 2.10 |
| DSP48E2 | 69 | 1,248 | 5.53 |
| Block RAM tiles | 45.5 | 144 | 31.60 |
| — RAMB36E2 | 44 | 144 | 30.56 |
| — RAMB18E2 | 3 | 288 | 1.04 |
| **URAM288** | **32** | **64** | **50.00** |
| PS8 | 1 | 1 | 100.00 |
| BUFGCE / BUFG_PS | 1 / 1 | 112 / 96 | 0.89 / 1.04 |
| Bonded IOB | 0 | 189 | 0.00 |

URAM at 50 % is the tightest resource and constrains any future feature-map
buffering work. No black boxes reported.

---

## Files in this directory

| File | Source | Produced by |
|---|---|---|
| `neural_reconstruction_bd_wrapper_timing_summary_routed.rpt` | `…runs/impl_1/` | `impl_1` (`run_system_impl.tcl`) |
| `neural_reconstruction_bd_wrapper_route_status.rpt` | `…runs/impl_1/` | `impl_1` (`run_system_impl.tcl`) |
| `system_utilization_routed.rpt` | `vivado/kv260_project/` | `vivado/report_system_utilization.tcl` |
| `system_utilization_summary_routed.rpt` | `vivado/kv260_project/` | `vivado/report_system_utilization_summary.tcl` |

The two `system_utilization*` files are ignored at their generated location
(they are rewritten on every report run); these curated copies are the tracked
ones.

## What this evidence does NOT cover

- **No RTL functional verification.** Co-simulation has never passed — see
  `hls/reports/cosim_xsim_failure/README.md`. Routing and timing closure show the
  design *fits and runs at speed*, not that it *computes the right answer*.
- **No on-hardware result.** The bitstream was written; nothing in the repository
  records it having been loaded onto or exercised on a KV260.
- **No reproducibility guarantee.** The build came from an uncommitted working
  tree, and the Tcl scripts do not recreate the block design.

## Status 2026-10-05

Two statements above are out of date; the timing and utilization numbers are
unaffected.

- **RTL functional verification now exists** for the packaged IP in this
  build: standalone XSim simulation, 3 golden frames, 0 mismatches, with and
  without injected AXI backpressure (`hls/reports/standalone_rtl_sim/`,
  `hls/reports/standalone_rtl_stress/`). It is behavioural RTL simulation, not
  post-route or on-hardware validation.
- **The block design is reproducible from Tcl:** `vivado/replay_bd.tcl` rebuilds
  it from the `write_bd_tcl` export `vivado/neural_reconstruction_bd.tcl`, and
  the reset scripts were shown to produce the correct topology
  (`vivado/reports/reset_replay/`). Synthesis to bitstream still has no single
  portable entry point.

The worst setup paths in this report are all inside the accelerator: Conv2
weight ROM `p_ZL13CONV2_WEIGHTS_1_U/q0_reg` → unregistered
`mul_8s_8ns_16_1_1_U104` → `mac_muladd_8s_8ns_16s_17_4_1_U106`. The accelerator's
`interrupt` output is not connected in this block design; software must poll
`ap_done`.
