"""Pin the firmware's baked-in CRC constants against independent references.

crc32_bitwise below is a line-for-line transliteration of crc32_ieee() in
firmware/payload/workloads.c; it is checked against zlib (an implementation
we did not write) and the published CRC-32 check value, so the firmware
algorithm and the EXPECTED_CRC constant cannot drift unnoticed.
"""

import zlib

from bench.dut import CRC_SEED, CRC_WORDS, EXPECTED_CRC, buffer_bytes, expected_crc32
from bench.dut import xorshift32_words as xorshift

CRC32_CHECK_VALUE = 0xCBF43926  # CRC-32/ISO-HDLC check value for b"123456789"


def crc32_bitwise(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xEDB88320 & (0xFFFFFFFF if crc & 1 else 0))
    return crc ^ 0xFFFFFFFF


def test_bitwise_crc_matches_published_check_value():
    assert crc32_bitwise(b"123456789") == CRC32_CHECK_VALUE
    assert zlib.crc32(b"123456789") == CRC32_CHECK_VALUE


def test_bitwise_crc_matches_zlib_on_assorted_buffers():
    for data in (b"", b"\x00", b"\xff" * 17, bytes(range(256)), buffer_bytes(count=64)):
        assert crc32_bitwise(data) == zlib.crc32(data) & 0xFFFFFFFF


def test_xorshift_stream_is_pinned():
    # Same first four words asserted in firmware/host_test/test_workloads.c.
    first4 = list(xorshift(CRC_SEED, 4))
    assert first4 == [0x6EE4450B, 0x2EEF9309, 0x4D55748E, 0x9B5C68EC]
    # Seed of zero is a fixed point of xorshift32 and must never be used.
    assert CRC_SEED != 0


def test_expected_crc_constant_is_consistent():
    assert expected_crc32(CRC_SEED, CRC_WORDS) == EXPECTED_CRC
    assert crc32_bitwise(buffer_bytes()) == EXPECTED_CRC


def test_buffer_is_16_kib():
    assert len(buffer_bytes()) == 16 * 1024
