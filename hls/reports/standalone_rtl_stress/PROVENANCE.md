# Standalone RTL backpressure stress — completed run

Harness, injection detail and reproduction: [`README.md`](README.md).
Unstressed baseline: [`../standalone_rtl_sim/`](../standalone_rtl_sim/).

| Field | Value |
|---|---|
| Source repository commit | **`57b0d55`** (`docs(verification): record standalone RTL golden-vector pass`) |
| Branch | `kv260-integration` |
| RTL under test | `vivado/ip_repo/reconstruction_accel_1_0/hdl/verilog/` — the packaged IP consumed by `neural_reconstruction_bd.bd` |
| Tool | **XSim 2025.1.1** (64-bit), SW Build 6233196, from `C:/Xilinx/2025.1.1` |
| Elaboration | `xelab work.tb -s rtl_verify -mt off -debug off` → `xelab_stress.txt`, exit 0, **zero warnings or errors** |
| Invocation | `xsim.bat -f stress_complete.args` (`CASES=3`, `STALL=1`) |
| Completed run | **2026-09-18**, 16:45:13 → 17:01:38 local, 16 m 21 s elapsed |
| Host | `Fortune`, 12th Gen Intel Core i5-1240P |
| Run directory | `C:\Users\avent\rtl_stress\stall1_full_2026-09-18` (outside the repository) |

Nothing was re-run to produce this record. Original file timestamps are
preserved; `.log` files were renamed to `.txt` only because `*.log` is gitignored
repo-wide. `xelab_stress.txt` was emitted as `xelab_full.log` by the run.

## Result

**`RTL_SUITE_PASS frames=3 stalls=1 stalled_cycles=2202721`** — exit code **0**,
normal `$finish` at 95,393,635 ns (`tb.sv` line 401). Not a timeout: the suite
ended at 19,078,727 cycles against a 100 M-cycle global limit, with a per-frame
peak of 6,362,231 against a 20 M-cycle per-frame limit (31.8 %).

Verbatim from `stress_complete.txt`:

```
RTL_GOLDEN_PASS id=0805 pixels=65536 mismatches=0 observed_cycles=6362231 read_beats=262144 write_beats=32768 stalls=1
RTL_GOLDEN_PASS id=0809 pixels=65536 mismatches=0 observed_cycles=6358129 read_beats=262144 write_beats=32768 stalls=1
RTL_GOLDEN_PASS id=0824 pixels=65536 mismatches=0 observed_cycles=6358129 read_beats=262144 write_beats=32768 stalls=1
RTL_SUITE_PASS frames=3 stalls=1 stalled_cycles=2202721
```

| Frame | Start cycle | Observed cycles | `STALL=0` cycles | Delta | Read beats | Write beats | Pixels | Mismatches |
|---|---|---|---|---|---|---|---|---|
| 0805 | 106 | 6,362,231 | 6,164,920 | +197,311 (**+3.20 %**) | 262,144 | 32,768 | 65,536 | **0** |
| 0809 | 6,362,403 | 6,358,129 | 6,164,920 | +193,209 (**+3.13 %**) | 262,144 | 32,768 | 65,536 | **0** |
| 0824 | 12,720,598 | 6,358,129 | 6,164,920 | +193,209 (**+3.13 %**) | 262,144 | 32,768 | 65,536 | **0** |

- **196,608 / 196,608** pixel comparisons, **0 mismatches**.
- **AXI transaction counts are identical to the unstressed baseline** on every
  frame — 262,144 read beats and 32,768 write beats. Backpressure altered
  timing only, never the traffic the accelerator generated.
- **0 missing output writes.** The output memory is prefilled with `8'ha5` and
  each byte carries a `written[]` flag; a pixel counts as a mismatch unless both
  bytes were actually driven by the DUT. Zero mismatches means all 393,216
  output bytes per frame were genuinely written.
- No fatal, error, warning, timeout, X/Z, payload-stability assertion, protocol
  assertion, guard-region corruption or deadlock anywhere in the log.

## Evidence that backpressure was genuinely injected

`stalled_cycles` rose from **1,579,005** (three frames, `STALL=0`) to
**2,202,721** (three frames, `STALL=1`) — **+623,716, +39.5 %**.

> [!IMPORTANT]
> **`stalled_cycles` is not a direct measure of injected backpressure.** It
> counts `(arvalid && !arready) || (awvalid && !awready) || (wvalid && !wready)`
> summed over both memory instances, and therefore also includes ordinary
> handshake waits arising from the single-outstanding-burst testbench memory
> model — which is why the unstressed baseline already reported 1,579,005. It
> also never counts the `tick%3` R-channel bubbles at all, since those are the
> model withholding data rather than the DUT waiting with a valid asserted. The
> counter is consistent with injection, but it does not by itself establish it.

