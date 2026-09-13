#include "reconstruction_accel.h"
#include "reconstruction_params.h"

#include <stdint.h>


// --------------------------------------------------
// Utility functions
// --------------------------------------------------

static int64_t rounded_shift_signed(
    int64_t value,
    int shift
) {
    const int64_t offset =
        ((int64_t)1 << (shift - 1));

    if (value >= 0) {
        return (
            value + offset
        ) >> shift;
    }

    return -(
        (
            (-value) + offset
        ) >> shift
    );
}


static uint8_t divide16_nearest_even(
    uint16_t value
) {
    uint16_t quotient =
        value >> 4;

    const uint16_t remainder =
        value & 0xF;

    if (
        remainder > 8
        ||
        (
            remainder == 8
            &&
            (quotient & 1)
        )
    ) {
        ++quotient;
    }

    if (quotient > 255) {
        quotient = 255;
    }

    return (uint8_t)quotient;
}


static uint8_t clamp_u8(
    int64_t value
) {
    if (value < 0) {
        return 0;
    }

    if (value > 255) {
        return 255;
    }

    return (uint8_t)value;
}


static int8_t clamp_s8(
    int64_t value
) {
    if (value < -127) {
        return -127;
    }

    if (value > 127) {
        return 127;
    }

    return (int8_t)value;
}


// --------------------------------------------------
// 2x bilinear coordinate coefficients
// --------------------------------------------------

static void axis_terms(
    int j,
    int length,
    int &index0,
    int &index1,
    int &weight0,
    int &weight1
) {
    const int output_length =
        2 * length;

    if (j == 0) {

        index0 = 0;
        index1 = 0;

        weight0 = 4;
        weight1 = 0;

    } else if (
        j == output_length - 1
    ) {

        index0 = length - 1;
        index1 = length - 1;

        weight0 = 4;
        weight1 = 0;

    } else if (
        (j & 1) == 0
    ) {

        const int i =
            j >> 1;

        index0 = i - 1;
        index1 = i;

        weight0 = 1;
        weight1 = 3;

    } else {

        const int i =
            j >> 1;

        index0 = i;
        index1 = i + 1;

        weight0 = 3;
        weight1 = 1;
    }
}


// --------------------------------------------------
// Top-level accelerator
// --------------------------------------------------

