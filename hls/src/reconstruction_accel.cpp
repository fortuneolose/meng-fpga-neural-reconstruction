#include "reconstruction_accel.h"
#include "reconstruction_params.h"

#include <stdint.h>
#include <ap_int.h>


// --------------------------------------------------
// Packed CNN feature-map word
//
// 8 channels x 8 bits = 64 bits:
//
// bits  7:0   -> channel 0
// bits 15:8   -> channel 1
// bits 23:16  -> channel 2
// bits 31:24  -> channel 3
// bits 39:32  -> channel 4
// bits 47:40  -> channel 5
// bits 55:48  -> channel 6
// bits 63:56  -> channel 7
// --------------------------------------------------

typedef ap_uint<64> feature_word_t;


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


    // ------------------------------------------------
    // Intermediate storage
    //
    // baseline_ticks:
    //     exact integer bilinear result in output ticks
    //
    // branch_input:
    //     UINT8 input to the CNN residual branch
    //
    // conv1_out / conv2_out:
    //     eight 8-bit feature channels packed into one
    //     64-bit word for every output pixel.
    // ------------------------------------------------

    static uint16_t baseline_ticks
        [OUTPUT_H][OUTPUT_W];

    static uint8_t branch_input
        [OUTPUT_H][OUTPUT_W];

    static uint8_t conv1_line0[OUTPUT_W + 2];
    static uint8_t conv1_line1[OUTPUT_W + 2];

    static feature_word_t conv1_out
        [OUTPUT_H][OUTPUT_W];

    static feature_word_t conv2_out
        [OUTPUT_H][OUTPUT_W];


    // Store the two large CNN feature maps in UltraRAM.
    //
    // Packing all eight channels into one 64-bit word
    // makes much better use of the physical URAM width
    // than the previous eight-bit-wide memory layout.

#pragma HLS bind_storage variable=conv1_line0 type=ram_s2p impl=bram
#pragma HLS bind_storage variable=conv1_line1 type=ram_s2p impl=bram

#pragma HLS bind_storage variable=conv1_out type=ram_1p impl=uram
#pragma HLS bind_storage variable=conv2_out type=ram_1p impl=uram

#pragma HLS ARRAY_PARTITION variable=CONV1_WEIGHTS cyclic factor=9 dim=1
#pragma HLS ARRAY_PARTITION variable=CONV2_WEIGHTS cyclic factor=8 dim=1
#pragma HLS ARRAY_PARTITION variable=CONV3_WEIGHTS block factor=8 dim=1

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
    // 3x3
    // padding 1
    //
    // All eight output channels for one pixel are
    // collected into a single 64-bit feature word.
    // ------------------------------------------------

    uint8_t win00 = 0, win01 = 0, win02 = 0;
    uint8_t win10 = 0, win11 = 0, win12 = 0;
    uint8_t win20 = 0, win21 = 0, win22 = 0;

