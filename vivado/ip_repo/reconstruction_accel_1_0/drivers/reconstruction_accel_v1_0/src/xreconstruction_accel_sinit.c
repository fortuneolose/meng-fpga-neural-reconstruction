// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2025.1.1 (64-bit)
// Tool Version Limit: 2025.05
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2025 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
#ifndef __linux__

#include "xstatus.h"
#ifdef SDT
#include "xparameters.h"
#endif
#include "xreconstruction_accel.h"

extern XReconstruction_accel_Config XReconstruction_accel_ConfigTable[];

#ifdef SDT
XReconstruction_accel_Config *XReconstruction_accel_LookupConfig(UINTPTR BaseAddress) {
	XReconstruction_accel_Config *ConfigPtr = NULL;

	int Index;

	for (Index = (u32)0x0; XReconstruction_accel_ConfigTable[Index].Name != NULL; Index++) {
		if (!BaseAddress || XReconstruction_accel_ConfigTable[Index].Control_BaseAddress == BaseAddress) {
			ConfigPtr = &XReconstruction_accel_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XReconstruction_accel_Initialize(XReconstruction_accel *InstancePtr, UINTPTR BaseAddress) {
	XReconstruction_accel_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XReconstruction_accel_LookupConfig(BaseAddress);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XReconstruction_accel_CfgInitialize(InstancePtr, ConfigPtr);
}
#else
XReconstruction_accel_Config *XReconstruction_accel_LookupConfig(u16 DeviceId) {
	XReconstruction_accel_Config *ConfigPtr = NULL;

	int Index;

	for (Index = 0; Index < XPAR_XRECONSTRUCTION_ACCEL_NUM_INSTANCES; Index++) {
		if (XReconstruction_accel_ConfigTable[Index].DeviceId == DeviceId) {
			ConfigPtr = &XReconstruction_accel_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XReconstruction_accel_Initialize(XReconstruction_accel *InstancePtr, u16 DeviceId) {
	XReconstruction_accel_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XReconstruction_accel_LookupConfig(DeviceId);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XReconstruction_accel_CfgInitialize(InstancePtr, ConfigPtr);
}
#endif

#endif

