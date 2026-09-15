"""The Mirror without a phone: the tap maths, the touch message, and the service's states."""
from __future__ import annotations

import socket
import struct
import time
from types import SimpleNamespace

import numpy as np
import pytest

from androidcontextdeploy import mirror_service
from androidcontextdeploy.mirror_service import MirrorService
from androidcontextdeploy.models import AppLogger
from androidcontextdeploy.ui.mirror import stream_point

FRAME = np.zeros((1024, 464, 3), np.uint8)          # scrcpy max_size=1024, portrait


def _wait(condition, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while not condition():
        assert time.time() < deadline, "timed out"
        time.sleep(0.01)


# ── Tap maths ────────────────────────────────────────────────────────────
def test_the_margins_around_the_picture_come_off_first() -> None:
    # A 400x1000 widget shows the stream at 400x883: 58.5 px of margin above and below.
    assert stream_point((200, 500), (400, 1000), (400, 883), (464, 1024), clamp=False) == \
        pytest.approx((232, 512), abs=1)
    assert stream_point((0, 58.5), (400, 1000), (400, 883), (464, 1024), clamp=False) == (0, 0)


def test_a_press_off_the_picture_is_ignored_but_a_drag_sticks_to_the_edge() -> None:
    assert stream_point((200, 10), (400, 1000), (400, 883), (464, 1024), clamp=False) is None
    assert stream_point((200, 10), (400, 1000), (400, 883), (464, 1024), clamp=True) == (232, 0)


def test_no_picture_yet_means_no_touch() -> None:
    assert stream_point((1, 1), (400, 1000), (0, 0), (464, 1024), clamp=True) is None


# ── Touch message (scrcpy v3 control protocol) ───────────────────────────
@pytest.fixture
def running() -> tuple[MirrorService, socket.socket]:
    service = MirrorService(AppLogger(), "")
    ours, phone = socket.socketpair()
    service._control_socket, service._state, service._latest = ours, "running", (1, FRAME)
    yield service, phone
    ours.close()
    phone.close()


@pytest.mark.parametrize(("action", "code", "pressure"), [("down", 0, 0xFFFF), ("move", 2, 0xFFFF), ("up", 1, 0)])
def test_a_touch_is_one_32_byte_message(running, action, code, pressure) -> None:
    service, phone = running
    service.touch(100.7, 200.2, action)
    message = phone.recv(64)
    assert len(message) == 32
    assert struct.unpack(">BBqiiHHHii", message) == (2, code, -2, 100, 200, 464, 1024, pressure, 0, 0)


def test_no_touch_without_a_picture_or_a_running_stream(running) -> None:
    service, phone = running
    phone.setblocking(False)
    service._latest = (1, None)
    service.touch(1, 1, "down")
    service._latest, service._state = (1, FRAME), "idle"
    service.touch(1, 1, "down")
    with pytest.raises(BlockingIOError):
        phone.recv(64)


def test_a_closed_control_socket_is_harmless(running) -> None:
    service, _ = running
    service._control_socket.close()
    service.touch(1, 1, "down")


# ── Service states ───────────────────────────────────────────────────────
class FakeDevice:
    """adbutils' device: records the push and hands out the two sockets."""

    def __init__(self, sockets: list[socket.socket]) -> None:
        self.sockets = sockets
        self.pushed: list[tuple[str, str]] = []
        self.sync = SimpleNamespace(push=lambda src, dst: self.pushed.append((src, dst)))
        output = SimpleNamespace(settimeout=lambda s: None, recv=lambda n: b"Aborted: device busy", close=lambda: None)
        self.stream = SimpleNamespace(conn=output, close=lambda: None)

    def shell(self, command, stream=False):
        return self.stream

    def create_connection(self, network, name):
        if not self.sockets:
            raise ConnectionRefusedError
        return self.sockets.pop(0)


@pytest.fixture
def jar(monkeypatch, tmp_path):
    path = tmp_path / "scrcpy-server.jar"
    path.write_bytes(b"jar")
    monkeypatch.setattr(mirror_service, "_server_jar_path", lambda: path)
    return path


def _with_device(monkeypatch, device: FakeDevice) -> None:
    monkeypatch.setattr(mirror_service, "adbutils", SimpleNamespace(adb=SimpleNamespace(device=lambda serial: device)))


def test_the_stream_starts_decodes_and_reports_an_unplug(monkeypatch, jar) -> None:
    video, video_phone = socket.socketpair()
    control, control_phone = socket.socketpair()
    device = FakeDevice([video, control])
    _with_device(monkeypatch, device)
    logger = AppLogger()
    service = MirrorService(logger, "")

    assert service.start("SERIAL")
    assert not service.start("SERIAL"), "a second start while starting is refused"
    _wait(lambda: service.state == "running")
    assert device.pushed == [(str(jar), mirror_service._DEVICE_PATH)]

    video_phone.sendall(b"\x00\x00\x00\x01 not really h264")   # the decoder shrugs it off
    video_phone.close()                                       # unplugged
    _wait(lambda: service.state == "failed")
    assert any(event.level == "WARN" for event in logger.drain())

    service.stop()
    assert service.state == "idle" and service.get_frame()[1] is None
    control_phone.close()


def test_a_server_that_never_listens_fails_once_with_its_output(monkeypatch, jar) -> None:
    _with_device(monkeypatch, FakeDevice([]))
    monkeypatch.setattr(mirror_service.time, "time", _fast_clock())
    logger = AppLogger()
    service = MirrorService(logger, "")
    service.start("SERIAL")
    _wait(lambda: service.state == "failed")
    assert "device busy" in " ".join(event.message for event in logger.drain())


def _fast_clock():
    """time.time() that runs 10 s per call, so the 3 s connection wait ends at once."""
    now = [0.0]

    def clock() -> float:
        now[0] += 10
        return now[0]
    return clock


def test_without_the_jar_the_mirror_is_unavailable(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mirror_service, "_server_jar_path", lambda: tmp_path / "missing.jar")
    service = MirrorService(AppLogger(), "")
    assert not service.available and not service.start("SERIAL")


def test_stopping_a_running_mirror_logs_it(running) -> None:
    service, _ = running
    logger = service.logger
    service.stop()
    assert service.state == "idle"
    assert [event.level for event in logger.drain()] == ["INFO"]


def test_the_mirror_uses_the_same_adb_as_the_tool(monkeypatch, tmp_path) -> None:
    adb = tmp_path / "adb"
    adb.touch()
    monkeypatch.delenv("ADBUTILS_ADB_PATH", raising=False)
    MirrorService(AppLogger(), str(adb))
    assert mirror_service.os.environ["ADBUTILS_ADB_PATH"] == str(adb)
