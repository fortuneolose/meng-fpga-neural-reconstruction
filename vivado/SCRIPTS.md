# Vivado Tcl scripts — categorization

60 Tcl scripts in `vivado/`, preserved **in place** (no files moved, so nothing
that referenced them by path breaks). This file is the categorization; it does
not change behaviour.

> ⚠️ **Read "Known defects in the build sequence" before replaying anything.**
> The scripts as written do **not** reproduce the shipped design.

## Invocation conventions (two, undocumented until now)

| Convention | Used by | Assumption |
|---|---|---|
| Relative | most Sept-15 scripts | CWD is a repo **subdirectory** (e.g. `hls/`), so `../vivado/…` resolves into the repo |
| `subst` drives | 13 later scripts | `V:` = `vivado/kv260_project/`, `M:` = repo root |

Neither is created automatically. Establish the mapping before running anything.

---

## 1. Build / reproduction (23)

Applied in this order to build the design. Timestamps are the real sequence.

| # | Script | Purpose |
|---|---|---|
| 1 | `create_kv260_project.tcl` | Create project, part `xck26-sfvc784-2LV-c`, board `kv260_som:1.4`, set `ip_repo_paths` |
| 2 | `create_base_bd.tcl` | ⚠️ Adds `zynq_ultra_ps_e` + `reconstruction_accel` cells — **opens an existing BD, does not create one** |
| 3 | `apply_ps_preset.tcl` | Apply KV260 board preset to the PS |
| 4 | `enable_hp_ports.tcl` | Enable `S_AXI_GP2` / `S_AXI_GP3` (HP0/HP1) |
| 5 | `set_pl_clk0_200.tcl` | `PL0_REF_CTRL` → 200 MHz |
| 6 | `connect_accel_clock.tcl` | `pl_clk0` → `ap_clk`, `maxihpm0_fpd_aclk`, `saxihp0/1_fpd_aclk` |
| 7 | `add_reset_200m.tcl` | Add `proc_sys_reset` + `xlconstant`; ⚠️ sets `C_EXT_RESET_HIGH 0` |
| 8 | `fix_reset_polarity.tcl` | ⚠️ Insert `util_vector_logic` NOT on `pl_resetn0` — **does not restore the polarity property** |
| 9 | `connect_hpm1_clock.tcl` | `pl_clk0` → `maxihpm1_fpd_aclk` |
| 10 | `disable_hpm1_fpd.tcl` | Disable `M_AXI_GP1` (supersedes #9) |
| 11 | `connect_gmem0_smartconnect.tcl` | `sc_gmem0`: accel `m_axi_gmem0` → `S_AXI_HP0_FPD` |
| 12 | `connect_gmem1_smartconnect.tcl` | `sc_gmem1`: accel `m_axi_gmem1` → `S_AXI_HP1_FPD` |
| 13 | `connect_control_smartconnect.tcl` | `sc_control`: `M_AXI_HPM0_FPD` → accel `s_axi_control` |
| 14 | `assign_control_address.tcl` | Control @ `0xA000_0000`, 64K |
| 15 | `assign_gmem0_ddr_low.tcl` | gmem0 → `SAXIGP2/HP0_DDR_LOW`, `0x0`, 2G |
| 16 | `assign_gmem1_ddr_low.tcl` | gmem1 → `SAXIGP3/HP1_DDR_LOW`, `0x0`, 2G |
| 17 | `fix_ip_repo.tcl` | Re-point `ip_repo_paths`, `update_ip_catalog`, `report_ip_status` |
| 18 | `generate_bd_targets_short_fixed.tcl` | `validate_bd_design` + `generate_target all` (the working variant) |
| 19 | `create_bd_wrapper.tcl` | `make_wrapper -top`, set `neural_reconstruction_bd_wrapper` as top |
| 20 | `run_system_synth.tcl` | `launch_runs synth_1 -jobs 8` |
| 21 | `run_system_impl.tcl` | `launch_runs impl_1 -to_step route_design -jobs 8` |
| 22 | `run_write_bitstream.tcl` | `launch_runs impl_1 -to_step write_bitstream -jobs 4` |
| 23 | `export_xsa_embedded.tcl` | Set `platform.design_intent.embedded true`, `open_run impl_1`, `write_hw_platform -fixed -include_bit` |

### Known defects in the build sequence

1. **No script creates the block design.** There is no `create_bd_design` and no
   `write_bd_tcl` anywhere in the 60 scripts. Every script does
   `open_bd_design [get_files */neural_reconstruction_bd.bd]` on a BD that must
   already exist, and `create_kv260_project.tcl` never adds the `.bd` to the
   project. **The `.bd` file is therefore the authoritative design description**,
   not this script set.
2. **Reset polarity contradiction.** `add_reset_200m.tcl` sets
   `CONFIG.C_EXT_RESET_HIGH 0` and wires `pl_resetn0` straight in;
   `fix_reset_polarity.tcl` later inserts an inverter but never restores the
   property. The **shipped** design has `C_EXT_RESET_HIGH = 1` (verified in the
   generated XCI, `value_src="propagated"`; the `.bd` records no override), so
   inverter + active-high is correct. Replaying both scripts gives active-**low**
   `ext_reset_in` fed by an inverted `pl_resetn0` → **reset held asserted forever.**
3. **Unportable paths** — see the invocation conventions above.

Until #1 and #2 are fixed, reproduce from the `.bd`, not from these scripts.

---

## 2. Validation / reporting (9)

Read-only or report-producing; safe to re-run.

| Script | Purpose |
|---|---|
| `check_kv260_board.tcl` | List available `*kv260*` board parts |
| `check_ip_repo.tcl` | In-memory project; confirm the accelerator IP def resolves |
| `verify_kv260_project.tcl` | Print `board_part`, `ip_repo_paths`, accelerator IP def |
| `validate_pre_axi.tcl` | `validate_bd_design` |
| `validate-bd.tcl` | `validate_bd_design` with banner output (Sept-16 restatement) |
| `check_embedded_intent.tcl` | Print `platform.design_intent.embedded` |
| `inspect-run-status.tcl` | Print every run's `STATUS` / `PROGRESS` / `NEEDS_REFRESH` |
| `report_system_utilization.tcl` | → `system_utilization_routed.rpt` |
| `report_system_utilization_summary.tcl` | → `system_utilization_summary_routed.rpt` |

Output of the last two is preserved in `vivado/reports/system_routed/`.

---

## 3. One-off diagnostics (23)

Written to answer a single question during bring-up. Kept as a record of *why*
the design ended up as it did; not part of any build or check flow.

`inspect_interfaces.tcl` · `inspect_ps_axi_props.tcl` · `probe_s_axi_mapping.tcl` ·
`inspect_clock_reset_pins.tcl` · `inspect_reset_polarity.tcl` ·
`inspect_axi_interfaces.tcl` · `inspect_clock_metadata.tcl` ·
`inspect_smartconnect_catalog.tcl` · `inspect_smartconnect_properties.tcl` ·
`inspect_address_map.tcl` · `inspect_address_segment_properties.tcl` ·
`inspect_hpm_properties.tcl` · `inspect_m_axi_gp_properties.tcl` ·
`inspect_axi_user_widths.tcl` · `inspect_sc_gmem0_user_properties.tcl` ·
`probe_sc_user_width_writable.tcl` · `inspect_ps_hp0_properties.tcl` ·
`probe_ps_hp0_user_width_writable.tcl` · `inspect_project_top.tcl` ·
`inspect_bd.tcl` · `inspect-clocks.tcl` · `inspect-nets.tcl` · `inspect-ps-clock.tcl`

The `inspect_axi_user_widths` / `probe_*_user_width_writable` cluster records the
investigation into AXI USER-signal width propagation between the accelerator's
32-bit masters and the PS HP ports.

---

## 4. Superseded / incorrect (5)

Kept for history. **Do not use.**

| Script | Superseded by | Why |
|---|---|---|
| `export-xsa.tcl` | `export_xsa_embedded.tcl` | ❌ **Actively wrong.** Omits `open_run impl_1` *and* `platform.design_intent.embedded` — both required by the Vitis platform that actually consumed the XSA |
| `export_xsa.tcl` | `export_xsa_embedded.tcl` | No embedded design intent |
| `generate_bd_targets.tcl` | `generate_bd_targets_short_fixed.tcl` | No `ip_repo_paths` / `update_ip_catalog` |
| `generate_bd_targets_short.tcl` | `generate_bd_targets_short_fixed.tcl` | Same omission |
| `inspect-addresses.tcl` | `inspect_address_map.tcl` | Sept-16 duplicate of an existing Sept-15 script |

The hyphenated names (`export-xsa`, `validate-bd`, `inspect-addresses`,
`inspect-clocks`, `inspect-nets`, `inspect-ps-clock`, `inspect-run-status`) all
date from a second session on 2026-09-16 that re-derived work from 09-15 under a
different naming convention.