void reconstruction_accel(
    const uint8_t input[INPUT_PIXELS],
    uint16_t output[OUTPUT_PIXELS]
) {
#pragma HLS INTERFACE m_axi port=input \
    offset=slave bundle=gmem0 depth=16384

#pragma HLS INTERFACE m_axi port=output \
    offset=slave bundle=gmem1 depth=65536

#pragma HLS INTERFACE s_axilite \
    port=input bundle=control

#pragma HLS INTERFACE s_axilite \
    port=output bundle=control

#pragma HLS INTERFACE s_axilite \
    port=return bundle=control


    // This first implementation intentionally uses
    // full-frame intermediate buffers.
    //
    // It is the bit-exact baseline, not yet the
    // optimized streaming architecture.

    static uint16_t baseline_ticks
        [OUTPUT_H][OUTPUT_W];

    static uint8_t branch_input
        [OUTPUT_H][OUTPUT_W];

    static uint8_t conv1_out
        [CHANNELS][OUTPUT_H][OUTPUT_W];

    static uint8_t conv2_out
        [CHANNELS][OUTPUT_H][OUTPUT_W];


    // ------------------------------------------------
    // Integer 2x bilinear interpolation
    // ------------------------------------------------

BILINEAR_Y:
    for (
        int y = 0;
        y < OUTPUT_H;
        ++y
    ) {

        int y0;
        int y1;

        int wy0;
        int wy1;

        axis_terms(
            y,
            INPUT_H,
            y0,
            y1,
            wy0,
            wy1
        );


BILINEAR_X:
        for (
            int x = 0;
            x < OUTPUT_W;
            ++x
        ) {

            int x0;
            int x1;

            int wx0;
            int wx1;

            axis_terms(
                x,
                INPUT_W,
                x0,
                x1,
                wx0,
                wx1
            );


            const uint8_t p00 =
                input[
                    y0 * INPUT_W + x0
                ];

            const uint8_t p01 =
                input[
                    y0 * INPUT_W + x1
                ];

            const uint8_t p10 =
                input[
                    y1 * INPUT_W + x0
                ];

            const uint8_t p11 =
                input[
                    y1 * INPUT_W + x1
                ];


            const uint16_t h0 =
                ((uint16_t)p00 * wx0)
                +
                ((uint16_t)p01 * wx1);


            const uint16_t h1 =
                ((uint16_t)p10 * wx0)
                +
                ((uint16_t)p11 * wx1);


            const uint16_t ticks =
                (uint16_t)(
                    h0 * wy0
                    +
                    h1 * wy1
                );


            baseline_ticks[y][x] =
                ticks;


            branch_input[y][x] =
                divide16_nearest_even(
                    ticks
                );
        }
    }


    // ------------------------------------------------
    // Conv1
    //
    // 1 input channel
    // 8 output channels
    // 3x3, padding 1
    // ------------------------------------------------

CONV1_OC:
    for (
        int oc = 0;
        oc < 8;
        ++oc
    ) {

CONV1_Y:
        for (
            int y = 0;
            y < OUTPUT_H;
            ++y
        ) {

CONV1_X:
            for (
                int x = 0;
                x < OUTPUT_W;
                ++x
            ) {

                int32_t acc =
                    CONV1_BIAS[oc];


CONV1_KY:
                for (
                    int ky = 0;
                    ky < 3;
                    ++ky
                ) {

CONV1_KX:
                    for (
                        int kx = 0;
                        kx < 3;
                        ++kx
                    ) {

                        const int iy =
                            y + ky - 1;

                        const int ix =
                            x + kx - 1;


                        if (
                            iy >= 0
                            &&
                            iy < OUTPUT_H
                            &&
                            ix >= 0
                            &&
                            ix < OUTPUT_W
                        ) {

                            const int weight_index =
                                oc * 9
                                +
                                ky * 3
                                +
                                kx;


                            acc +=
                                (
                                    (int32_t)
                                    branch_input[iy][ix]
                                )
                                *
                                (
                                    (int32_t)
                                    CONV1_WEIGHTS[
                                        weight_index
                                    ]
                                );
                        }
                    }
                }


                const int64_t product =
                    ((int64_t)acc)
                    *
                    ((int64_t)
                        CONV1_MULT[oc]);


                const int64_t q =
                    rounded_shift_signed(
                        product,
                        REQUANT_SHIFT
                    );


                conv1_out[oc][y][x] =
                    clamp_u8(q);
            }
        }
    }


    // ------------------------------------------------
    // Conv2
    //
    // 8 input channels
    // 8 output channels
    // ------------------------------------------------

CONV2_OC:
    for (
        int oc = 0;
        oc < 8;
        ++oc
    ) {

CONV2_Y:
        for (
            int y = 0;
            y < OUTPUT_H;
            ++y
        ) {

CONV2_X:
            for (
                int x = 0;
                x < OUTPUT_W;
                ++x
            ) {

                int32_t acc =
                    CONV2_BIAS[oc];


CONV2_IC:
                for (
                    int ic = 0;
                    ic < 8;
                    ++ic
                ) {

CONV2_KY:
                    for (
                        int ky = 0;
                        ky < 3;
                        ++ky
                    ) {

CONV2_KX:
                        for (
                            int kx = 0;
                            kx < 3;
                            ++kx
                        ) {

                            const int iy =
                                y + ky - 1;

                            const int ix =
                                x + kx - 1;


                            if (
                                iy >= 0
                                &&
                                iy < OUTPUT_H
                                &&
                                ix >= 0
                                &&
                                ix < OUTPUT_W
                            ) {

                                const int weight_index =
                                    (
                                        oc * 8
                                        + ic
                                    )
                                    * 9
                                    +
                                    ky * 3
                                    +
                                    kx;


                                acc +=
                                    (
                                        (int32_t)
                                        conv1_out[
                                            ic
                                        ][iy][ix]
                                    )
                                    *
                                    (
                                        (int32_t)
                                        CONV2_WEIGHTS[
                                            weight_index
                                        ]
                                    );
                            }
                        }
                    }
                }


                const int64_t product =
                    ((int64_t)acc)
                    *
                    ((int64_t)
                        CONV2_MULT[oc]);


                const int64_t q =
                    rounded_shift_signed(
                        product,
                        REQUANT_SHIFT
                    );


                conv2_out[oc][y][x] =
                    clamp_u8(q);
            }
        }
    }


    // ------------------------------------------------
    // Conv3 + residual conversion + final add
    // ------------------------------------------------

CONV3_Y:
    for (
        int y = 0;
        y < OUTPUT_H;
        ++y
    ) {

CONV3_X:
        for (
            int x = 0;
            x < OUTPUT_W;
            ++x
        ) {

            int32_t acc =
                CONV3_BIAS[0];


CONV3_IC:
            for (
                int ic = 0;
                ic < 8;
                ++ic
            ) {

CONV3_KY:
                for (
                    int ky = 0;
                    ky < 3;
                    ++ky
                ) {

CONV3_KX:
                    for (
                        int kx = 0;
                        kx < 3;
                        ++kx
                    ) {

                        const int iy =
                            y + ky - 1;

                        const int ix =
                            x + kx - 1;


                        if (
                            iy >= 0
                            &&
                            iy < OUTPUT_H
                            &&
                            ix >= 0
                            &&
                            ix < OUTPUT_W
                        ) {

                            const int weight_index =
                                ic * 9
                                +
                                ky * 3
                                +
                                kx;


                            acc +=
                                (
                                    (int32_t)
                                    conv2_out[
                                        ic
                                    ][iy][ix]
                                )
                                *
                                (
                                    (int32_t)
                                    CONV3_WEIGHTS[
                                        weight_index
                                    ]
                                );
                        }
                    }
                }
            }


            const int64_t requant_product =
                ((int64_t)acc)
                *
                ((int64_t)
                    CONV3_MULT[0]);


            const int64_t residual_q_raw =
                rounded_shift_signed(
                    requant_product,
                    REQUANT_SHIFT
                );


            const int8_t residual_q =
                clamp_s8(
                    residual_q_raw
                );


            const int64_t residual_product =
                ((int64_t)residual_q)
                *
                ((int64_t)
                    RESIDUAL_TO_OUTPUT_MULT);


            const int64_t residual_ticks =
                rounded_shift_signed(
                    residual_product,
                    FINAL_SHIFT
                );


            int32_t final_value =
                ((int32_t)
                    baseline_ticks[y][x])
                +
                ((int32_t)
                    residual_ticks);


            if (final_value < 0) {
                final_value = 0;
            }

            if (
                final_value > OUTPUT_DEN
            ) {
                final_value = OUTPUT_DEN;
            }


            output[
                y * OUTPUT_W + x
            ] = (
                (uint16_t)final_value
            );
        }
    }
}