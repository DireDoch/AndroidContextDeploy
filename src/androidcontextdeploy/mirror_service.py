"""The Mirror (ADR-0003): a minimal scrcpy client -- H.264 decoded in Python,
clicks sent back as touches.

The official scrcpy-server jar (scrcpy_server/, Apache-2.0) is pushed to
/data/local/tmp and started with raw_stream=true. Nothing is installed on the
phone. The video socket carries raw H.264 decoded by PyAV; a second socket
carries touches. The service is inert if its dependencies are missing: the
tool keeps working without a Mirror.
"""
from __future__ import annotations

import os
import socket
import struct
import threading
import time
from pathlib import Path
from typing import Any

from androidcontextdeploy.i18n import t
from androidcontextdeploy.manifest import app_root
from androidcontextdeploy.models import AppLogger

try:
    import adbutils
    from adbutils import Network
    from av.codec import CodecContext
    _MIRROR_AVAILABLE = True
except Exception:
    adbutils = None
    _MIRROR_AVAILABLE = False

# Must match the jar's file name exactly.
_SERVER_VERSION = "3.3.4"
_SERVER_JAR = f"scrcpy-server-v{_SERVER_VERSION}.jar"
_DEVICE_PATH = f"/data/local/tmp/{_SERVER_JAR}"

# scrcpy v3 control protocol -- touch injection.
_TYPE_INJECT_TOUCH = 2
_POINTER_ID_GENERIC_FINGER = -2
_ACTIONS = {"down": 0, "up": 1, "move": 2}


def _server_jar_path() -> Path:
    return app_root() / "scrcpy_server" / _SERVER_JAR


class MirrorService:
    """idle -> starting -> running | failed; stop() returns to idle. "failed"
    sticks while the phone stays plugged in, so there is no reconnect storm."""

    def __init__(self, logger: AppLogger, adb_command: str) -> None:
        self.logger = logger
        self._state = "idle"
        self._state_lock = threading.Lock()
        # (frame number, BGR frame or None), replaced as one tuple so the UI
        # never pairs a number with another frame.
        self._latest: tuple[int, Any] = (0, None)
        self._video_socket: socket.socket | None = None
        self._control_socket: socket.socket | None = None
        self._control_lock = threading.Lock()
        self._server_stream: Any = None        # adbutils' shell stream
        # adbutils must use the same adb as AdbService, or two adb servers of
        # different versions fight over port 5037.
        if adb_command and Path(adb_command).exists():
            os.environ.setdefault("ADBUTILS_ADB_PATH", adb_command)

    @property
    def available(self) -> bool:
        return _MIRROR_AVAILABLE and _server_jar_path().exists()

    @property
    def state(self) -> str:
        return self._state

    def start(self, serial: str) -> bool:
        if not self.available:
            return False
        with self._state_lock:
            if self._state != "idle":
                return False
            self._state = "starting"
        threading.Thread(target=self._start_client, args=(serial,),
                         daemon=True, name="mirror-start").start()
        return True

    def _start_client(self, serial: str) -> None:
        try:
            device = adbutils.adb.device(serial=serial)
            device.sync.push(str(_server_jar_path()), _DEVICE_PATH)
            self._server_stream = device.shell([
                f"CLASSPATH={_DEVICE_PATH}", "app_process", "/",
                "com.genymobile.scrcpy.Server", _SERVER_VERSION,
                "log_level=info", "video=true", "audio=false", "control=true",
                "max_size=1024", "video_bit_rate=8000000", "max_fps=30",
                "video_codec=h264", "tunnel_forward=true", "raw_stream=true",
                "stay_awake=true", "cleanup=true",
            ], stream=True)
            # The server listens on the abstract socket "scrcpy". Video first, then control.
            video = self._connect(device)
            if video is None:
                raise ConnectionError(f"scrcpy server unreachable: {self._server_output()}")
            control = self._connect(device)
            video.setblocking(False)
            with self._state_lock:
                if self._state != "starting":        # stop() during startup
                    video.close()
                    if control:
                        control.close()
                    return
                self._video_socket, self._control_socket = video, control
                self._state = "running"
            threading.Thread(target=self._stream_loop, args=(video,),
                             daemon=True, name="mirror-stream").start()
            self.logger.ok(t("log.mirror.started", serial=serial))
        except Exception as exc:
            with self._state_lock:
                self._state = "failed"
            self.logger.warn(t("log.mirror.unavailable", error=exc))

    @staticmethod
    def _connect(device, timeout_s: float = 3.0) -> socket.socket | None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                return device.create_connection(Network.LOCAL_ABSTRACT, "scrcpy")
            except Exception:
                time.sleep(0.1)
        return None

    def _server_output(self) -> str:
        try:
            self._server_stream.conn.settimeout(1.0)
            output = self._server_stream.conn.recv(4096).decode("utf-8", errors="replace")
            return " ".join(output.split())[-300:] or "no server output"
        except Exception:
            return "no server output"

    def stop(self) -> None:
        with self._state_lock:
            was_running = self._state == "running"
            self._state = "idle"
            closeables = (self._video_socket, self._control_socket, self._server_stream)
            self._video_socket = self._control_socket = self._server_stream = None
        self._latest = (self._latest[0], None)
        for closeable in closeables:
            try:
                if closeable is not None:
                    closeable.close()
            except Exception:
                pass
        if was_running:
            self.logger.info(t("log.mirror.stopped"))

    def _stream_loop(self, video: socket.socket) -> None:
        """Decoder thread: raw H.264 -> BGR numpy frames, the latest one wins."""
        codec = CodecContext.create("h264", "r")
        while self._state == "running":
            try:
                raw = video.recv(0x10000)
            except BlockingIOError:
                time.sleep(0.01)
                continue
            except OSError:
                break                               # closed by stop() or unplug
            if not raw:
                if self._state == "running":
                    self.logger.warn(t("log.mirror.interrupted"))
                    with self._state_lock:
                        self._state = "failed"
                break
            try:
                for packet in codec.parse(raw):
                    for frame in codec.decode(packet):
                        self._latest = (self._latest[0] + 1, frame.to_ndarray(format="bgr24"))
            except Exception:
                continue                            # truncated packet mid-transition

    def get_frame(self) -> tuple[int, Any]:
        """(frame number, BGR frame or None) -- the UI redraws on a new number only."""
        return self._latest

    def touch(self, x: float, y: float, action: str) -> None:
        """A touch in stream coordinates (the scrcpy resolution)."""
        control, frame = self._control_socket, self._latest[1]
        if control is None or frame is None or self._state != "running":
            return
        height, width = frame.shape[0], frame.shape[1]
        message = struct.pack(
            ">BBqiiHHHii", _TYPE_INJECT_TOUCH, _ACTIONS.get(action, 0),
            _POINTER_ID_GENERIC_FINGER, int(x), int(y), width, height,
            0 if action == "up" else 0xFFFF, 0, 0)
        try:
            with self._control_lock:
                control.send(message)
        except Exception:
            pass                                    # control socket closed on unplug
