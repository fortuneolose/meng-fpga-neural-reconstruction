# HLS evidence — current HEAD source state

These reports correspond to the **current HEAD source**, commit `8d075ac`
*"hls: bind Conv1 requant multiply for 200MHz timing closure"*.

They were produced in the ignored `hls/work/` tree and are copied here verbatim
so the HEAD result survives a workspace clean. **Original file timestamps are
preserved.** Nothing was re-run to produce them.

| Field | Value |
|---|---|
| Source commit | `8d075ac` (`hls/src/reconstruction_accel.cpp` edited 2026-09-14 20:47) |
| Tool | Vitis HLS 2025.1.1 (Build 6214317), Vivado 2025.1.1 (Build 6233196) |
| Part | `xck26-sfvc784-2LV-c` |
| Clock | 5.00 ns target (200 MHz), 12 % uncertainty (0.60 ns) |
| Config | `hls/hls_config.cfg` with `vivado.flow=impl` |
| C synthesis | 2026-09-14 20:51 |
| Vivado implementation (out-of-context) | 2026-09-15 03:07 |

## Results

| Metric | Value |
|---|---|
| Estimated clock (csynth) | **4.400 ns** |
| CP achieved post-synthesis | 4.942 ns |
| **CP achieved post-implementation** | **4.793 ns — timing met** |
| Latency | 5,637,182 cycles = **28.186 ms / image** @ 200 MHz |
| — Conv2 | 4,718,602 cycles = 23.593 ms (**84 %** of total) |
| — Conv3 | 589,835 cycles = 2.949 ms |
| — Bilinear | 262,159 cycles = 1.311 ms |
| — Conv1 | 66,574 cycles = 0.333 ms |
| Post-impl resources | LUT 5,848 · FF 4,467 · **DSP 69** · BRAM 91 · URAM 32 · SRL 241 |

This is the evidence backing the claim in the commit message of `8d075ac`.
The preceding diagnostic state (`conv1_pipeline_off_impl`, commit `07b87ea`)
used **27 DSP**; binding the Conv1 requant multiply to DSP with `latency=2`
raised that to **69 DSP** and moved post-implementation timing from 4.861 ns to
4.793 ns while latency fell from 54.725 ms to 28.186 ms.

## Files

| File | Source in `hls/work/` |
|---|---|
| `reconstruction_accel_csynth.rpt` | `hls/syn/report/reconstruction_accel_csynth.rpt` |
| `reconstruction_accel_export.rpt` | `hls/impl/report/verilog/reconstruction_accel_export.rpt` |
| `reconstruction_accel_timing_routed.rpt` | `hls/impl/verilog/report/reconstruction_accel_timing_routed.rpt` |
| `reconstruction_accel_utilization_routed.rpt` | `hls/impl/verilog/report/reconstruction_accel_utilization_routed.rpt` |
| `hls_impl_pnr.rpt` | `reports/hls_impl_pnr.rpt` |

## Scope

This is **out-of-context HLS implementation** of the accelerator alone. It is
not the integrated KV260 system result — for that see
`vivado/reports/system_routed/`, where the routed system closes at
**WNS = +0.058 ns**.

RTL co-simulation is **not** covered by this evidence and does not pass; see
`hls/reports/cosim_xsim_failure/README.md`.
