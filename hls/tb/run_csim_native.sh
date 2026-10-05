#!/usr/bin/env bash
# Build and run the HLS C testbench natively with g++, without Vitis.
#
# The kernel only needs ap_uint<>, so it compiles against Xilinx's open-source
# arbitrary-precision headers (Apache-2.0), pinned to a fixed commit:
#   https://github.com/Xilinx/HLS_arbitrary_Precision_Types
#
# This is a functional check of the C model against the golden vectors. It is
# not Vitis CSim, and it says nothing about the synthesised RTL.
#
# Usage:  hls/tb/run_csim_native.sh [extra testbench arguments]
#
# Environment:
#   AP_TYPES_INCLUDE  use an existing include directory instead of fetching
#   CXX               compiler (default g++)

set -euo pipefail

AP_TYPES_REPO="https://github.com/Xilinx/HLS_arbitrary_Precision_Types.git"
AP_TYPES_COMMIT="200a9aecaadf471592558540dc5a88256cbf880f"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
hls_dir="$(cd "${script_dir}/.." && pwd)"
work_dir="${script_dir}/.native"

mkdir -p "${work_dir}"

if [[ -z "${AP_TYPES_INCLUDE:-}" ]]; then
    ap_dir="${work_dir}/ap_types"
    if [[ "$(git -C "${ap_dir}" rev-parse HEAD 2>/dev/null || true)" != "${AP_TYPES_COMMIT}" ]]; then
        rm -rf "${ap_dir}"
        git init -q "${ap_dir}"
        git -C "${ap_dir}" fetch -q --depth 1 "${AP_TYPES_REPO}" "${AP_TYPES_COMMIT}"
        git -C "${ap_dir}" checkout -q FETCH_HEAD
    fi
    AP_TYPES_INCLUDE="${ap_dir}/include"
fi

"${CXX:-g++}" -std=c++14 -O2 \
    -Wall -Wextra -Wno-unknown-pragmas -Wno-unused-label \
    -isystem "${AP_TYPES_INCLUDE}" -I"${hls_dir}/src" \
    "${hls_dir}/src/reconstruction_accel.cpp" \
    "${hls_dir}/tb/test_reconstruction.cpp" \
    -o "${work_dir}/test_reconstruction"

cd "${hls_dir}"
exec "${work_dir}/test_reconstruction" "$@"
