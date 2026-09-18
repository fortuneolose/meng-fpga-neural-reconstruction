set repo "C:/Users/avent/meng-fpga-neural-reconstruction"
set tmp  "C:/Users/avent/bdreplay/proj"

proc probe {label} {
    set v "<no rst_200m>"
    catch { set v [get_property CONFIG.C_EXT_RESET_HIGH [get_bd_cells rst_200m]] }
    puts "PROBE|$label|C_EXT_RESET_HIGH=$v"
    catch {
        foreach n [get_bd_nets -of_objects [get_bd_pins rst_200m/ext_reset_in]] {
            puts "PROBE|$label|ext_reset_in_net=$n pins=[get_bd_pins -of_objects $n]"
        }
    }
}

# --- steps 1-2: project + BD (note: create_bd_design is the step NO historical script performs)
create_project replay_kv260 $tmp -part xck26-sfvc784-2LV-c -force
set_property board_part xilinx.com:kv260_som:part0:1.4 [current_project]
set_property ip_repo_paths $repo/vivado/ip_repo [current_project]
update_ip_catalog
create_bd_design neural_reconstruction_bd
create_bd_cell -type ip -vlnv xilinx.com:ip:zynq_ultra_ps_e:3.5 zynq_ultra_ps_e_0
create_bd_cell -type ip -vlnv xilinx.com:hls:reconstruction_accel:1.0 reconstruction_accel_0

# --- steps 3-6
apply_bd_automation -rule xilinx.com:bd_rule:zynq_ultra_ps_e -config {apply_board_preset "1"} [get_bd_cells zynq_ultra_ps_e_0]
set ps [get_bd_cells zynq_ultra_ps_e_0]
set_property CONFIG.PSU__USE__S_AXI_GP2 1 $ps
set_property CONFIG.PSU__USE__S_AXI_GP3 1 $ps
set_property CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ 200 $ps
connect_bd_net [get_bd_pins zynq_ultra_ps_e_0/pl_clk0] [get_bd_pins reconstruction_accel_0/ap_clk] [get_bd_pins zynq_ultra_ps_e_0/maxihpm0_fpd_aclk] [get_bd_pins zynq_ultra_ps_e_0/saxihp0_fpd_aclk] [get_bd_pins zynq_ultra_ps_e_0/saxihp1_fpd_aclk]

# --- step 7: add_reset_200m.tcl  (VERBATIM BODY)
create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_200m
probe "7a_after_create_before_setprop"
set_property CONFIG.C_EXT_RESET_HIGH 0 [get_bd_cells rst_200m]
probe "7b_immediately_after_set_0"
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 reset_locked_const
set_property CONFIG.CONST_VAL 1 [get_bd_cells reset_locked_const]
connect_bd_net [get_bd_pins zynq_ultra_ps_e_0/pl_clk0] [get_bd_pins rst_200m/slowest_sync_clk]
connect_bd_net [get_bd_pins zynq_ultra_ps_e_0/pl_resetn0] [get_bd_pins rst_200m/ext_reset_in]
connect_bd_net [get_bd_pins reset_locked_const/dout] [get_bd_pins rst_200m/dcm_locked]
connect_bd_net [get_bd_pins rst_200m/peripheral_aresetn] [get_bd_pins reconstruction_accel_0/ap_rst_n]
save_bd_design
probe "7c_end_of_add_reset_200m"

# --- step 8: fix_reset_polarity.tcl  (VERBATIM BODY)
disconnect_bd_net [get_bd_nets -of_objects [get_bd_pins rst_200m/ext_reset_in]] [get_bd_pins rst_200m/ext_reset_in]
create_bd_cell -type ip -vlnv xilinx.com:ip:util_vector_logic:2.0 resetn_inverter
set_property -dict [list CONFIG.C_OPERATION {not} CONFIG.C_SIZE {1}] [get_bd_cells resetn_inverter]
connect_bd_net [get_bd_pins zynq_ultra_ps_e_0/pl_resetn0] [get_bd_pins resetn_inverter/Op1]
connect_bd_net [get_bd_pins resetn_inverter/Res] [get_bd_pins rst_200m/ext_reset_in]
save_bd_design
probe "8_end_of_fix_reset_polarity"

