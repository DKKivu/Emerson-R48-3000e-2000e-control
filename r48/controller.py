"""Application-level facade over a CAN transport and the R48 codec.

Depends only on the `CANTransport` abstraction and `R48Protocol`
(SRP + DIP). No I/O, no Tkinter, no serial - trivially testable with a fake
transport.
"""
from __future__ import annotations

from typing import Optional

from .models import CANFrame, TelemetryValue
from .protocol import R48Protocol
from .transport import CANTransport


class R48Controller:
    def __init__(self, transport: CANTransport) -> None:
        self._transport = transport
        self._protocol = R48Protocol()

    @property
    def is_connected(self) -> bool:
        return self._transport.is_connected

    def connect(self) -> None:
        self._transport.connect()

    def disconnect(self) -> None:
        self._transport.disconnect()

    def drain_events(self, max_items: int):
        return self._transport.drain_events(max_items)

    def set_target_address(self, address: Optional[int]) -> None:
        self._protocol.set_target_address(address)

    @property
    def target_address(self) -> Optional[int]:
        return self._protocol.target_address

    def request_telemetry(self) -> None:
        self._transport.send_frame(self._protocol.build_read_all())

    def request_property(self, property_id: int) -> None:
        self._transport.send_frame(self._protocol.build_read_property(property_id))

    def set_voltage(self, value: float, permanent: bool = False) -> None:
        self._transport.send_frame(self._protocol.build_set_voltage(value, permanent))

    def set_current(self, value: float, permanent: bool = False) -> None:
        self._transport.send_frame(self._protocol.build_set_current(value, permanent))

    def send_control(self, fan_full: bool, flash_led: bool) -> None:
        self._transport.send_frame(
            self._protocol.build_control(fan_full=fan_full, flash_led=flash_led)
        )

    def send_raw(self, frame: CANFrame) -> None:
        self._transport.send_frame(frame)

    def decode(self, frame: CANFrame) -> Optional[TelemetryValue]:
        return self._protocol.decode_telemetry(frame)

    @staticmethod
    def source_address(frame: CANFrame) -> Optional[int]:
        return R48Protocol.extract_source_address(frame)

    @property
    def protocol(self) -> R48Protocol:
        return self._protocol