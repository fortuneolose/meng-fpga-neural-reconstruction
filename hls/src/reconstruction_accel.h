#ifndef RECONSTRUCTION_ACCEL_H
#define RECONSTRUCTION_ACCEL_H

#include <stdint.h>

static const int INPUT_H = 128;
static const int INPUT_W = 128;

static const int OUTPUT_H = 256;
static const int OUTPUT_W = 256;

static const int CHANNELS = 8;

static const int INPUT_PIXELS =
    INPUT_H * INPUT_W;

static const int OUTPUT_PIXELS =
    OUTPUT_H * OUTPUT_W;

void reconstruction_accel(
    const uint8_t input[INPUT_PIXELS],
    uint16_t output[OUTPUT_PIXELS]
);

#endif