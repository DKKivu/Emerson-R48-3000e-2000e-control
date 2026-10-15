"""CAN transport layer.

`CANTransport` is the abstraction the rest of the application depends on.
Concrete transports (currently only the Waveshare USB-CAN-A serial bridge)
publish events on an internal queue that the GUI drains on the Tk main loop.
"""
from __future__ import annotations

import queue
import threading
from abc import ABC, abstractmethod
from typing import Iterator, Optional
import sys
import logging

from .exceptions import TransportError
from .models import CANFrame
from .protocol import WaveshareProtocol

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # pragma: no cover
    serial = None
    list_ports = None


EventKind = str


class CANTransport(ABC):
    """Abstract CAN transport (Dependency Inversion point)."""

    @property
    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def send_frame(self, frame: CANFrame) -> None: ...

    @abstractmethod
    def drain_events(self, max_items: int) -> Iterator[tuple[EventKind, object]]:
        """Yield up to `max_items` queued events (non-blocking)."""


# ---------------------------------------------------------------
# Waveshare USB-CAN-A implementation
# ---------------------------------------------------------------

class WaveshareSerialCAN(CANTransport):
    def __init__(self, port: str, baud: int, bitrate: int) -> None:
        self.port = port
        self.baud = baud
        self.bitrate = bitrate

        self._events: queue.Queue = queue.Queue()
        self._serial = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._write_lock = threading.Lock()
        self._buffer = bytearray()

    @property
    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def connect(self) -> None:
        if serial is None:
            raise TransportError(
                "pyserial is missing. Run: python -m pip install pyserial"
            )
        if self.is_connected:
            return

        try:
            self._serial = serial.Serial(
                self.port,
                self.baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1,
                write_timeout=1,
            )
        except Exception as exc:
            raise TransportError(f"Cannot open {self.port}: {exc}") from exc

        self._stop.clear()
        self._buffer.clear()

        try:
            config_packet = WaveshareProtocol.build_configuration(
                bitrate=self.bitrate, extended=True, mode=0
            )
            with self._write_lock:
                self._serial.write(config_packet)
                self._serial.flush()

            self._emit("log", "Adapter configuration TX: "
                       + config_packet.hex(" ").upper())

            self._thread = threading.Thread(
                target=self._reader, name="WaveshareReader", daemon=True
            )
            self._thread.start()

            self._emit("status",
                       f"Connected: {self.port}, CAN {self.bitrate} bit/s")
        except Exception:
            self.disconnect()
            raise

    def disconnect(self) -> None:
        self._stop.set()

        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.5)

        with self._write_lock:
            if self._serial is not None:
                try:
                    if self._serial.is_open:
                        self._serial.close()
                finally:
                    self._serial = None

        self._emit("status", "Disconnected")

    def send_frame(self, frame: CANFrame) -> None:
        packet = WaveshareProtocol.encode(frame)
        with self._write_lock:
            if not self.is_connected:
                raise TransportError("Adapter is disconnected")
            self._serial.write(packet)
            self._serial.flush()

        self._emit(
            "log",
            f"CAN TX ID=0x{frame.arbitration_id:08X} "
            f"EXT={int(frame.extended)} "
            f"DATA={frame.data.hex(' ').upper()}",
        )

    def drain_events(self, max_items: int) -> Iterator[tuple[EventKind, object]]:
        for _ in range(max_items):
            try:
                yield self._events.get_nowait()
            except queue.Empty:
                return

    def _emit(self, kind: EventKind, payload: object) -> None:
        self._events.put((kind, payload))

    def _reader(self) -> None:
        while not self._stop.is_set():
            try:
                ser = self._serial
                if ser is None or not ser.is_open:
                    break

                incoming = ser.read(256)
                if not incoming:
                    continue

                self._buffer.extend(incoming)
                for frame in WaveshareProtocol.decode_buffer(self._buffer):
                    self._emit("can_rx", frame)
                    self._emit(
                        "log",
                        f"CAN RX ID=0x{frame.arbitration_id:08X} "
                        f"EXT={int(frame.extended)} "
                        f"DATA={frame.data.hex(' ').upper()}",
                    )

                if len(self._buffer) > 4096:
                    del self._buffer[:-32]
            except Exception as exc:
                if not self._stop.is_set():
                    self._emit("error", f"Serial RX: {exc}")
                break


def list_serial_ports() -> list:
    """Return a list of available serial port names.

    This function attempts to import and call pyserial's list_ports at
    runtime so the package can be installed or unavailable without
    causing the whole application to fail to import. If pyserial isn't
    installed we return a sentinel entry to make it obvious in the UI;
    the Connect action will still raise a clear error prompting the
    user to install pyserial.
    """
    # First try the already-imported name (module-level variable).
    global list_ports
    try:
        if list_ports is None:
            # try importing lazily in case the environment changed
            from serial.tools import list_ports as _list_ports  # type: ignore
            list_ports = _list_ports
    except Exception:
        logging.debug("pyserial not available (list_ports import failed)")
        return ["(pyserial missing)"]

    try:
        ports = [port.device for port in list_ports.comports()]
    except Exception:
        logging.exception("Error enumerating serial ports")
        ports = []

    # On some systems `COM1` can exist but not be reported by list_ports; do
    # not invent ports, but if no ports were found on Windows include a
    # common default so users can try it.
    if not ports and sys.platform.startswith("win"):
        # Only include COM1 if it seems to exist: attempting to open it would
        # block or raise, so we simply include it as a hint (connect will
        # report a clear error if it can't be opened).
        ports = ["COM1"]

    return ports
