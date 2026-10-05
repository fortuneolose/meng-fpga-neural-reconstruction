# Standalone RTL backpressure stress simulation (`STALL=1`)

The deliberate AXI backpressure variant of the standalone XSim regression
preserved in [`../standalone_rtl_sim/`](../standalone_rtl_sim/). Same harness,
same packaged RTL, same golden vectors — the only change is the `STALL`
plusarg.

**Result: `RTL_SUITE_PASS frames=3 stalls=1`** — 196,608 / 196,608 output pixels,
**0 mismatches**, AXI transaction counts identical to the unstressed baseline.

## Why this exists

The `STALL=0` baseline proved the packaged accelerator RTL is bit-exact against
the committed golden vectors when the testbench memory is always ready. It left
open whether that result depended on convenient memory timing. `PROJECT_STATE.md`
recorded the gap as *"`STALL=0` baseline only (no backpressure stress)"*.

This run closes that gap for the exercised stall pattern.

> **Note 2026-10-05.** "Always ready" is not accurate for `STALL=0`: the memory
> model accepts one read burst and one write burst at a time (`arready` is low
> while a burst is in flight), so `STALL=0` already applies ordinary handshake
> backpressure. `STALL=1` adds the injected pattern on top of that. See the
> errata in `../standalone_rtl_sim/PROVENANCE.md`.

## The harness is not duplicated here

`prepare.py`, `tb_body.sv`, `axi_ram.sv` and the generated `tb.sv` live in
[`../standalone_rtl_sim/`](../standalone_rtl_sim/) and are **authoritative**.
Nothing in this directory replaces them.

The `tb.sv` generated for this run was verified byte-identical to the preserved
one (SHA256 `a09ce544…`), so the stress run used the same testbench as the
baseline. See `PROVENANCE.md`.

`manifest.json` **is** preserved here, because it is this run's own provenance
record. It differs from `../standalone_rtl_sim/manifest.json` in exactly one
field — `repository_commit` — and its `files`, `sources` and `golden_files`
sections are identical, which independently establishes that the stress run
simulated the same 101 RTL/ROM files and the same golden data as the baseline.

## What `STALL=1` actually injects

`stall_enable` is driven from the `STALL` plusarg
(`tb_body.sv`: `if($value$plusargs("STALL=%d",stress)) stall_enable=(stress!=0)`)
and reaches two places.

**Both `axi_ram` instances** (testbench as AXI slave, backpressuring the DUT's
`m_axi_gmem0` / `m_axi_gmem1` masters), gated on a free-running per-instance
`tick` counter:

| Channel | Condition when `stall_enable` | Effect |
|---|---|---|
| `AWREADY` | `tick%7!=0` | withheld 1 cycle in 7 |
| `ARREADY` | `tick%5!=0` | withheld 1 cycle in 5 |
| `WREADY` | `tick%4!=0` | withheld 1 cycle in 4 |
| R data | `tick%3!=0` | `RVALID` bubble 1 cycle in 3, mid-burst |
| B response | `bdelay = 3` | 3 idle cycles per burst before `BVALID` |

**The testbench's own AXI4-Lite tasks** (testbench as AXI master, delaying its
responses to the DUT's `s_axi_control` slave): `repeat(2)` before driving
`WVALID`, `repeat(3)` before asserting `BREADY`, `repeat(3)` before asserting
`RREADY`.

`tick` is reset only on `aresetn`, which is asserted once before frame 0, so it
runs continuously across all three frames and each frame begins at a different
stall phase.

## Checker behaviour

Identical to the baseline in every acceptance check — 65,536-pixel compare,
per-byte `written[]` enforcement against the `8'ha5` prefill, guard-region
sweep, non-zero-traffic assertion, `ap_idle`/`ap_done`, write-response drain,
AXI-Lite pointer readback, and all `axi_ram` protocol assertions.

`STALL=1` adds one guard at the end of the suite:

```systemverilog
if(stress && input_ram.stalled_cycles+output_ram.stalled_cycles==0)
    $fatal(1,"Stressed run did not exercise backpressure");
```

> [!WARNING]
> **This guard is not evidence that injection occurred.** The `STALL=0` baseline
> already reported `stalled_cycles=1,579,005`, because that counter also tallies
> ordinary handshake waits produced by the single-outstanding-burst memory model.
> The sum cannot reach zero on any functioning run, so the guard would pass even
> if `stall_enable` were silently ineffective. `PROVENANCE.md` records the
> independent evidence that injection was genuinely active.

## Reproducing

From a scratch directory **outside** this repository, using the authoritative
harness:

```powershell
$repo = '<repo root>'
$run  = '<fresh scratch dir>'
python "$repo\hls\reports\standalone_rtl_sim\prepare.py" --repo $repo --run-dir $run
Set-Location $run
# stress_complete.args, written LF / UTF-8 without BOM
& 'C:\Xilinx\2025.1.1\Vivado\bin\xvlog.bat' -prj rtl.prj
& 'C:\Xilinx\2025.1.1\Vivado\bin\xelab.bat' work.tb -s rtl_verify -mt off -debug off -log xelab_stress.log
& 'C:\Xilinx\2025.1.1\Vivado\bin\xsim.bat' -f stress_complete.args
```

The `-f` options file is required, not stylistic: `xsim.bat` is a batch wrapper
and `cmd.exe` splits arguments on `=`, so passing `-testplusarg CASES=3` on the
command line fails with *"Expected a switch but found 3"* before the snapshot
loads. See `../standalone_rtl_sim/README.md`.

Run it in a fresh directory. `<id>_actual.hex` filenames are hardcoded in
`tb_body.sv` and are identical for `STALL=0` and `STALL=1`, so two runs sharing
a directory silently overwrite each other's output evidence.

## Preserved here

| File | What |
|---|---|
| `stress_complete.args` | The exact XSim options file used (`CASES=3`, `STALL=1`) |
| `stress_complete.txt` | Verbatim simulator log of the definitive 3-frame run |
| `stress_scout.txt` | Verbatim log of the independent 1-frame scout |
| `xelab_stress.txt` | Elaboration log for the 3-frame run |
| `manifest.json` | RTL/golden-vector snapshot record for this run |

**Not** preserved, for the same reasons as the baseline directory: the 101
copied `.v`/`.dat` files (hashed in `manifest.json`), the `*_input.hex` /
`*_expected.hex` / `*_actual.hex` (~2.7 MB, regenerable; hashes in
`PROVENANCE.md`), `xsim.dir/`, `*.wdb`, `xsim.jou` and `xvlog.log`.

`*.log` is gitignored repo-wide, so logs are preserved as `.txt`. Those `.txt`
files carry scoped `-text` rules in `.gitattributes` so their simulator-emitted
bytes survive checkout unchanged and continue to hash to the recorded values.
