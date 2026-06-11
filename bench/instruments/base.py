"""Abstract instrument interface.

Planned concrete drivers, all behind this one interface:

* instrument Pico — MOSFET high-side power switch, INA260 readout, edge
  counter, over a simple serial protocol (session 4)
* sigrok CLI — logic analyzer clone capture and protocol decode (session 7)
* WaveForms SDK — borrowed Analog Discovery 3, August on-campus phase
"""

from __future__ import annotations

import abc
import time


class InstrumentError(Exception):
    """Raised when an instrument cannot service a request."""


class BenchInstrument(abc.ABC):
    """Interface every concrete instrument driver implements."""

    @abc.abstractmethod
    def power_on(self) -> None:
        """Close the high-side switch on the DUT supply rail."""

    @abc.abstractmethod
    def power_off(self) -> None:
        """Open the high-side switch, removing DUT power."""

    def power_cycle(self, off_time_s: float = 0.25) -> None:
        """Hard power cycle the DUT, holding it off for ``off_time_s``.

        Used between shmoo points so a hard hang can never stall an
        overnight campaign.
        """
        if off_time_s <= 0:
            raise InstrumentError(f"off_time_s must be positive, got {off_time_s}")
        self.power_off()
        self._sleep(off_time_s)
        self.power_on()

    @abc.abstractmethod
    def read_voltage_mv(self) -> float:
        """DUT supply rail voltage in millivolts (INA260 bus voltage)."""

    @abc.abstractmethod
    def read_current_ma(self) -> float:
        """DUT supply current in milliamps (INA260)."""

    @abc.abstractmethod
    def count_edges(self, window_s: float) -> int:
        """Count signal edges on the counter input over ``window_s`` seconds."""

    @abc.abstractmethod
    def close(self) -> None:
        """Release the underlying transport. Idempotent."""

    def _sleep(self, seconds: float) -> None:
        """Wait hook; mocks override this to advance simulated time instead."""
        time.sleep(seconds)

    def __enter__(self) -> BenchInstrument:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
