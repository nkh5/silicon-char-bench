/* Workload kernels for the bench payload.
 *
 * Pure C11, no pico-sdk dependencies, so the same code compiles on a host
 * compiler for self-test (firmware/host_test/test_workloads.c) and on the
 * DUT.
 */
#ifndef WORKLOADS_H
#define WORKLOADS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* 16 KiB shared workload buffer (RP2040 has 264 KiB SRAM, RP2350 520 KiB). */
#define WORKLOAD_BUF_WORDS 4096u

/* CRC workload: buffer filled by xorshift32(CRC_SEED), CRC-32/ISO-HDLC over
 * its little-endian byte image. CRC_EXPECTED is pinned independently in
 * tests/test_crc_reference.py via zlib, and bench/dut.py recomputes it on
 * the host at soak time, so a transcription error here cannot pass silently.
 */
#define CRC_SEED     0x1234ABCDu
#define CRC_EXPECTED 0xC0C5191Fu

typedef struct {
    size_t   index;    /* word index of the first failing read */
    uint32_t expected;
    uint32_t got;
    int      element;  /* march element 1..6 */
} march_fault_t;

/* March C- over a word array:
 *   1. up   (w0)        2. up   (r0, w1)     3. up   (r1, w0)
 *   4. down (r0, w1)    5. down (r1, w0)     6. up   (r0)
 * "0" is pattern p0, "1" is pattern p1 (call with 0x00000000/0xFFFFFFFF and
 * again with 0x55555555/0xAAAAAAAA). Returns true on pass; on failure fills
 * *fault and stops.
 */
bool march_c_minus(volatile uint32_t *buf, size_t words,
                   uint32_t p0, uint32_t p1, march_fault_t *fault);

/* Marsaglia xorshift32 fill; seed must be nonzero. Mirrors
 * bench.dut.xorshift32_words on the host. */
void fill_xorshift32(uint32_t *buf, size_t words, uint32_t seed);

/* Bitwise CRC-32/ISO-HDLC (poly 0xEDB88320 reflected, init and final XOR
 * 0xFFFFFFFF). Check value: crc32_ieee("123456789", 9) == 0xCBF43926. */
uint32_t crc32_ieee(const uint8_t *data, size_t len);

#endif /* WORKLOADS_H */
