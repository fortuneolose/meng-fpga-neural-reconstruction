# Standalone RTL simulation — completed run

Reproducible harness and usage: [`README.md`](README.md).

| Field | Value |
|---|---|
| Source repository commit | **`423d06c`** (`docs(project): add verified project state and Claude context`) |
| Branch | `kv260-integration` |
| RTL under test | `vivado/ip_repo/reconstruction_accel_1_0/hdl/verilog/` — the packaged IP consumed by `neural_reconstruction_bd.bd` |
| Tool | **XSim 2025.1.1** (64-bit), SW Build 6233196, from `C:/Xilinx/2025.1.1` |
| Elaboration | `xelab work.tb -s rtl_verify -mt off -debug off` → `xelab_verify.txt` |
| Invocation | `xsim.bat -f baseline_complete.args` (`CASES=3`, `STALL=0`) |
| Completed run | **2026-09-18**, 14:54:10 → 15:11:59 local, 17 m 34 s elapsed |
| Host | `Fortune`, 12th Gen Intel Core i5-1240P |

Nothing was re-run to produce this record. Original file timestamps are
preserved; the `.log` files were renamed to `.txt` only because `*.log` is
gitignored repo-wide.

## Result

**`RTL_SUITE_PASS`** — exit code **0**, normal `$finish` at 92,474,465 ns
(`tb.sv` line 401). Not a timeout: the run ended at 18.49 M cycles against a
100 M-cycle global and 20 M-cycle per-frame limit.

Verbatim from `baseline_complete.txt`:

```
RTL_GOLDEN_PASS id=0805 pixels=65536 mismatches=0 observed_cycles=6164920 read_beats=262144 write_beats=32768 stalls=0
RTL_GOLDEN_PASS id=0809 pixels=65536 mismatches=0 observed_cycles=6164920 read_beats=262144 write_beats=32768 stalls=0
RTL_GOLDEN_PASS id=0824 pixels=65536 mismatches=0 observed_cycles=6164920 read_beats=262144 write_beats=32768 stalls=0
RTL_SUITE_PASS frames=3 stalls=0 stalled_cycles=1579005
```

| Frame | Start cycle | Observed cycles | Read beats | Write beats | Pixels | Mismatches |
|---|---|---|---|---|---|---|
| 0805 | 71 | 6,164,920 | 262,144 | 32,768 | 65,536 | **0** |
| 0809 | 6,165,022 | 6,164,920 | 262,144 | 32,768 | 65,536 | **0** |
| 0824 | 12,329,973 | 6,164,920 | 262,144 | 32,768 | 65,536 | **0** |

- **196,608 / 196,608** pixel comparisons — expected and actual totals agree.
- **0 mismatches** across the suite.
- **0 missing output writes.** The output memory is pre-filled with `8'ha5` and
  each byte carries a `written[]` flag; a pixel counts as a mismatch unless both
  of its bytes were actually driven by the DUT. Zero mismatches therefore means
  all 393,216 output bytes were genuinely written, not coincidentally correct.
- No fatal, error, timeout, or X/Z message anywhere in the log.
- Beat counts are exactly as expected: 262,144 read beats = 16,384 input bytes
  ÷ 4 B/beat × 64 passes; 32,768 write beats = 131,072 output bytes ÷ 4 B/beat.

### `stalls=0` with `stalled_cycles=1579005`

These two counters measure different things, and the combination is expected.

- **`stalls=0`** echoes the `+STALL` plusarg. It means **no deliberate
  backpressure was injected**. With `stall_enable = 0`, every artificial
  stall term in `axi_ram.sv` (`tick%7`, `tick%5`, `tick%4`, `tick%3`, and the
  3-cycle B-response delay) is disabled, so the model never withholds `ready`
  or `rvalid` artificially.

- **`stalled_cycles=1579005`** counts cycles where the DUT asserted a valid that
  the memory model could not accept — `(arvalid && !arready) || (awvalid &&
  !awready) || (wvalid && !wready)` — summed over **both** memory instances and
  **cumulative across all three frames** (it is reset only on `aresetn`, which is
  asserted once before frame 0). It averages ~526 K cycles per frame.

With injection disabled, these are **ordinary AXI handshake waits arising from
the memory model's single-outstanding-burst design**: `arready` drops while a
read burst is in flight or an R beat is outstanding, `awready` drops while a
write burst or B response is pending, and `wready` is low until an AW has been
accepted. They are a property of the 1-deep testbench memory, not injected
stress and not a defect in the accelerator.

They are also **not** a measure of time the accelerator spent waiting overall.
The design is compute-bound — Conv2 alone is 84 % of latency — so most of the
6,164,920 cycles per frame involve no AXI activity at all.

Consequently `stalled_cycles` being non-zero here does **not** mean backpressure
was stress-tested. The testbench's own guard for that only arms when injection is
enabled (`if(stress && stalled_cycles==0) $fatal`) — and, because this baseline
shows the counter is already non-zero without injection, that guard cannot
distinguish working injection from silently broken injection.

**A deliberate `STALL=1` run was subsequently performed (2026-09-18) and also
passed — see [`../standalone_rtl_stress/`](../standalone_rtl_stress/).** This
record describes the unstressed baseline only.

## Evidence integrity

