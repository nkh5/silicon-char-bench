import pytest

from bench.dut import DutLink, ProtocolError, parse_line


class FakeSerial:
    """Pyserial stand-in: scripted RX lines, captured TX bytes."""

    def __init__(self, lines):
        self.rx = [line.encode("ascii") + b"\r\n" for line in lines]
        self.tx = []

    def write(self, data):
        self.tx.append(data)

    def readline(self):
        return self.rx.pop(0) if self.rx else b""  # b"" emulates port timeout


def test_parse_line():
    msg = parse_line("PONG 1234\r\n")
    assert msg.kind == "PONG"
    assert msg.fields == ("1234",)

    msg = parse_line("RESULT MARCH FAIL elem=4 idx=17 exp=0x00000000 got=0x00010000")
    assert msg.kind == "RESULT"
    assert msg.fields[:2] == ("MARCH", "FAIL")

    assert parse_line("") is None
    assert parse_line("   \r\n") is None


def test_command_skips_heartbeats_and_boot():
    fake = FakeSerial(["HB 41 41000", "BOOT CLEAN 0.2.0", "HB 42 42000", "PONG 42500"])
    link = DutLink(fake)
    msg = link.command("PING", want=("PONG",), timeout_s=1.0)
    assert msg.fields == ("42500",)
    assert fake.tx == [b"PING\n"]


def test_command_times_out_on_silence():
    link = DutLink(FakeSerial([]))
    with pytest.raises(ProtocolError, match="no .* reply"):
        link.command("PING", want=("PONG",), timeout_s=0.05)


def test_command_rejects_wrong_reply():
    link = DutLink(FakeSerial(["ERR unknown command: PNIG"]))
    with pytest.raises(ProtocolError, match="expected"):
        link.command("PNIG", want=("PONG",), timeout_s=1.0)


def test_run_workload_march_pass():
    link = DutLink(FakeSerial(["HB 1 1000", "RESULT MARCH PASS 3"]))
    result = link.run_workload("MARCH", timeout_s=1.0)
    assert result.passed
    assert result.workload == "MARCH"
    assert result.elapsed_ms == 3
    assert result.value is None


def test_run_workload_march_fail_keeps_detail():
    link = DutLink(FakeSerial(["RESULT MARCH FAIL elem=2 idx=99 exp=0x00000000 got=0x00000400"]))
    result = link.run_workload("MARCH", timeout_s=1.0)
    assert not result.passed
    assert "elem=2" in result.raw


def test_run_workload_crc_parses_value():
    link = DutLink(FakeSerial(["RESULT CRC PASS 0xC0C5191F 11"]))
    result = link.run_workload("CRC", timeout_s=1.0)
    assert result.passed
    assert result.value == 0xC0C5191F
    assert result.elapsed_ms == 11


def test_run_workload_rejects_mismatched_workload():
    link = DutLink(FakeSerial(["RESULT CRC PASS 0xC0C5191F 11"]))
    with pytest.raises(ProtocolError, match="malformed RESULT"):
        link.run_workload("MARCH", timeout_s=1.0)


def test_run_workload_rejects_bad_crc_field():
    link = DutLink(FakeSerial(["RESULT CRC PASS notahex 11"]))
    with pytest.raises(ProtocolError, match="bad CRC value"):
        link.run_workload("CRC", timeout_s=1.0)
