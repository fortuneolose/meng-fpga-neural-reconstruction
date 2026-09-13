@echo off
setlocal

echo ==========================================
echo AMD Vitis 2026.1 HLS C Simulation
echo ==========================================
echo.

call C:\AMDDesignTools\2026.1\Vitis\settings64.bat

if errorlevel 1 (
    echo ERROR: Failed to initialize Vitis environment.
    exit /b 1
)

cd /d "C:\Users\avent\OneDrive\Documents\meng-fpga-neural-reconstruction"

echo.
echo Checking Vitis environment...
echo.

where vitis-run

if errorlevel 1 (
    echo ERROR: vitis-run was not found after settings64.bat.
    exit /b 1
)

echo.
vitis-run --version

echo.
echo Starting HLS C simulation...
echo.

vitis-run --mode hls --csim --config hls\hls_config.cfg --work_dir hls\work

set VITIS_EXIT=%ERRORLEVEL%

echo.
echo ==========================================
echo Vitis exit code: %VITIS_EXIT%
echo ==========================================

exit /b %VITIS_EXIT%