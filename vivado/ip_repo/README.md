# `vivado/ip_repo/` — packaged HLS IP

Contains `reconstruction_accel_1_0/`, the Vitis HLS export of the accelerator,
packaged as an IP-XACT IP that Vivado resolves as
`xilinx.com:hls:reconstruction_accel:1.0`.

## This directory is GENERATED — and is preserved anyway

`reconstruction_accel_1_0/component.xml` is **byte-identical** to
`hls/work/hls/impl/ip/component.xml` (SHA256
`37b32cd43ddaeebd23ff2dda4acfc8b938ced2178f5b58e563792fa245e7eb1e`).
It is a verbatim copy
of the HLS export, not hand-authored. Nothing here should ever be edited by hand.

It is committed regardless, because:

1. **The block design cannot open without it.** `neural_reconstruction_bd.bd`
   references the accelerator by VLNV. Without a resolvable IP definition the BD
   fails to load, and the BD is the only authoritative description of the design.
2. **Regenerating it is expensive and currently unrepeatable.** It requires Vitis
   HLS 2025.1.1 plus a full csynth + out-of-context implementation run. The
   committed CSim/HLS runner scripts still point at Vitis 2026.1 and an old
   OneDrive path, so they will not reproduce it as written.
3. **It pins the hardware contract.** The `.dat` files under `hdl/verilog/` are
   ROM initialisation images with the quantised weights baked in, derived from
   `hardware_reference/parameters/reconstruction_params.h`.

195 files, 2.65 MB.

## Provenance

| Field | Value |
|---|---|
| Generated | 2026-09-14 20:51–20:55 |
| Source commit | `8d075ac` (`.cpp` edited 20:47, export at 20:51 — so this IP **matches current HEAD**) |
| `xilinx:xilinxVersion` | `2025.1.1` |
| `xilinx:coreRevision` | `2114786034` |
| Part / clock | `xck26-sfvc784-2LV-c`, 5 ns |
| Copied from | `hls/work/hls/impl/ip/` |

Note the commit date of `8d075ac` (09-15 10:33) lags the source edit (09-14
20:47). The IP corresponds to the **source**, not the commit timestamp.

## Interfaces

| Interface | Type | Width |
|---|---|---|
| `s_axi_control` | AXI4-Lite slave | — |
| `m_axi_gmem0` | AXI4 master (input) | **32-bit** data, 64-bit address |
| `m_axi_gmem1` | AXI4 master (output) | **32-bit** data, 64-bit address |

The 32-bit gmem width against 128-bit PS HP ports is a 4× bandwidth de-rate.
It is not currently the bottleneck — Conv2 accounts for 84 % of latency — but it
caps any future dataflow or burst optimisation.

## When to regenerate

Any change to `hls/src/`, `hls/hls_config.cfg`, or the Vitis version invalidates
this directory **and** the block design's IP instance. After regenerating, re-run
`update_ip_catalog` / `report_ip_status`, re-generate BD targets, and re-run
synthesis, implementation and timing — system WNS is only +0.058 ns, so timing
closure must not be assumed to survive.
