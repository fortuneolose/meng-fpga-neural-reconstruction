#include "../src/reconstruction_accel.h"

#include <stdint.h>

#include <fstream>
#include <iostream>
#include <string>
#include <vector>


static bool file_exists(
    const std::string &path
) {
    std::ifstream file(
        path.c_str(),
        std::ios::binary
    );

    return file.good();
}


static std::string find_data_root() {

    const char *candidates[] = {
        "hls/tb/data",
        "tb/data",
        "../tb/data",
        "../../tb/data",
        "../../../tb/data",
        "../../../../tb/data",
        "../../../../../hls/tb/data"
    };


    for (
        const char *candidate
        : candidates
    ) {

        const std::string test =
            std::string(candidate)
            + "/0805/input_lr_u8.bin";


        if (file_exists(test)) {
            return std::string(candidate);
        }
    }


    return "";
}


template <typename T>
static bool read_binary(
    const std::string &path,
    std::vector<T> &data,
    size_t count
) {
    std::ifstream file(
        path.c_str(),
        std::ios::binary
    );


    if (!file) {
        return false;
    }


    data.resize(count);


    file.read(
        reinterpret_cast<char *>(
            data.data()
        ),
        count * sizeof(T)
    );


    return (
        file.gcount()
        ==
        static_cast<std::streamsize>(
            count * sizeof(T)
        )
    );
}


// Frame selection:
//
//   (no arguments)   the three golden frames 0805, 0809, 0824
//   --all            every frame listed in <data root>/frames.txt
//   ID [ID ...]      the named frames
//
// The default is what Vitis CSim and C/RTL co-simulation run.

int main(
    int argc,
    char **argv
) {

    const std::string root =
        find_data_root();


    if (root.empty()) {

        std::cerr
            << "ERROR: could not locate "
            << "golden-vector data."
            << std::endl;

        return 1;
    }


    std::cout
        << "Golden-vector root: "
        << root
        << std::endl
        << std::endl;


    std::vector<std::string> ids;


    if (
        argc > 1
        &&
        std::string(argv[1]) == "--all"
    ) {

        std::ifstream list(
            (root + "/frames.txt").c_str()
        );

        std::string id;

        while (list >> id) {
            ids.push_back(id);
        }

        if (ids.empty()) {

            std::cerr
                << "ERROR: no frames in "
                << root
                << "/frames.txt"
                << std::endl;

            return 1;
        }

    } else if (argc > 1) {

        ids.assign(
            argv + 1,
            argv + argc
        );

    } else {

        ids = {
            "0805",
            "0809",
            "0824"
        };
    }


    bool all_passed = true;


    for (
        const std::string &id
        : ids
    ) {

        const std::string directory =
            root
            + "/"
            + id;


        std::vector<uint8_t> input;

        std::vector<uint16_t> expected;

        std::vector<uint16_t> actual(
            OUTPUT_PIXELS
        );


        if (
            !read_binary<uint8_t>(
                directory
                + "/input_lr_u8.bin",
                input,
                INPUT_PIXELS
            )
        ) {

            std::cerr
                << id
                << ": failed to read input."
                << std::endl;

            return 1;
        }


        if (
            !read_binary<uint16_t>(
                directory
                + "/output_ticks_u16.bin",
                expected,
                OUTPUT_PIXELS
            )
        ) {

            std::cerr
                << id
                << ": failed to read "
                << "expected output."
                << std::endl;

            return 1;
        }


        reconstruction_accel(
            input.data(),
            actual.data()
        );


        size_t mismatch_count = 0;

        int maximum_difference = 0;

        size_t first_mismatch = 0;


        for (
            size_t i = 0;
            i < OUTPUT_PIXELS;
            ++i
        ) {

            const int difference =
                static_cast<int>(
                    actual[i]
                )
                -
                static_cast<int>(
                    expected[i]
                );


            const int abs_difference =
                difference < 0
                ? -difference
                : difference;


            if (
                abs_difference
                > maximum_difference
            ) {
                maximum_difference =
                    abs_difference;
            }


            if (
                actual[i]
                != expected[i]
            ) {

                if (
                    mismatch_count == 0
                ) {
                    first_mismatch = i;
                }

                ++mismatch_count;
            }
        }


        if (
            mismatch_count == 0
        ) {

            std::cout
                << id
                << ": BIT-EXACT PASS"
                << std::endl;

        } else {

            all_passed = false;

            const int y =
                static_cast<int>(
                    first_mismatch
                    / OUTPUT_W
                );

            const int x =
                static_cast<int>(
                    first_mismatch
                    % OUTPUT_W
                );


            std::cout
                << id
                << ": FAIL"
                << std::endl;

            std::cout
                << "  mismatches: "
                << mismatch_count
                << " / "
                << OUTPUT_PIXELS
                << std::endl;

            std::cout
                << "  maximum tick difference: "
                << maximum_difference
                << std::endl;

            std::cout
                << "  first mismatch: "
                << "("
                << y
                << ", "
                << x
                << ")"
                << std::endl;

            std::cout
                << "  expected: "
                << expected[
                    first_mismatch
                ]
                << std::endl;

            std::cout
                << "  actual: "
                << actual[
                    first_mismatch
                ]
                << std::endl;
        }


        std::cout << std::endl;
    }


    if (!all_passed) {

        std::cout
            << "HLS C MODEL VERIFICATION: FAIL"
            << std::endl;

        return 1;
    }


    std::cout
        << "All "
        << ids.size()
        << " golden vectors "
        << "matched exactly."
        << std::endl;

    std::cout
        << "Maximum allowed difference: 0 ticks"
        << std::endl;

    std::cout
        << "HLS C MODEL VERIFICATION: PASS"
        << std::endl;


    return 0;
}