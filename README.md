# silicon-char-bench

Automated post-silicon-style validation bench for the Raspberry Pi RP2040 and
RP2350: scripted bring-up, voltage/frequency shmoo, protocol compliance,
power characterization, and stepping comparison, driven by a Python test
framework with pass/fail criteria.

## Status

| Session | Scope | State |
|---|---|---|
| 1 | Framework skeleton: pytest scaffold, mocked instrument layer, YAML test plan loader, CI (lint + unit tests, zero hardware) | done |
| 2 | Firmware v0: USB serial command protocol, heartbeat, SRAM march + CRC workloads, watchdog recovery, 100-cycle host soak script | code done — soak run pending hardware |
| 3+ | Shmoo engine, power control, campaigns | not started |

## Layout

```
bench/                  Python framework (installable package)
  instruments/          abstract BenchInstrument + MockInstrument (CI runs on this)
  testplan.py           YAML test plan loader; spec_ref and pass_criterion mandatory
  dut.py                DUT serial protocol parsing + host-side CRC reference (zlib)
  soak.py               session 2 done-gate: N consecutive MARCH+CRC cycles
testplans/              YAML campaign definitions
tests/                  unit suite, runs with zero hardware
firmware/
  payload/              pico-sdk C firmware (main.c) + pure-C workload kernels
  host_test/            workload kernel self-test, builds with any C11 compiler
  CMakeLists.txt
.github/workflows/      lint + unit tests + firmware kernel self-test
```

## Framework quickstart (no hardware)

```sh
python -m pip install -e ".[dev]"
ruff check .
pytest
```

## Firmware build

Requires [pico-sdk](https://github.com/raspberrypi/pico-sdk) and the
`arm-none-eabi-gcc` toolchain.

```sh
export PICO_SDK_PATH=/path/to/pico-sdk
cmake -S firmware -B firmware/build -DPICO_BOARD=pico   # pico2 for RP2350
cmake --build firmware/build
```

Flash by holding BOOTSEL while plugging the Pico in, then copy
`firmware/build/bench_payload.uf2` onto the `RPI-RP2` drive.

## Session 2 done-gate: the soak run

With the flashed Pico connected (it enumerates as USB CDC, VID 0x2E8A):

```sh
python -m bench.soak --cycles 100
```

Each cycle runs the SRAM March C- test (two pattern pairs: all-0/all-1 and
0x55/0xAA checkerboard over a 16 KiB buffer) and the CRC-32 kernel. The
firmware judges CRC against its baked-in constant **and** the host
independently recomputes the reference with `zlib`, so both sides must agree.
Exit code 0 means 100/100 passed.

## Serial protocol (firmware v0.2.0)

| Host sends | Firmware replies |
|---|---|
| `PING` | `PONG <uptime_ms>` |
| `ID` | `ID <unique_board_id> <board> <fw_version>` |
| `STATUS` | `STATUS uptime_ms=<n> hb_seq=<n>` |
| `MARCH` | `RESULT MARCH PASS <ms>` or `RESULT MARCH FAIL elem=<n> idx=<i> exp=<hex> got=<hex>` |
| `CRC` | `RESULT CRC PASS\|FAIL 0x<crc32> <ms>` |
| (unsolicited) | `HB <seq> <uptime_ms>` every second while idle |
| (on connect) | `BOOT CLEAN\|WATCHDOG <fw_version>` |

The watchdog (5 s) is always armed: a hung workload reboots the DUT and the
host sees `BOOT WATCHDOG` rather than a dead port. True MOSFET power cycling
replaces watchdog recovery in session 4.

## Correctness cross-checks

* `crc32_ieee` (firmware) is transliterated and pinned in
  `tests/test_crc_reference.py` against `zlib.crc32` and the published
  CRC-32/ISO-HDLC check value `0xCBF43926`.
* The xorshift32 fill stream and the baked `CRC_EXPECTED = 0xC0C5191F` are
  pinned in both the Python suite and `firmware/host_test/test_workloads.c`,
  which CI builds and runs with gcc.
* The soak script never trusts the firmware's PASS verdict alone; it compares
  the reported CRC value against its own zlib-computed reference.
