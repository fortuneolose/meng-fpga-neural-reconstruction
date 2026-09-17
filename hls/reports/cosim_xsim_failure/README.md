# C/RTL co-simulation failure evidence

**Verdict: C/RTL co-simulation FAILS. It has never completed successfully.**

The failure is an **XSim simulator kernel exception inside the Xilinx-supplied
AXI VIP slave sequence** — not a demonstrated arithmetic mismatch between the C
model and the generated RTL. The RTL testbench died with 0 of 1 transactions
completed, so no output was ever compared against a golden vector.

Run date 2026-09-13 20:55, Vitis HLS / XSIM 2025.1.1 (`C:/Xilinx/2025.1.1`).
Source state: commit `8c847cd` *"hls: parallelize Conv3 input channels"*.
**Cosim has not been re-run since**, so this evidence predates the current HEAD
(`8d075ac`) by three source commits.

## What each file actually is

| File | What it is | Status |
|---|---|---|
| `hls_cosim.rpt` | The cosim verdict table: **Verilog = Fail**, VHDL = NA | Authoritative verdict |
| `hls_run_cosim_axi_vip_exception.txt` | Curated excerpt of the 848-line run log: cosim start, simulator build ID, and the `FATAL_ERROR` in `axi_slave_seq_lib.sv` | Authoritative failure evidence |
| `xsimcrash.txt` | Raw XSim crash stacktrace (addresses only, no module names) | Supporting, low diagnostic value alone |
| `csim_c_model_pass.txt` | CSim output only — **not** RTL evidence; see below | Renamed from `run_xsim.txt` |

### About `csim_c_model_pass.txt` (was `run_xsim.txt`)

This file was committed in `6a8451b` as `run_xsim.txt`. Despite that name and its
location in a directory called `cosim_xsim_failure`, it contains only this:

```
0805: BIT-EXACT PASS
All 3 golden vectors matched exactly.
HLS C MODEL VERIFICATION: PASS
```

That is the **CSim** stage that Vitis runs at the *start* of a cosim run, before
any RTL simulation begins. It reports that the C model is bit-exact against the
golden vectors. **It says nothing about RTL correctness**, and reading it as
evidence that RTL simulation passed would be wrong.

The file **contents are unmodified**; only the filename changed, so that it no
longer implies RTL evidence it does not contain. The real RTL co-simulation
evidence is `hls_cosim.rpt` and `hls_run_cosim_axi_vip_exception.txt`.

## Bottom line for the hardware

- **CSim:** bit-exact on golden vectors 0805 / 0809 / 0824.
- **Cosim (RTL):** never completed — blocked by the XSim/AXI VIP kernel exception.
- **Therefore:** the synthesised RTL, the packaged IP, and the KV260 bitstream
  carry **no passing RTL-level functional verification** at any level.

`STRB_WIDTH=4` in the failing sequence corroborates the 32-bit `m_axi` gmem data
width recorded in the packaged IP's `component.xml`.
