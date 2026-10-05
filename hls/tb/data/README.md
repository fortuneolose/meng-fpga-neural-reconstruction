# C-testbench golden vectors

Raw little-endian binaries read by `hls/tb/test_reconstruction.cpp`.
`frames.txt` lists every frame; `SHA256SUMS` hashes every `.bin` (binary files,
so the hashes are the same on any platform).

| Frames | Files | Source |
|---|---|---|
| **0805, 0809, 0824** — the primary golden frames | all 7: input, the 5 intermediates, output | Exported from `hardware_reference/golden_vectors/` by `src/export_golden_binary.py` (commit `599da3e`). Primary data |
| **0806–0808, 0810–0823** — the other 17 Round 3 validation frames | `input_lr_u8.bin`, `output_ticks_u16.bin` | Regenerated 2026-10-05, see below |

## Running

```
hls/tb/run_csim_native.sh          # the 3 primary frames (what Vitis CSim / cosim run)
hls/tb/run_csim_native.sh --all    # every frame in frames.txt
hls/tb/run_csim_native.sh 0810     # named frames
```

Under Vitis, pass the same arguments with `csim.argv` in `hls_config.cfg` (or
`csim_design -argv` in Tcl). With no arguments the testbench behaves exactly as
before.

## Provenance of the 17 regenerated frames

The original Round 3 dataset is not in the repository, but its validation
high-resolution crops are: `results/round3/comparison/<id>_target.png` are the
lossless 256×256 grayscale HR images. The frames were rebuilt from them:

1. `src/rebuild_round3_val.py` — HR = the target PNG; LR = Pillow bicubic resize
   to 128×128, exactly as `prepare_dataset_round3.py` (`save_pair`) made them.
2. `src/generate_golden_vectors.py --all` — the project's integer reference,
   whose arithmetic is unchanged since `599da3e`; only command-line options
   were added.
3. `src/export_golden_binary.py --interface-only` for the 17 new frames.

Environment: Linux, Python 3.11.15, numpy 2.4.6, **Pillow 12.3.0**.

Evidence that the method is exact, all checked 2026-10-05:

- Regenerating the 3 primary frames this way reproduces all 21 committed
  `.npy` files and all 21 `.bin` files **byte for byte**.
- The regenerated outputs reproduce `full_integer_mse` in
  `results/round4_int8/full_integer/comparison_metrics.csv` — produced by a
  separate evaluation script — for all 20 frames, worst relative difference
  6.3e-7 (float32 vs float64 arithmetic).
- `tests/check_integer_reference.py`, an independent implementation of the
  fixed-point contract, matches every frame's output, and every stage of the
  3 primary frames.
- The HLS C model (`hls/tb/run_csim_native.sh --all`, g++ 13.3) is bit-exact on
  all 20 frames.

`tests/check_golden_regeneration.py` repeats the regeneration and byte
comparison; CI runs it on every push.

Only the interface files are committed for the 17 frames; their intermediates
regenerate exactly with the commands above. The LR inputs depend on the Pillow
version — re-run the regeneration check before trusting a different one.
