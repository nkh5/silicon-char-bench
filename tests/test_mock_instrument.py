import pytest

from bench.instruments import InstrumentError, MockConfig, MockInstrument


def test_readings_are_gated_on_power_state():
    inst = MockInstrument()
    assert inst.read_voltage_mv() == 0.0
    assert inst.read_current_ma() == pytest.approx(0.02)

    inst.power_on()
    assert inst.read_voltage_mv() == pytest.approx(3300.0)
    assert inst.read_current_ma() == pytest.approx(22.0)

    inst.power_off()
    assert inst.read_voltage_mv() == 0.0


def test_power_cycle_sequencing_and_off_time():
    inst = MockInstrument()
    inst.power_on()
    inst.call_log.clear()

    inst.power_cycle(off_time_s=0.5)

    assert inst.call_log == ["power_off", "power_on"]
    assert inst.simulated_time_s == pytest.approx(0.5)
    assert inst.powered


def test_power_cycle_rejects_nonpositive_off_time():
    inst = MockInstrument()
    with pytest.raises(InstrumentError):
        inst.power_cycle(off_time_s=0)


def test_edge_counting():
    inst = MockInstrument(MockConfig(edge_hz=125.0))
    assert inst.count_edges(window_s=2.0) == 0  # unpowered DUT toggles nothing

    inst.power_on()
    assert inst.count_edges(window_s=2.0) == 250

    with pytest.raises(InstrumentError):
        inst.count_edges(window_s=-1.0)


def test_closed_instrument_refuses_commands():
    inst = MockInstrument()
    inst.close()
    with pytest.raises(InstrumentError):
        inst.power_on()


def test_context_manager_closes():
    with MockInstrument() as inst:
        inst.power_on()
    assert inst.closed
