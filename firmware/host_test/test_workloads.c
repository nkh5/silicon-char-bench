/* Host-side self-test for the workload kernels (no pico-sdk needed).
 *
 * Build and run with any C11 compiler on a little-endian host:
 *   cc -std=c11 -Wall -Wextra -O2 -o test_workloads \
 *      firmware/host_test/test_workloads.c firmware/payload/workloads.c
 *   ./test_workloads
 *
 * The same constants are pinned in tests/test_crc_reference.py against an
 * independent zlib computation.
 */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>

#include "../payload/workloads.h"

static uint32_t buf[WORKLOAD_BUF_WORDS];

int main(void)
{
    /* CRC-32/ISO-HDLC check value */
    assert(crc32_ieee((const uint8_t *)"123456789", 9) == 0xCBF43926u);

    /* xorshift32 stream pinned against bench.dut.xorshift32_words */
    uint32_t first4[4];
    fill_xorshift32(first4, 4, CRC_SEED);
    assert(first4[0] == 0x6EE4450Bu);
    assert(first4[1] == 0x2EEF9309u);
    assert(first4[2] == 0x4D55748Eu);
    assert(first4[3] == 0x9B5C68ECu);

    /* CRC workload constant (buffer byte image is little-endian) */
    fill_xorshift32(buf, WORKLOAD_BUF_WORDS, CRC_SEED);
    assert(crc32_ieee((const uint8_t *)buf, sizeof buf) == CRC_EXPECTED);

    /* March C- passes on healthy memory with both pattern pairs */
    march_fault_t fault;
    assert(march_c_minus(buf, WORKLOAD_BUF_WORDS, 0x00000000u, 0xFFFFFFFFu, &fault));
    assert(march_c_minus(buf, WORKLOAD_BUF_WORDS, 0x55555555u, 0xAAAAAAAAu, &fault));

    puts("all workload self-tests passed");
    return 0;
}