Three independent lines of evidence do establish it.

**1 — Exact arithmetic match on the AXI4-Lite path.** `FRAME_START` for frame
0805 moved from cycle **71** (`STALL=0`) to **106** (`STALL=1`): +35 cycles. The
pre-frame setup performs 5 `axil_read` and 4 `axil_write` calls. The stall
delays predict (5 × 3) + (4 × (2 + 3)) = 15 + 20 = **35 cycles exactly**. The
measured delta matches the prediction with no residual, which requires
`stall_enable` to have gated those `repeat` statements.

**2 — Deterministic stimulus produced a different cycle count.** The RTL, the
input data and the testbench are identical between the two runs (`tb.sv` SHA256
`a09ce544…` in both). Frame 0805 took 6,164,920 cycles unstressed and 6,362,231
stressed. A deterministic simulation cannot change its cycle count unless the
memory model's ready/valid behaviour genuinely differed.

**3 — Phase-dependent variation appeared.** Under `STALL=0` all three frames
took *exactly* 6,164,920 cycles. Under `STALL=1`, frame 0805 diverges from 0809
and 0824 by 4,102 cycles, because `tick` free-runs across frames and each frame
therefore begins at a different phase of the modulo stall pattern. Such variation
can only exist if the modulo gating is live. It is benign: the output is
bit-identical at every phase observed.

## Independent reproduction — the scout run

A separate one-frame run (`CASES=1 STALL=1`) was performed **before** the suite,
in a different directory (`C:\Users\avent\rtl_stress\stall1_scout_2026-09-18`),
from its own `prepare.py` snapshot and its own `xvlog`/`xelab` build.
Log: `stress_scout.txt`.

```
RTL_GOLDEN_PASS id=0805 pixels=65536 mismatches=0 observed_cycles=6362231 read_beats=262144 write_beats=32768 stalls=1
RTL_SUITE_PASS frames=1 stalls=1 stalled_cycles=733766
```

It reproduced the stressed frame 0805 result **exactly**: the same 6,362,231
observed cycles, the same `FRAME_START` at cycle 106, the same 262,144 / 32,768
beat counts, and the same output SHA256. Two independent XSim invocations in
separate directories agree bit-for-bit.

## Evidence integrity

| File | SHA256 |
|---|---|
| `stress_complete.txt` (the passing 3-frame run) | `7d208a66f422166cb9235291537d1025689a21691c4202975adeca912b85c4c7` |
| `stress_scout.txt` (independent 1-frame run) | `1a25361b1e19a78f0abc9b7c5b8e4e11d03d08d2286eb5f25a9cf082699e0e36` |
| `xelab_stress.txt` | `9b1e7f6623e013111b4711e12fb23487cf6d756f3c4841357a338e39fd6213a1` |

These three files carry scoped `-text` rules in `.gitattributes`, so the bytes
checked out are the bytes the simulator emitted regardless of `core.autocrlf`,
and continue to hash to the values above. Each was verified to hash identically
as the original run artefact, as the preserved working-tree copy, and as the
staged Git blob.

No byte hash is recorded for `manifest.json` or `stress_complete.args`, because
neither carries a `-text` rule and both are therefore subject to Git's ordinary
end-of-line conversion. `prepare.py` writes `manifest.json` with
`Path.write_text()`, which emits CRLF on Windows, so its stored blob is the
LF-normalized form — identical in content, 429 bytes shorter. This matches how
`../standalone_rtl_sim/manifest.json` is already stored, whose committed blob is
likewise LF-normalized. Their value here is their content, not their byte
layout; the byte-exact evidence of record is the three `.txt` files above.

### Output pixel data

Each `<id>_actual.hex` produced by the DUT under backpressure was compared with
the corresponding `<id>_expected.hex` **and** with the archived `STALL=0` output
for the same frame. All three are 65,536 lines / 393,216 bytes and byte-for-byte
identical to both (`cmp` clean), so all three share a hash:

| Frame | SHA256 — `STALL=1` actual, expected, **and** `STALL=0` actual | Identical |
|---|---|---|
| 0805 | `eaf61b45e96d2adf122f7e64a2e372c3a08f68fedae847db8c22e9702c8fdcff` | ✅ |
| 0809 | `c7b497fd75bea4f78c6b2261c9b4767ce9bed8313955cf5fc799a9ec4b253b47` | ✅ |
| 0824 | `ceee38784a1c9d84711aef96aa5432783d5e2fb4665b1683ed52d39b2f4f93ba` | ✅ |

