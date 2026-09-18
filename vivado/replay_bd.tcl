# replay_bd.tcl — portable wrapper for the exported block design.
#
# Recreates the KV260 block design from neural_reconstruction_bd.tcl in a fresh
# project, with no dependence on the caller's working directory, no subst drives
# (V: / M:) and no absolute paths. All paths are derived from [info script].
#
# WHY THIS EXISTS
#   neural_reconstruction_bd.tcl is a verbatim write_bd_tcl export and is left
#   unedited. It needs one thing it does not set itself: the custom HLS IP
#   xilinx.com:hls:reconstruction_accel:1.0 must resolve in the IP catalog, i.e.
#   ip_repo_paths must point at the repository's committed vivado/ip_repo. This
#   wrapper supplies exactly that, and nothing else.
#
#   See docs/PROJECT_STATE.md §5.1 and vivado/SCRIPTS.md defect #1: no historical
#   script creates the block design. The export plus this wrapper is the
#   reproduction path.
#
# WHAT THIS DOES NOT DO
#   No synthesis, no implementation, no bitstream, no XSA export. It builds the
#   block design only. Those steps remain deliberate, separate actions.
#
# USAGE
#   vivado -mode batch -source vivado/replay_bd.tcl -tclargs <output_project_dir>
#
#   <output_project_dir> is created if absent. If omitted, defaults to
#   ./replay_bd_project relative to the current working directory.
#
#   Keep the output directory OUTSIDE the repository, and keep the path short —
#   Vivado hits the Windows 260-byte MAX_PATH limit on deep BD/IP paths.
#
# AFTER IT COMPLETES
#   Verify the reset arrangement with the read-only assertion script:
#     vivado -mode batch -source vivado/assert_reset_topology.tcl \
#            -tclargs <output_project_dir>/replay_bd.xpr

set _script_dir [file dirname [file normalize [info script]]]
set _repo_root  [file dirname $_script_dir]
set _ip_repo    [file join $_repo_root vivado ip_repo]
set _bd_tcl     [file join $_script_dir neural_reconstruction_bd.tcl]

if {[llength $argv] > 0} {
    set _out [file normalize [lindex $argv 0]]
} else {
    set _out [file normalize replay_bd_project]
}

puts "repo root      : $_repo_root"
puts "ip_repo_paths  : $_ip_repo"
puts "bd tcl         : $_bd_tcl"
puts "output project : $_out"

if {![file isdirectory $_ip_repo]} {
    error "REPLAY_BD_ERROR: ip_repo not found at $_ip_repo"
}
if {![file exists $_bd_tcl]} {
    error "REPLAY_BD_ERROR: exported block design not found at $_bd_tcl"
}

create_project replay_bd $_out -part xck26-sfvc784-2LV-c -force
set_property board_part xilinx.com:kv260_som:part0:1.4 [current_project]

# The one prerequisite the exported Tcl does not set for itself.
set_property ip_repo_paths $_ip_repo [current_project]
update_ip_catalog

if {[llength [get_ipdefs -quiet xilinx.com:hls:reconstruction_accel:1.0]] == 0} {
    error "REPLAY_BD_ERROR: xilinx.com:hls:reconstruction_accel:1.0 did not\
           resolve after update_ip_catalog. Check $_ip_repo."
}
puts "accelerator IP resolved from committed ip_repo"

source $_bd_tcl

puts "REPLAY_BD_DONE: [current_bd_design] created in $_out"
puts "Next: vivado -mode batch -source vivado/assert_reset_topology.tcl -tclargs\
      [file join $_out replay_bd.xpr]"
