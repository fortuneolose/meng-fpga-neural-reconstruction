# Reset polarity replay experiment — evidence

The controlled experiment that resolved `docs/PROJECT_STATE.md` §6.1 and
`vivado/SCRIPTS.md` defect #2.

| Field | Value |
|---|---|
| Repository commit | **`553af34`** (`docs(project): refresh state after RTL stress verification`) |
| Branch | `kv260-integration` |
| Tool | **Vivado 2025.1.1** (64-bit), from `C:/Xilinx/2025.1.1` |
| Date | **2026-09-18** |
| Host | `Fortune`, 12th Gen Intel Core i5-1240P |
| Temporary project | `C:\Users\avent\bdreplay` — **outside** the repository, not committed |

## The question

`add_reset_200m.tcl` contains `set_property CONFIG.C_EXT_RESET_HIGH 0`, and
`fix_reset_polarity.tcl` later inserts a NOT gate without restoring it. Both
`PROJECT_STATE.md` §6.1 and `SCRIPTS.md` previously asserted that replaying the
two scripts in order would leave reset asserted permanently. That claim had never
been tested; it was inferred from reading the scripts.

## What was done

A throwaway project was built outside the repository following the documented
build sequence in `SCRIPTS.md` §1 — project creation, PS preset, HP ports,
200 MHz `PL0_REF_CTRL`, clock connections, **both reset scripts verbatim in
order**, the three SmartConnects, the address assignments, then
`validate_bd_design` and `generate_target all`.

`C_EXT_RESET_HIGH` and the `ext_reset_in` net were probed at every stage. No
synthesis or implementation was run. The real project was never opened for
write.

The exact instrumented script is preserved as `replay_instrumented.tcl`; it is
the file that produced `replay_console.txt`.

## Result

**The claim is disproved.** The property is read-only:

```
CRITICAL WARNING: [BD 41-737] Cannot set the parameter C_EXT_RESET_HIGH
                  on /rst_200m. It is read-only.
```

| Stage | `C_EXT_RESET_HIGH` | `ext_reset_in` driven by |
|---|---|---|
| after `create_bd_cell rst_200m`, before `set_property` | **1** | — |
| immediately after `set_property … 0` | **1** (rejected) | — |
| end of `add_reset_200m.tcl` | **1** | `pl_resetn0` (direct) |
| end of `fix_reset_polarity.tcl` | **1** | `resetn_inverter/Res` |
| after `validate_bd_design` | **1** | `resetn_inverter/Res` |
| after `generate_target all` | **1** | `resetn_inverter/Res` |

On `proc_sys_reset:5.0`, `C_EXT_RESET_HIGH` is owned by block-design parameter
propagation (`value_permission="bd"`, `value_src="propagated"`). It defaults to
`1` and cannot be set by the user. The `set_property … 0` line is dead code.

The replayed XCI and generated VHDL are identical to the shipped design on this
parameter — see `rst_200m_params.txt`. The replayed block design has identical
cells, identical net names and identical reset topology to the authoritative
`.bd`.

**Correct reading of the two scripts:** step 7 leaves a genuine transient
mismatch (active-low `pl_resetn0` into an input configured active-high); step 8
repairs it by inverting the signal, which is the only available remedy since the
property cannot be changed. `fix_reset_polarity.tcl` is correctly named and does
the right thing. The script sequence reproduces the correct reset topology.

This does **not** resolve `SCRIPTS.md` defect #1 — no script creates the block
design — which remains the actual reproduction blocker. See
`vivado/neural_reconstruction_bd.tcl` and `vivado/replay_bd.tcl`.

## Regression guard

`vivado/assert_reset_topology.tcl` is a read-only assertion that the topology and
the propagated value are as proven here. It contains no `set_property`, no
`connect_bd_net`, no `disconnect_bd_net` and no `save_bd_design` — it observes
only, and deliberately does not attempt to force the BD-owned property.

`assert_reset_topology.txt` records it passing against the authoritative design
and against the design reproduced by `vivado/replay_bd.tcl`, plus a negative
control against an empty block design where it fails loudly with exit code 1.

## Preserved here

| File | What |
|---|---|
| `replay_instrumented.tcl` | The exact instrumented replay script |
| `replay_console.txt` | Verbatim Vivado console transcript of the replay |
| `rst_200m_params.txt` | Replayed vs. authoritative `C_EXT_RESET_HIGH` in XCI and generated VHDL |
| `assert_reset_topology.txt` | Assertion script: two passes and a negative control |

**Not** preserved: the throwaway Vivado project itself (~33 MB of regenerable
project, IP and generated-target output), Vivado journal files and backup logs.
`replay_instrumented.tcl` regenerates the experiment.

## Evidence integrity

| File | SHA256 |
|---|---|
| `replay_console.txt` | `27286fd5743cec671dde16187b4982543c60d54bbb7eb60385cfe4f0a9ec3ba0` |
| `replay_instrumented.tcl` | `bae205e4b020df5f10ce91f36ae9ce70920d123e7220c0b7054bd2df5b0746b1` |
| `rst_200m_params.txt` | `77bf255e3cbbe7c5cb9860032887aee6d37aa79baf3a3f37b218b1c90351ece5` |
| `assert_reset_topology.txt` | `c6bb18f11007a9816592a27757b2caecd382cfb5ec284bbed7b358b716382fa6` |

The `.txt` files carry scoped `-text` rules in `.gitattributes`, so the bytes
checked out are the bytes the tool emitted regardless of `core.autocrlf`, and
continue to hash to the values above.

## Effect on the authoritative artefacts

None. Verified unchanged after every Vivado invocation in this session:

| Artefact | SHA256 |
|---|---|
| `neural_reconstruction_bd.bd` | `12ef4b3982ca04e00602ccb15c29bd7932f0d32e494862c3ba10a2d9395d7eca` |
| `rst_200m` XCI | `1068286fb77d195a4a2ad30e4ed48f67575abad7bc79eac1eec50750531601fb` |
| `neural_reconstruction_kv260_embedded.xsa` | `4b2b2bfb9b722441fa478ad354c85d87bb7f115c914943b151012dd0f7d00d74` |
| `neural_reconstruction_bd_wrapper.bit` | `0ae427314550b4e4bb8884ce09e8776b325d0ecf517bba134e4e81d7dad853f9` |

No synthesis, implementation, bitstream generation or XSA export was performed.
This experiment carries **no hardware validation** of any kind.
