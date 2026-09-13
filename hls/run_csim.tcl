open_project -reset hls/reconstruction_hls

set_top reconstruction_accel

add_files hls/src/reconstruction_accel.cpp
add_files hls/src/reconstruction_accel.h
add_files hls/src/reconstruction_params.h

add_files -tb hls/tb/test_reconstruction.cpp

open_solution -reset solution1 -flow_target vivado

set_part {xck26-sfvc784-2LV-c}

create_clock -period 5.0 -name default

csim_design

exit