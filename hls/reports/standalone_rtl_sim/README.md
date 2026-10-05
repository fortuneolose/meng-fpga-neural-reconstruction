# Standalone RTL golden-vector simulation

A self-contained XSim regression that drives the **packaged accelerator RTL**
(`vivado/ip_repo/reconstruction_accel_1_0/hdl/verilog/`) through its real AXI4
memory and AXI4-Lite control interfaces and compares every output pixel against
the committed golden vectors.

## Why this exists

Vitis HLS C/RTL co-simulation **cannot** verify this design: XSim raises a kernel
`FATAL_ERROR` inside the Xilinx-supplied AXI VIP slave sequence before a single
transaction completes, so no output is ever compared. That failure is preserved
separately in [`../cosim_xsim_failure/`](../cosim_xsim_failure/) and is a tool
defect, not a demonstrated arithmetic mismatch.

> **Note 2026-10-05.** That describes Vitis HLS 2025.1.1. A cosim pass under
> 2026.1.1 has since been reported, with evidence outside the repository (see
> `../cosim_xsim_failure/README.md`). Cosim re-synthesises the RTL, so this
> standalone run remains the only in-repository functional evidence for the
> **packaged 2025.1.1 IP** in the bitstream.

This harness bypasses the AXI VIP entirely. It replaces it with a small,
hand-written AXI4 memory model (`axi_ram.sv`) and a directed testbench body
(`tb_body.sv`), so nothing from the crashing UVM/VIP stack is loaded. The
accelerator RTL itself is untouched — it is simulated exactly as packaged.

## What it checks

`tb_body.sv` is deliberately strict. A frame passes only if all of the following
hold:

- every one of the **65,536** output pixels equals the golden value;
- every output byte was **actually written** by the DUT — the output memory is
  pre-filled with `8'ha5` and a per-byte `written[]` flag is required, so a
  missing write is a mismatch rather than a lucky match;
- memory **outside** the output window is untouched (guard-region check);
- both memories saw **non-zero AXI traffic**;
- the accelerator reported `ap_idle` before the frame and `ap_done` after it, and
  all write responses drained before comparison;
- AXI-Lite pointer writes read back correctly.

The memory model itself fails the run on unsupported or malformed traffic:
non-32-bit or non-INCR bursts, unaligned addresses, addresses outside the active
image, 4 KiB boundary crossings, `WLAST` disagreeing with `AWLEN`, unknown (X)
write data or strobes, and any payload that changes while stalled.

Timeouts: 100 M cycles global, 20 M cycles per frame, plus per-channel AXI-Lite
handshake timeouts.

## How `prepare.py` assembles the run

```
python prepare.py --repo <repo root> --run-dir <run dir>
```

1. Copies all `*.v` and `*.dat` from the packaged IP
   (`vivado/ip_repo/reconstruction_accel_1_0/hdl/verilog/`) into the run
   directory — **101 files: 79 `.v` + 22 `.dat`**.
2. Hashes each one and records in `manifest.json` whether it is byte-identical to
   the HLS synthesis output in `hls/work/hls/syn/verilog/`. The preserved run
   reports **101 / 101 byte-identical**, so the simulated RTL is provably the
   same RTL that was packaged into the IP and the block design.
3. Converts the committed golden vectors in `hls/tb/data/<id>/` to
   `<id>_input.hex` / `<id>_expected.hex`, recording the SHA256 of each source
   `.bin`, and asserting their exact lengths (16,384 B in, 131,072 B out).
4. Parses the **110 top-level ports** out of `reconstruction_accel.v`, generates
   matching `reg`/`wire` declarations and the DUT instantiation, appends
   `tb_body.sv`, and wires two `axi_ram` instances to `m_axi_gmem0` (read-only)
   and `m_axi_gmem1` (write-only). The result is `tb.sv`.
5. Writes the filelists `rtl.prj` (XSim) and `iverilog.f` (Icarus) and the
   `manifest.json` record.

`tb.sv` is generated, but is preserved here because it pins the exact port
binding that was simulated.

## Running it

```powershell
# from the run directory, after prepare.py
& 'C:\Xilinx\2025.1.1\Vivado\bin\xvlog.bat' -prj rtl.prj
& 'C:\Xilinx\2025.1.1\Vivado\bin\xelab.bat' work.tb -s rtl_verify -mt off -debug off -log xelab_verify.log
& 'C:\Xilinx\2025.1.1\Vivado\bin\xsim.bat' -f baseline_complete.args
```

### Why the args file, and not the obvious command line

The apparently obvious invocation **does not work**:

```powershell
# FAILS: "Expected a switch but found 3", exit code 1, nothing simulated
& 'C:\Xilinx\2025.1.1\Vivado\bin\xsim.bat' rtl_verify -runall -testplusarg CASES=3 -testplusarg STALL=0 -log baseline_complete.log
```

`xsim.bat` is a batch wrapper, and `cmd.exe` splits arguments on `=`. XSim
therefore receives `-testplusarg CASES` followed by a bare `3`, and rejects the
`3` as a stray token before loading the snapshot. The failure is immediate and
looks like a simulator problem; it is purely argument quoting.

`baseline_complete.args` avoids the shell and the batch wrapper entirely by using
XSim's own `-f` options-file mechanism, one switch per line:

```
rtl_verify
--runall
--testplusarg CASES=3
--testplusarg STALL=0
--log baseline_complete.log
```

Plusargs: `CASES=1..3` selects how many golden frames to run; `STALL=1` enables
injected AXI backpressure (see `PROVENANCE.md` for what the reported
`stalled_cycles` counter does and does not mean). The completed `STALL=1` run is
preserved separately in [`../standalone_rtl_stress/`](../standalone_rtl_stress/).

## What is deliberately **not** preserved here

| Excluded | Why |
|---|---|
| The 101 copied `.v` / `.dat` files | Verbatim duplicates of `vivado/ip_repo/reconstruction_accel_1_0/hdl/verilog/`; `manifest.json` records the SHA256 of each, so the match is provable without a second copy |
| `*_input.hex`, `*_expected.hex`, `*_actual.hex` | ~2.7 MB, fully regenerated by `prepare.py` from the committed golden vectors; the `_actual` SHA256s are recorded in `PROVENANCE.md` |
| `xsim.dir/` | ~2.2 MB compiled snapshot, rebuilt by `xvlog` + `xelab` |
| `smoke.vvp` | 1.6 MB Icarus build product from an early smoke test |
| `*.wdb`, `xsim.jou`, `dfx_runtime.txt`, `xvlog.log` | Disposable simulator products and routine compile chatter |

`*.log` is gitignored repo-wide, so the preserved logs are stored as `.txt` —
the same convention used by `../cosim_xsim_failure/`.

To reproduce from this directory: copy `prepare.py`, `tb_body.sv` and
`axi_ram.sv` to a scratch directory outside the repository, run `prepare.py`
against a clean checkout, then `xvlog` / `xelab` / `xsim` as above. Nothing here
writes into the repository.
