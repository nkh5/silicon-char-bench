"""Session 2 done-gate: run N consecutive MARCH + CRC cycles against the DUT.

Usage::

    python -m bench.soak --cycles 100          # auto-detect the Pico
    python -m bench.soak --port COM7           # explicit port

Exits 0 only if every cycle passed, including the host-side CRC cross-check.
"""

from __future__ import annotations

import argparse
import sys
import time

import serial
from serial.tools import list_ports

from bench.dut import EXPECTED_CRC, DutLink, ProtocolError, expected_crc32

RPI_VID = 0x2E8A  # Raspberry Pi; pico-sdk USB CDC stdio enumerates as 2E8A:000A


def find_port() -> str | None:
    for port in list_ports.comports():
        if port.vid == RPI_VID:
            return port.device
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="serial port (default: first Raspberry Pi VID device)")
    parser.add_argument("--cycles", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=10.0, help="per-command timeout, s")
    args = parser.parse_args(argv)

    reference_crc = expected_crc32()
    if reference_crc != EXPECTED_CRC:
        print(
            f"FATAL: host reference 0x{reference_crc:08X} != pinned "
            f"EXPECTED_CRC 0x{EXPECTED_CRC:08X}; bench/dut.py is inconsistent"
        )
        return 2

    port_name = args.port or find_port()
    if not port_name:
        print("FATAL: no Raspberry Pi serial device found; pass --port explicitly")
        return 2

    with serial.Serial(port_name, 115200, timeout=0.5) as port:
        link = DutLink(port)
        time.sleep(0.2)
        port.reset_input_buffer()

        try:
            pong = link.command("PING", want=("PONG",), timeout_s=args.timeout)
            ident = link.command("ID", want=("ID",), timeout_s=args.timeout)
        except ProtocolError as exc:
            print(f"FATAL: DUT not responding on {port_name}: {exc}")
            return 2
        print(f"DUT on {port_name}: {' '.join(ident.fields)} (uptime {pong.fields[0]} ms)")
        print(f"reference CRC 0x{reference_crc:08X}, running {args.cycles} cycles")

        failures = 0
        for cycle in range(1, args.cycles + 1):
            try:
                march = link.run_workload("MARCH", timeout_s=args.timeout)
                crc = link.run_workload("CRC", timeout_s=args.timeout)
            except ProtocolError as exc:
                failures += 1
                print(f"cycle {cycle:4d}: FAIL (protocol: {exc})")
                continue
            crc_ok = crc.passed and crc.value == reference_crc
            ok = march.passed and crc_ok
            if not ok:
                failures += 1
                print(f"cycle {cycle:4d}: FAIL  march={march.raw!r}  crc={crc.raw!r}")
            elif cycle % 10 == 0 or cycle == 1:
                print(
                    f"cycle {cycle:4d}: PASS  march {march.elapsed_ms} ms, "
                    f"crc 0x{crc.value:08X} in {crc.elapsed_ms} ms"
                )

        print(f"done: {args.cycles - failures}/{args.cycles} cycles passed")
        return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
