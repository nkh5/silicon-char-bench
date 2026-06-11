"""Instrument layer: one abstract interface, concrete drivers behind it.

Campaigns talk to :class:`bench.instruments.base.BenchInstrument` and never to
a specific instrument, so the instrument Pico, the sigrok logic analyzer, or
the borrowed AD3 (August phase) drop in without touching test code.
"""

from bench.instruments.base import BenchInstrument, InstrumentError
from bench.instruments.mock import MockConfig, MockInstrument

__all__ = ["BenchInstrument", "InstrumentError", "MockConfig", "MockInstrument"]
