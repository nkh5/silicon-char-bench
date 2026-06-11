#include "workloads.h"

static bool check_word(volatile uint32_t *buf, size_t i, uint32_t expect,
                       int element, march_fault_t *fault)
{
    uint32_t got = buf[i];
    if (got == expect) {
        return true;
    }
    if (fault) {
        fault->index = i;
        fault->expected = expect;
        fault->got = got;
        fault->element = element;
    }
    return false;
}

bool march_c_minus(volatile uint32_t *buf, size_t words,
                   uint32_t p0, uint32_t p1, march_fault_t *fault)
{
    size_t i;

    /* 1: up (w0) */
    for (i = 0; i < words; i++) {
        buf[i] = p0;
    }
    /* 2: up (r0, w1) */
    for (i = 0; i < words; i++) {
        if (!check_word(buf, i, p0, 2, fault)) return false;
        buf[i] = p1;
    }
    /* 3: up (r1, w0) */
    for (i = 0; i < words; i++) {
        if (!check_word(buf, i, p1, 3, fault)) return false;
        buf[i] = p0;
    }
    /* 4: down (r0, w1) */
    for (i = words; i-- > 0;) {
        if (!check_word(buf, i, p0, 4, fault)) return false;
        buf[i] = p1;
    }
    /* 5: down (r1, w0) */
    for (i = words; i-- > 0;) {
        if (!check_word(buf, i, p1, 5, fault)) return false;
        buf[i] = p0;
    }
    /* 6: up (r0) */
    for (i = 0; i < words; i++) {
        if (!check_word(buf, i, p0, 6, fault)) return false;
    }
    return true;
}

void fill_xorshift32(uint32_t *buf, size_t words, uint32_t seed)
{
    uint32_t x = seed;
    for (size_t i = 0; i < words; i++) {
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
        buf[i] = x;
    }
}

uint32_t crc32_ieee(const uint8_t *data, size_t len)
{
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int bit = 0; bit < 8; bit++) {
            crc = (crc >> 1) ^ (0xEDB88320u & (uint32_t)-(int32_t)(crc & 1u));
        }
    }
    return ~crc;
}