CONV1_Y_PAD:
    for (int py = 0; py < OUTPUT_H + 2; ++py) {
    CONV1_X_PAD:
        for (int px = 0; px < OUTPUT_W + 2; ++px) {
#pragma HLS PIPELINE II=1

            uint8_t current = 0;

            if (
                py > 0
                &&
                py <= OUTPUT_H
                &&
                px > 0
                &&
                px <= OUTPUT_W
            ) {
                current =
                    branch_input[
                        py - 1
                    ][
                        px - 1
                    ];
            }

            const uint8_t row_m2 =
                conv1_line0[px];

            const uint8_t row_m1 =
                conv1_line1[px];

            conv1_line0[px] =
                row_m1;

            conv1_line1[px] =
                current;

            if (px == 0) {
                win00 = 0;
                win01 = 0;
                win02 = 0;
                win10 = 0;
                win11 = 0;
                win12 = 0;
                win20 = 0;
                win21 = 0;
                win22 = 0;
            }

            win00 = win01;
            win01 = win02;
            win02 = row_m2;

            win10 = win11;
            win11 = win12;
            win12 = row_m1;

            win20 = win21;
            win21 = win22;
            win22 = current;

            if (
                py >= 2
                &&
                px >= 2
            ) {
                feature_word_t packed =
                    0;

            CONV1_OC:
                for (
                    int oc = 0;
                    oc < CHANNELS;
                    ++oc
                ) {
#pragma HLS PIPELINE II=1

#pragma HLS UNROLL factor=8
                    const int weight_base =
                        oc * 9;

                    int32_t acc =
                        CONV1_BIAS[oc];

                    acc += (int32_t)win00 * (int32_t)CONV1_WEIGHTS[weight_base + 0];
                    acc += (int32_t)win01 * (int32_t)CONV1_WEIGHTS[weight_base + 1];
                    acc += (int32_t)win02 * (int32_t)CONV1_WEIGHTS[weight_base + 2];
                    acc += (int32_t)win10 * (int32_t)CONV1_WEIGHTS[weight_base + 3];
                    acc += (int32_t)win11 * (int32_t)CONV1_WEIGHTS[weight_base + 4];
                    acc += (int32_t)win12 * (int32_t)CONV1_WEIGHTS[weight_base + 5];
                    acc += (int32_t)win20 * (int32_t)CONV1_WEIGHTS[weight_base + 6];
                    acc += (int32_t)win21 * (int32_t)CONV1_WEIGHTS[weight_base + 7];
                    acc += (int32_t)win22 * (int32_t)CONV1_WEIGHTS[weight_base + 8];

                    const int64_t product =
                        ((int64_t)acc)
                        *
                        (
                            (int64_t)
                            CONV1_MULT[oc]
                        );

                    #pragma HLS bind_op variable=product op=mul impl=dsp latency=2

                    const int64_t q =
                        rounded_shift_signed(
                            product,
                            REQUANT_SHIFT
                        );

                    const uint8_t q8 =
                        clamp_u8(q);

                    packed.range(
                        oc * 8 + 7,
                        oc * 8
                    ) = q8;
                }

                conv1_out[
                    py - 2
                ][
                    px - 2
                ] = packed;
            }
        }
    }


     // ------------------------------------------------
    // Conv2
    //
    // 8 input channels
    // 8 output channels
    // 3x3
    // padding 1
    //
    // Channel-parallel implementation:
    //
    // Each 64-bit feature word contains all eight
    // UINT8 input channels for one spatial location.
    //
    // One packed URAM read therefore supplies all
    // eight activations required for one kernel
    // position.
    //
    // Eight channel multiplications are evaluated
    // in parallel and reduced through an adder tree.
    // ------------------------------------------------

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

            feature_word_t packed =
                0;


        CONV2_OC:
            for (
                int oc = 0;
                oc < CHANNELS;
                ++oc
            ) {

                int32_t acc =
                    CONV2_BIAS[oc];


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

#pragma HLS PIPELINE II=1

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

                            // One 64-bit URAM read
                            // supplies all 8 channels.

                            const feature_word_t word =
                                conv1_out[
                                    iy
                                ][ix];


                            const uint8_t a0 =
                                (uint8_t)word.range(7, 0);

                            const uint8_t a1 =
                                (uint8_t)word.range(15, 8);

                            const uint8_t a2 =
                                (uint8_t)word.range(23, 16);

                            const uint8_t a3 =
                                (uint8_t)word.range(31, 24);

                            const uint8_t a4 =
                                (uint8_t)word.range(39, 32);

                            const uint8_t a5 =
                                (uint8_t)word.range(47, 40);

                            const uint8_t a6 =
                                (uint8_t)word.range(55, 48);

                            const uint8_t a7 =
                                (uint8_t)word.range(63, 56);


                            // Weight layout:
                            //
                            // [output_channel]
                            // [input_channel]
                            // [3x3 kernel]
                            //
                            // For a fixed output channel and
                            // kernel location, input-channel
                            // weights are spaced nine entries
                            // apart.

                            const int kernel_index =
                                ky * 3 + kx;

                            const int weight_base =
                                oc * CHANNELS * 9
                                +
                                kernel_index;


                            // Eight channel products.
                            //
                            // These are independent and can be
                            // implemented concurrently.

                            const int32_t p0 =
                                ((int32_t)a0)
                                *
                                ((int32_t)
                                    CONV2_WEIGHTS[
                                        weight_base
                                        +
                                        0 * 9
                                    ]);

                            const int32_t p1 =
                                ((int32_t)a1)
                                *
                                ((int32_t)
                                    CONV2_WEIGHTS[
                                        weight_base
                                        +
                                        1 * 9
                                    ]);

                            const int32_t p2 =
                                ((int32_t)a2)
                                *
                                ((int32_t)
                                    CONV2_WEIGHTS[
                                        weight_base
                                        +
                                        2 * 9
                                    ]);

                            const int32_t p3 =
                                ((int32_t)a3)
                                *
                                ((int32_t)
                                    CONV2_WEIGHTS[
                                        weight_base
                                        +
                                        3 * 9
                                    ]);

                            const int32_t p4 =
                                ((int32_t)a4)
                                *
                                ((int32_t)
                                    CONV2_WEIGHTS[
                                        weight_base
                                        +
                                        4 * 9
                                    ]);

                            const int32_t p5 =
                                ((int32_t)a5)
                                *
                                ((int32_t)
                                    CONV2_WEIGHTS[
                                        weight_base
                                        +
                                        5 * 9
                                    ]);

                            const int32_t p6 =
                                ((int32_t)a6)
                                *
                                ((int32_t)
                                    CONV2_WEIGHTS[
                                        weight_base
                                        +
                                        6 * 9
                                    ]);

                            const int32_t p7 =
                                ((int32_t)a7)
                                *
                                ((int32_t)
                                    CONV2_WEIGHTS[
                                        weight_base
                                        +
                                        7 * 9
                                    ]);


                            // Balanced reduction tree.

                            const int32_t s01 =
                                p0 + p1;

                            const int32_t s23 =
                                p2 + p3;

                            const int32_t s45 =
                                p4 + p5;

                            const int32_t s67 =
                                p6 + p7;


                            const int32_t s0123 =
                                s01 + s23;

                            const int32_t s4567 =
                                s45 + s67;


                            const int32_t channel_sum =
                                s0123 + s4567;


                            acc +=
                                channel_sum;
                        }
                    }
                }


                const int64_t product =
                    ((int64_t)acc)
                    *
                    (
                        (int64_t)
                        CONV2_MULT[oc]
                    );


                const int64_t q =
                    rounded_shift_signed(
                        product,
                        REQUANT_SHIFT
                    );


                const uint8_t q8 =
                    clamp_u8(q);


                packed.range(
                    oc * 8 + 7,
                    oc * 8
                ) = q8;
            }


            conv2_out[y][x] =
                packed;
        }
    }
     // ------------------------------------------------
    // Conv3
    //
    // 8 input channels
    // 1 output channel
    // 3x3
    // padding 1
    //
    // Channel-parallel implementation:
    //
    // One packed 64-bit Conv2 feature word supplies
    // all eight UINT8 input channels for one spatial
    // kernel position.
    //
    // Eight products are evaluated in parallel and
    // reduced with a balanced integer adder tree.
    //
    // Followed by:
    //     residual requantisation
    //     residual-to-output conversion
    //     skip addition
    //     final clipping
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

