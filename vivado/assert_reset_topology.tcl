# assert_reset_topology.tcl — READ-ONLY reset topology assertion.
#
# Verifies that the block design carries the reset arrangement proven correct in
# docs/PROJECT_STATE.md §6.1:
#
#   zynq_ultra_ps_e_0/pl_resetn0  ->  resetn_inverter/Op1
#   resetn_inverter/Res           ->  rst_200m/ext_reset_in
#   rst_200m C_EXT_RESET_HIGH     == 1
#
# WHY THIS EXISTS
#   C_EXT_RESET_HIGH on proc_sys_reset:5.0 is owned by block-design parameter
#   propagation (value_permission="bd") and is READ-ONLY. It cannot be forced,
#   and must not be. This script therefore only *observes* — it is a regression
#   guard against the topology silently changing, not a repair.
#
#   Run it after validate_bd_design / generate_target, when propagation has
#   settled.
#
# THIS SCRIPT MUST NEVER MUTATE THE DESIGN.
#   Only getters are used. There is deliberately no set_property, no
#   connect_bd_net, no disconnect_bd_net and no save_bd_design anywhere below.
#
# USAGE
#   With a project to open:
#     vivado -mode batch -source vivado/assert_reset_topology.tcl \
#            -tclargs <path/to/project.xpr>
#   With a block design already open in the current session:
#     source vivado/assert_reset_topology.tcl
#
# EXIT
#   Silent success prints ASSERT_RESET_TOPOLOGY_PASS and returns 0.
#   Any disagreement prints every failure and raises a Tcl error (non-zero exit).

set _failures [list]

proc _fail {msg} {
    global _failures
    lappend _failures $msg
    puts "ASSERT FAIL | $msg"
}

proc _ok {msg} {
    puts "ASSERT OK   | $msg"
}

# --- open a project only if one was given and nothing is open -----------------
set _opened_here 0
if {[llength $argv] > 0} {
    set _xpr [lindex $argv 0]
    puts "Opening project: $_xpr"
    open_project $_xpr
    set _opened_here 1
}

set _bd ""
catch { set _bd [current_bd_design -quiet] }
if {$_bd eq ""} {
    set _bdfile [get_files -quiet */neural_reconstruction_bd.bd]
    if {$_bdfile eq ""} {
        error "ASSERT_RESET_TOPOLOGY_ERROR: no block design open and none found"
    }
    open_bd_design $_bdfile
}
puts "Block design: [current_bd_design]"
puts "-----------------------------------------------------------------------"

# --- 1. cells exist -----------------------------------------------------------
foreach _cell {zynq_ultra_ps_e_0 resetn_inverter rst_200m} {
    if {[llength [get_bd_cells -quiet $_cell]] == 0} {
        _fail "cell missing: $_cell"
    } else {
        _ok "cell present: $_cell"
    }
}

# --- 2. inverter is actually a NOT --------------------------------------------
if {[llength [get_bd_cells -quiet resetn_inverter]] > 0} {
    set _op [get_property CONFIG.C_OPERATION [get_bd_cells resetn_inverter]]
    if {$_op ne "not"} {
        _fail "resetn_inverter C_OPERATION is '$_op', expected 'not'"
    } else {
        _ok "resetn_inverter C_OPERATION = not"
    }
}

# --- 3. pl_resetn0 -> resetn_inverter/Op1 -------------------------------------
set _pins_a {}
catch {
    set _net_a [get_bd_nets -quiet -of_objects [get_bd_pins zynq_ultra_ps_e_0/pl_resetn0]]
    if {$_net_a ne ""} { set _pins_a [lsort [get_bd_pins -quiet -of_objects $_net_a]] }
}
if {[lsearch -exact $_pins_a "/resetn_inverter/Op1"] < 0} {
    _fail "pl_resetn0 does not drive resetn_inverter/Op1 (net pins: $_pins_a)"
} else {
    _ok "pl_resetn0 -> resetn_inverter/Op1"
}

# pl_resetn0 must NOT still reach rst_200m/ext_reset_in directly
if {[lsearch -exact $_pins_a "/rst_200m/ext_reset_in"] >= 0} {
    _fail "pl_resetn0 drives rst_200m/ext_reset_in DIRECTLY — inverter bypassed"
}

# --- 4. resetn_inverter/Res -> rst_200m/ext_reset_in --------------------------
set _pins_b {}
catch {
    set _net_b [get_bd_nets -quiet -of_objects [get_bd_pins rst_200m/ext_reset_in]]
    if {$_net_b ne ""} { set _pins_b [lsort [get_bd_pins -quiet -of_objects $_net_b]] }
}
if {[lsearch -exact $_pins_b "/resetn_inverter/Res"] < 0} {
    _fail "rst_200m/ext_reset_in is not driven by resetn_inverter/Res (net pins: $_pins_b)"
} else {
    _ok "resetn_inverter/Res -> rst_200m/ext_reset_in"
}

# --- 5. C_EXT_RESET_HIGH == 1 (observed, never forced) ------------------------
if {[llength [get_bd_cells -quiet rst_200m]] > 0} {
    set _erh [get_property CONFIG.C_EXT_RESET_HIGH [get_bd_cells rst_200m]]
    if {$_erh ne "1"} {
        _fail "rst_200m C_EXT_RESET_HIGH = '$_erh', expected '1' — with an\
               inverted pl_resetn0 this would hold reset asserted. Do NOT force\
               this property; it is BD-propagated and read-only. Investigate the\
               topology instead."
    } else {
        _ok "rst_200m C_EXT_RESET_HIGH = 1"
    }
}

# --- verdict ------------------------------------------------------------------
puts "-----------------------------------------------------------------------"
if {$_opened_here} { close_project }

if {[llength $_failures] > 0} {
    puts "ASSERT_RESET_TOPOLOGY_FAIL: [llength $_failures] check(s) failed"
    foreach _f $_failures { puts "  - $_f" }
    error "ASSERT_RESET_TOPOLOGY_FAIL: [llength $_failures] check(s) failed"
}
puts "ASSERT_RESET_TOPOLOGY_PASS"
