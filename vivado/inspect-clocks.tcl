open_project [file normalize {../vivado/kv260_project/neural_reconstruction_kv260.xpr}]; open_bd_design [get_files */neural_reconstruction_bd.bd]; puts {=== PS CLOCK RESET PINS ===}; puts [get_bd_pins zynq_ultra_ps_e_0/*clk*]; puts [get_bd_pins zynq_ultra_ps_e_0/*reset*]; puts {=== ACCEL CLOCK RESET PINS ===}; puts [get_bd_pins reconstruction_accel_0/*clk*]; puts [get_bd_pins reconstruction_accel_0/*rst*]