#pragma HLS PIPELINE II=1

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

                        // One packed URAM read supplies
                        // all eight Conv2 channels.

                        const feature_word_t word =
                            conv2_out[
                                iy
                            ][ix];


                        const uint8_t a0 =
                            (uint8_t)word.range(7, 0);

                        const uint8_t a1 =
                            (uint8_t)word.range(15, 8);

                        const uint8_t a2 =
                            (uint8_t)word.range(23, 16);

                        const uint8_t a3 =
                            (uint8_t)word.range(31, 24);

                        const uint8_t a4 =
                            (uint8_t)word.range(39, 32);

                        const uint8_t a5 =
                            (uint8_t)word.range(47, 40);

                        const uint8_t a6 =
                            (uint8_t)word.range(55, 48);

                        const uint8_t a7 =
                            (uint8_t)word.range(63, 56);


                        const int kernel_index =
                            ky * 3 + kx;


                        // Conv3 layout:
                        //
                        // [input_channel][3x3 kernel]
                        //
                        // Input-channel weights are spaced
                        // nine entries apart.

                        const int32_t p0 =
                            ((int32_t)a0)
                            *
                            ((int32_t)
                                CONV3_WEIGHTS[
                                    kernel_index
                                    +
                                    0 * 9
                                ]);

                        const int32_t p1 =
                            ((int32_t)a1)
                            *
                            ((int32_t)
                                CONV3_WEIGHTS[
                                    kernel_index
                                    +
                                    1 * 9
                                ]);

                        const int32_t p2 =
                            ((int32_t)a2)
                            *
                            ((int32_t)
                                CONV3_WEIGHTS[
                                    kernel_index
                                    +
                                    2 * 9
                                ]);

                        const int32_t p3 =
                            ((int32_t)a3)
                            *
                            ((int32_t)
                                CONV3_WEIGHTS[
                                    kernel_index
                                    +
                                    3 * 9
                                ]);

                        const int32_t p4 =
                            ((int32_t)a4)
                            *
                            ((int32_t)
                                CONV3_WEIGHTS[
                                    kernel_index
                                    +
                                    4 * 9
                                ]);

                        const int32_t p5 =
                            ((int32_t)a5)
                            *
                            ((int32_t)
                                CONV3_WEIGHTS[
                                    kernel_index
                                    +
                                    5 * 9
                                ]);

                        const int32_t p6 =
                            ((int32_t)a6)
                            *
                            ((int32_t)
                                CONV3_WEIGHTS[
                                    kernel_index
                                    +
                                    6 * 9
                                ]);

                        const int32_t p7 =
                            ((int32_t)a7)
                            *
                            ((int32_t)
                                CONV3_WEIGHTS[
                                    kernel_index
                                    +
                                    7 * 9
                                ]);


                        // Balanced reduction tree.

                        const int32_t s01 =
                            p0 + p1;

                        const int32_t s23 =
                            p2 + p3;

                        const int32_t s45 =
                            p4 + p5;

                        const int32_t s67 =
                            p6 + p7;


                        const int32_t s0123 =
                            s01 + s23;

                        const int32_t s4567 =
                            s45 + s67;


                        const int32_t channel_sum =
                            s0123 + s4567;


                        acc +=
                            channel_sum;
                    }
                }
            }


            const int64_t requant_product =
                ((int64_t)acc)
                *
                (
                    (int64_t)
                    CONV3_MULT[0]
                );


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
                (
                    (int64_t)
                    RESIDUAL_TO_OUTPUT_MULT
                );


            const int64_t residual_ticks =
                rounded_shift_signed(
                    residual_product,
                    FINAL_SHIFT
                );


            int32_t final_value =
                (
                    (int32_t)
                    baseline_ticks[y][x]
                )
                +
                (
                    (int32_t)
                    residual_ticks
                );


            if (
                final_value < 0
            ) {
                final_value = 0;
            }


            if (
                final_value > OUTPUT_DEN
            ) {
                final_value =
                    OUTPUT_DEN;
            }


            output[
                y * OUTPUT_W + x
            ] =
                (uint16_t)final_value;
        }
    }
}