# --- steps 10-16
set_property CONFIG.PSU__USE__M_AXI_GP1 0 [get_bd_cells zynq_ultra_ps_e_0]
foreach {sc si mi} {sc_gmem0 x x sc_gmem1 x x sc_control x x} {}
create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:1.0 sc_gmem0
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {1} CONFIG.NUM_CLKS {1} CONFIG.HAS_ARESETN {1}] [get_bd_cells sc_gmem0]
connect_bd_intf_net [get_bd_intf_pins reconstruction_accel_0/m_axi_gmem0] [get_bd_intf_pins sc_gmem0/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins sc_gmem0/M00_AXI] [get_bd_intf_pins zynq_ultra_ps_e_0/S_AXI_HP0_FPD]
connect_bd_net [get_bd_pins zynq_ultra_ps_e_0/pl_clk0] [get_bd_pins sc_gmem0/aclk]
connect_bd_net [get_bd_pins rst_200m/interconnect_aresetn] [get_bd_pins sc_gmem0/aresetn]
create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:1.0 sc_gmem1
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {1} CONFIG.NUM_CLKS {1} CONFIG.HAS_ARESETN {1}] [get_bd_cells sc_gmem1]
connect_bd_intf_net [get_bd_intf_pins reconstruction_accel_0/m_axi_gmem1] [get_bd_intf_pins sc_gmem1/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins sc_gmem1/M00_AXI] [get_bd_intf_pins zynq_ultra_ps_e_0/S_AXI_HP1_FPD]
connect_bd_net [get_bd_pins zynq_ultra_ps_e_0/pl_clk0] [get_bd_pins sc_gmem1/aclk]
connect_bd_net [get_bd_pins rst_200m/interconnect_aresetn] [get_bd_pins sc_gmem1/aresetn]
create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:1.0 sc_control
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {1} CONFIG.NUM_CLKS {1} CONFIG.HAS_ARESETN {1}] [get_bd_cells sc_control]
connect_bd_intf_net [get_bd_intf_pins zynq_ultra_ps_e_0/M_AXI_HPM0_FPD] [get_bd_intf_pins sc_control/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins sc_control/M00_AXI] [get_bd_intf_pins reconstruction_accel_0/s_axi_control]
connect_bd_net [get_bd_pins zynq_ultra_ps_e_0/pl_clk0] [get_bd_pins sc_control/aclk]
connect_bd_net [get_bd_pins rst_200m/interconnect_aresetn] [get_bd_pins sc_control/aresetn]
assign_bd_address -offset 0xA0000000 -range 64K -target_address_space [get_bd_addr_spaces zynq_ultra_ps_e_0/Data] [get_bd_addr_segs reconstruction_accel_0/s_axi_control/Reg]
assign_bd_address -offset 0x00000000 -range 2G -target_address_space [get_bd_addr_spaces reconstruction_accel_0/Data_m_axi_gmem0] [get_bd_addr_segs zynq_ultra_ps_e_0/SAXIGP2/HP0_DDR_LOW]
assign_bd_address -offset 0x00000000 -range 2G -target_address_space [get_bd_addr_spaces reconstruction_accel_0/Data_m_axi_gmem1] [get_bd_addr_segs zynq_ultra_ps_e_0/SAXIGP3/HP1_DDR_LOW]
save_bd_design
probe "16_before_validate"

# --- step 18
validate_bd_design
probe "18a_after_validate_bd_design"
save_bd_design
generate_target all [get_files */neural_reconstruction_bd.bd]
probe "18b_after_generate_target"
puts "REPLAY_DONE"
close_project