| File | SHA256 |
|---|---|
| `baseline_complete.txt` (the passing run) | `05144b4c8f77458c7c8699a3e0d6cb8e023755b8be82298cf1a8035d77a5cd97` |
| `baseline_partial.txt` (earlier interrupted run) | `d1bb4e62597043320b77261df3629967659e5118130159f96ac5c4237b3bfbc2` |
| `xelab_verify.txt` | `3139f31662441e57558988c81b3b2f7f63a1d9ae19d09a1fc6c75d80ffac1f23` |

### Output pixel data

Each `<id>_actual.hex` produced by the DUT was compared with the corresponding
`<id>_expected.hex`. All three pairs are **65,536 lines / 393,216 bytes** and
**byte-for-byte identical** (`cmp` clean), so actual and expected share a hash:

| Frame | SHA256 — actual **and** expected | Identical |
|---|---|---|
| 0805 | `eaf61b45e96d2adf122f7e64a2e372c3a08f68fedae847db8c22e9702c8fdcff` | ✅ |
| 0809 | `c7b497fd75bea4f78c6b2261c9b4767ce9bed8313955cf5fc799a9ec4b253b47` | ✅ |
| 0824 | `ceee38784a1c9d84711aef96aa5432783d5e2fb4665b1683ed52d39b2f4f93ba` | ✅ |

The `.hex` files themselves are not preserved (~2.7 MB, regenerable by
`prepare.py`); these hashes are the record.

### Traceability to the committed golden vectors

Verified independently of the simulation, against `hls/tb/data/<id>/`:

| Frame | `input_lr_u8.bin` (16,384 B) | `output_ticks_u16.bin` (131,072 B) |
|---|---|---|
| 0805 | `1391f2ae…eab32c` | `0dea0441…39b0a7` |
| 0809 | `dc4394ea…3929c3` | `50974a57…ca506e7` |
| 0824 | `25571acc…f306db6` | `27a348ec…0f5ffd69` |

All six hash exactly to the values recorded in `manifest.json` at commit
`423d06c`. Re-deriving each `_expected.hex` from the committed `.bin` reproduces
the on-disk file identically, and each RTL `_actual.hex` equals that
re-derivation — so the comparison chains to repository data with no intermediate
file taken on trust.

### RTL identity

`manifest.json` records **101 files (79 `.v` + 22 `.dat`)** copied from
`vivado/ip_repo/reconstruction_accel_1_0/hdl/verilog/`, each hashed and compared
against the HLS synthesis output in `hls/work/hls/syn/verilog/`:
**101 / 101 byte-identical**. The RTL simulated here is therefore provably the
RTL packaged into the IP and instantiated by `neural_reconstruction_bd.bd`.

### Reproducibility

An earlier run of the same snapshot was interrupted by session teardown partway
through frame 0809 (`baseline_partial.txt`). Its frame 0805 result is
**bit-identical** to the completed run — same `0805_actual.hex` SHA256, same
6,164,920 cycles, same 262,144 / 32,768 beat counts. Two independent XSim
invocations, identical results.

## Scope and limitations

This result covers the **packaged accelerator RTL** only.

- **3 of 20 frames.** Coverage is golden vectors 0805 / 0809 / 0824, not the full
  Round 3 / Round 4 evaluation set.
- **Final output only.** Only `output_ticks_u16` is compared. The five committed
  intermediates (`conv1_output_u8`, `conv2_output_u8`, `branch_input_u8`,
  `residual_int8`, `bilinear_ticks_u16`) remain unchecked by any automated test —
  see `docs/PROJECT_STATE.md` §6.2, which this run does not change.
- **No backpressure stress in *this* run.** `STALL=0` baseline only. The
  `STALL=1` stress run is a separate result — see
  [`../standalone_rtl_stress/`](../standalone_rtl_stress/).
- **Behavioural RTL simulation.** This is not post-synthesis or post-route
  gate-level simulation, carries no timing information, and is **not** a
  functional verification of the generated bitstream.
- **No hardware execution.** The design has still never been run on a KV260.

The earlier Vitis HLS C/RTL co-simulation failure remains a separate historical
result and is unaffected by this run — see
[`../cosim_xsim_failure/README.md`](../cosim_xsim_failure/README.md).

## Errata (2026-10-05)

The run, its logs and its pass verdict are unaffected. Three explanations above
are corrected:

- **Read beats.** "16,384 input bytes ÷ 4 B/beat × 64 passes" gets the right
  number for the wrong reason. The bilinear stage reads four input bytes per
  output pixel, each as its own single-byte beat
  (`hls/src/reconstruction_accel.cpp:291-308`): 65,536 pixels × 4 = 262,144.
- **`stalled_cycles` and accelerator waiting.** The section above says the
  stalls are "not a measure of time the accelerator spent waiting". In fact
  they account for essentially all of the RTL's extra latency: the run took
  6,164,920 cycles per frame against the HLS estimate of 5,637,182, a
  difference of 527,738, while `stalled_cycles` averages 526,335 per frame.
  The memory model's one-burst-at-a-time handshaking serialises the bilinear
  stage's single-byte reads. Real DDR behind SmartConnect will have higher
  latency, so this stage is the one most likely to be slower on the board.
- **Hashes.** The SHA256s in this file and in `manifest.json` were taken on a
  Windows checkout (CRLF line endings) and match a Linux checkout only after
  LF→CRLF conversion: 0 of 101 `manifest.json` RTL hashes match as-is.
  `tools/verify_recorded_hashes.py` checks every record in both forms;
  all match.
