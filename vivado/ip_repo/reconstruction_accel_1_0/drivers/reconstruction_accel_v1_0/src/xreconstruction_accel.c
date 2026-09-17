// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2025.1.1 (64-bit)
// Tool Version Limit: 2025.05
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2025 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
/***************************** Include Files *********************************/
#include "xreconstruction_accel.h"

/************************** Function Implementation *************************/
#ifndef __linux__
int XReconstruction_accel_CfgInitialize(XReconstruction_accel *InstancePtr, XReconstruction_accel_Config *ConfigPtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(ConfigPtr != NULL);

    InstancePtr->Control_BaseAddress = ConfigPtr->Control_BaseAddress;
    InstancePtr->IsReady = XIL_COMPONENT_IS_READY;

    return XST_SUCCESS;
}
#endif

void XReconstruction_accel_Start(XReconstruction_accel *InstancePtr) {
    u32 Data;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XReconstruction_accel_ReadReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_AP_CTRL) & 0x80;
    XReconstruction_accel_WriteReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_AP_CTRL, Data | 0x01);
}

u32 XReconstruction_accel_IsDone(XReconstruction_accel *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XReconstruction_accel_ReadReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_AP_CTRL);
    return (Data >> 1) & 0x1;
}

u32 XReconstruction_accel_IsIdle(XReconstruction_accel *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XReconstruction_accel_ReadReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_AP_CTRL);
    return (Data >> 2) & 0x1;
}

u32 XReconstruction_accel_IsReady(XReconstruction_accel *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XReconstruction_accel_ReadReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_AP_CTRL);
    // check ap_start to see if the pcore is ready for next input
    return !(Data & 0x1);
}

void XReconstruction_accel_EnableAutoRestart(XReconstruction_accel *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XReconstruction_accel_WriteReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_AP_CTRL, 0x80);
}

void XReconstruction_accel_DisableAutoRestart(XReconstruction_accel *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XReconstruction_accel_WriteReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_AP_CTRL, 0);
}

void XReconstruction_accel_Set_input_r(XReconstruction_accel *InstancePtr, u64 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XReconstruction_accel_WriteReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_INPUT_R_DATA, (u32)(Data));
    XReconstruction_accel_WriteReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_INPUT_R_DATA + 4, (u32)(Data >> 32));
}

u64 XReconstruction_accel_Get_input_r(XReconstruction_accel *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XReconstruction_accel_ReadReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_INPUT_R_DATA);
    Data += (u64)XReconstruction_accel_ReadReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_INPUT_R_DATA + 4) << 32;
    return Data;
}

void XReconstruction_accel_Set_output_r(XReconstruction_accel *InstancePtr, u64 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XReconstruction_accel_WriteReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_OUTPUT_R_DATA, (u32)(Data));
    XReconstruction_accel_WriteReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_OUTPUT_R_DATA + 4, (u32)(Data >> 32));
}

u64 XReconstruction_accel_Get_output_r(XReconstruction_accel *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XReconstruction_accel_ReadReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_OUTPUT_R_DATA);
    Data += (u64)XReconstruction_accel_ReadReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_OUTPUT_R_DATA + 4) << 32;
    return Data;
}

void XReconstruction_accel_InterruptGlobalEnable(XReconstruction_accel *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XReconstruction_accel_WriteReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_GIE, 1);
}

void XReconstruction_accel_InterruptGlobalDisable(XReconstruction_accel *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XReconstruction_accel_WriteReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_GIE, 0);
}

void XReconstruction_accel_InterruptEnable(XReconstruction_accel *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XReconstruction_accel_ReadReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_IER);
    XReconstruction_accel_WriteReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_IER, Register | Mask);
}

void XReconstruction_accel_InterruptDisable(XReconstruction_accel *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XReconstruction_accel_ReadReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_IER);
    XReconstruction_accel_WriteReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_IER, Register & (~Mask));
}

void XReconstruction_accel_InterruptClear(XReconstruction_accel *InstancePtr, u32 Mask) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XReconstruction_accel_WriteReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_ISR, Mask);
}

u32 XReconstruction_accel_InterruptGetEnabled(XReconstruction_accel *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XReconstruction_accel_ReadReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_IER);
}

u32 XReconstruction_accel_InterruptGetStatus(XReconstruction_accel *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XReconstruction_accel_ReadReg(InstancePtr->Control_BaseAddress, XRECONSTRUCTION_ACCEL_CONTROL_ADDR_ISR);
}

