@echo off
call "C:\AMDDesignTools\2026.1\Vitis\.settings64-Vitis_for_HLS.bat"

cd /d "C:\Users\avent\OneDrive\Documents\meng-fpga-neural-reconstruction"

"C:\AMDDesignTools\2026.1\Vitis\bin\unwrapped\win64.o\vitis_hls.exe" -f hls\run_csim.tcl

exit /b %ERRORLEVEL%
