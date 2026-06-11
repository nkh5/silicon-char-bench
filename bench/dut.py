"""DUT serial protocol: line framing, parsing, and host-side CRC reference.

One ASCII line per message, newline terminated (firmware emits CRLF because
pico-sdk stdio translates ``\\n`` to ``\\r\\n`` on output):

==================  =====================================================
host sends          firmware replies
==================  =====================================================
``PING``            ``PONG <uptime_ms>``
``ID``              ``ID <unique_board_id> <board> <fw_version>``
``MARCH``           ``RESULT MARCH PASS <ms>`` or
                    ``RESULT MARCH FAIL elem=<n> idx=<i> exp=<x> got=<x>``
``CRC``             ``RESULT CRC PASS|FAIL 0x<crc32> <ms>``
(unsolicited)       ``HB <seq> <uptime_ms>`` every second while idle
(on boot)           ``BOOT CLEAN|WATCHDOG <fw_version>``
(bad input)         ``ERR <message>``
==================  =====================================================

The firmware judges CRC pass/fail against its baked-in ``CRC_EXPECTED``; the
host *independently* recomputes the reference here with :mod:`zlib` so a
transcription error on either side shows up as a mismatch.
"""

from __future__ import annotations

import struct
import time
import zlib
from collections.abc import Iterator
from dataclasses import dataclass

# Must match firmware/payload/workloads.h. EXPECTED_CRC is pinned by
# tests/test_crc_reference.py against an independent zlib computation.
CRC_SEED = 0x1234ABCD
CRC_WORDS = 4096  # 16 KiB workload buffer
EXPECTED_CRC = 0xC0C5191F


class ProtocolError(Exception):
    """Raised when the DUT does not answer, or answers gibberish."""


def xorshift32_words(seed: int = CRC_SEED, count: int = CRC_WORDS) -> Iterator[int]:
    """Marsaglia xorshift32, identical to fill_xorshift32() in workloads.c."""
    x = seed & 0xFFFFFFFF
    for _ in range(count):
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        yield x


def buffer_bytes(seed: int = CRC_SEED, count: int = CRC_WORDS) -> bytes:
    """The workload buffer exactly as it sits in DUT RAM (little-endian words)."""
    return struct.pack(f"<{count}I", *xorshift32_words(seed, count))


def expected_crc32(seed: int = CRC_SEED, count: int = CRC_WORDS) -> int:
    """Host-side reference CRC, computed via zlib rather than our own code."""
    return zlib.crc32(buffer_bytes(seed, count)) & 0xFFFFFFFF


@dataclass(frozen=True)
class Message:
    kind: str
    fields: tuple[str, ...]
    raw: str


@dataclass(frozen=True)
class WorkloadResult:
    workload: str
    passed: bool
    value: int | None  # reported CRC for CRC workload, else None
    elapsed_ms: int | None
    raw: str


def parse_line(line: str) -> Message | None:
    """Tokenize one protocol line; returns None for blank lines."""
    tokens = line.split()
    if not tokens:
        return None
    return Message(kind=tokens[0].upper(), fields=tuple(tokens[1:]), raw=line.strip())


class DutLink:
    """Line protocol over any pyserial-like object (``write``/``readline``).

    The port's own read timeout must be set short (e.g. 0.5 s); ``command``
    layers a deadline on top and skips unsolicited HB/BOOT traffic.
    """

    UNSOLICITED = ("HB", "BOOT")

    def __init__(self, port) -> None:
        self.port = port

    def send(self, command: str) -> None:
        self.port.write((command + "\n").encode("ascii"))

    def read_message(self) -> Message | None:
        line = self.port.readline()
        if not line:
            return None
        return parse_line(line.decode("ascii", errors="replace"))

    def command(self, command: str, want: tuple[str, ...], timeout_s: float = 5.0) -> Message:
        """Send ``command`` and return the first reply whose kind is in ``want``."""
        self.send(command)
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            msg = self.read_message()
            if msg is None or msg.kind in self.UNSOLICITED:
                continue
            if msg.kind in want:
                return msg
            raise ProtocolError(f"sent {command!r}, expected {want}, got: {msg.raw!r}")
        raise ProtocolError(f"sent {command!r}, no {want} reply within {timeout_s} s")

    def run_workload(self, workload: str, timeout_s: float = 10.0) -> WorkloadResult:
        """Run MARCH or CRC and parse the RESULT line."""
        msg = self.command(workload, want=("RESULT",), timeout_s=timeout_s)
        if len(msg.fields) < 2 or msg.fields[0] != workload.upper():
            raise ProtocolError(f"malformed RESULT for {workload}: {msg.raw!r}")
        passed = msg.fields[1] == "PASS"
        value: int | None = None
        elapsed_ms: int | None = None
        rest = msg.fields[2:]
        if workload.upper() == "CRC" and rest:
            try:
                value = int(rest[0], 16)
            except ValueError as exc:
                raise ProtocolError(f"bad CRC value in: {msg.raw!r}") from exc
            rest = rest[1:]
        if rest and rest[0].isdigit():
            elapsed_ms = int(rest[0])
        return WorkloadResult(
            workload=workload.upper(),
            passed=passed,
            value=value,
            elapsed_ms=elapsed_ms,
            raw=msg.raw,
        )
