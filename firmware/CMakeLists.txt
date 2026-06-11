cmake_minimum_required(VERSION 3.13)

# Requires the PICO_SDK_PATH environment variable to point at a pico-sdk
# checkout. (Alternative: copy ${PICO_SDK_PATH}/external/pico_sdk_import.cmake
# into this directory and include it by name.)
include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)

project(silicon_char_bench_firmware C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

add_executable(bench_payload
    payload/main.c
    payload/workloads.c
)

target_include_directories(bench_payload PRIVATE payload)

target_link_libraries(bench_payload
    pico_stdlib
    pico_unique_id
    hardware_watchdog
)

# Command protocol runs over USB CDC; UART stdio stays off.
pico_enable_stdio_usb(bench_payload 1)
pico_enable_stdio_uart(bench_payload 0)

# Emit .uf2 for BOOTSEL drag-and-drop flashing.
pico_add_extra_outputs(bench_payload)
