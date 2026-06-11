"""Deterministic mock instrument so the full suite runs in CI with zero hardware.

Readings are fixed by :class:`MockConfig` and gated on the simulated power
state — reading the rail with the switch open returns 0 V and leakage-level
current, which is exactly the behavior campaigns must tolerate on the real
bench.
"""

from __future__ import annotations

from dataclasses import dataclass

from bench.instruments.base import BenchInstrument, InstrumentError


@dataclass(frozen=True)
class MockConfig:
    rail_mv: float = 3300.0
    active_ma: float = 22.0
    leakage_ma: float = 0.02
    edge_hz: float = 1000.0


class MockInstrument(BenchInstrument):
    def __init__(self, config: MockConfig | None = None) -> None:
        self.config = config or MockConfig()
        self.powered = False
        self.closed = False
        self.simulated_time_s = 0.0
        self.call_log: list[str] = []

    def _sleep(self, seconds: float) -> None:
        self.simulated_time_s += seconds

    def _require_open(self) -> None:
        if self.closed:
            raise InstrumentError("instrument is closed")

    def power_on(self) -> None:
        self._require_open()
        self.powered = True
        self.call_log.append("power_on")

    def power_off(self) -> None:
        self._require_open()
        self.powered = False
        self.call_log.append("power_off")

    def read_voltage_mv(self) -> float:
        self._require_open()
        self.call_log.append("read_voltage_mv")
        return self.config.rail_mv if self.powered else 0.0

    def read_current_ma(self) -> float:
        self._require_open()
        self.call_log.append("read_current_ma")
        return self.config.active_ma if self.powered else self.config.leakage_ma

    def count_edges(self, window_s: float) -> int:
        self._require_open()
        if window_s <= 0:
            raise InstrumentError(f"window_s must be positive, got {window_s}")
        self.call_log.append(f"count_edges({window_s})")
        if not self.powered:
            return 0
        return int(self.config.edge_hz * window_s)

    def close(self) -> None:
        self.closed = True
        self.call_log.append("close")