These are the same values recorded in `../standalone_rtl_sim/PROVENANCE.md`. The
`.hex` files themselves are not preserved (~2.7 MB, regenerable by
`prepare.py`); these hashes are the record.

### RTL and harness identity

`manifest.json` records **101 files (79 `.v` + 22 `.dat`)** copied from
`vivado/ip_repo/reconstruction_accel_1_0/hdl/verilog/` and compared against the
HLS synthesis output in `hls/work/hls/syn/verilog/`: **101 / 101
byte-identical**. Its `files`, `sources` and `golden_files` sections are
identical to `../standalone_rtl_sim/manifest.json`; the two differ only in
`repository_commit` (`57b0d55` here, `423d06c` there). The stress run therefore
simulated the same RTL and the same golden data as the baseline.

The generated `tb.sv` and the copied `axi_ram.sv` were verified byte-identical
to the preserved harness files before the run:

| File | SHA256 |
|---|---|
| `tb.sv` (generated; matches `../standalone_rtl_sim/tb.sv`) | `a09ce5442199a541d76d555f0527a22c790fc67bcd15d11fc1921ff854c2680c` |
| `axi_ram.sv` (matches `../standalone_rtl_sim/axi_ram.sv`) | `d2098fc1bb48615f2446c6e2e1765bd61a64f39cc8781db3e92eaa4635476db0` |

The three `<id>_expected.hex` files regenerated by `prepare.py` hash to the same
values as the archived `STALL=0` outputs, so the comparison targets chain to the
committed golden vectors in `hls/tb/data/` with no intermediate file taken on
trust.

## Simulation cost

`STALL=1` carries no measurable simulation cost. The three-frame stressed suite
consumed **935,186 ms** of kernel CPU in 16 m 21 s, against **949,061 ms** in
17 m 34 s for the unstressed baseline, for 3.2 % more simulated cycles.

The one-frame scout is an outlier at 1,605,499 ms CPU for a third of the work.
That is a property of the machine during that window, not of the stall pattern —
the suite refutes any intrinsic per-cycle penalty.

## Scope and limitations

This result covers the **packaged accelerator RTL** only.

### What it establishes

Under the exercised backpressure pattern, the packaged accelerator RTL:

- remained **bit-exact across all three golden vectors** — 196,608 / 196,608
  pixels, 0 mismatches;
- maintained **identical AXI beat counts** (262,144 read / 32,768 write per
  frame), so backpressure changed timing without changing the traffic generated;
- **held `AW`/`AR`/`W` payloads stable while stalled** — the `axi_ram`
  payload-stability assertions never fired;
- **did not deadlock**, completing every frame well inside both timeout limits;
- **tolerated the exercised AXI4-Lite host delays** on the `s_axi_control` path.

### What it does **not** verify

- **Real KV260 DDR.** The testbench memory is a one-outstanding-burst model with
  fixed modulo stall patterns and otherwise zero-latency responses. Actual DDR
  behind the PS has variable latency, refresh, reordering and multiple
  outstanding transactions. Nothing here predicts behaviour against it.
- **SmartConnect 32 → 128-bit width conversion.** The `m_axi_gmem0`/`gmem1`
  32-bit interfaces are driven directly. The SmartConnect and `S_AXI_HP0`/`HP1`
  path of `docs/PROJECT_STATE.md` §6.6 is not in this testbench at all.
- **Post-synthesis or post-route functionality.** This is behavioural RTL
  simulation.
- **The generated bitstream.** No bitstream is loaded, simulated or validated.
- **Timing closure behaviour.** The simulation carries no timing information and
  says nothing about the +0.058 ns system WNS.
- **More than 3 of the validation frames.** Coverage is golden vectors
  0805 / 0809 / 0824, not the 20-frame Round 3 / Round 4 evaluation set.
- **Internal or intermediate activations.** Only `output_ticks_u16` is compared.
  The five committed intermediates (`conv1_output_u8`, `conv2_output_u8`,
  `branch_input_u8`, `residual_int8`, `bilinear_ticks_u16`) remain unchecked by
  any automated test — see `docs/PROJECT_STATE.md` §6.2, which this run does not
  change.
- **Stall patterns other than the one exercised.** A single fixed modulo pattern
  was applied; it is not an exhaustive exploration of AXI timing.

**The design has still never been run on a KV260.**

The earlier Vitis HLS C/RTL co-simulation failure remains a separate historical
result, unaffected by this run — see
[`../cosim_xsim_failure/README.md`](../cosim_xsim_failure/README.md).
