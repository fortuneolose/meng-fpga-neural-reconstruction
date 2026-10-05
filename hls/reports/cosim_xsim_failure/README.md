# C/RTL co-simulation failure evidence

> **Status 2026-10-05.** The verdict below is the **2025.1.1** record, and the
> evidence in this directory supports it. The "Resolution (2026-09-19)" section
> further down reports a **pass under 2026.1.1**, but that run's evidence is held
> outside the repository (`C:\kv260_cosim_recovery\evidence\`), so it is
> *reported, not verified in repository*. Two caveats on it:
>
> 1. Cosim re-synthesises the RTL from source. A 2026.1.1 pass verifies
>    2026.1.1-generated RTL, **not** the packaged 2025.1.1 IP in
>    `vivado/ip_repo/` that the bitstream contains. The packaged IP is verified
>    by `../standalone_rtl_sim/` and `../standalone_rtl_stress/`.
> 2. The failing run reports `0 / 1` transactions
>    (`hls_run_cosim_axi_vip_exception.txt`), but the committed C testbench —
>    unchanged from `599da3e` until 2026-10-05 — calls the kernel three times,
>    which would show as `/ 3`. That is unexplained, so the 2026.1.1 "isolated
>    historical control" may not have reproduced the failing configuration.
>
> "Current HEAD `a5e1e07`" in the Resolution section is a documentation commit;
> its HLS source is identical to `8d075ac`.

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
- **Therefore (as assessed on 2026-09-13):** the synthesised RTL, the packaged
  IP, and the KV260 bitstream carried **no passing RTL-level functional
  verification** at any level.
  **This conclusion is SUPERSEDED — see "Resolution (2026-09-19)" below.**

`STRB_WIDTH=4` in the failing sequence corroborates the 32-bit `m_axi` gmem data
width recorded in the packaged IP's `component.xml`.

---

## Resolution (2026-09-19)

**C/RTL co-simulation now PASSES.** The evidence above is retained unmodified
as the historical record of the 2025.1.1 failure; this section records the
subsequent outcome.

### What the historical failure was

The Vitis HLS / XSim **2025.1.1** run failed **before transaction 1 retired**
(`RTL Simulation : 0 / 1 [0.00%]`), with a simulator kernel exception raised
inside the generated **AXI VIP** infrastructure (`axi_slave_seq_lib.sv`).
**No accelerator output comparison occurred in that run.** No arithmetic
mismatch between the C model and the RTL was ever demonstrated.

### Current HEAD result

Under **Vitis / XSim 2026.1.1**, current HEAD `a5e1e07` passed:

| Stage | Result |
|---|---|
| CSim | PASS |
| Synthesis | PASS |
| Verilog C/RTL co-simulation | **PASS** |

Golden vectors **0805, 0809 and 0824 were all BIT-EXACT**, **mismatch count 0**,
with **3/3 RTL transactions completed**. No `FATAL_ERROR`, no `ERROR`, no
`CRITICAL WARNING`.

### Isolated historical control

An isolated control experiment using the **exact historical source state
`8c847cd`** — the same commit that failed in 2025.1.1 — also **passed** the same
three-vector C/RTL co-simulation under 2026.1.1, likewise 3/3 transactions,
all three vectors bit-exact, mismatch count 0.

**Therefore `8c847cd` is ruled out as the necessary cause of the historical
failure.** The remaining changed factors are the **toolchain version**
(2025.1.1 → 2026.1.1) and the **host environment** (8 GB laptop → 32 GB PC).
These changed together and could not be varied independently, so **the
experiment does not uniquely determine the historical root cause.**

### Independent RTL evidence

Separately from co-simulation, standalone RTL simulation passes
**196,608 / 196,608 output pixels with zero mismatches** under both the
baseline and deterministic AXI backpressure (`STALL=1`) configurations — see
`../standalone_rtl_sim/` and `../standalone_rtl_stress/`.

### Still outstanding

**Physical KV260 hardware validation remains unperformed.** No board has been
programmed; PS–PL control, DDR access and end-to-end execution on real
hardware are untested.

Full investigation evidence (consoles, cosim/csynth reports, provenance and a
verified SHA-256 manifest) is held outside this repository at
`C:\kv260_cosim_recovery\evidence\`.
